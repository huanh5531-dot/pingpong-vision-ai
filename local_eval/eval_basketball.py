#!/usr/bin/env python3
"""篮球球员跟踪：验证集评估脚本 (计算 MOTA, IDF1, IDSW 及算法效果分)"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment


def box_iou(box1: list[float], box2: list[float]) -> float:
    # box: [x1, y1, x2, y2]
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    boxBArea = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])

    denom = boxAArea + boxBArea - interArea
    return interArea / denom if denom > 0 else 0.0


def evaluate_basketball(
    pred_path: str | Path,
    gt_path: str | Path,
    frame_cap: int = 15,
) -> dict:
    gt_by_vf = defaultdict(list)
    gt_tracks = set()
    total_gt = 0

    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                key = (rec["video_id"], rec["frame_id"])
                gt_by_vf[key].append(rec)
                gt_tracks.add((rec["video_id"], rec["track_id"]))
                total_gt += 1

    pred_by_vf = defaultdict(list)
    pred_tracks = set()
    with open(pred_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                key = (rec["video_id"], rec["frame_id"])
                pred_by_vf[key].append(rec)
                pred_tracks.add((rec["video_id"], rec["track_id"]))

    all_keys = sorted(set(gt_by_vf.keys()) | set(pred_by_vf.keys()))

    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_idsw = 0

    # For IDF1: track overlap counts
    # (gt_vid, gt_tid, pr_tid) -> match count
    track_matches = defaultdict(int)
    gt_track_len = defaultdict(int)
    pr_track_len = defaultdict(int)

    # For MOTA IDSW tracking: gt_id -> last matched pred_id
    last_match = {}

    for vid, fid in all_keys:
        gts = gt_by_vf.get((vid, fid), [])
        preds = pred_by_vf.get((vid, fid), [])

        # Cap predictions to frame_cap
        valid_preds = preds[:frame_cap]
        total_fp += max(0, len(preds) - frame_cap)

        for g in gts:
            gt_track_len[(vid, g["track_id"])] += 1
        for p in valid_preds:
            pr_track_len[(vid, p["track_id"])] += 1

        if not gts:
            total_fp += len(valid_preds)
            continue
        if not valid_preds:
            total_fn += len(gts)
            continue

        cost_matrix = np.full((len(gts), len(valid_preds)), 1e6)
        for i, g in enumerate(gts):
            for j, p in enumerate(valid_preds):
                iou = box_iou(g["bbox"], p["bbox"])
                if iou >= 0.5:
                    cost_matrix[i, j] = 1.0 - iou

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matched_g = set()
        matched_p = set()

        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < 0.51:
                matched_g.add(r)
                matched_p.add(c)
                total_tp += 1

                gt_tid = gts[r]["track_id"]
                pr_tid = valid_preds[c]["track_id"]
                track_matches[(vid, gt_tid, pr_tid)] += 1

                # Check IDSW
                if (vid, gt_tid) in last_match and last_match[(vid, gt_tid)] != pr_tid:
                    total_idsw += 1
                last_match[(vid, gt_tid)] = pr_tid

        total_fn += len(gts) - len(matched_g)
        total_fp += len(valid_preds) - len(matched_p)

    mota = 1.0 - (total_fn + total_fp + total_idsw) / total_gt if total_gt > 0 else 0.0

    # Optimal bipartite matching between GT tracks and Pred tracks for IDF1
    # For each video:
    all_vids = {v for v, f in all_keys}
    idtp = 0
    idfp = 0
    idfn = 0

    for v in all_vids:
        v_gts = [tid for (vid, tid) in gt_tracks if vid == v]
        v_prs = [tid for (vid, tid) in pred_tracks if vid == v]

        if not v_gts:
            idfp += sum(pr_track_len[(v, p)] for p in v_prs)
            continue
        if not v_prs:
            idfn += sum(gt_track_len[(v, g)] for g in v_gts)
            continue

        cost = np.zeros((len(v_gts), len(v_prs)))
        for i, g in enumerate(v_gts):
            for j, p in enumerate(v_prs):
                cost[i, j] = -track_matches.get((v, g, p), 0)

        r_ind, c_ind = linear_sum_assignment(cost)
        v_idtp = 0
        for r, c in zip(r_ind, c_ind):
            v_idtp += track_matches.get((v, v_gts[r], v_prs[c]), 0)

        idtp += v_idtp
        v_gt_total = sum(gt_track_len[(v, g)] for g in v_gts)
        v_pr_total = sum(pr_track_len[(v, p)] for p in v_prs)
        idfn += (v_gt_total - v_idtp)
        idfp += (v_pr_total - v_idtp)

    idf1 = (2 * idtp) / (2 * idtp + idfp + idfn) if (2 * idtp + idfp + idfn) > 0 else 0.0
    score = (0.6 * idf1 + 0.4 * mota) * 75.0

    print("=" * 60)
    print("             篮球球员跟踪 · 验证集评测报告")
    print("=" * 60)
    print(f"GT 框数: {total_gt} | TP: {total_tp} | FP: {total_fp} | FN: {total_fn} | IDSW: {total_idsw}")
    print(f"MOTA: {mota:.4f} (官方参考基线: ~0.53)")
    print(f"IDF1: {idf1:.4f} (官方参考基线: ~0.34)")
    print("-" * 60)
    print(f"算法效果分 (0.6*IDF1 + 0.4*MOTA) * 75: {score:.2f} / 75.0")
    print("=" * 60)
    return {"mota": mota, "idf1": idf1, "score": score}


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
    parser.add_argument("--pred", default=str(base / "output/basketball/predictions.jsonl"))
    parser.add_argument("--gt", default=str(base / "basketball/public_data/gt_public.jsonl"))
    args = parser.parse_args()

    evaluate_basketball(args.pred, args.gt)
