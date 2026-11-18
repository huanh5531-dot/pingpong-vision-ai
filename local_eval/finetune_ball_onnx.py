# -*- coding: utf-8 -*-
"""
In-Place Fine-Tuning of ball.onnx on pp_train_data (Tune Split: folders 01..19 & 22..23)
Evaluated strictly on Unseen Holdout Split (folders 20..21 & 24) and Public Data.

Uses ONNXRuntime-GPU (CUDAExecutionProvider) to run the frozen HRNet backbone at high speed
and caches intermediate Stage-4 multi-resolution features (b0_in, b1, b2, b3), then
fine-tunes the final Stage-4 high-res residual block + multi-scale fusion + 3-channel output head
in PyTorch with Focal Heatmap Loss + L2 Weight Anchoring.
"""
import os
import json
import glob
import time
import copy
import cv2
import numpy as np
import onnx
from onnx import helper, TensorProto, numpy_helper
import onnxruntime as ort
import torch
import torch.nn as nn
import torch.nn.functional as F

TRAIN_ROOT = "/data_pp_train"
ORIG_ONNX = "/participant/pingpang/participant/weights/ball.onnx"
OUT_ONNX = "/tmp/ball_finetuned.onnx"

FEAT_NAMES = [
    "/model/stage4/stage4.0/branches.0/branches.0.0/relu_1/Relu_output_0",
    "/model/stage4/stage4.0/branches.1/branches.1.1/relu_1/Relu_output_0",
    "/model/stage4/stage4.0/branches.2/branches.2.1/relu_1/Relu_output_0",
    "/model/stage4/stage4.0/branches.3/branches.3.1/relu_1/Relu_output_0",
]


def make_feature_extractor_session(onnx_path: str):
    model = onnx.load(onnx_path)
    existing_outs = {o.name for o in model.graph.output}
    for name in FEAT_NAMES:
        if name not in existing_outs:
            vi = helper.make_tensor_value_info(name, TensorProto.FLOAT, None)
            model.graph.output.append(vi)
    providers = [
        p for p in ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if p in ort.get_available_providers()
    ]
    return ort.InferenceSession(model.SerializeToString(), providers=providers)


class Stage4HeadModule(nn.Module):
    """Exact PyTorch replica of HRNet Stage-4 Branch-0.1 + Multi-Scale Fusion + Final Head."""

    def __init__(self, onnx_model: onnx.ModelProto):
        super().__init__()
        inits = {
            t.name: numpy_helper.to_array(t).copy()
            for t in onnx_model.graph.initializer
        }
        self.param_names = [
            "onnx::Conv_1365",
            "onnx::Conv_1366",
            "onnx::Conv_1368",
            "onnx::Conv_1369",
            "onnx::MatMul_1463",
            "onnx::MatMul_1464",
            "onnx::Conv_1407",
            "onnx::Conv_1408",
            "onnx::Conv_1410",
            "onnx::Conv_1411",
            "onnx::Conv_1413",
            "onnx::Conv_1414",
            "model.final_layers.0.weight",
            "model.final_layers.0.bias",
        ]
        self.weights = nn.ParameterDict()
        self.orig_weights = {}
        for k in self.param_names:
            safe_k = k.replace("::", "__").replace(".", "_")
            arr = torch.from_numpy(inits[k].astype(np.float32))
            self.weights[safe_k] = nn.Parameter(arr.clone())
            self.orig_weights[safe_k] = arr.clone()

    def _w(self, name: str) -> torch.Tensor:
        return self.weights[name.replace("::", "__").replace(".", "_")]

    def forward(self, b0_in, b1, b2, b3):
        # branches.0.1
        x = F.conv2d(b0_in, self._w("onnx::Conv_1365"), self._w("onnx::Conv_1366"), stride=1, padding=1)
        x = F.relu(x)
        conv2 = F.conv2d(x, self._w("onnx::Conv_1368"), self._w("onnx::Conv_1369"), stride=1, padding=1)
        # SE block
        se = conv2.mean(dim=(2, 3))  # (B, 16)
        se = F.relu(torch.matmul(se, self._w("onnx::MatMul_1463")))
        se = torch.sigmoid(torch.matmul(se, self._w("onnx::MatMul_1464")))
        se = se.unsqueeze(-1).unsqueeze(-1)
        b0 = F.relu(conv2 * se + b0_in)

        # fuse_layers
        f1 = F.conv2d(b1, self._w("onnx::Conv_1407"), self._w("onnx::Conv_1408"), stride=1, padding=0)
        f1 = F.interpolate(f1, scale_factor=2.0, mode="nearest")

        f2 = F.conv2d(b2, self._w("onnx::Conv_1410"), self._w("onnx::Conv_1411"), stride=1, padding=0)
        f2 = F.interpolate(f2, scale_factor=4.0, mode="nearest")

        f3 = F.conv2d(b3, self._w("onnx::Conv_1413"), self._w("onnx::Conv_1414"), stride=1, padding=0)
        f3 = F.interpolate(f3, scale_factor=8.0, mode="nearest")

        fused = F.relu(b0 + f1 + f2 + f3)
        logits = F.conv2d(
            fused,
            self._w("model.final_layers.0.weight"),
            self._w("model.final_layers.0.bias"),
            stride=1,
            padding=0,
        )
        return torch.sigmoid(logits)

    def anchor_loss(self) -> torch.Tensor:
        loss = 0.0
        for k, p in self.weights.items():
            loss = loss + torch.sum((p - self.orig_weights[k]) ** 2)
        return loss

    def export_to_onnx(self, onnx_model: onnx.ModelProto, out_path: str):
        out_model = copy.deepcopy(onnx_model)
        init_map = {t.name: t for t in out_model.graph.initializer}
        for k in self.param_names:
            safe_k = k.replace("::", "__").replace(".", "_")
            new_arr = self.weights[safe_k].detach().cpu().numpy().astype(np.float32)
            new_tensor = numpy_helper.from_array(new_arr, name=k)
            init_map[k].CopyFrom(new_tensor)
        onnx.save(out_model, out_path)


def normalize_frame(frame_bgr: np.ndarray) -> np.ndarray:
    resized = cv2.resize(frame_bgr, (512, 288), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    norm = (rgb - mean) / std
    return np.transpose(norm, (2, 0, 1))


def make_disk_target_and_weight(cx_512: float, cy_288: float, orig_hm: np.ndarray):
    """
    Margin-calibrated target masks matching ball.onnx's native 5x5 plateau:
    - Positive core: r <= 2.0px (d2 <= 4.0)
    - Safe background zone: r > 6.0px (d2 > 36.0)
    """
    yy, xx = np.meshgrid(
        np.arange(288, dtype=np.float32),
        np.arange(512, dtype=np.float32),
        indexing="ij",
    )
    d2 = (xx - cx_512) ** 2 + (yy - cy_288) ** 2
    pos_mask = (d2 <= 4.0).astype(np.float32)
    neg_mask = ((d2 > 36.0) & (orig_hm > 0.22)).astype(np.float32)
    return pos_mask, neg_mask


def get_ball_center(shapes, width: int, height: int):
    for s in shapes:
        if s.get("label") == "ball":
            pts = s.get("points", [])
            if len(pts) == 2:
                x1, y1 = pts[0]
                x2, y2 = pts[1]
                cx = 0.5 * (x1 + x2) * (512.0 / width)
                cy = 0.5 * (y1 + y2) * (288.0 / height)
                return (cx, cy)
    return None


def weighted_bce_loss(pred: torch.Tensor, pos_mask: torch.Tensor, neg_mask: torch.Tensor) -> torch.Tensor:
    """Zero-drift Margin Loss: only penalizes weak true balls (<0.82) and hard background peaks (>0.22)."""
    pos_err = F.relu(0.82 - pred) ** 2 * pos_mask
    neg_err = F.relu(pred - 0.22) ** 2 * neg_mask
    pos_term = pos_err.sum() / pos_mask.sum().clamp(min=1.0)
    neg_term = neg_err.sum() / neg_mask.sum().clamp(min=1.0)
    return pos_term + 0.5 * neg_term


def mine_tune_samples(sess: ort.InferenceSession, max_samples: int = 160):
    tune_jsons = sorted(
        glob.glob(os.path.join(TRAIN_ROOT, "annotations", "0[1-9]", "*.json"))
        + glob.glob(os.path.join(TRAIN_ROOT, "annotations", "1[0-9]", "*.json"))
    )
    selected_jsons = tune_jsons[::3]  # Sample evenly across 01..19

    out_names = ["output"] + FEAT_NAMES
    samples = []
    print(f"Mining hard samples from {len(selected_jsons)} tune videos (strictly disjoint from Holdout 20..24)...")

    for jpath in selected_jsons:
        if len(samples) >= max_samples:
            break
        with open(jpath, "r", encoding="utf-8") as f:
            ann = json.load(f)
        vpath = os.path.join(TRAIN_ROOT, ann["video_path"])
        if not os.path.exists(vpath):
            continue
        w = ann["frame_width"]
        h = ann["frame_height"]
        sx = 512.0 / w
        sy = 288.0 / h

        ball_pts = {}
        for fr in ann["frames"]:
            fid = fr["frame_id"]
            for a in fr["annotations"]:
                if a.get("label") == "ball" and a.get("bbox_xyxy"):
                    b = a["bbox_xyxy"][0]
                    ball_pts[fid] = (0.5 * (b[0] + b[2]) * sx, 0.5 * (b[1] + b[3]) * sy)

        cap = cv2.VideoCapture(vpath)
        buf = []
        fid = 0
        while True:
            ret, bgr = cap.read()
            if not ret or len(samples) >= max_samples:
                break
            buf.append((fid, normalize_frame(bgr)))
            if len(buf) > 3:
                buf.pop(0)
            if len(buf) == 3 and fid % 2 == 0:
                fids = [buf[0][0], buf[1][0], buf[2][0]]
                if any(f in ball_pts for f in fids):
                    inp = np.concatenate([b[1] for b in buf], axis=0)[None]
                    outs = sess.run(out_names, {"input": inp})
                    hm = outs[0][0]
                    feats = [outs[1][0], outs[2][0], outs[3][0], outs[4][0]]

                    is_hard = False
                    target = np.zeros((3, 288, 512), dtype=np.float32)
                    weight = np.zeros((3, 288, 512), dtype=np.float32)

                    for ch, tfid in enumerate(fids):
                        gt = ball_pts.get(tfid)
                        if gt is not None:
                            cx, cy = gt
                            t_ch, w_ch = make_disk_target_and_weight(cx, cy, hm[ch])
                            target[ch] = t_ch
                            weight[ch] = w_ch
                            ix = int(np.clip(round(cx), 0, 511))
                            iy = int(np.clip(round(cy), 0, 287))
                            y0, y1 = max(0, iy - 3), min(288, iy + 4)
                            x0, x1 = max(0, ix - 3), min(512, ix + 4)
                            gt_peak = float(hm[ch, y0:y1, x0:x1].max())

                            hm_copy = hm[ch].copy()
                            my0, my1 = max(0, iy - 10), min(288, iy + 11)
                            mx0, mx1 = max(0, ix - 10), min(512, ix + 11)
                            hm_copy[my0:my1, mx0:mx1] = 0.0
                            bg_peak = float(hm_copy.max())

                            if (0.20 <= gt_peak <= 0.68) or (bg_peak >= 0.40):
                                is_hard = True

                    if is_hard:
                        samples.append((feats, target, weight))
            fid += 1
        cap.release()

    print(f"Collected {len(samples)} hard 3-frame training windows.")
    return samples


def main():
    t0 = time.time()
    onnx_model = onnx.load(ORIG_ONNX)
    head = Stage4HeadModule(onnx_model)
    sess = make_feature_extractor_session(ORIG_ONNX)

    # Verify exact numerical equivalence between ONNXRuntime and PyTorch Stage4HeadModule
    rng = np.random.RandomState(42)
    test_x = rng.randn(1, 9, 288, 512).astype(np.float32)
    outs = sess.run(["output"] + FEAT_NAMES, {"input": test_x})
    ort_out = outs[0]
    with torch.no_grad():
        pt_out = head(
            torch.from_numpy(outs[1]),
            torch.from_numpy(outs[2]),
            torch.from_numpy(outs[3]),
            torch.from_numpy(outs[4]),
        ).numpy()
    max_diff = float(np.max(np.abs(ort_out - pt_out)))
    print(f"[Sanity Check] Max diff between ONNXRuntime and PyTorch Stage4HeadModule: {max_diff:.2e}")
    assert max_diff < 1e-5, f"Equivalence check failed: {max_diff}"

    samples = mine_tune_samples(sess, max_samples=160)
    if not samples:
        print("No samples mined; copying original model.")
        head.export_to_onnx(onnx_model, OUT_ONNX)
        return

    # Split 85% train, 15% val inside Tune set
    n_val = max(10, len(samples) // 6)
    train_samples = samples[:-n_val]
    val_samples = samples[-n_val:]

    # Train with conservative lr and strong L2 weight anchoring to preserve calibration
    optimizer = torch.optim.AdamW(head.parameters(), lr=3e-5, weight_decay=0.0)
    best_val_loss = float("inf")
    best_state = copy.deepcopy(head.state_dict())

    batch_size = 8
    for epoch in range(1, 6):
        head.train()
        np.random.shuffle(train_samples)
        tr_losses = []
        for i in range(0, len(train_samples), batch_size):
            batch = train_samples[i : i + batch_size]
            b0 = torch.from_numpy(np.stack([s[0][0] for s in batch], axis=0))
            b1 = torch.from_numpy(np.stack([s[0][1] for s in batch], axis=0))
            b2 = torch.from_numpy(np.stack([s[0][2] for s in batch], axis=0))
            b3 = torch.from_numpy(np.stack([s[0][3] for s in batch], axis=0))
            tgt = torch.from_numpy(np.stack([s[1] for s in batch], axis=0))
            wgt = torch.from_numpy(np.stack([s[2] for s in batch], axis=0))

            optimizer.zero_grad()
            pred = head(b0, b1, b2, b3)
            loss_bce = weighted_bce_loss(pred, tgt, wgt)
            loss_anchor = 2.0 * head.anchor_loss()
            loss = loss_bce + loss_anchor
            loss.backward()
            torch.nn.utils.clip_grad_norm_(head.parameters(), 0.5)
            optimizer.step()
            tr_losses.append(float(loss_bce.item()))

        head.eval()
        val_losses = []
        with torch.no_grad():
            for i in range(0, len(val_samples), batch_size):
                batch = val_samples[i : i + batch_size]
                b0 = torch.from_numpy(np.stack([s[0][0] for s in batch], axis=0))
                b1 = torch.from_numpy(np.stack([s[0][1] for s in batch], axis=0))
                b2 = torch.from_numpy(np.stack([s[0][2] for s in batch], axis=0))
                b3 = torch.from_numpy(np.stack([s[0][3] for s in batch], axis=0))
                tgt = torch.from_numpy(np.stack([s[1] for s in batch], axis=0))
                wgt = torch.from_numpy(np.stack([s[2] for s in batch], axis=0))
                pred = head(b0, b1, b2, b3)
                v_loss = weighted_bce_loss(pred, tgt, wgt)
                val_losses.append(float(v_loss.item()))

        m_tr = float(np.mean(tr_losses))
        m_val = float(np.mean(val_losses))
        print(f"Epoch {epoch}/5 | Train Disk BCE: {m_tr:.4f} | Val Disk BCE: {m_val:.4f} | Anchor L2: {float(head.anchor_loss().item()):.5f}")
        if m_val < best_val_loss:
            best_val_loss = m_val
            best_state = copy.deepcopy(head.state_dict())

    head.load_state_dict(best_state)
    head.export_to_onnx(onnx_model, OUT_ONNX)
    print(f"Saved fine-tuned ONNX model to {OUT_ONNX} in {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
