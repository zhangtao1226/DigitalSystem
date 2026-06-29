# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : 归档章表格检测-通用版.py
# @Desc      : 归档章检测（兼容红色/蓝色/黑色印章）→ 自动分件 + 格子计数
# @Time      : 2026/6/3
# @Software  : PyCharm

import shutil
import cv2
import numpy as np
from itertools import combinations
from pathlib import Path


# ══════════════════════════════════════════════════════════════
# 内部工具函数
# ══════════════════════════════════════════════════════════════




def _cluster_lines(segs: list, coord_idx: int, tol: int = 12) -> list:
    """按指定轴坐标聚类线段"""
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


def _count_cells_from_mask(stamp_mask: np.ndarray) -> dict:
    """
    从红色/蓝色印章的颜色 mask 计算格子数
    返回 {'rows': N, 'cols': M, 'cells': N*M}
    """
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
    ends   = np.where(transitions == -1)[0] + 1
    if rh > 0 and in_stripe[0]:  starts = np.insert(starts, 0, 0)
    if rh > 0 and in_stripe[-1]: ends   = np.append(ends, rh)
    n_stripes = sum(1 for s, e in zip(starts, ends) if e - s >= 3)

    n_v = len(xs_merged)
    cols = max(0, n_v - 1)
    rows = max(0, n_stripes - 1)  # 条带数 = 行数 + 1（含边框条带）
    return {'rows': rows, 'cols': cols, 'cells': rows * cols,
            'v_lines': n_v, 'h_lines': n_stripes}


def _count_cells_from_edges(stamp_img: np.ndarray) -> dict:
    """
    从灰度/黑色印章图像计算格子数（用 LAB 增强 + HoughLinesP）
    返回 {'rows': N, 'cols': M, 'cells': N*M}，不确定时返回 cells=-1
    """
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

    h_cls = _cluster_lines(h_segs, 1, tol=12)
    v_cls = _cluster_lines(v_segs, 0, tol=12)

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


# ══════════════════════════════════════════════════════════════
# 误检过滤：验证候选区域确实是"表格"而非普通文字/边框
# ══════════════════════════════════════════════════════════════

def _is_valid_stamp(img: np.ndarray, x: int, y: int, w: int, h: int,
                    color_mask=None) -> bool:
    """
    二次校验：候选框是否像归档章
    校验点：
      1. 宽高比 1.3~10
      2. 不是全图宽（排除文档外框）
      3. 内部有竖向分隔（至少2列）
      4. 绝对高度上限（排除大段落框）
      5. 位置在图片上半部分（自适应：矮图放宽）
    """
    ih, iw = img.shape[:2]
    aspect = w / h if h > 0 else 0

    # 宽高比过滤
    if not (1.3 < aspect < 10):
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
        pos_limit = 0.95   # 矮图（横幅/裁剪图）极宽松
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
    ends   = np.where(transitions == -1)[0] + 1
    if in_stripe[0]:  starts = np.insert(starts, 0, 0)
    if in_stripe[-1]: ends   = np.append(ends, rh2)
    n_stripes = sum(1 for s, e in zip(starts, ends) if e - s >= 3)

    # 通过条件：竖线≥3（两侧边框+至少1条分隔）且 条带≥2（至少2行内容或1行+边框）
    if len(valid_v) < 3 or n_stripes < 2:
        return False

    return True


# ══════════════════════════════════════════════════════════════
# 检测方法一：颜色检测（红色/蓝色章）
# ══════════════════════════════════════════════════════════════

def _detect_color_stamp(img: np.ndarray, debug=False) -> dict | None:
    """
    HSV 颜色检测（红色/蓝色章）
    返回 {'bbox': (x1,y1,x2,y2), 'cells': N, 'rows': R, 'cols': C} 或 None
    """
    ih, iw = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    color_defs = {
        # S 阈值从 30 降到 15：扫描件红色边框颜色偏淡，S 值约 40~60，
        # 降低阈值才能完整捕获边框线（已验证不影响误检率）
        'red': (
            cv2.inRange(hsv, np.array([0, 15, 80]), np.array([15, 255, 255])) |
            cv2.inRange(hsv, np.array([160, 15, 80]), np.array([180, 255, 255]))
        ),
        'blue': cv2.inRange(hsv, np.array([100, 15, 80]), np.array([140, 255, 255])),
    }

    for color_name, raw_mask in color_defs.items():
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in sorted(contours, key=cv2.contourArea, reverse=True):
            area = cv2.contourArea(c)
            if area < 500:
                continue
            x, y, w, h = cv2.boundingRect(c)

            if not _is_valid_stamp(img, x, y, w, h, color_mask=mask):
                if debug:
                    print(f"  [颜色/{color_name}] 过滤: x={x},y={y},w={w},h={h}")
                continue

            # 格子计数
            pad = 5
            rx1, ry1 = max(0, x - pad), max(0, y - pad)
            rx2, ry2 = min(iw, x + w + pad), min(ih, y + h + pad)
            stamp_mask_crop = mask[ry1:ry2, rx1:rx2]
            grid = _count_cells_from_mask(stamp_mask_crop)

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


# ══════════════════════════════════════════════════════════════
# 检测方法二：结构检测（黑色/灰色章，分块滑窗）
# ══════════════════════════════════════════════════════════════

def _detect_struct_in_block(img: np.ndarray, sx1: int, sy1: int,
                             sx2: int, sy2: int, debug=False) -> dict | None:
    """在指定块内用霍夫直线检测表格矩形"""
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

    h_cls = _cluster_lines(h_segs, 1, tol=12)
    v_cls = _cluster_lines(v_segs, 0, tol=12)

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
    full_img_w = sx2 - sx1
    full_img_h = sy2 - sy1
    if bw > full_img_w * 0.95:   # 横跨全图
        return None
    if bh > full_img_h * 0.60:   # 太高
        return None

    # 转换为全图坐标
    pad = 20
    gx1 = max(0, sx1 + lx1 - pad)
    gy1 = max(0, sy1 + ly1 - pad)
    gx2 = min(iw, sx1 + lx2 + pad)
    gy2 = min(ih, sy1 + ly2 + pad)

    # 格子计数
    stamp_crop = img[gy1:gy2, gx1:gx2]
    grid = _count_cells_from_edges(stamp_crop)

    result = {
        'method': 'structure',
        'bbox': (gx1, gy1, gx2, gy2),
        **grid
    }
    if debug:
        print(f"  ✅ [结构检测] bbox={result['bbox']}, "
              f"{grid['rows']}行×{grid['cols']}列={grid['cells']}格")
    return result


def _detect_struct_stamp(img: np.ndarray, debug=False) -> dict | None:
    """分块滑窗结构检测（搜索图片上半部分）"""
    ih, iw = img.shape[:2]
    search_h = int(ih * 0.40)   # 只搜索上40%
    bw = int(iw * 0.35)
    bh = int(search_h * 0.70)
    stride_x = int(iw * 0.20)
    stride_y = int(search_h * 0.30)

    for y in range(0, search_h - bh // 2, stride_y):
        for x in range(0, iw - bw // 2, stride_x):
            x2 = min(iw, x + bw)
            y2 = min(ih, y + bh)
            result = _detect_struct_in_block(img, x, y, x2, y2, debug=debug)
            if result:
                return result
    return None


# ══════════════════════════════════════════════════════════════
# 对外接口
# ══════════════════════════════════════════════════════════════

def detect_stamp(image_path: str, debug=False) -> dict:
    """
    检测图片中的归档章（兼容红/蓝/黑/灰色印章）

    返回:
        {
          'found': True/False,
          'method': 'red'/'blue'/'structure'/None,
          'bbox': (x1,y1,x2,y2) 或 None,
          'rows': 行数,
          'cols': 列数,
          'cells': 格子总数 (-1表示无法计数)
        }
    """
    img = cv2.imread(image_path)
    if img is None:
        return {'found': False, 'method': None, 'bbox': None,
                'rows': 0, 'cols': 0, 'cells': 0}

    if debug:
        ih, iw = img.shape[:2]
        print(f"\n🔍 [{image_path}] ({iw}x{ih})")

    # 优先颜色检测（快速精准）
    result = _detect_color_stamp(img, debug=debug)

    # 颜色检测失败则用结构检测
    if result is None:
        if debug:
            print("  颜色检测未命中，切换结构检测...")
        result = _detect_struct_stamp(img, debug=debug)

    if result is None:
        if debug:
            print("  ❌ 未检测到归档章")
        return {'found': False, 'method': None, 'bbox': None,
                'rows': 0, 'cols': 0, 'cells': 0}

    return {'found': True, **result}


def has_stamp(image_path: str, debug=False) -> bool:
    """快捷接口：是否有归档章（用于分件判断）"""
    return detect_stamp(image_path, debug=debug)['found']


def get_stamp_crop(image_path: str, debug=False) -> np.ndarray | None:
    """获取归档章裁剪区域（用于OCR）"""
    r = detect_stamp(image_path, debug=debug)
    if not r['found']:
        return None
    img = cv2.imread(image_path)
    x1, y1, x2, y2 = r['bbox']
    return img[y1:y2, x1:x2]


# ══════════════════════════════════════════════════════════════
# 主功能：自动分件
# ══════════════════════════════════════════════════════════════

def split_archives(input_dir: str, output_dir: str, debug=False):
    """
    遍历 input_dir，按归档章自动分件。
    检测到归档章 → 新建文件夹（新档案起点）
    未检测到 → 归入最近建立的文件夹
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_files = sorted(
        [f for f in input_path.iterdir()
         if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')],
        key=lambda f: f.name
    )

    if not image_files:
        print("⚠️ 未找到图片文件")
        return

    print(f"📂 共 {len(image_files)} 张图片，开始处理...\n")

    current_folder = None
    archive_index = 0

    for img_file in image_files:
        result = detect_stamp(str(img_file), debug=debug)

        if result['found']:
            archive_index += 1
            cells_str = (f" [{result['rows']}行×{result['cols']}列={result['cells']}格]"
                         if result['cells'] > 0 else "")
            folder_name = f"archive_{archive_index:03d}"
            current_folder = output_path / folder_name
            current_folder.mkdir(exist_ok=True)
            print(f"📁 新建档案: {folder_name}  ← {img_file.name}{cells_str}")
        else:
            if current_folder is None:
                current_folder = output_path / "uncategorized"
                current_folder.mkdir(exist_ok=True)
            print(f"  ↳ {current_folder.name}  ← {img_file.name}")

        shutil.copy2(str(img_file), current_folder / img_file.name)

    print(f"\n✅ 完成！共分出 {archive_index} 份档案，输出至: {output_dir}")


# ══════════════════════════════════════════════════════════════
# 主程序入口
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import time

    TEST_IMAGES = [
        # 黑色铅笔印章
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0001.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0013.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0025.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0037.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0047.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0055.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0073.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0075.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0087.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0099.jpg",
    ]

    print("=" * 60)
    print("单图测试")
    print("=" * 60)
    t1 = time.time()
    for path in TEST_IMAGES:
        t0 = time.time()
        r = detect_stamp(path, debug=True)
        elapsed = time.time() - t0
        status = "✅ 有归档章" if r['found'] else "❌ 无归档章"
        cells = f"{r['rows']}行×{r['cols']}列={r['cells']}格" if r['cells'] > 0 else "格子数未知"
        print(f"结果: {status}  {cells}  耗时:{elapsed:.2f}s\n")

    print(f"总耗时: {time.time() - t1}")

    # 批量分件（取消注释使用）
    # split_archives(
    #     input_dir  = r"/Volumes/.../stamp_test",
    #     output_dir = r"/Volumes/.../stamp_output",
    #     debug=True
    # )