# -*- coding: utf-8 -*-
"""
Evaluate /tmp/ball_finetuned.onnx on the 15 public_data videos using the v2 Solution pipeline.
"""
import sys
import json
import math
import glob
import os
from collections import defaultdict
import cv2
import numpy as np
import onnxruntime as ort
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, "/participant/pingpang")
from core.types import VideoMeta
from participant.ball_detector import BallDetector
from participant.solution import Solution


def eval_onnx_on_public(onnx_path: str):
    sess = ort.InferenceSession(onnx_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    infer_fn = lambda x: sess.run(None, {in_name: x})[0]

    sol = Solution()
    sol.det = BallDetector(infer_fn, onnx_path)
    sol.raw_traj = []

    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    in_root = "/participant/input/pingpang"

    for angle in ["0度", "45度", "90度"]:
        angle_dir = os.path.join(in_root, angle)
        mp4s = sorted(glob.glob(os.path.join(angle_dir, "*.mp4")))
        for mp4 in mp4s:
            jpath = mp4.replace(".mp4", ".json")
            with open(jpath, "r", encoding="utf-8") as f:
                gt_data = json.load(f)

            cap = cv2.VideoCapture(mp4)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 60.0)

            vmeta = VideoMeta(
                video_id=os.path.basename(mp4).replace(".mp4", ""),
                angle=angle,
                fps=fps,
                width=w,
                height=h,
                n_frames=n_frames,
            )
            sol.reset(vmeta)
            fid = 0
            while True:
                ret, bgr = cap.read()
                if not ret:
                    break
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                sol.process_frame(rgb, {"frame_id": fid, "width": w, "height": h})
                fid += 1
            cap.release()
            preds = sol.finish_video(vmeta)

            gts = gt_data.get("landing_frames", [])
            valid_gts = [g for g in gts if g.get("valid", True)]
            ignore_gts = [g for g in gts if not g.get("valid", True)]
            tau_s = 0.025 * w
            st = stats[angle]

            if not preds:
                st["fn"] += len(valid_gts)
                continue
            cm = np.full((len(preds), len(valid_gts)), 1e6)
            for i, p in enumerate(preds):
                for j, g in enumerate(valid_gts):
                    if abs(p.frame_id - g["frame_id"]) <= 1:
                        d = math.hypot(p.x - g["x"], p.y - g["y"])
                        if d <= tau_s:
                            cm[i, j] = d
            ri, ci = linear_sum_assignment(cm)
            mp, mg = set(), set()
            for r, c in zip(ri, ci):
                if cm[r, c] < 1e5:
                    mp.add(r)
                    mg.add(c)
                    st["tp"] += 1
            st["fn"] += len(valid_gts) - len(mg)
            for i, p in enumerate(preds):
                if i not in mp:
                    if not any(
                        abs(p.frame_id - ig["frame_id"]) <= 1
                        and math.hypot(p.x - ig["x"], p.y - ig["y"]) <= tau_s
                        for ig in ignore_gts
                    ):
                        st["fp"] += 1

    f1s = {}
    tot_tp = tot_fp = tot_fn = 0
    for angle in ["0度", "45度", "90度"]:
        s = stats[angle]
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        tot_tp += tp
        tot_fp += fp
        tot_fn += fn
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        f1s[angle] = f1
        print(f"[ {angle:4s} ] Precision: {prec:.4f} | Recall: {rec:.4f} | F1: {f1:.4f} (TP={tp}, FP={fp}, FN={fn})")
    macro = sum(f1s.values()) / 3.0
    print(f"Macro F1: {macro:.4f} | Accuracy Score: {macro * 75.0:.2f} / 75.0 (Total TP={tot_tp}, FP={tot_fp}, FN={tot_fn})")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ball_finetuned.onnx"
    print(f"=== Evaluating {p} on Public Validation Set (15 videos) ===")
    eval_onnx_on_public(p)
