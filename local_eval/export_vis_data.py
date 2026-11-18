# -*- coding: utf-8 -*-
"""
Export complete trajectory, predictions (with physics mode/impulse metadata), fps,
match titles, and GTs for the interactive real-video visualizer plugin.
"""
import os
import re
import json
import math
import sys
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'D:\pingpang源文件汇总\local_eval')
from ablate_and_cv import data, detect_with_config, build_clean_traj, ROI_BY_ANGLE

with open(r'D:\pingpang源文件汇总\participant\pingpang\public_data\manifest.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)
meta_map = {v['video_id']: v for v in manifest['videos']}

def extract_match_title(rel_path):
    base = os.path.basename(rel_path)
    m = re.search(r'\[(.*?)\]', base)
    if m:
        title = m.group(1)
        # Shorten common prefixes for crisp dropdown display
        title = title.replace('直通WTT大满贯·世乒赛', '世乒赛直通')
        title = title.replace('中国乒超联赛', '乒超')
        title = title.replace('全运会乒乓球', '全运会')
        title = title.replace('乒乓球超级联赛', '乒超')
        title = title.replace('全场回放-', '')
        title = title.replace('回放-', '')
        return title
    return base

def annotate_landing_physics(traj, preds, angle, width, height):
    """Annotate each predicted landing with kinematic mode and impulse details."""
    sx = 1920.0 / max(1, width)
    sy = 1080.0 / max(1, height)
    # Build lookup from frame_id to traj index
    idx_by_f = {f: idx for idx, (f, _, _, _) in enumerate(traj)}
    enriched = []
    for p in preds:
        fid = int(p['frame_id'])
        j = idx_by_f.get(fid, -1)
        mode = "物理极值反弹"
        vy_in, vy_out, vx_in, vx_out, dvy = 0.0, 0.0, 0.0, 0.0, 0.0
        if 1 <= j < len(traj) - 1:
            f_prev, xp, yp, _ = traj[j - 1]
            _, x, y, _ = traj[j]
            f_next, xn, yn, _ = traj[j + 1]
            dt_in = max(1, fid - f_prev)
            dt_out = max(1, f_next - fid)
            vx_in = (x - xp) / dt_in
            vy_in = (y - yp) / dt_in
            vx_out = (xn - x) / dt_out
            vy_out = (yn - y) / dt_out
            dvy = vy_in - vy_out

            if y >= yp - 4.0 and y >= yn - 2.8 and vy_out <= 2.2:
                mode = "模态1·平顶极值反弹"
            elif angle in ("0度", "45度") and vy_out <= -11.0 and vy_in <= 3.0:
                mode = "模态2·远台深度加速反弹"
            elif vy_in >= 10.0:
                mode = "模态3·近台高速触台急停"

        enriched.append({
            'frame_id': fid,
            'x': round(float(p['x']), 1),
            'y': round(float(p['y']), 1),
            'mode': mode,
            'vx_in': round(vx_in, 1),
            'vy_in': round(vy_in, 1),
            'vx_out': round(vx_out, 1),
            'vy_out': round(vy_out, 1),
            'impulse': round(dvy, 1),
        })
    return enriched

vis_data = {}
for vid, info in data.items():
    m_info = meta_map.get(vid, {})
    fps = float(m_info.get('fps', 25.0))
    rel_path = m_info.get('path', '')
    match_name = extract_match_title(rel_path)

    cleaned = build_clean_traj(info)
    raw_preds = detect_with_config(info, {'use_r1': False, 'use_r6': False})
    preds = annotate_landing_physics(cleaned, raw_preds, info['angle'], info['width'], info['height'])

    gts = info['gts']
    valid_gts = [g for g in gts if g.get('valid', True)]
    ignore_gts = [g for g in gts if not g.get('valid', True)]
    tau_s = 0.025 * info['width']
    
    cm = [[1e6] * len(valid_gts) for _ in preds]
    for i, p in enumerate(preds):
        for j, g in enumerate(valid_gts):
            if abs(p['frame_id'] - g['frame_id']) <= 1:
                d = math.hypot(p['x'] - g['x'], p['y'] - g['y'])
                if d <= tau_s:
                    cm[i][j] = d
                    
    matched_preds = {}
    matched_gts = set()
    if preds and valid_gts:
        ri, ci = linear_sum_assignment(np.array(cm))
        for r, c in zip(ri, ci):
            if cm[r][c] < 1e5:
                matched_preds[r] = round(float(cm[r][c]), 1)
                matched_gts.add(c)
                
    pred_items = []
    for i, p in enumerate(preds):
        is_tp = i in matched_preds
        is_ignored = False
        if not is_tp:
            is_ignored = any(
                abs(p['frame_id'] - ig['frame_id']) <= 1
                and math.hypot(p['x'] - ig['x'], p['y'] - ig['y']) <= tau_s
                for ig in ignore_gts
            )
        p_out = dict(p)
        p_out['is_tp'] = bool(is_tp)
        p_out['is_ignored'] = bool(is_ignored)
        p_out['error_px'] = matched_preds[i] if is_tp else None
        pred_items.append(p_out)
        
    gt_items = []
    valid_idx = 0
    for g in gts:
        is_valid = bool(g.get('valid', True))
        is_hit = False
        if is_valid:
            is_hit = valid_idx in matched_gts
            valid_idx += 1
        gt_items.append({
            'frame_id': int(g['frame_id']),
            'x': round(float(g['x']), 1),
            'y': round(float(g['y']), 1),
            'valid': is_valid,
            'is_hit': bool(is_hit)
        })
        
    tp = len(matched_preds)
    fp = sum(1 for p in pred_items if not p['is_tp'] and not p['is_ignored'])
    fn = len(valid_gts) - tp
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    
    traj_dict = {
        int(f): {'x': round(float(x), 1), 'y': round(float(y), 1), 'c': round(float(c), 2)}
        for f, x, y, c in cleaned
    }
    
    vis_data[vid] = {
        'video_id': vid,
        'match_name': match_name,
        'angle': info['angle'],
        'fps': fps,
        'width': info['width'],
        'height': info['height'],
        'n_frames': info['n_frames'],
        'rel_path': rel_path,
        'stats': {
            'tp': tp,
            'fp': max(0, fp),
            'fn': fn,
            'precision': round(prec, 4),
            'recall': round(rec, 4),
            'f1': round(f1, 4)
        },
        'traj': traj_dict,
        'preds': pred_items,
        'gts': gt_items
    }

out_path1 = r'C:\Users\LENOVO\.gemini\antigravity\brain\45eb8651-a8aa-499d-8cfa-d4e66e108527\scratch\vis_data.json'
out_path2 = r'D:\pingpang源文件汇总\local_eval\vis_data.json'
for out_p in [out_path1, out_path2]:
    os.makedirs(os.path.dirname(out_p), exist_ok=True)
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(vis_data, f, ensure_ascii=False)

# Verify pooled angle Macro F1
from collections import defaultdict
st_ang = defaultdict(lambda: [0, 0, 0])
for v in vis_data.values():
    s = st_ang[v['angle']]
    s[0] += v['stats']['tp']
    s[1] += v['stats']['fp']
    s[2] += v['stats']['fn']
ang_f1s = {}
for ang, (tp, fp, fn) in st_ang.items():
    p = tp / (tp + fp) if (tp + fp) > 0 else 0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0
    ang_f1s[ang] = 2 * p * r / (p + r) if (p + r) > 0 else 0
macro_f1 = sum(ang_f1s.values()) / len(ang_f1s)
print(f"Exported {len(vis_data)} videos. Pooled Macro F1={macro_f1:.4f} (0°={ang_f1s['0度']:.4f}, 45°={ang_f1s['45度']:.4f}, 90°={ang_f1s['90度']:.4f})")
