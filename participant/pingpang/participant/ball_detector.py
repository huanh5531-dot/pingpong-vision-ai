"""球检测模型与多通道局部峰值融合解码器。

改进点：
  1. 利用模型输出的全部 3 个时间通道 (ch0, ch1, ch2 对应 [t-2, t-1, t]) 对同一目标帧做跨窗口融合，
     解决乒乓球在落桌折返瞬间因轨迹呈 V 字折角导致单通道 (ch1) 置信度骤降漏检的问题（零额外推理开销）。
  2. 采用最高响应点邻域 (9x9) 局部加权质心替代全图阈值质心，消除球台反光/球拍白边双峰拉偏坐标的问题。
  3. 流式 O(1) 内存管理：每帧推理完立即结算 t-2 帧并释放热图缓存，视频结束时 flush 尾部两帧。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

IN_H, IN_W = 288, 512
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
SCORE_TH = 0.7
OUT_CHANNEL = 1  # 3 通道热图对应 buffer 的 [旧, 中, 新] 三帧


class BallDetector:
    """球检测器：依赖一个外部传入的推理函数 _infer（输入 (1,9,H,W)，输出 (1,3,H,W) 热图）。"""

    def __init__(self, infer_fn, onnx_path: str | Path):
        self._infer = infer_fn
        self.onnx_path = Path(onnx_path)
        self._blank = self._normalize(np.zeros((IN_H, IN_W, 3), np.uint8))
        self.reset()

    # ── 预处理 ──────────────────────────────────────────────────────────────
    @staticmethod
    def _normalize(frame_rgb: np.ndarray) -> np.ndarray:
        """(H,W,3) uint8 -> (3,288,512) float32 归一化与标准化。"""
        x = cv2.resize(frame_rgb, (IN_W, IN_H), interpolation=cv2.INTER_LINEAR)
        x = x.astype(np.float32) / 255.0
        x = (x - _MEAN) / _STD
        return np.ascontiguousarray(x.transpose(2, 0, 1))

    @staticmethod
    def _decode_peak(heat: np.ndarray, orig_w: int, orig_h: int, th: float = 0.3) -> dict | None:
        """在峰值周围 9x9 局部窗口内计算加权质心，划定质心区域，避免远处噪点拉偏球心坐标。"""
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
        return {
            "x": lcx,
            "y": lcy,
            "conf": max_val,
        }

    def reset(self) -> None:
        self._buf = [self._blank, self._blank]
        self._heat_accum: dict[int, list[np.ndarray]] = {}
        self._ch1_dets: dict[int, dict | None] = {}

    def _finalize_frame(self, tfid: int, orig_w: int, orig_h: int) -> tuple[int, float, float, float] | None:
        """融合目标帧 tfid 收集到的多窗口热图，输出高鲁棒性球心检测点。"""
        hlist = self._heat_accum.pop(tfid, None)
        c1 = self._ch1_dets.pop(tfid, None)
        if not hlist:
            return None

        max_h = np.max(hlist, axis=0)
        avg_h = np.mean(hlist, axis=0)
        fm = self._decode_peak(max_h, orig_w, orig_h, th=0.30)
        fa = self._decode_peak(avg_h, orig_w, orig_h, th=0.25)

        if c1 and c1["conf"] >= 0.65:
            return (tfid, c1["x"], c1["y"], c1["conf"])
        if fm and fm["conf"] >= 0.60:
            return (tfid, fm["x"], fm["y"], fm["conf"])
        if c1 and fa and c1["conf"] >= 0.50 and fa["conf"] >= 0.45:
            return (tfid, c1["x"], c1["y"], max(c1["conf"], fa["conf"]))
        return None

    # ── 流式多通道推理 + 解码 ──────────────────────────────────────────────
    def push_frame(
        self, frame_rgb: np.ndarray, fid: int, orig_w: int, orig_h: int
    ) -> tuple[int, float, float, float] | None:
        """推入当前帧 fid，返回已集齐 3 个滑动窗口的 (fid-2) 帧融合检测结果。"""
        self._buf.append(self._normalize(frame_rgb))
        self._buf = self._buf[-3:]
        inp = np.concatenate(self._buf, axis=0)[None]  # (1,9,288,512)
        out = self._infer(inp)[0]                      # (3,288,512) 对应 [fid-2, fid-1, fid]

        for c_idx, target_fid in enumerate((fid - 2, fid - 1, fid)):
            if target_fid >= 0:
                self._heat_accum.setdefault(target_fid, []).append(out[c_idx])

        if fid - 1 >= 0:
            self._ch1_dets[fid - 1] = self._decode_peak(out[1], orig_w, orig_h, th=0.30)

        if fid - 2 >= 0:
            return self._finalize_frame(fid - 2, orig_w, orig_h)
        return None

    def flush(self, orig_w: int, orig_h: int) -> list[tuple[int, float, float, float]]:
        """视频结束时结算缓冲中剩余的最后两帧。"""
        out = []
        for tfid in sorted(list(self._heat_accum.keys())):
            det = self._finalize_frame(tfid, orig_w, orig_h)
            if det is not None:
                out.append(det)
        self._ch1_dets.clear()
        return out

    # ── 兼容旧接口（如 prepare 阶段 warmup 调用）──────────────────────────
    def detect(self, frame_rgb: np.ndarray, orig_w: int, orig_h: int) -> dict | None:
        """单通道即时检测接口（保留向后兼容）。"""
        self._buf.append(self._normalize(frame_rgb))
        self._buf = self._buf[-3:]
        inp = np.concatenate(self._buf, axis=0)[None]
        heat = self._infer(inp)[0, OUT_CHANNEL]
        return self._decode_peak(heat, orig_w, orig_h, th=SCORE_TH)
