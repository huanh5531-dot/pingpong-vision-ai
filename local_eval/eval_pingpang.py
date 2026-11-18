#!/usr/bin/env python3
"""乒乓球落点检测：官方规则验证集评估脚本 (计算 0度/45度/90度 F1 及算法效果分)"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment


def evaluate_pingpang(
    pred_path: str | Path,
    gt_path: str | Path,
    manifest_path: str | Path,
) -> dict:
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    video_angles = {v["video_id"]: v["angle"] for v in manifest["videos"]}

    gt_by_vid = defaultdict(list)
    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                gt_by_vid[rec["video_id"]].append(rec)

    pred_by_vid = defaultdict(list)
    with open(pred_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                pred_by_vid[rec["video_id"]].append(rec)

    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "gt_valid": 0, "pred": 0})

    for vid, angle in video_angles.items():
        preds = pred_by_vid[vid]
        gts = gt_by_vid[vid]

        valid_gts = [g for g in gts if g.get("valid", True)]
        ignore_gts = [g for g in gts if not g.get("valid", True)]

        st = stats[angle]
        st["gt_valid"] += len(valid_gts)
        st["pred"] += len(preds)

        if not preds:
            st["fn"] += len(valid_gts)
            continue
        if not valid_gts:
            for p in preds:
                hit_ignore = any(
                    abs(p["frame_id"] - ig["frame_id"]) <= 1
                    and np.hypot(p["x"] - ig["x"], p["y"] - ig["y"]) <= 50.0
                    for ig in ignore_gts
                )
                if not hit_ignore:
                    st["fp"] += 1
            continue

        cost_matrix = np.full((len(preds), len(valid_gts)), 1e6)
        for i, p in enumerate(preds):
            for j, g in enumerate(valid_gts):
                if abs(p["frame_id"] - g["frame_id"]) <= 1:
                    d = np.hypot(p["x"] - g["x"], p["y"] - g["y"])
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

        for i, p in enumerate(preds):
            if i not in matched_preds:
                hit_ignore = any(
                    abs(p["frame_id"] - ig["frame_id"]) <= 1
                    and np.hypot(p["x"] - ig["x"], p["y"] - ig["y"]) <= 50.0
                    for ig in ignore_gts
                )
                if not hit_ignore:
                    st["fp"] += 1

    results = {}
    f1_list = []
    print("=" * 60)
    print("             乒乓球落点检测 · 验证集评测报告")
    print("=" * 60)
    for angle in ["0度", "45度", "90度"]:
        s = stats[angle]
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_list.append(f1)
        results[angle] = {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
        print(f"[{angle:^6}] Precision: {prec:.4f} | Recall: {rec:.4f} | F1: {f1:.4f} (TP={tp}, FP={fp}, FN={fn})")

    macro_f1 = sum(f1_list) / len(f1_list)
    accuracy_score = sum(f1_list) * 25.0
    print("-" * 60)
    print(f"Macro F1: {macro_f1:.4f} (官方参考基线: ~0.604)")
    print(f"算法效果分 (满分75): {accuracy_score:.2f} / 75.0")
    print("=" * 60)
    return results


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    base = Path(__file__).resolve().parent.parent / "participant"
    if not base.exists():
        base = Path("/participant")
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred", default=str(base / "output/pingpang/predictions.jsonl"))
    parser.add_argument("--gt", default=str(base / "pingpang/public_data/gt_public.jsonl"))
    parser.add_argument("--manifest", default=str(base / "pingpang/public_data/manifest.json"))
    args = parser.parse_args()

    evaluate_pingpang(args.pred, args.gt, args.manifest)
