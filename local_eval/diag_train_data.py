import glob, json, math, os
from collections import defaultdict
import cv2
import numpy as np
import onnxruntime as ort

IN_H, IN_W = 288, 512
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

def normalize(frame_rgb):
    x = cv2.resize(frame_rgb, (IN_W, IN_H), interpolation=cv2.INTER_LINEAR)
    x = x.astype(np.float32) / 255.0
    x = (x - _MEAN) / _STD
    return np.ascontiguousarray(x.transpose(2, 0, 1))

def decode_peak(heat, orig_w, orig_h, th=0.30):
    max_val = float(heat.max())
    if max_val <= th:
        return None
    py, px = np.unravel_index(int(np.argmax(heat)), heat.shape)
    y0, y1 = max(0, py - 4), min(IN_H, py + 5)
    x0, x1 = max(0, px - 4), min(IN_W, px + 5)
    patch = heat[y0:y1, x0:x1]
    pmask = patch > th
    if not pmask.any():
        return None
    pys, pxs = np.nonzero(pmask)
    pw = patch[pys, pxs].astype(np.float64)
    ptotal = pw.sum()
    lcx = float(((pxs + x0) * pw).sum() / ptotal) * orig_w / IN_W
    lcy = float(((pys + y0) * pw).sum() / ptotal) * orig_h / IN_H
    return {"x": lcx, "y": lcy, "conf": max_val}

def extract_gt_bounces(ann_data):
    """From human-annotated per-frame ball and table boxes, find clear physical table bounce frames."""
    w = ann_data["frame_width"]
    h = ann_data["frame_height"]
    sx = 1920.0 / w
    sy = 1080.0 / h

    ball_pts = {}
    table_boxes = []
    for fr in ann_data["frames"]:
        fid = fr["frame_id"]
        for a in fr["annotations"]:
            if a["label"] == "ball" and a["bbox_xyxy"]:
                b = a["bbox_xyxy"][0]
                cx = 0.5 * (b[0] + b[2]) * sx
                cy = 0.5 * (b[1] + b[3]) * sy
                ball_pts[fid] = (cx, cy)
            elif a["label"] == "table" and a["bbox_xyxy"]:
                t = a["bbox_xyxy"][0]
                table_boxes.append((t[0] * sx, t[1] * sy, t[2] * sx, t[3] * sy))

    if not table_boxes or len(ball_pts) < 5:
        return [], ball_pts, None

    # Median table bbox in 1920x1080 space
    tx1 = float(np.median([t[0] for t in table_boxes]))
    ty1 = float(np.median([t[1] for t in table_boxes]))
    tx2 = float(np.median([t[2] for t in table_boxes]))
    ty2 = float(np.median([t[3] for t in table_boxes]))

    fids = sorted(ball_pts.keys())
    bounces = []
    for i in range(1, len(fids) - 1):
        f_prev, fid, f_next = fids[i - 1], fids[i], fids[i + 1]
        if fid - f_prev > 2 or f_next - fid > 2:
            continue
        xp, yp = ball_pts[f_prev]
        x, y = ball_pts[fid]
        xn, yn = ball_pts[f_next]
        # Must be near/above the table surface
        if not (tx1 - 30 <= x <= tx2 + 30 and ty1 - 40 <= y <= ty2 + 20):
            continue
        vx_in = (x - xp) / (fid - f_prev)
        vy_in = (y - yp) / (fid - f_prev)
        vx_out = (xn - x) / (f_next - fid)
        vy_out = (yn - y) / (f_next - fid)
        # Clear bounce: falling then rising, with continuous horizontal direction
        if vy_in >= 2.0 and vy_out <= -2.0 and (vy_in - vy_out) >= 8.0:
            if vx_in * vx_out > 0 and abs(vx_out - vx_in) <= 25.0:
                if not bounces or (fid - bounces[-1][0]) >= 8:
                    bounces.append((fid, x, y))
    return bounces, ball_pts, (tx1, ty1, tx2, ty2)

def evaluate_onnx_on_holdout(onnx_path, holdout_jsons):
    sess = ort.InferenceSession(str(onnx_path), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    infer = lambda x: sess.run(None, {in_name: x})[0]
    blank = normalize(np.zeros((IN_H, IN_W, 3), np.uint8))

    tot_ball = 0
    ch1_hit_07 = 0
    fused_hit = 0
    tot_bounce = 0
    ch1_bounce_hit = 0
    fused_bounce_hit = 0
    err_ch1 = []
    err_fused = []

    base_tp = base_fp = base_fn = 0
    v2_tp = v2_fp = v2_fn = 0

    import sys
    sys.path.insert(0, "/participant/pingpang")
    from participant.solution import Solution, ROI_BY_ANGLE
    from scipy.optimize import linear_sum_assignment

    for jpath in holdout_jsons:
        ann = json.load(open(jpath, encoding="utf-8"))
        bounces, ball_pts, tbox = extract_gt_bounces(ann)
        bounce_set = {b[0] for b in bounces}
        vpath = os.path.join("/data_pp_train", ann["video_path"])
        w, h = ann["frame_width"], ann["frame_height"]
        sx, sy = 1920.0 / w, 1080.0 / h

        cap = cv2.VideoCapture(vpath)
        buf = [blank, blank]
        heat_accum = {}
        ch1_dets = {}
        fid = 0
        while True:
            ret, bgr = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            buf.append(normalize(rgb))
            buf = buf[-3:]
            inp = np.concatenate(buf, axis=0)[None]
            out = infer(inp)[0]
            for c_idx, tfid in enumerate((fid - 2, fid - 1, fid)):
                if tfid >= 0:
                    heat_accum.setdefault(tfid, []).append(out[c_idx])
            if fid - 1 >= 0:
                ch1_dets[fid - 1] = decode_peak(out[1], 1920, 1080, th=0.30)
            fid += 1
        cap.release()
        n_frames = fid

        raw_v2 = []
        raw_base = []
        for tfid in range(n_frames):
            c1 = ch1_dets.get(tfid)
            if c1 and c1["conf"] >= 0.70:
                raw_base.append((tfid, c1["x"], c1["y"]))
            hlist = heat_accum.get(tfid, [])
            if hlist:
                fm = decode_peak(np.max(hlist, axis=0), 1920, 1080, th=0.30)
                fa = decode_peak(np.mean(hlist, axis=0), 1920, 1080, th=0.25)
                det = None
                if c1 and c1["conf"] >= 0.65:
                    det = c1
                elif fm and fm["conf"] >= 0.60:
                    det = fm
                elif c1 and fa and c1["conf"] >= 0.50 and fa["conf"] >= 0.45:
                    det = c1
                if det:
                    raw_v2.append((tfid, det["x"], det["y"], det["conf"]))

        # Evaluate per-frame recall against GT ball_pts
        for tfid, (gx, gy) in ball_pts.items():
            tot_ball += 1
            is_b = tfid in bounce_set
            if is_b:
                tot_bounce += 1

            c1 = ch1_dets.get(tfid)
            if c1 and c1["conf"] >= 0.70 and math.hypot(c1["x"] - gx, c1["y"] - gy) <= 20.0:
                ch1_hit_07 += 1
                err_ch1.append(math.hypot(c1["x"] - gx, c1["y"] - gy))
                if is_b:
                    ch1_bounce_hit += 1

            hlist = heat_accum.get(tfid, [])
            if hlist:
                fm = decode_peak(np.max(hlist, axis=0), 1920, 1080, th=0.30)
                fa = decode_peak(np.mean(hlist, axis=0), 1920, 1080, th=0.25)
                det = None
                if c1 and c1["conf"] >= 0.65:
                    det = c1
                elif fm and fm["conf"] >= 0.60:
                    det = fm
                elif c1 and fa and c1["conf"] >= 0.50 and fa["conf"] >= 0.45:
                    det = c1
                if det and math.hypot(det["x"] - gx, det["y"] - gy) <= 20.0:
                    fused_hit += 1
                    err_fused.append(math.hypot(det["x"] - gx, det["y"] - gy))
                    if is_b:
                        fused_bounce_hit += 1

        # Evaluate End-to-End Bounce Detection on Holdout video if table box and bounces exist
        if tbox and bounces:
            tx1, ty1, tx2, ty2 = tbox
            rx0, rx1 = (tx1 - 30.0) / 1920.0, (tx2 + 30.0) / 1920.0
            ry0, ry1 = (ty1 - 40.0) / 1080.0, (ty2 + 20.0) / 1080.0

            # 1. Baseline v0 bounce detector (3-pt local y-max)
            preds_base = []
            for i in range(1, len(raw_base) - 1):
                f0, x0, y0 = raw_base[i - 1]
                f1, x1, y1 = raw_base[i]
                f2, x2, y2 = raw_base[i + 1]
                if (f1 - f0) <= 3 and (f2 - f1) <= 3:
                    if (tx1 - 30 <= x1 <= tx2 + 30) and (ty1 - 40 <= y1 <= ty2 + 20):
                        if y1 >= y0 and y1 > y2 and (not preds_base or f1 - preds_base[-1][0] >= 3):
                            preds_base.append((f1, x1, y1))

            # 2. v2 Solution bounce detector
            sol = Solution()
            sol.raw_traj = raw_v2
            sol.width = 1920
            sol.height = 1080
            sol.n_frames = n_frames
            sol.angle = "holdout"
            ROI_BY_ANGLE["holdout"] = (rx0, rx1, ry0, ry1)
            preds_v2 = [(l.frame_id, l.x, l.y) for l in sol._detect_landings()]

            def match_events(preds, gts):
                if not preds:
                    return 0, 0, len(gts)
                cm = np.full((len(preds), len(gts)), 1e6)
                for pi, (pf, px, py) in enumerate(preds):
                    for gi, (gf, gx, gy) in enumerate(gts):
                        if abs(pf - gf) <= 1:
                            d = math.hypot(px - gx, py - gy)
                            if d <= 48.0:
                                cm[pi, gi] = d
                ri, ci = linear_sum_assignment(cm)
                tp = sum(1 for r, c in zip(ri, ci) if cm[r, c] < 1e5)
                return tp, len(preds) - tp, len(gts) - tp

            tp0, fp0, fn0 = match_events(preds_base, bounces)
            base_tp += tp0; base_fp += fp0; base_fn += fn0
            tp2, fp2, fn2 = match_events(preds_v2, bounces)
            v2_tp += tp2; v2_fp += fp2; v2_fn += fn2

    print(f"Holdout videos: {len(holdout_jsons)} | GT ball frames: {tot_ball} | GT bounce apex frames: {tot_bounce}")
    print(f"Baseline ch1 (conf>=0.70) | Overall Recall: {ch1_hit_07/max(1,tot_ball):.4f} ({ch1_hit_07}/{tot_ball}) | Bounce Recall: {ch1_bounce_hit/max(1,tot_bounce):.4f} ({ch1_bounce_hit}/{tot_bounce}) | Mean Err: {np.mean(err_ch1):.2f}px")
    print(f"3-Ch Fused (v2 detector)  | Overall Recall: {fused_hit/max(1,tot_ball):.4f} ({fused_hit}/{tot_ball}) | Bounce Recall: {fused_bounce_hit/max(1,tot_bounce):.4f} ({fused_bounce_hit}/{tot_bounce}) | Mean Err: {np.mean(err_fused):.2f}px")
    p0 = base_tp / max(1, base_tp + base_fp); r0 = base_tp / max(1, base_tp + base_fn); f1_0 = 2*p0*r0/max(1e-9, p0+r0)
    p2 = v2_tp / max(1, v2_tp + v2_fp); r2 = v2_tp / max(1, v2_tp + v2_fn); f1_2 = 2*p2*r2/max(1e-9, p2+r2)
    print(f"[Holdout E2E Bounce F1] Baseline v0: P={p0:.4f} R={r0:.4f} F1={f1_0:.4f} (TP={base_tp}, FP={base_fp}, FN={base_fn})")
    print(f"[Holdout E2E Bounce F1] Our v2 Sol : P={p2:.4f} R={r2:.4f} F1={f1_2:.4f} (TP={v2_tp}, FP={v2_fp}, FN={v2_fn})")

if __name__ == "__main__":
    import sys
    onnx_p = sys.argv[1] if len(sys.argv) > 1 else "/participant/pingpang/participant/weights/ball.onnx"
    holdout_jsons = sorted(glob.glob("/data_pp_train/annotations/2[0-4]/*.json"))
    print(f"=== Evaluating {onnx_p} on 29 Unseen Holdout Videos (20..24) ===")
    evaluate_onnx_on_holdout(onnx_p, holdout_jsons)
