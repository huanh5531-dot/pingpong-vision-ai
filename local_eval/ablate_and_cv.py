import json, math, sys, glob
import numpy as np
from collections import defaultdict, Counter
from scipy.optimize import linear_sum_assignment

sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open(r'D:\pingpang源文件汇总\local_eval\public_trajs.json', encoding='utf-8'))

ROI_BY_ANGLE = {
    "0度":  (0.35, 0.65, 0.25, 0.60),
    "45度": (0.25, 0.75, 0.35, 0.61),
    "90度": (0.37, 0.64, 0.38, 0.72),
}

def build_clean_traj(info):
    ch1 = {int(k): v for k, v in info['ch1'].items()}
    fused = {int(k): v for k, v in info['fused'].items()}
    n_frames = info['n_frames']

    raw = []
    for f in range(n_frames):
        c1 = ch1.get(f)
        fm = fused.get(f, {}).get('max')
        fa = fused.get(f, {}).get('avg')
        if c1 and c1['conf'] >= 0.65:
            raw.append((f, c1['lx'], c1['ly'], c1['conf']))
        elif fm and fm['conf'] >= 0.60:
            raw.append((f, fm['lx'], fm['ly'], fm['conf']))
        elif c1 and fa and c1['conf'] >= 0.50 and fa['conf'] >= 0.45:
            raw.append((f, c1['lx'], c1['ly'], max(c1['conf'], fa['conf'])))

    cell_counts = Counter((round(x / 4.0), round(y / 4.0)) for _, x, y, _ in raw)
    hotspots = {cell for cell, cnt in cell_counts.items() if cnt >= 4}
    raw_no_hotspot = [
        (f, x, y, c) for (f, x, y, c) in raw
        if (round(x / 4.0), round(y / 4.0)) not in hotspots
    ]

    cleaned = []
    m = len(raw_no_hotspot)
    for i in range(m):
        f, x, y, c = raw_no_hotspot[i]
        is_bad = False
        if 0 < i < m - 1:
            f_prev, xp, yp, _ = raw_no_hotspot[i - 1]
            f_next, xn, yn, _ = raw_no_hotspot[i + 1]
            if f - f_prev <= 2 and f_next - f <= 2:
                d_prev = math.hypot(x - xp, y - yp)
                d_next = math.hypot(xn - x, yn - y)
                d_bridge = math.hypot(xn - xp, yn - yp)
                if d_prev > 45 and d_next > 45 and d_bridge < 0.45 * (d_prev + d_next):
                    is_bad = True
                elif d_prev > 120 and d_next > 120 and d_bridge < 0.65 * (d_prev + d_next):
                    is_bad = True
        if not is_bad:
            cleaned.append((f, x, y, c))
    return cleaned

def eval_quiet(preds_by_vid):
    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for vid, info in data.items():
        angle = info['angle']
        preds = preds_by_vid.get(vid, [])
        gts = info['gts']
        valid_gts = [g for g in gts if g.get("valid", True)]
        ignore_gts = [g for g in gts if not g.get("valid", True)]
        st = stats[angle]
        tau_s = 0.025 * info['width']
        if not preds:
            st["fn"] += len(valid_gts)
            continue
        cost_matrix = np.full((len(preds), len(valid_gts)), 1e6)
        for i, p in enumerate(preds):
            for j, g in enumerate(valid_gts):
                if abs(p["frame_id"] - g["frame_id"]) <= 1:
                    d = math.hypot(p["x"] - g["x"], p["y"] - g["y"])
                    if d <= tau_s:
                        cost_matrix[i, j] = d
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matched_preds, matched_gts = set(), set()
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < 1e5:
                matched_preds.add(r)
                matched_gts.add(c)
                st["tp"] += 1
        st["fn"] += (len(valid_gts) - len(matched_gts))
        for i, p in enumerate(preds):
            if i not in matched_preds:
                hit_ignore = any(
                    abs(p["frame_id"] - ig["frame_id"]) <= 1
                    and math.hypot(p["x"] - ig["x"], p["y"] - ig["y"]) <= tau_s
                    for ig in ignore_gts
                )
                if not hit_ignore:
                    st["fp"] += 1
    f1s = {}
    tot_tp = tot_fp = tot_fn = 0
    for angle in ["0度", "45度", "90度"]:
        s = stats[angle]
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        tot_tp += tp; tot_fp += fp; tot_fn += fn
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1s[angle] = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    macro = sum(f1s.values()) / 3.0
    return macro, macro * 75.0, f1s, (tot_tp, tot_fp, tot_fn)

def detect_with_config(info, cfg):
    angle = info['angle']
    width = info['width']
    height = info['height']
    rx0, rx1, ry0, ry1 = ROI_BY_ANGLE.get(angle, (0.25, 0.75, 0.25, 0.72))

    traj = build_clean_traj(info)
    n = len(traj)
    candidates = []
    s = cfg.get("scale", {})
    def S(key, val):
        return val * s.get(key, 1.0)

    for j in range(1, n - 1):
        fid, x, y, conf = traj[j]
        nx, ny = x / width, y / height
        if not (rx0 <= nx <= rx1 and ry0 <= ny <= ry1):
            continue

        f_prev, xp, yp, _ = traj[j - 1]
        f_next, xn, yn, _ = traj[j + 1]
        dt_in = fid - f_prev
        dt_out = f_next - fid

        vx_in = (x - xp) / dt_in
        vy_in = (y - yp) / dt_in
        vx_out = (xn - x) / dt_out
        vy_out = (yn - y) / dt_out

        # R1: Video start bounce
        if cfg.get("use_r1", True) and j == 1 and fid <= 4 and dt_in == 1 and dt_out == 1:
            nxp, nyp = xp / width, yp / height
            if rx0 <= nxp <= rx1 and ry0 <= nyp <= ry1 and abs(vx_in) >= 4.0:
                if vy_in >= -2.0 and vy_out <= -15.0 and (vy_in - vy_out) >= 18.0:
                    candidates.append((f_prev, float(xp), float(yp), 50.0))
                    continue

        if dt_in > 3 or dt_out > 3:
            continue

        vy_in2, vx_in2 = vy_in, vx_in
        prev_vy, prev_vx = vy_in, vx_in
        prev_dt = 99
        if j >= 2:
            prev_dt = f_prev - traj[j - 2][0]
            if prev_dt <= 3:
                prev_vy = (yp - traj[j - 2][2]) / prev_dt
                prev_vx = (xp - traj[j - 2][1]) / prev_dt
            if (fid - traj[j - 2][0]) <= 4:
                dt2 = fid - traj[j - 2][0]
                vy_in2 = (y - traj[j - 2][2]) / dt2
                vx_in2 = (x - traj[j - 2][1]) / dt2

        vy_out2, next_vy = vy_out, vy_out
        if j + 2 < n:
            next_dt = traj[j + 2][0] - f_next
            if next_dt <= 3:
                next_vy = (traj[j + 2][2] - yn) / next_dt
            if (traj[j + 2][0] - fid) <= 4:
                dt2 = traj[j + 2][0] - fid
                vy_out2 = (traj[j + 2][2] - y) / dt2

        speed_in = math.hypot(vx_in, vy_in)
        speed_out = math.hypot(vx_out, vy_out)
        if (speed_in < 2.5 and speed_out < 2.5) or max(speed_in, speed_out) < 4.0 or speed_in > 220 or speed_out > 220:
            continue

        # R4: 1-frame downward teleport filter
        if cfg.get("use_r4", True) and prev_dt == 1 and vy_in > S("r4_vy", 50.0) and (vy_in - prev_vy) > S("r4_dvy", 35.0):
            continue

        # Serve paddle hit filter
        if prev_dt <= 2 and min(abs(vx_in), abs(prev_vx)) < S("srv_vx", 4.2) and abs(vx_in2) < 12.0 and max(abs(vx_out), abs(vx_in)) > S("srv_vxo", 14.0):
            continue

        # R5: 2-step horizontal reversal filter
        if cfg.get("use_r5", True) and prev_dt <= 2 and prev_vx * vx_out < 0 and abs(prev_vx) > S("r5_vxi", 4.5) and abs(vx_out) > S("r5_vxo", 12.0):
            continue

        if angle == "90度":
            # R2: 90-deg start-of-segment exception
            if cfg.get("use_r2", True):
                if abs(vx_in) < S("vx90", 4.5) and abs(vx_in2) < S("vx90", 4.5) and (prev_dt <= 3 or abs(vx_out) < 10.0):
                    continue
            else:
                if abs(vx_in) < S("vx90", 4.5) and abs(vx_in2) < S("vx90", 4.5):
                    continue
            if vx_in * vx_out < 0 and abs(vx_in) > 5.0 and abs(vx_out) > 5.0:
                continue
            if abs(vx_out - vx_in) > 35.0 and vx_in * vx_out <= 0:
                continue
        elif angle == "45度":
            if vx_in * vx_out < 0 and abs(vx_in) > 6.0 and abs(vx_out) > 6.0:
                continue
            if abs(vx_out - vx_in) > 38.0 and vx_in * vx_out <= 0:
                continue
        else:
            if vx_in * vx_out < 0 and abs(vx_in) > 6.0 and abs(vx_out) > 6.0:
                continue
            if abs(vx_out - vx_in) > 35.0 and abs(vy_out) > 50.0:
                continue

        is_landing = False
        score = 0.0

        # Mode 1
        eff_fall = max(vy_in, vy_in2, prev_vy if prev_dt <= 2 else vy_in)
        eff_rise = -min(vy_out, vy_out2, next_vy if dt_out == 1 else vy_out)
        if cfg.get("use_r6", True):
            min_sum = S("m1_sum", 6.5 if angle == "90度" else 8.0)
        else:
            min_sum = S("m1_sum", 7.0)
        if (y >= yp - S("m1_flat", 4.0) and y >= yn - S("m1_flat", 2.8)) and eff_fall >= S("m1_fall", 2.0) and eff_rise >= S("m1_rise", 1.2):
            if vy_in >= -S("m1_flat", 4.0) and vy_out <= 2.2 and (eff_fall + eff_rise) >= min_sum:
                if dt_out == 1 or vy_out <= -4.0:
                    if abs(vx_out - vx_in) <= S("m1_dvx", 32.0) or angle == "90度" or (vx_in * vx_out > 0 and vy_in >= 30.0):
                        is_landing = True
                        score = vy_in - vy_out

        # Mode 2
        if not is_landing and angle in ("0度", "45度"):
            best_vy_out = min(vy_out, vy_out2)
            min_prev_vy = min(prev_vy, vy_in2) if prev_dt <= 2 else prev_vy
            if dt_in == 1 and prev_dt <= 2 and prev_vx * vx_in > 0:
                if min_prev_vy <= -1.8 and -8.0 <= vy_in <= 3.0 and (vy_in - prev_vy) >= -1.5:
                    if best_vy_out <= -S("m2_vyo", 11.0) and (vy_in - best_vy_out) >= S("m2_imp", 12.0):
                        if abs(vx_out - vx_in) <= S("m2_dvx", 18.0) and vx_in * vx_out > 0:
                            is_landing = True
                            score = (vy_in - best_vy_out)
            # R3: Mode 2B occlusion bounce
            elif cfg.get("use_r3", True) and dt_in == 1 and prev_dt > 2 and prev_vx * vx_in > 0 and -7.0 <= vy_in <= 1.0 and vy_out <= -12.0 and (vy_in - vy_out) >= 8.0:
                if abs(vx_out - vx_in) <= 6.0 and vx_in * vx_out > 0:
                    is_landing = True
                    score = (vy_in - vy_out)

        # Mode 3
        if not is_landing:
            if prev_dt <= 2 and prev_vy >= 10.0 and abs(vy_in - prev_vy) <= 30.0 and math.hypot(prev_vx, prev_vy) <= 150.0:
                peak_fall = max(vy_in, prev_vy)
                if peak_fall >= S("m3_fall", 20.0) and vy_in >= 10.0:
                    drop1 = vy_in - vy_out
                    drop2 = peak_fall - vy_out
                    if (drop1 >= S("m3_drop1", 13.0) or drop2 >= S("m3_drop2", 24.0)) and -15.0 <= vy_out <= 16.0 and vy_out <= S("m3_ratio", 0.55) * peak_fall:
                        if vy_out2 <= 0.60 * peak_fall and abs(vx_out - vx_in) <= S("m3_dvx", 22.0) and vx_in * vx_out >= -5.0:
                            is_landing = True
                            score = max(drop1, drop2)

        if is_landing:
            candidates.append((fid, float(x), float(y), score))

    out = []
    cluster_start = -999
    for fid, x, y, sc in candidates:
        if out and (fid - cluster_start) == 1:
            if sc > out[-1][3]:
                out[-1] = (fid, x, y, sc)
        elif out and (fid - out[-1][0]) < 8:
            continue
        else:
            out.append((fid, x, y, sc))
            cluster_start = fid

    return [{"frame_id": fid, "x": x, "y": y} for fid, x, y, _ in out]

print("=== 1. ABLATION OF HIGH-RISK (🔴) RULES ===")
ablations = [
    ("Full v1 (Current)", {}),
    ("- R1 (No video-start f<=4 rule)", {"use_r1": False}),
    ("- R2 (No 90-deg start exception)", {"use_r2": False}),
    ("- R3 (No Mode 2B after-occlusion)", {"use_r3": False}),
    ("- R4 (No 1-frame teleport filter)", {"use_r4": False}),
    ("- R5 (No 2-step reversal filter)", {"use_r5": False}),
    ("- R6 (Unified min_sum=7.0)", {"use_r6": False}),
    ("- ALL Single-Sample Rules (R1+R2+R3+R6 off)", {"use_r1": False, "use_r2": False, "use_r3": False, "use_r6": False}),
]
for name, cfg in ablations:
    preds = {vid: detect_with_config(info, cfg) for vid, info in data.items()}
    macro, score, f1s, (tp, fp, fn) = eval_quiet(preds)
    print(f"{name:42s} | Macro F1={macro:.4f} ({score:5.2f}/75) | TP={tp:2d} FP={fp:2d} FN={fn:2d} | 0°={f1s['0度']:.3f} 45°={f1s['45度']:.3f} 90°={f1s['90度']:.3f}")

print("\n=== 2. MONTE CARLO THRESHOLD SENSITIVITY (300 runs) ===")
rng = np.random.default_rng(42)
keys = ["r4_vy", "r4_dvy", "srv_vx", "srv_vxo", "r5_vxi", "r5_vxo", "vx90",
        "m1_sum", "m1_flat", "m1_fall", "m1_rise", "m1_dvx",
        "m2_vyo", "m2_imp", "m2_dvx", "m3_fall", "m3_drop1", "m3_drop2", "m3_ratio", "m3_dvx"]
for noise_lvl in [0.10, 0.15, 0.20]:
    f1_samples = []
    for _ in range(300):
        sc_map = {k: float(rng.uniform(1.0 - noise_lvl, 1.0 + noise_lvl)) for k in keys}
        preds = {vid: detect_with_config(info, {"scale": sc_map}) for vid, info in data.items()}
        macro, _, _, _ = eval_quiet(preds)
        f1_samples.append(macro)
    arr = np.array(f1_samples)
    print(f"Noise ±{int(noise_lvl*100):2d}% | Mean F1={arr.mean():.4f} ± {arr.std():.4f} | Median={np.median(arr):.4f} | P10={np.percentile(arr,10):.4f} | P90={np.percentile(arr,90):.4f} | Min={arr.min():.4f}")

print("\n=== 3. LEAVE-ONE-VIDEO-OUT CROSS-VALIDATION (LOVO-CV) ===")
# Compare v2 (R1=False, R6=False) vs Out-of-Fold threshold tuning where scale factors are optimized on 14 videos and tested on the 1 held-out video
lovo_preds = {}
rng_cv = np.random.default_rng(123)
cand_configs = [{"use_r1": False, "use_r6": False}]
for _ in range(60):
    sc_map = {k: float(rng_cv.uniform(0.88, 1.12)) for k in keys}
    cand_configs.append({"use_r1": False, "use_r6": False, "scale": sc_map})

all_vids = list(data.keys())
for held_out_vid in all_vids:
    train_vids = [v for v in all_vids if v != held_out_vid]
    best_cfg = cand_configs[0]
    best_tr_f1 = -1.0
    for cfg in cand_configs:
        # Evaluate on 14 training videos
        sub_preds = {v: detect_with_config(data[v], cfg) for v in train_vids}
        # Compute micro F1 on 14 videos
        tp = fp = fn = 0
        for v in train_vids:
            info = data[v]
            ps = sub_preds[v]
            valid_gts = [g for g in info['gts'] if g.get("valid", True)]
            ignore_gts = [g for g in info['gts'] if not g.get("valid", True)]
            tau_s = 0.025 * info['width']
            if not ps:
                fn += len(valid_gts)
                continue
            cm = np.full((len(ps), len(valid_gts)), 1e6)
            for i, p in enumerate(ps):
                for j, g in enumerate(valid_gts):
                    if abs(p["frame_id"] - g["frame_id"]) <= 1:
                        d = math.hypot(p["x"] - g["x"], p["y"] - g["y"])
                        if d <= tau_s:
                            cm[i, j] = d
            ri, ci = linear_sum_assignment(cm)
            mp, mg = set(), set()
            for r, c in zip(ri, ci):
                if cm[r, c] < 1e5:
                    mp.add(r); mg.add(c); tp += 1
            fn += (len(valid_gts) - len(mg))
            for i, p in enumerate(ps):
                if i not in mp:
                    if not any(abs(p["frame_id"] - ig["frame_id"]) <= 1 and math.hypot(p["x"] - ig["x"], p["y"] - ig["y"]) <= tau_s for ig in ignore_gts):
                        fp += 1
        f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0
        if f1 > best_tr_f1:
            best_tr_f1 = f1
            best_cfg = cfg
    lovo_preds[held_out_vid] = detect_with_config(data[held_out_vid], best_cfg)

macro_lovo, score_lovo, f1s_lovo, (tp_l, fp_l, fn_l) = eval_quiet(lovo_preds)
print(f"Out-of-Fold LOVO-CV (15 folds)             | Macro F1={macro_lovo:.4f} ({score_lovo:5.2f}/75) | TP={tp_l:2d} FP={fp_l:2d} FN={fn_l:2d} | 0°={f1s_lovo['0度']:.3f} 45°={f1s_lovo['45度']:.3f} 90°={f1s_lovo['90度']:.3f}")

