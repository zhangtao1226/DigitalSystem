# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : StampTableCheck.py
# @Time     : 2026/6/3 14:57
# @Desc     : 归档章表格检测
import os
import time
from itertools import combinations


import cv2
import numpy as np
from paddle.base.libpaddle.eager.ops.legacy import row_conv

from src.utils.LoggerDetector import logger
from src.utils.ResultDetector import Result

class StampTableCheck:

    def has_stamp(self, image_source) -> bool:
        result = self.detect_stamp(image_source)
        print(f"result: {result}")
        return result['found']

    def detect_stamp(self, image_source, debug=False) -> Result:
        if isinstance(image_source, np.ndarray):
            img = image_source
            source_name = "<内存裁剪图>"
        else:
            img = cv2.imread(image_source)
            source_name = image_source
        if img is None:
            return {'found': False, 'method': None, 'bbox': None,
                    'rows': 0, 'cols': 0, 'cells': 0}

        if debug:
            ih, iw = img.shape[:2]
            print(f"\n🔍 [{source_name}] ({iw}x{ih})")

        # 优先检测红色线条构成的网格，避免把红头字体误判为归档章。
        result = self._detect_strict_red_grid(img, debug=debug)

        # 严格网格未命中时，再使用宽松颜色检测兼容浅色扫描章。
        if result is None:
            result = self._detect_color_stamp(img, debug=debug)

        # 颜色检测失败则用结构检测
        if result is None:
            if debug:
                print("  颜色检测未命中，切换结构检测...")
            result = self._detect_struct_stamp(img, debug=debug)

        if result is None:
            if debug:
                print("  ❌ 未检测到归档章")
            return {'found': False, 'method': None, 'bbox': None,
                    'rows': 0, 'cols': 0, 'cells': 0}

        return {'found': True, **result}

    def _detect_strict_red_grid(self, img: np.ndarray, debug=False) -> dict | None:
        """检测红色线条构成的紧凑多列表格，排除只有红头文字的页面。"""
        ih, iw = img.shape[:2]
        blue, green, red = cv2.split(img)
        red_i16 = red.astype(np.int16)
        other_max = np.maximum(green, blue).astype(np.int16)

        # 红色必须明显强于另外两个通道，轻微偏色和屏幕纹理不会进入。
        raw_mask = (
            ((red_i16 - other_max) > 20) & (red > 100)
        ).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            if cv2.contourArea(contour) < 500:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if not self._is_valid_stamp(img, x, y, w, h, color_mask=mask):
                continue

            pad = 5
            rx1, ry1 = max(0, x - pad), max(0, y - pad)
            rx2, ry2 = min(iw, x + w + pad), min(ih, y + h + pad)
            grid = self._count_cells_from_mask(mask[ry1:ry2, rx1:rx2])
            result = {
                'method': 'red_grid',
                'bbox': (
                    max(0, x - 20),
                    max(0, y - 20),
                    min(iw, x + w + 20),
                    min(ih, y + h + 20),
                ),
                **grid,
            }
            if debug:
                print(
                    f"  ✅ [红色网格章] bbox={result['bbox']}, "
                    f"{grid['rows']}行×{grid['cols']}列={grid['cells']}格"
                )
            return result

        return None

    def get_stamp_crop(self, image_path:str) -> np.ndarray | None:
        """
        获取归档章区域
        """
        r = self.detect_stamp(image_path)
        if not r['found']:
            return None
        img = cv2.imread(image_path)
        x1, y1, x2, y2 = r['bbox']
        return img[y1:y2, x1:x2]


    def _detect_color_stamp(self, img: np.ndarray, debug=False) -> dict | None:
        ih, iw = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        color_defs = {
            # S 阈值从 30 降到 15：扫描件红色边框颜色偏淡，S 值约 40~60，
            # 降低阈值才能完整捕获边框线（已验证不影响误检率）
            'red': (
                    cv2.inRange(hsv, np.array([0, 15, 80]), np.array([15, 255, 255])) |
                    cv2.inRange(hsv, np.array([160, 15, 80]), np.array([180, 255, 255]))
            ),
            # 'blue': cv2.inRange(hsv, np.array([100, 15, 80]), np.array([140, 255, 255])),
        }

        for color_name, raw_mask in color_defs.items():
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if debug:
                cv2.imwrite("mask_1.png", mask)

            for c in sorted(contours, key=cv2.contourArea, reverse=True):
                area = cv2.contourArea(c)
                if area < 500:
                    continue
                x, y, w, h = cv2.boundingRect(c)

                if not self._is_valid_stamp(img, x, y, w, h, color_mask=mask):
                    if debug:
                        print(f"  [颜色/{color_name}] 过滤: x={x},y={y},w={w},h={h}")
                    continue

                # 格子计数
                pad = 5
                rx1, ry1 = max(0, x - pad), max(0, y - pad)
                rx2, ry2 = min(iw, x + w + pad), min(ih, y + h + pad)
                stamp_mask_crop = mask[ry1:ry2, rx1:rx2]
                grid = self._count_cells_from_mask(stamp_mask_crop)

                result = {
                    'method': color_name,
                    'bbox': (max(0, x - 20), max(0, y - 20),
                             min(iw, x + w + 20), min(ih, y + h + 20)),
                    **grid
                }
                if debug:
                    print(f"  ✅ [{color_name}章] bbox={result['bbox']}, "
                          f"{grid['rows']}行×{grid['cols']}列={grid['cells']}格")
                return result

        return None

    def _is_valid_stamp(self, img: np.ndarray, x: int, y: int, w: int, h: int, color_mask=None) -> bool:
        ih, iw = img.shape[:2]
        aspect = w / h if h > 0 else 0

        # 宽高比过滤
        # 归档章通常是紧凑的多列表格；红头标题往往是一条很宽的红色
        # 文字带。限制最大宽高比可避免把红头字体连接块识别为归档章。
        if not (1.3 < aspect < 6):
            return False

        # 横跨全图宽度 → 文档外框/下划线
        if w > iw * 0.92:
            return False

        # 太小
        if w < 60 or h < 30:
            return False

        # 高度过滤：
        #   - 绝对上限 800px（任何情况下印章不超过这个高度）
        #   - 相对上限：h 不超过图片高度的 70%
        #     （对于裁剪横幅图，印章可能占图高50%+，放宽到70%）
        if h > 800:
            return False
        if h > ih * 0.70:
            return False

        # 位置过滤（自适应）：
        #   - 完整A4页（ih > 1000px）：归档章底部 < 图高40%
        #   - 裁剪横幅图（ih <= 1000px）：归档章底部 < 图高90%（几乎不过滤）
        if ih > 1000:
            pos_limit = 0.45
        elif ih > 600:
            pos_limit = 0.75
        else:
            pos_limit = 0.95  # 矮图（横幅/裁剪图）极宽松
        if (y + h) / ih > pos_limit:
            return False

        # 表格线验证：竖线（形态学）+ 横向条带（行密度分析）
        #
        # 设计原理：
        # - 竖线用闭运算mask的形态学open，50%高度核确保贯穿表格；宽度≤10%排除文字笔画块
        # - 横线用"行密度条带分析"而非横向open核：
        #   归档章的横线是细边框，文字内容在两条横线之间，形成"条带"结构
        #   open核25%对这类印章失效（文字填满了行，导致横线连成一片被截断）
        #   行密度分析只要密度>8%的连续区间>=2个即通过，对文字行和纯框线均有效
        pad = 5
        rx1, ry1 = max(0, x - pad), max(0, y - pad)
        rx2, ry2 = min(iw, x + w + pad), min(ih, y + h + pad)

        if color_mask is not None:
            roi_closed = color_mask[ry1:ry2, rx1:rx2]
            # 取原始（未闭运算）color_mask → 这里传入的已经是闭运算mask
            # 需要从外部拿原始mask；此处用闭运算mask做行密度分析（已足够区分）
            roi_raw = roi_closed
        else:
            roi_img = img[ry1:ry2, rx1:rx2]
            lab = cv2.cvtColor(roi_img, cv2.COLOR_BGR2LAB)
            L, _, _ = cv2.split(lab)
            L_norm = cv2.normalize(L, None, 0, 255, cv2.NORM_MINMAX)
            edges = cv2.Canny(L_norm, 15, 45)
            roi_closed = edges
            roi_raw = edges

        rh2, rw2 = roi_closed.shape[:2]

        # ── 竖线：闭运算mask + 50%高度核 + 宽度≤10%过滤 ──
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, int(rh2 * 0.50))))
        vc, _ = cv2.findContours(
            cv2.morphologyEx(roi_closed, cv2.MORPH_OPEN, vk),
            cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_v = [c for c in vc if cv2.boundingRect(c)[2] <= rw2 * 0.10]

        # ── 横线：行密度条带分析 ──
        # 统计每行红色像素密度，找密度>8%的连续区间（= 印章内容行）
        # 归档章2行表格 → 3个条带（行1内容、行2内容、底框）或2个（行1+行2合并情况）
        if rw2 > 0:
            row_den = np.array([roi_raw[i, :].sum() / 255 / rw2
                                for i in range(rh2)], dtype=float)
        else:
            row_den = np.zeros(rh2)
        in_stripe = row_den > 0.08
        transitions = np.diff(in_stripe.astype(int))
        starts = np.where(transitions == 1)[0] + 1
        ends = np.where(transitions == -1)[0] + 1
        if in_stripe[0]:  starts = np.insert(starts, 0, 0)
        if in_stripe[-1]: ends = np.append(ends, rh2)
        n_stripes = sum(1 for s, e in zip(starts, ends) if e - s >= 3)

        # 通过条件：竖线≥3（两侧边框+至少1条分隔）且 条带≥2（至少2行内容或1行+边框）
        if len(valid_v) < 3 or n_stripes < 2:
            return False

        return True

    def _count_cells_from_mask(self, stamp_mask:np.ndarray) -> dict:
        rh, rw = stamp_mask.shape[:2]

        # 竖线：高度 >= 40% 印章高度（与 _is_valid_stamp 保持一致）
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, int(rh * 0.40))))
        v_lines = cv2.morphologyEx(stamp_mask, cv2.MORPH_OPEN, vk)
        vc, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # 过滤宽竖线（文字笔画），只保留细线
        valid_vc = [c for c in vc if cv2.boundingRect(c)[2] <= rw * 0.10]
        # 对 x 坐标聚类，相邻 5% 范围内算同一条线
        xs_raw = sorted([cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] // 2
                         for c in valid_vc])
        xs_merged = []
        for x_val in xs_raw:
            if not xs_merged or x_val - xs_merged[-1] > rw * 0.05:
                xs_merged.append(x_val)

        # 横线：用行密度条带分析（比横向 open 核更可靠）
        if rw > 0:
            row_den = np.array([stamp_mask[i, :].sum() / 255 / rw
                                for i in range(rh)], dtype=float)
        else:
            row_den = np.zeros(rh)
        in_stripe = row_den > 0.08
        transitions = np.diff(in_stripe.astype(int))
        starts = np.where(transitions == 1)[0] + 1
        ends = np.where(transitions == -1)[0] + 1
        if rh > 0 and in_stripe[0]:  starts = np.insert(starts, 0, 0)
        if rh > 0 and in_stripe[-1]: ends = np.append(ends, rh)
        n_stripes = sum(1 for s, e in zip(starts, ends) if e - s >= 3)

        n_v = len(xs_merged)
        cols = max(0, n_v - 1)
        rows = max(0, n_stripes - 1)  # 条带数 = 行数 + 1（含边框条带）
        return {'rows': rows, 'cols': cols, 'cells': rows * cols,
                'v_lines': n_v, 'h_lines': n_stripes}

    def _detect_struct_stamp(self, img: np.ndarray, debug=False) -> dict | None:
        ih, iw = img.shape[:2]
        # PartsDetector 会先截取页面顶部约 500px。对于这种矮图，如果仍只
        # 搜索前 40%，归档章下半部分会被排除；矮图放宽到前 90%，完整页
        # 仍限制在前 40%，避免扩大正文表格的误检范围。
        search_h = int(ih * (0.90 if ih <= 1000 else 0.40))
        bw = int(iw * 0.35)
        bh = int(search_h * 0.70)
        stride_x = int(iw * 0.20)
        stride_y = int(search_h * 0.30)

        for y in range(0, search_h - bh // 2, stride_y):
            for x in range(0, iw - bw // 2, stride_x):
                x2 = min(iw, x + bw)
                y2 = min(ih, y + bh)
                result = self._detect_struct_in_block(img, x, y, x2, y2, debug=debug)
                if result:
                    return result
        return None

    def _detect_struct_in_block(self, img:np.ndarray, sx1:int, sy1:int, sx2:int, sy2:int, debug=False) -> dict | None:
        ih, iw = img.shape[:2]
        roi = img[sy1:sy2, sx1:sx2]
        rh, rw = roi.shape[:2]

        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        L, _, _ = cv2.split(lab)
        L_norm = cv2.normalize(L, None, 0, 255, cv2.NORM_MINMAX)
        edges = cv2.Canny(L_norm, 30, 80)

        min_line = max(30, rw // 30)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                                threshold=25, minLineLength=min_line, maxLineGap=15)
        if lines is None:
            return None

        h_segs, v_segs = [], []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if ang < 10 or ang > 170:
                h_segs.append((x1, y1, x2, y2))
            elif 80 < ang < 100:
                v_segs.append((x1, y1, x2, y2))

        h_cls = self._cluster_lines(h_segs, 1, tol=12)
        v_cls = self._cluster_lines(v_segs, 0, tol=12)

        h_long = []
        for cl in h_cls:
            y = float(np.mean([s[1] for s in cl]))
            xmin = min(min(s[0], s[2]) for s in cl)
            xmax = max(max(s[0], s[2]) for s in cl)
            if xmax - xmin >= 50:
                h_long.append((y, xmin, xmax))

        v_long = []
        for cl in v_cls:
            x = float(np.mean([s[0] for s in cl]))
            ymin = min(min(s[1], s[3]) for s in cl)
            ymax = max(max(s[1], s[3]) for s in cl)
            if ymax - ymin >= 40:
                v_long.append((x, ymin, ymax))

        if len(h_long) < 2 or len(v_long) < 3:
            return None

        # 交叉点
        pts = set()
        for hy, hx1, hx2 in h_long:
            for vx, vy1, vy2 in v_long:
                if hx1 <= vx <= hx2 and vy1 <= hy <= vy2:
                    pts.add((round(vx), round(hy)))

        if len(pts) < 4:
            return None

        # 找最优矩形
        ys_u = sorted(set(p[1] for p in pts))
        best_rect, best_score = None, 0

        for y_top, y_bot in combinations(ys_u, 2):
            table_h = y_bot - y_top
            if table_h < 20:
                continue
            xs_top = {p[0] for p in pts if abs(p[1] - y_top) < 20}
            xs_bot = {p[0] for p in pts if abs(p[1] - y_bot) < 20}
            common_xs = sorted(xs_top & xs_bot)
            if len(common_xs) < 3:
                continue
            table_w = common_xs[-1] - common_xs[0]
            aspect = table_w / table_h if table_h > 0 else 0
            if 1.2 < aspect < 12:
                score = len(common_xs) * table_w
                if score > best_score:
                    best_score = score
                    best_rect = (common_xs[0], y_top, common_xs[-1], y_bot,
                                 len(common_xs))

        if best_rect is None:
            return None

        lx1, ly1, lx2, ly2, n_v_lines = best_rect
        bw = lx2 - lx1
        bh = ly2 - ly1

        # 误检过滤
        # 单个汉字的横竖笔画也可能形成若干交点，但相对于整页通常很小。
        # 归档章应达到一定的页面占比，避免将红头文字中的单字识别为小表格。
        min_stamp_w = max(80, int(iw * 0.06))
        min_stamp_h = max(35, int(ih * 0.08))
        if bw < min_stamp_w or bh < min_stamp_h:
            return None

        full_img_w = sx2 - sx1
        full_img_h = sy2 - sy1
        if bw > full_img_w * 0.95:  # 横跨全图
            return None
        if bh > full_img_h * 0.60:  # 太高
            return None

        # 转换为全图坐标
        pad = 20
        gx1 = max(0, sx1 + lx1 - pad)
        gy1 = max(0, sy1 + ly1 - pad)
        gx2 = min(iw, sx1 + lx2 + pad)
        gy2 = min(ih, sy1 + ly2 + pad)

        # 归档章应是页面内部的独立小表格。贴住页面左右边界的候选通常
        # 是正文大表格被滑动窗口截出的局部，不应作为分件起始章。
        edge_margin = max(5, int(iw * 0.01))
        if gx1 <= edge_margin or gx2 >= iw - edge_margin:
            return None

        # 格子计数
        stamp_crop = img[gy1:gy2, gx1:gx2]
        grid = self._count_cells_from_edges(stamp_crop)

        result = {
            'method': 'structure',
            'bbox': (gx1, gy1, gx2, gy2),
            **grid
        }
        if debug:
            print(f"  ✅ [结构检测] bbox={result['bbox']}, "
                  f"{grid['rows']}行×{grid['cols']}列={grid['cells']}格")
        return result


    def _cluster_lines(self, segs: list, coord_idx: int, tol: int = 12) -> list:
        if not segs:
            return []
        ss = sorted(segs, key=lambda s: s[coord_idx])
        clusters, cur = [], [ss[0]]
        for s in ss[1:]:
            if abs(s[coord_idx] - cur[-1][coord_idx]) <= tol:
                cur.append(s)
            else:
                clusters.append(cur)
                cur = [s]
        clusters.append(cur)
        return clusters

    def _count_cells_from_edges(self, stamp_img: np.ndarray) -> dict:
        sh, sw = stamp_img.shape[:2]

        lab = cv2.cvtColor(stamp_img, cv2.COLOR_BGR2LAB)
        L, _, _ = cv2.split(lab)
        L_norm = cv2.normalize(L, None, 0, 255, cv2.NORM_MINMAX)
        edges = cv2.Canny(L_norm, 15, 45)

        lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                                threshold=15, minLineLength=max(30, sw // 15),
                                maxLineGap=20)
        if lines is None:
            return {'rows': -1, 'cols': -1, 'cells': -1}

        h_segs, v_segs = [], []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if ang < 10 or ang > 170:
                h_segs.append((x1, y1, x2, y2))
            elif 80 < ang < 100:
                v_segs.append((x1, y1, x2, y2))

        h_cls = self._cluster_lines(h_segs, 1, tol=12)
        v_cls = self._cluster_lines(v_segs, 0, tol=12)

        # 找"长"水平线（span > 10% 宽度）
        h_long = []
        for cl in h_cls:
            y = float(np.mean([s[1] for s in cl]))
            xmin = min(min(s[0], s[2]) for s in cl)
            xmax = max(max(s[0], s[2]) for s in cl)
            if xmax - xmin > sw * 0.10:
                h_long.append((y, xmin, xmax))

        if len(h_long) < 2:
            return {'rows': -1, 'cols': -1, 'cells': -1}

        # 选间距最均匀的水平线组（表格行线）
        h_long.sort(key=lambda l: l[0])
        best_h, best_u = None, 999.0
        for sz in range(2, len(h_long) + 1):
            for combo in combinations(range(len(h_long)), sz):
                ys = [h_long[i][0] for i in combo]
                gaps = [ys[j + 1] - ys[j] for j in range(len(ys) - 1)]
                if not gaps or min(gaps) < 20:
                    continue
                u = float(np.std(gaps) / np.mean(gaps)) if np.mean(gaps) > 0 else 999.0
                x_overlap = (min(h_long[i][2] for i in combo)
                             - max(h_long[i][1] for i in combo))
                if u < best_u and x_overlap > sw * 0.05:
                    best_u = u
                    best_h = [h_long[i] for i in combo]

        if best_h is None or best_u > 0.4:
            return {'rows': -1, 'cols': -1, 'cells': -1}

        y_top = min(l[0] for l in best_h)
        y_bot = max(l[0] for l in best_h)
        x_common_l = max(l[1] for l in best_h)
        x_common_r = min(l[2] for l in best_h)
        table_h = y_bot - y_top

        # 穿越表格区域的竖线
        crossing_v = []
        for cl in v_cls:
            x = float(np.mean([s[0] for s in cl]))
            ymin = float(min(min(s[1], s[3]) for s in cl))
            ymax = float(max(max(s[1], s[3]) for s in cl))
            overlap = max(0.0, min(ymax, y_bot) - max(ymin, y_top))
            if (overlap / table_h >= 0.50
                    and (x_common_l - 20) <= x <= (x_common_r + 20)):
                crossing_v.append(x)

        crossing_v.sort()
        # 过滤间距过小的竖线（文字笔画噪点）
        filtered_v = [crossing_v[0]] if crossing_v else []
        for xv in crossing_v[1:]:
            if xv - filtered_v[-1] > 40:
                filtered_v.append(xv)

        rows = max(0, len(best_h) - 1)
        cols = max(0, len(filtered_v) - 1)
        return {'rows': rows, 'cols': cols, 'cells': rows * cols}

if __name__ == "__main__":
    test_images = [
        r"D:\ZT_Projects\Projects\DigitalSystem\src\resources\temp\images\parts_temp_0014_1780650267.jpg"
    ]
    stamp = StampTableCheck()
    print("+"*60)
    print("开始测试时")
    print("+"*60)

    for path in test_images:
        t0 = time.time()
        r = stamp.detect_stamp(path, debug=True)
        print(f"r = {r}")
        elapsed = time.time() - t0
        status = "有归档章" if r['found'] else "无归档章"
        cells = f"{r['rows']} 行 x {r['cols']} 列 = {r['cells']}格" if r['cells'] > 0 else "格子数未知"
        print(f"检测结果: {status} {cells}, 耗时: {elapsed}")