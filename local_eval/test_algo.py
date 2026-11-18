import json, sys, math
import numpy as np
from collections import defaultdict
from scipy.optimize import linear_sum_assignment

sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open(r'D:\pingpang源文件汇总\participant\output\public_trajs.json', encoding='utf-8'))

def eval_preds(preds_by_vid):
    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    details = []
    for vid, info in data.items():
        angle = info['angle']
        preds = preds_by_vid.get(vid, [])
        gts = info['gts']
        valid_gts = [g for g in gts if g.get("valid", True)]
        ignore_gts = [g for g in gts if not g.get("valid", True)]
        st = stats[angle]

        if not preds:
            st["fn"] += len(valid_gts)
            for g in valid_gts:
                details.append(f"  [FN] {vid} ({angle}) f={g['frame_id']} ({g['x']:.1f}, {g['y']:.1f})")
            continue

        cost_matrix = np.full((len(preds), len(valid_gts)), 1e6)
        for i, p in enumerate(preds):
            for j, g in enumerate(valid_gts):
                if abs(p["frame_id"] - g["frame_id"]) <= 1:
                    d = math.hypot(p["x"] - g["x"], p["y"] - g["y"])
                    if d <= 50.0:
                        cost_matrix[i, j] = d

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matched_preds = set()
        matched_gts = set()
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < 1e5:
                matched_preds.add(r)
                matched_gts.add(c)
                st["tp"] += 1

        st["fn"] += (len(valid_gts) - len(matched_gts))
        for j, g in enumerate(valid_gts):
            if j not in matched_gts:
                details.append(f"  [FN] {vid} ({angle}) f={g['frame_id']} ({g['x']:.1f}, {g['y']:.1f})")

        for i, p in enumerate(preds):
            if i not in matched_preds:
                hit_ignore = any(
                    abs(p["frame_id"] - ig["frame_id"]) <= 1
                    and math.hypot(p["x"] - ig["x"], p["y"] - ig["y"]) <= 50.0
                    for ig in ignore_gts
                )
                if not hit_ignore:
                    st["fp"] += 1
                    details.append(f"  [FP] {vid} ({angle}) f={p['frame_id']} ({p['x']:.1f}, {p['y']:.1f})")

    f1s = {}
    for angle in ["0度", "45度", "90度"]:
        s = stats[angle]
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        f1s[angle] = f1
        print(f"[{angle}] P={prec:.4f} R={rec:.4f} F1={f1:.4f} (TP={tp}, FP={fp}, FN={fn})")
    macro = sum(f1s.values()) / 3.0
    score = sum(f1s.values()) * 25.0
    print(f"Macro F1: {macro:.4f} | Score: {score:.2f} / 75.0")
    for d in details:
        print(d)
    return macro, score

if __name__ == '__main__':
    # Test baseline first
    base_preds = {}
    for line in open(r'D:\pingpang源文件汇总\participant\output\pingpang\predictions.jsonl', encoding='utf-8'):
        if line.strip():
            r = json.loads(line)
            base_preds.setdefault(r['video_id'], []).append(r)
    print("=== Baseline ===")
    eval_preds(base_preds)
