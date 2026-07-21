# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : DualLayerPDFGenerator.py
# @Desc      : 将图片生成双层PDF
# @Time      : 2026/3/3 11:17
# @Software  : PyCharm
import gc
import os
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from src.utils.LoggerDetector import logger


TARGET_PAGE_W  = 595
TARGET_PAGE_H  = 842
PX_TO_PT       = 72 / 96
CONFIDENCE_THR = 0.5
FONT_REG_NAME  = "OCRFont"

CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode MS.ttf",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

_FONT_PATH: str = None


class DualLayerPDFGenerator:
    def __init__(self):
        self.DPI = 72
        self.PIXEL_TO_POINT = self.DPI / 96
        self.TARGET_PAGE_SIZE = (595, 842)


    def image_to_pdf(self, image_paths: list, output_pdf_path: str, raw_result: list):
        self.get_font_path()

        pdf_canvas = None
        success_count = 0

        for idx, img_path in enumerate(image_paths):
            tag = f"[{idx + 1}/{len(image_paths)}]"

            if not os.path.exists(img_path):
                logger.warning(f"图片文件不存在, 跳过; {img_path}")
                continue

            try:
                with Image.open(img_path) as img:
                    img_w_px, img_h_px = img.size
                logger.info(f"{tag} 尺寸：{img_w_px}×{img_h_px}px  {img_path}")

                scale, ox, oy, sw, sh = self._calc_layout(img_w_px, img_h_px)
                logger.info(f"{tag} 缩放：{sw:.1f}×{sh:.1f}pt  偏移：({ox:.1f},{oy:.1f})")

                if pdf_canvas is None:
                    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
                    pdf_canvas = rl_canvas.Canvas(output_pdf_path, pagesize=(TARGET_PAGE_W, TARGET_PAGE_H))

                image_y = TARGET_PAGE_H - oy - sh
                pdf_canvas.drawImage(
                    ImageReader(img_path),
                    ox,
                    image_y,
                    width=sw,
                    height=sh,
                    mask="auto",
                )

                ocr_result = raw_result[idx] if idx < len(raw_result) else {}
                lines = self._parse_ocr_result(ocr_result)
                written = self._draw_invisible_text(pdf_canvas, lines, scale, ox, oy)

                if written <= 0:
                    logger.error(f"无文本内容可写入")

                pdf_canvas.showPage()
                success_count += 1
                logger.info(f"{tag}; 完成\n")
                gc.collect()
            except Exception as e:
                import traceback
                logger.error(f"{tag}; 失败：{e}")
                traceback.print_exc()
                continue

        if pdf_canvas is not None and success_count > 0:
            pdf_canvas.save()
            logger.info(f"双层PDF已生成：{output_pdf_path}; 成功页数 : {success_count} / {len(image_paths)}")
            return True
        else:
            return False

    def _parse_ocr_result(self, raw_result) -> list:
        lines = []

        result_dict = raw_result

        if not isinstance(result_dict, dict):
            logger.error(f"[OCR] result_dict 类型异常：{type(result_dict)}")
            return lines

        texts = result_dict.get('rec_texts', [])
        scores = result_dict.get('rec_scores', [])
        polys = result_dict.get('rec_polys', None)
        if polys is None or len(polys) == 0:
            polys = result_dict.get('dt_polys', [])

        if not texts:
            logger.error(f"rec_texts 为空")
            return lines

        if not (len(texts) == len(scores) == len(polys)):
            logger.error(
                "[OCR] 文本、置信度与坐标数量不一致，已拒绝生成错位文本层: "
                f"texts={len(texts)}, scores={len(scores)}, boxes={len(polys)}"
            )
            return lines

        logger.info(f"共检测到 {len(texts)} 条文本")

        for i, (text, score, box) in enumerate(zip(texts, scores, polys)):
            try:
                text = str(text).strip()
                score = float(score)
                if not text or score < CONFIDENCE_THR:
                    continue
                if box is None or len(box) < 2:
                    continue
                lines.append((box, text, score))
            except Exception as e:
                logger.error(f"[OCR] 跳过第{i}条：{e}")
                continue

        logger.info(f"[OCR]过滤后有效文本 {len(lines)} 条（置信度 >= {CONFIDENCE_THR}）")
        return lines

    def _calc_layout(self, img_w_px: int, img_h_px: int):
        img_w_pt = img_w_px * PX_TO_PT
        img_h_pt = img_h_px * PX_TO_PT
        scale = min(TARGET_PAGE_W / img_w_pt, TARGET_PAGE_H / img_h_pt)
        sw = img_w_pt * scale
        sh = img_h_pt * scale
        ox = (TARGET_PAGE_W - sw) / 2
        oy = (TARGET_PAGE_H - sh) / 2
        return scale, ox, oy, sw, sh

    def _draw_invisible_text(self, pdf_canvas, lines: list, scale: float, ox: float, oy: float) -> int:
        if not lines:
            return 0

        self.get_font_path()
        written = 0

        for (box, text, score) in lines:
            try:
                pts = [(float(p[0]), float(p[1])) for p in box]

                mu_pts = [(px * PX_TO_PT * scale + ox,
                           py * PX_TO_PT * scale + oy)
                          for (px, py) in pts]

                mu_x0 = min(p[0] for p in mu_pts)
                mu_y0 = min(p[1] for p in mu_pts)
                mu_x1 = max(p[0] for p in mu_pts)
                mu_y1 = max(p[1] for p in mu_pts)

                if mu_x0 >= mu_x1 or mu_y0 >= mu_y1:
                    continue

                box_h = mu_y1 - mu_y0
                box_w = mu_x1 - mu_x0

                # 使用字体的实际 ascent/descent 让搜索高亮框纵向贴合 OCR 框。
                unit_ascent, unit_descent = pdfmetrics.getAscentDescent(FONT_REG_NAME, 1.0)
                metric_height = max(unit_ascent - unit_descent, 0.01)
                fontsize = max(1.0, box_h / metric_height)

                rl_x = mu_x0
                rl_bottom = TARGET_PAGE_H - mu_y1
                rl_base = rl_bottom - unit_descent * fontsize

                # 字体本身的字宽与图片中的字宽不同。将整行文本水平缩放到
                # OCR 框宽度，否则 Acrobat 的搜索高亮会逐字漂移。
                natural_width = pdfmetrics.stringWidth(text, FONT_REG_NAME, fontsize)
                horizontal_scale = 100.0
                if natural_width > 0:
                    horizontal_scale = max(10.0, min(500.0, box_w / natural_width * 100.0))

                t = pdf_canvas.beginText(rl_x, rl_base)
                t.setFont(FONT_REG_NAME, fontsize)
                t.setHorizScale(horizontal_scale)
                t.setTextRenderMode(3)
                t.textOut(text)
                pdf_canvas.drawText(t)
                written += 1

            except Exception as e:
                logger.warning(f"跳过行（{text[:10]}...）：{e}")
                continue

        logger.info(f"隐形文本写入 {written} 条")
        return written

    def get_font_path(self) -> str:
        global _FONT_PATH
        if _FONT_PATH is None:
            for path in CJK_FONT_CANDIDATES:
                if os.path.exists(path):
                    _FONT_PATH = path
                    pdfmetrics.registerFont(TTFont(FONT_REG_NAME, _FONT_PATH))
                    logger.info(f"已加载{_FONT_PATH} 字体")
                    break
            if _FONT_PATH is None:
                raise FileNotFoundError("未找到CJK字体，请在 CJK_FONT_CANDIDATES 中添加字体路径")
        return _FONT_PATH
