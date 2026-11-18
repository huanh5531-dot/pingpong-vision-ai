import json, sys, math
import numpy as np
from collections import defaultdict, Counter
from scipy.optimize import linear_sum_assignment

sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open(r'D:\pingpang源文件汇总\participant\output\public_trajs.json', encoding='utf-8'))

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

    # Identify static background false-positive hotspots (same 4x4 px cell visited >= 4 times)
    cell_counts = Counter((round(x / 4.0), round(y / 4.0)) for _, x, y, _ in raw)
    hotspots = {cell for cell, cnt in cell_counts.items() if cnt >= 4}

    raw_no_hotspot = [
        (f, x, y, c) for (f, x, y, c) in raw
        if (round(x / 4.0), round(y / 4.0)) not in hotspots
    ]

    # Filter out single-frame spatial spike outliers
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

def detect_landings(info):
    angle = info['angle']
    width = info['width']
    height = info['height']
    rx0, rx1, ry0, ry1 = ROI_BY_ANGLE.get(angle, (0.25, 0.75, 0.25, 0.72))

    traj = build_clean_traj(info)
    n = len(traj)
    candidates = []

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

        # Very start of video bounce (e.g. v000066 f=2..3)
        if j == 1 and fid <= 4 and dt_in == 1 and dt_out == 1:
            nxp, nyp = xp / width, yp / height
            if rx0 <= nxp <= rx1 and ry0 <= nyp <= ry1 and abs(vx_in) >= 4.0:
                if vy_in >= -2.0 and vy_out <= -15.0 and (vy_in - vy_out) >= 18.0:
                    candidates.append((f_prev, float(xp), float(yp), 50.0))
                    continue

        if dt_in > 3 or dt_out > 3:
            continue

        # 2-step lookback / lookahead
        vy_in2 = vy_in
        vx_in2 = vx_in
        prev_vy = vy_in
        prev_vx = vx_in
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

        vy_out2 = vy_out
        vx_out2 = vx_out
        next_vy = vy_out
        if j + 2 < n:
            next_dt = traj[j + 2][0] - f_next
            if next_dt <= 3:
                next_vy = (traj[j + 2][2] - yn) / next_dt
            if (traj[j + 2][0] - fid) <= 4:
                dt2 = traj[j + 2][0] - fid
                vy_out2 = (traj[j + 2][2] - y) / dt2
                vx_out2 = (traj[j + 2][1] - x) / dt2

        # Reject stationary detections or huge unphysical jumps
        speed_in = math.hypot(vx_in, vy_in)
        speed_out = math.hypot(vx_out, vy_out)
        if (speed_in < 2.5 and speed_out < 2.5) or max(speed_in, speed_out) < 4.0 or speed_in > 220 or speed_out > 220:
            continue

        # Reject unphysical 1-frame downward teleport before bounce (e.g. v000001 f=17)
        if prev_dt == 1 and vy_in > 50.0 and (vy_in - prev_vy) > 35.0:
            continue

        # Reject serve paddle hit (vertical toss for >=2 steps with small vx, suddenly hit horizontally with large vx)
        if prev_dt <= 2 and min(abs(vx_in), abs(prev_vx)) < 4.2 and abs(vx_in2) < 12.0 and max(abs(vx_out), abs(vx_in)) > 14.0:
            continue

        # Reject 2-step horizontal reversal (player paddle hit straddling 2 frames, e.g. v000106 f=69)
        if prev_dt <= 2 and prev_vx * vx_out < 0 and abs(prev_vx) > 4.5 and abs(vx_out) > 12.0:
            continue

        # Angle-specific paddle strike & serve toss rejection
        if angle == "90度":
            if abs(vx_in) < 4.5 and abs(vx_in2) < 4.5 and (prev_dt <= 3 or abs(vx_out) < 10.0):
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
        else:  # 0度
            if vx_in * vx_out < 0 and abs(vx_in) > 6.0 and abs(vx_out) > 6.0:
                continue
            if abs(vx_out - vx_in) > 35.0 and abs(vy_out) > 50.0:
                continue

        is_landing = False
        score = 0.0

        # Mode 1: Standard or Flat-top Local Maximum in Y (falling -> rising)
        eff_fall = max(vy_in, vy_in2, prev_vy if prev_dt <= 2 else vy_in)
        eff_rise = -min(vy_out, vy_out2, next_vy if dt_out == 1 else vy_out)
        min_sum = 6.5 if angle == "90度" else 8.0
        if (y >= yp - 4.0 and y >= yn - 2.8) and eff_fall >= 2.0 and eff_rise >= 1.2:
            if vy_in >= -4.0 and vy_out <= 2.2 and (eff_fall + eff_rise) >= min_sum:
                if dt_out == 1 or vy_out <= -4.0:
                    if abs(vx_out - vx_in) <= 32.0 or angle == "90度" or (vx_in * vx_out > 0 and vy_in >= 30.0):
                        is_landing = True
                        score = vy_in - vy_out

        # Mode 2: Far/Mid-table bounce in 0° and 45° (ball moving up on screen vy <= 2, decelerating under gravity, then sharp upward jump)
        if not is_landing and angle in ("0度", "45度"):
            best_vy_out = min(vy_out, vy_out2)
            min_prev_vy = min(prev_vy, vy_in2) if prev_dt <= 2 else prev_vy
            if dt_in == 1 and prev_dt <= 2 and prev_vx * vx_in > 0:
                if min_prev_vy <= -1.8 and -8.0 <= vy_in <= 3.0 and (vy_in - prev_vy) >= -1.5:
                    if best_vy_out <= -11.0 and (vy_in - best_vy_out) >= 12.0:
                        if abs(vx_out - vx_in) <= 18.0 and vx_in * vx_out > 0:
                            is_landing = True
                            score = (vy_in - best_vy_out)
            elif dt_in == 1 and prev_dt > 2 and prev_vx * vx_in > 0 and -7.0 <= vy_in <= 1.0 and vy_out <= -12.0 and (vy_in - vy_out) >= 8.0:
                if abs(vx_out - vx_in) <= 6.0 and vx_in * vx_out > 0:
                    is_landing = True
                    score = (vy_in - vy_out)

        # Mode 3: Near-table fast bounce (ball falling fast vy_in >> 0, then sudden strong deceleration even if vy_out >= 0)
        if not is_landing:
            if prev_dt <= 2 and prev_vy >= 10.0 and abs(vy_in - prev_vy) <= 30.0 and math.hypot(prev_vx, prev_vy) <= 150.0:
                peak_fall = max(vy_in, prev_vy)
                if peak_fall >= 20.0 and vy_in >= 10.0:
                    drop1 = vy_in - vy_out
                    drop2 = peak_fall - vy_out
                    if (drop1 >= 13.0 or drop2 >= 24.0) and -15.0 <= vy_out <= 16.0 and vy_out <= 0.55 * peak_fall:
                        if vy_out2 <= 0.60 * peak_fall and abs(vx_out - vx_in) <= 22.0 and vx_in * vx_out >= -5.0:
                            is_landing = True
                            score = max(drop1, drop2)

        if is_landing:
            candidates.append((fid, float(x), float(y), score))

    # Temporal State Management:
    # 1. Consecutive frame (fid - cluster_start == 1): flat-top bounce straddling 2 frames -> keep larger instantaneous impulse!
    # 2. Within 2..7 frames after a confirmed table bounce: refractory window (paddle strike / block) -> suppress!
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

if __name__ == '__main__':
    from test_algo import eval_preds
    new_preds = {}
    for vid, info in sorted(data.items()):
        new_preds[vid] = detect_landings(info)
    print("=== Improved Multi-Angle Physics + ROI + Clean State ===")
    eval_preds(new_preds)
