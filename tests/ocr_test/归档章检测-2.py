# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : 归档章检测-2.py
# @Desc      : 
# @Time      : 2026/6/4 14:49
# @Software  : PyCharm

# -*-coding  : utf-8 -*-
# @Desc      : 归档章检测｜修复红头标题框误检、漏检兼顾，国标2行3列校验
import shutil
import cv2
import numpy as np
from itertools import combinations
from pathlib import Path

# =====================全局可调参数（新增防红头误检配置）=====================
CFG = {
    # 颜色HSV配置(适配褪色红/蓝印章)
    "RED_HSV1": np.array([0, 20, 20]),
    "RED_HSV2": np.array([18, 255, 255]),
    "RED_HSV3": np.array([155, 20, 20]),
    "RED_HSV4": np.array([180, 255, 255]),
    "BLUE_HSV1": np.array([95, 20, 20]),
    "BLUE_HSV2": np.array([145, 255, 255]),
    "COLOR_CLOSE_KERNEL": (5, 5),
    "MIN_CONTOUR_AREA": 350,
    # 霍夫直线参数
    "HOUGH_THRESH": 12,
    "HOUGH_MIN_LEN_RATIO": 20,
    "HOUGH_MAX_GAP": 28,
    # 滑窗配置
    "SEARCH_RATIO": 0.85,
    "WIN_SCALE": [0.28, 0.38, 0.48],
    "STRIDE_X_RATIO": 0.18,
    "STRIDE_Y_RATIO": 0.22,
    # 外形过滤
    "ASPECT_MIN": 1.1, "ASPECT_MAX": 12,
    "MIN_W": 45, "MIN_H":22,
    "V_LINE_MIN":2, "H_LINE_MIN":2,
    # =========【防红头方框误检核心参数】=========
    "MIN_CELL_COUNT":3,          # 有效归档章最少3格，单框1格直接剔除
    "STD_STAMP_ROW":2,           # 国标归档章固定2行
    "STD_STAMP_COL":3,           # 国标归档章固定3列
    "TEXT_RED_RATIO_LIMIT":0.70, # 红像素>70%判定纯红头文字框，过滤
    "ROW_COL_FILTER": True       # 强制校验：满足≥2行 或 ≥3列
}
# =================================================================

def _preprocess_img(src: np.ndarray) -> np.ndarray:
    """预处理：高斯降噪+LAB自适应亮度均衡，解决泛黄、暗光漏检"""
    img = cv2.GaussianBlur(src, (3,3), 1.0)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    L,A,B = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8,8))
    L_eq = clahe.apply(L)
    lab_eq = cv2.merge((L_eq,A,B))
    return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

def _cluster_lines(segs: list, coord_idx: int, tol: int = 14) -> list:
    """线段聚类，兼容短线偏移"""
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
    """掩码统计行列格子，新增单格红头过滤"""
    rh, rw = stamp_mask.shape[:2]
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(4, rh // 4)))
    v_lines = cv2.morphologyEx(stamp_mask, cv2.MORPH_OPEN, vk)
    vc, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(8, rw // 6), 1))
    h_lines = cv2.morphologyEx(stamp_mask, cv2.MORPH_OPEN, hk)
    hc, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    n_v = len(vc)
    n_h = len(hc)
    cols = max(0, n_v - 1)
    rows = max(0, n_h - 1)
    cells = rows * cols

    # 单格/少格直接标记无效，过滤红头单方框
    if cells < CFG["MIN_CELL_COUNT"]:
        rows, cols, cells = -1, -1, -1
    return {'rows': rows, 'cols': cols, 'cells': cells,
            'v_lines': n_v, 'h_lines': n_h}

def _count_cells_from_edges(stamp_img: np.ndarray) -> dict:
    """边缘霍夫统计表格行列"""
    sh, sw = stamp_img.shape[:2]
    lab = cv2.cvtColor(stamp_img, cv2.COLOR_BGR2LAB)
    L, _, _ = cv2.split(lab)
    L_norm = cv2.normalize(L, None, 0, 255, cv2.NORM_MINMAX)
    edges = cv2.Canny(L_norm, 12, 48)
    minLine = max(25, sw // CFG["HOUGH_MIN_LEN_RATIO"])
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                             threshold=CFG["HOUGH_THRESH"], minLineLength=minLine,
                             maxLineGap=CFG["HOUGH_MAX_GAP"])
    if lines is None:
        return {'rows': -1, 'cols': -1, 'cells': -1}
    h_segs, v_segs = [], []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if ang < 12 or ang > 168:
            h_segs.append((x1, y1, x2, y2))
        elif 78 < ang < 102:
            v_segs.append((x1, y1, x2, y2))
    h_cls = _cluster_lines(h_segs, 1, tol=14)
    v_cls = _cluster_lines(v_segs, 0, tol=14)
    h_long = []
    for cl in h_cls:
        y = float(np.mean([s[1] for s in cl]))
        xmin = min(min(s[0], s[2]) for s in cl)
        xmax = max(max(s[0], s[2]) for s in cl)
        if xmax - xmin > sw * 0.08:
            h_long.append((y, xmin, xmax))
    if len(h_long) < 2:
        return {'rows': -1, 'cols': -1, 'cells': -1}
    h_long.sort(key=lambda l: l[0])
    best_h, best_u = None, 999.0
    for sz in range(2, len(h_long) + 1):
        for combo in combinations(range(len(h_long)), sz):
            ys = [h_long[i][0] for i in combo]
            gaps = [ys[j + 1] - ys[j] for j in range(len(ys) - 1)]
            if not gaps or min(gaps) < 15:
                continue
            u = float(np.std(gaps) / np.mean(gaps)) if np.mean(gaps) > 0 else 999.0
            x_overlap = (min(h_long[i][2] for i in combo) - max(h_long[i][1] for i in combo))
            if u < best_u and x_overlap > sw * 0.03:
                best_u = u
                best_h = [h_long[i] for i in combo]
    if best_h is None or best_u > 0.48:
        return {'rows': -1, 'cols': -1, 'cells': -1}
    y_top = min(l[0] for l in best_h)
    y_bot = max(l[0] for l in best_h)
    x_common_l = max(l[1] for l in best_h)
    x_common_r = min(l[2] for l in best_h)
    table_h = y_bot - y_top
    crossing_v = []
    for cl in v_cls:
        x = float(np.mean([s[0] for s in cl]))
        ymin = float(min(min(s[1], s[3]) for s in cl))
        ymax = float(max(max(s[1], s[3]) for s in cl))
        overlap = max(0.0, min(ymax, y_bot) - max(ymin, y_top))
        if (overlap / table_h >= 0.40 and (x_common_l - 25) <= x <= (x_common_r + 25)):
            crossing_v.append(x)
    crossing_v.sort()
    filtered_v = [crossing_v[0]] if crossing_v else []
    for xv in crossing_v[1:]:
        if xv - filtered_v[-1] > 32:
            filtered_v.append(xv)
    rows = max(0, len(best_h) - 1)
    cols = max(0, len(filtered_v) - 1)
    cells = rows * cols
    # 少格过滤
    if cells < CFG["MIN_CELL_COUNT"]:
        rows, cols, cells = -1, -1, -1
    return {'rows': rows, 'cols': cols, 'cells': cells}

def _is_valid_stamp(img: np.ndarray, x: int, y: int, w: int, h: int,
                    color_mask=None) -> bool:
    """外形校验，放宽尺寸+位置，依靠后续行列防误检"""
    ih, iw = img.shape[:2]
    aspect = w / h if h > 0 else 0
    if not (CFG["ASPECT_MIN"] < aspect < CFG["ASPECT_MAX"]):
        return False
    if w > iw * 0.95:
        return False
    if w < CFG["MIN_W"] or h < CFG["MIN_H"]:
        return False
    if h > 800 or h > ih * 0.80:
        return False
    # 底部位置限制
    if ih > 1000:
        pos_limit = 0.65
    elif ih > 600:
        pos_limit = 0.82
    else:
        pos_limit = 0.98
    if (y + h) / ih > pos_limit:
        return False
    pad = 3
    rx1, ry1 = max(0, x - pad), max(0, y - pad)
    rx2, ry2 = min(iw, x + w + pad), min(ih, y + h + pad)
    if color_mask is not None:
        roi_mask = color_mask[ry1:ry2, rx1:rx2]
        rh, rw = roi_mask.shape[:2]
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, int(rh * 0.50))))
        v_lines = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, vk)
        vc, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_v = [c for c in vc if cv2.boundingRect(c)[2] <= rw * 0.12]
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(8, int(rw * 0.45)), 1))
        h_lines = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, hk)
        hc, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(valid_v) < CFG["V_LINE_MIN"] or len(hc) < CFG["H_LINE_MIN"]:
            return False
    else:
        roi = img[ry1:ry2, rx1:rx2]
        rh, rw = roi.shape[:2]
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        L, _, _ = cv2.split(lab)
        L_norm = cv2.normalize(L, None, 0, 255, cv2.NORM_MINMAX)
        edges = cv2.Canny(L_norm, 12, 48)
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, int(rh * 0.50))))
        v_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vk)
        vc, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_v = [c for c in vc if cv2.boundingRect(c)[2] <= rw * 0.12]
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(8, int(rw * 0.45)), 1))
        h_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, hk)
        hc, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(valid_v) < CFG["V_LINE_MIN"] or len(hc) < CFG["H_LINE_MIN"]:
            return False
    return True

def _detect_color_stamp(img: np.ndarray, debug=False) -> dict | None:
    """颜色检测：新增红像素占比过滤红头框+国标行列校验"""
    img_pre = _preprocess_img(img)
    ih, iw = img_pre.shape[:2]
    hsv = cv2.cvtColor(img_pre, cv2.COLOR_BGR2HSV)
    color_defs = {
        'red': (cv2.inRange(hsv, CFG["RED_HSV1"], CFG["RED_HSV2"]) |
                cv2.inRange(hsv, CFG["RED_HSV3"], CFG["RED_HSV4"])),
        'blue': cv2.inRange(hsv, CFG["BLUE_HSV1"], CFG["BLUE_HSV2"]),
    }
    for color_name, raw_mask in color_defs.items():
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, CFG["COLOR_CLOSE_KERNEL"])
        mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(contours, key=cv2.contourArea, reverse=True):
            area = cv2.contourArea(c)
            if area < CFG["MIN_CONTOUR_AREA"]:
                continue
            x, y, w, h = cv2.boundingRect(c)

            # =========【1、红头过滤：红色像素占比过高直接跳过】=========
            roi_mask = mask[y:y+h, x:x+w]
            red_ratio = np.count_nonzero(roi_mask) / roi_mask.size
            if red_ratio > CFG["TEXT_RED_RATIO_LIMIT"]:
                if debug:
                    print(f"  过滤红头框：红占比{red_ratio:.2f}>{CFG['TEXT_RED_RATIO_LIMIT']}")
                continue

            if not _is_valid_stamp(img_pre, x, y, w, h, color_mask=mask):
                continue
            pad = 5
            rx1, ry1 = max(0, x - pad), max(0, y - pad)
            rx2, ry2 = min(iw, x + w + pad), min(ih, y + h + pad)
            stamp_mask_crop = mask[ry1:ry2, rx1:rx2]
            grid = _count_cells_from_mask(stamp_mask_crop)

            # =========【2、国标归档章强制行列校验：≥2行 or ≥3列】=========
            if CFG["ROW_COL_FILTER"]:
                row_ok = grid['rows'] >= CFG["STD_STAMP_ROW"]
                col_ok = grid['cols'] >= CFG["STD_STAMP_COL"]
                if not (row_ok or col_ok):
                    if debug:
                        print(f"  行列不达标过滤：{grid['rows']}行 {grid['cols']}列")
                    continue
            if grid['cells'] <= 0:
                continue

            result = {
                'method': color_name,
                'bbox': (max(0, x - 20), max(0, y - 20),
                         min(iw, x + w + 20), min(ih, y + h + 20)),
                **grid
            }
            if debug:
                print(f"  ✅ [{color_name}章] bbox={result['bbox']}, {grid['rows']}行×{grid['cols']}列={grid['cells']}格")
            return result
    return None

def _detect_struct_in_block(img: np.ndarray, sx1: int, sy1: int,
                             sx2: int, sy2: int, debug=False) -> dict | None:
    roi_raw = img[sy1:sy2, sx1:sx2]
    roi = _preprocess_img(roi_raw)
    rh, rw = roi.shape[:2]
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    L, _, _ = cv2.split(lab)
    L_norm = cv2.normalize(L, None, 0, 255, cv2.NORM_MINMAX)
    edges = cv2.Canny(L_norm, 22, 75)
    min_line = max(25, rw // CFG["HOUGH_MIN_LEN_RATIO"])
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                             threshold=CFG["HOUGH_THRESH"]+8, minLineLength=min_line, maxLineGap=22)
    if lines is None:
        return None
    h_segs, v_segs = [], []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if ang <12 or ang>168:
            h_segs.append((x1,y1,x2,y2))
        elif 78<ang<102:
            v_segs.append((x1,y1,x2,y2))
    h_cls = _cluster_lines(h_segs,1,14)
    v_cls = _cluster_lines(v_segs,0,14)
    h_long = []
    for cl in h_cls:
        y = float(np.mean([s[1] for s in cl]))
        xmin = min(min(s[0],s[2]) for s in cl)
        xmax = max(max(s[0],s[2]) for s in cl)
        if xmax-xmin>=40:
            h_long.append((y,xmin,xmax))
    v_long = []
    for cl in v_cls:
        x = float(np.mean([s[0] for s in cl]))
        ymin = min(min(s[1],s[3]) for s in cl)
        ymax = max(max(s[1],s[3]) for s in cl)
        if ymax-ymin>=32:
            v_long.append((x,ymin,ymax))
    if len(h_long) < 2 or len(v_long) < 3:
        return None
    pts = set()
    for hy,hx1,hx2 in h_long:
        for vx,vy1,vy2 in v_long:
            if hx1<=vx<=hx2 and vy1<=hy<=vy2:
                pts.add((round(vx),round(hy)))
    if len(pts)<3:
        return None
    ys_u = sorted(set(p[1] for p in pts))
    best_rect, best_score = None,0
    for y_top,y_bot in combinations(ys_u,2):
        table_h = y_bot-y_top
        if table_h<15:
            continue
        xs_top = {p[0] for p in pts if abs(p[1]-y_top)<18}
        xs_bot = {p[0] for p in pts if abs(p[1]-y_bot)<18}
        common_xs = sorted(xs_top & xs_bot)
        if len(common_xs)<2:
            continue
        table_w = common_xs[-1]-common_xs[0]
        aspect = table_w/table_h if table_h>0 else 0
        if 1.1<aspect<12:
            score = len(common_xs)*table_w
            if score>best_score:
                best_score=score
                best_rect=(common_xs[0],y_top,common_xs[-1],y_bot,len(common_xs))
    if best_rect is None:
        return None
    lx1,ly1,lx2,ly2,n_v_lines = best_rect
    bw = lx2-lx1
    bh = ly2-ly1
    full_img_w = sx2-sx1
    full_img_h = sy2-sy1
    if bw>full_img_w*0.96 or bh>full_img_h*0.65:
        return None
    pad=20
    gx1 = max(0,sx1+lx1-pad)
    gy1 = max(0,sy1+ly1-pad)
    gx2 = min(img.shape[1],sx1+lx2+pad)
    gy2 = min(img.shape[0],sy1+ly2+pad)
    stamp_crop = img[gy1:gy2,gx1:gx2]
    grid = _count_cells_from_edges(stamp_crop)

    # 结构检测同样行列防误检
    if CFG["ROW_COL_FILTER"]:
        row_ok = grid['rows'] >= CFG["STD_STAMP_ROW"]
        col_ok = grid['cols'] >= CFG["STD_STAMP_COL"]
        if not (row_ok or col_ok) or grid['cells'] <= 0:
            return None

    result = {
        'method':'structure',
        'bbox':(gx1,gy1,gx2,gy2),**grid
    }
    if debug:
        print(f"  ✅ [结构检测] bbox={result['bbox']},{grid['rows']}×{grid['cols']}列={grid['cells']}")
    return result

def _detect_struct_stamp(img: np.ndarray, debug=False) -> dict | None:
    """多尺度滑窗全图搜索，适配中下位置归档章"""
    ih,iw = img.shape[:2]
    search_h = int(ih*CFG["SEARCH_RATIO"])
    for win_ratio in CFG["WIN_SCALE"]:
        bw = int(iw*win_ratio)
        bh = int(search_h*0.72)
        stride_x = int(iw*CFG["STRIDE_X_RATIO"])
        stride_y = int(search_h*CFG["STRIDE_Y_RATIO"])
        for y in range(0, search_h - bh//2, stride_y):
            for x in range(0, iw - bw//2, stride_x):
                x2 = min(iw, x+bw)
                y2 = min(ih, y+bh)
                res = _detect_struct_in_block(img,x,y,x2,y2,debug)
                if res:
                    return res
    return None

def detect_stamp(image_path: str, debug=False) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        return {'found':False,'method':None,'bbox':None,'rows':0,'cols':0,'cells':0}
    if debug:
        ih,iw = img.shape[:2]
        print(f"\n🔍 [{image_path}] ({iw}×{ih})")
    res = _detect_color_stamp(img,debug=debug)
    if res is None:
        if debug:print("  颜色检测未命中，切换结构检测...")
        res = _detect_struct_stamp(img,debug=debug)
    if res is None:
        if debug:print("  ❌ 未检测到归档章")
        return {'found':False,'method':None,'bbox':None,'rows':0,'cols':0,'cells':0}
    return {'found':True,**res}

def has_stamp(image_path: str, debug=False) -> bool:
    return detect_stamp(image_path,debug)['found']

def get_stamp_crop(image_path: str, debug=False) -> np.ndarray | None:
    r = detect_stamp(image_path,debug)
    if not r['found']:return None
    img = cv2.imread(image_path)
    x1,y1,x2,y2 = r['bbox']
    return img[y1:y2,x1:x2]

def split_archives(input_dir: str, output_dir: str, debug=False):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True,exist_ok=True)
    image_files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in ('.jpg','.jpeg','.png','.bmp','.tiff','.tif')],key=lambda f:f.name)
    if not image_files:
        print("⚠️未找到图片")
        return
    print(f"📂共{len(image_files)}张图片，开始处理\n")
    current_folder = None
    archive_index =0
    for img_file in image_files:
        res = detect_stamp(str(img_file),debug=debug)
        if res['found']:
            archive_index +=1
            cells_str = f" [{res['rows']}行×{res['cols']}列={res['cells']}格]" if res['cells']>0 else ""
            folder_name = f"archive_{archive_index:03d}"
            current_folder = output_path/folder_name
            current_folder.mkdir(exist_ok=True)
            print(f"📁新建档案:{folder_name} ←{img_file.name}{cells_str}")
        else:
            if current_folder is None:
                current_folder = output_path/"uncategorized"
                current_folder.mkdir(exist_ok=True)
            print(f"  ↳ {current_folder.name} ←{img_file.name}")
        shutil.copy2(str(img_file),current_folder/img_file.name)
    print(f"\n✅完成！分出{archive_index}份档案，输出：{output_dir}")

if __name__ == "__main__":
    import time
    TEST_IMAGES = [
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0001.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0013_1780549817.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0025_1780549818.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0037_1780549820.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0045_1780553119.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0055_1780549822.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0057_1780553119.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0073_1780553276.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0075_1780549823.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0087_1780553121.jpg",
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/parts_temp_0099_1780553278.jpg",
    ]
    print("="*60)
    print("【优化版-单图测试】")
    print("="*60)
    for path in TEST_IMAGES:
        t0 = time.time()
        r = detect_stamp(path,debug=True)
        elapsed = time.time()-t0
        status = "✅有归档章" if r['found'] else "❌无归档章"
        cells = f"{r['rows']}行×{r['cols']}列={r['cells']}格" if r['cells']>0 else "格子未知"
        print(f"结果:{status} {cells} 耗时:{elapsed:.2f}s\n")

    # 批量分件启用
    # split_archives("input_dir","output_dir",debug=True)
