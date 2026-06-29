# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : DualLayerPDFGenerator.py
# @Desc      : 将图片生成双层PDF
# @Time      : 2026/3/3 11:17
# @Software  : PyCharm
import gc
import os
import io
import fitz
import json
from PIL import Image
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

        pdf_doc = fitz.open()
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

                page = pdf_doc.new_page(width=TARGET_PAGE_W, height=TARGET_PAGE_H)
                img_rect = fitz.Rect(ox, oy, ox + sw, oy + sh)
                page.insert_image(img_rect, filename=img_path)

                lines = self._parse_ocr_result(raw_result[idx])

                text_pdf_bytes = self._build_text_layer(lines, scale, ox, oy)

                if text_pdf_bytes:
                    text_doc = fitz.open("pdf", text_pdf_bytes)
                    if text_doc.page_count > 0:
                        page.show_pdf_page(page.rect, text_doc, 0, overlay=True)
                    text_doc.close()
                else:
                    logger.error(f"无文本内容可写入")

                success_count += 1
                logger.info(f"{tag}; 完成\n")
                gc.collect()
            except Exception as e:
                import traceback
                logger.error(f"{tag}; 失败：{e}")
                traceback.print_exc()
                continue

        if pdf_doc.page_count > 0:
            os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
            pdf_doc.save(output_pdf_path, deflate=True, clean=True)
            pdf_doc.close()
            logger.info(f"双层PDF已生成：{output_pdf_path}; 成功页数 : {success_count} / {len(image_paths)}")
            return True
        else:
            pdf_doc.close()
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

    def _build_text_layer(self, lines: list, scale: float, ox: float, oy: float) -> bytes | None:
        if not lines:
            return None

        self.get_font_path()
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(TARGET_PAGE_W, TARGET_PAGE_H))
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
                n_chars = max(len(text), 1)
                fontsize = max(4.0, min(box_h * 0.85, box_w / n_chars * 1.5))

                rl_x = mu_x0
                rl_base = TARGET_PAGE_H - mu_y1

                t = c.beginText(rl_x, rl_base)
                t.setFont(FONT_REG_NAME, fontsize)
                t.setTextRenderMode(3)
                t.textOut(text)
                c.drawText(t)
                written += 1

            except Exception as e:
                logger.warning(f"跳过行（{text[:10]}...）：{e}")
                continue

        c.save()
        logger.info(f"隐形文本写入 {written} 条")
        return buf.getvalue() if written > 0 else None

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