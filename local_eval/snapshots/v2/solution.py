from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import numpy as np

from core.types import Landing, RunContext, VideoMeta

from .ball_detector import BallDetector
from .base_solution import BaseSolution

# 不同机位视角下的球台有效空间区域 (归一化坐标 rx0, rx1, ry0, ry1)
ROI_BY_ANGLE: dict[str, tuple[float, float, float, float]] = {
    "0度":  (0.35, 0.65, 0.25, 0.60),
    "45度": (0.25, 0.75, 0.35, 0.61),
    "90度": (0.37, 0.64, 0.38, 0.72),
}


class Solution(BaseSolution):
    """分视角物理运动学落点检测器 + 多通道轨迹去噪状态管理。

    核心改进：
      1. 状态管理（State Management）：
         - 接收 BallDetector 的 3 通道跨窗口融合检测结果，恢复落桌折返瞬间的低置信度帧；
         - 剔除背景静态反光噪点（同一网格高频静止点）与单帧空间跳变离群点（Spike Outlier），防止单帧噪点触发假阳性并锁死后续真落点；
         - 球台空间 ROI 门控：按 `video_meta.angle`（0度/45度/90度）设定球台空间边界，直接过滤球台外的挥拍击球与抛球。
      2. 分视角物理落点判定（Multi-Angle Physics Landing Detection）：
         - 过滤球员发球垂直抛球、发球击球瞬间（水平速度从 0 突变）与回合中球拍反拉（水平速度反向突变）；
         - 模态 1（标准/平顶局部极大值）：支持 1~2 帧平顶落点，按牛顿第二定律瞬时竖直冲量 Δvy = vy_in - vy_out 精选起跳帧；
         - 模态 2（0度/45度 远台深度落点）：识别透视投影下球向画面上方飞行时“重力减速 (vy_in > prev_vy) -> 触台向上急剧加速 (vy_out << vy_in)”的冲量突变；
         - 模态 3（近台高速下砸落点）：识别球高速下落 (vy_in >> 0) 触台后竖直速度断崖式衰减（即使受透视影响 vy_out 仍微弱 >= 0）；
         - 落点后不应期抑制：由于乒乓球规则必须先落台再由球员挥拍击球，确认落台后 2~7 帧内的二次拐点（接球方挡球/拉球）予以抑制，仅对相邻 1 帧的平顶落点做冲量择优。
    """

    def prepare(self, context: RunContext) -> None:
        onnx_path = Path(__file__).resolve().parent / "weights" / "ball.onnx"
        assert onnx_path.exists(), f"缺少权重: {onnx_path}"

        from core.trt import load_or_build
        trt_cache = Path(context.output_dir) / "trt_cache"

        # 优先尝试 TensorRT（评测机 4090 正常构建加速）；若本地 5060 架构报错则自动回退到 ONNX Runtime
        try:
            model, how = load_or_build(
                onnx_path, trt_cache, input_name="input",
                shape=(1, 9, 288, 512), log=print)
            infer_fn = model.infer
            backend_name = f"tensorrt_{how}"
        except Exception as e:
            print(f"[pingpang] TRT 不可用（{e}），回退 onnxruntime")
            import onnxruntime as ort
            sess = ort.InferenceSession(
                str(onnx_path),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
            )
            in_name = sess.get_inputs()[0].name
            infer_fn = lambda x: sess.run(None, {in_name: x})[0]
            backend_name = "onnxruntime"

        self.det = BallDetector(infer_fn, onnx_path)
        self.det.detect(np.zeros((288, 512, 3), np.uint8), 512, 288)
        self.det.reset()
        context.info["backend"] = backend_name

        self.raw_traj: list[tuple[int, float, float, float]] = []
        self.angle: str = "45度"
        self.width: int = 1920
        self.height: int = 1080
        self.n_frames: int = 0

    def reset(self, video_meta: VideoMeta) -> None:
        self.det.reset()
        self.raw_traj = []
        self.angle = video_meta.angle
        self.width = video_meta.width
        self.height = video_meta.height
        self.n_frames = video_meta.n_frames

    def process_frame(self, frame_rgb, frame_meta) -> list[Landing]:
        fid = frame_meta["frame_id"]
        det = self.det.push_frame(frame_rgb, fid, frame_meta["width"], frame_meta["height"])
        if det is not None:
            self.raw_traj.append(det)
        return []

    def finish_video(self, video_meta: VideoMeta) -> list[Landing]:
        for det in self.det.flush(video_meta.width, video_meta.height):
            self.raw_traj.append(det)
        return self._detect_landings()

    def _build_clean_traj(self) -> list[tuple[int, float, float, float]]:
        """状态清洗：统一归一化至 1920x1080 物理尺度，剔除静态背景反光热点与单帧空间跳变离群点。"""
        if not self.raw_traj:
            return []

        sx = 1920.0 / max(1, self.width)
        sy = 1080.0 / max(1, self.height)
        scaled_traj = [(f, x * sx, y * sy, c) for f, x, y, c in self.raw_traj]

        # 1. 过滤视频中反复出现的静态背景反光点（同一 4x4 像素网格出现 >= 4 次）
        cell_counts = Counter((round(x / 4.0), round(y / 4.0)) for _, x, y, _ in scaled_traj)
        hotspots = {cell for cell, cnt in cell_counts.items() if cnt >= 4}
        traj_no_hotspot = [
            pt for pt in scaled_traj
            if (round(pt[1] / 4.0), round(pt[2] / 4.0)) not in hotspots
        ]

        # 2. 过滤单帧空间跳变离群点（Spike Outlier：跳出后下一帧立即回到原轨迹附近）
        cleaned: list[tuple[int, float, float, float]] = []
        m = len(traj_no_hotspot)
        for i in range(m):
            f, x, y, c = traj_no_hotspot[i]
            is_bad = False
            if 0 < i < m - 1:
                f_prev, xp, yp, _ = traj_no_hotspot[i - 1]
                f_next, xn, yn, _ = traj_no_hotspot[i + 1]
                if f - f_prev <= 2 and f_next - f <= 2:
                    d_prev = math.hypot(x - xp, y - yp)
                    d_next = math.hypot(xn - x, yn - y)
                    d_bridge = math.hypot(xn - xp, yn - yp)
                    if d_prev > 45.0 and d_next > 45.0 and d_bridge < 0.45 * (d_prev + d_next):
                        is_bad = True
                    elif d_prev > 120.0 and d_next > 120.0 and d_bridge < 0.65 * (d_prev + d_next):
                        is_bad = True
            if not is_bad:
                cleaned.append((f, x, y, c))
        return cleaned

    def _detect_landings(self) -> list[Landing]:
        angle = self.angle
        width = self.width
        height = self.height
        sx = 1920.0 / max(1, width)
        sy = 1080.0 / max(1, height)
        rx0, rx1, ry0, ry1 = ROI_BY_ANGLE.get(angle, (0.25, 0.75, 0.25, 0.72))

        traj = self._build_clean_traj()
        n = len(traj)
        candidates: list[tuple[int, float, float, float]] = []

        for j in range(1, n - 1):
            fid, x, y, _ = traj[j]
            nx, ny = x / 1920.0, y / 1080.0
            if not (rx0 <= nx <= rx1 and ry0 <= ny <= ry1):
                continue

            f_prev, xp, yp, _ = traj[j - 1]
            f_next, xn, yn, _ = traj[j + 1]
            dt_in = fid - f_prev
            dt_out = f_next - fid

            if dt_in > 3 or dt_out > 3:
                continue

            vx_in = (x - xp) / dt_in
            vy_in = (y - yp) / dt_in
            vx_out = (xn - x) / dt_out
            vy_out = (yn - y) / dt_out

            # 2 步前瞻与回溯速度估计（应对平顶落点与帧间微弱抖动）
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
            next_vy = vy_out
            if j + 2 < n:
                next_dt = traj[j + 2][0] - f_next
                if next_dt <= 3:
                    next_vy = (traj[j + 2][2] - yn) / next_dt
                if (traj[j + 2][0] - fid) <= 4:
                    dt2 = traj[j + 2][0] - fid
                    vy_out2 = (traj[j + 2][2] - y) / dt2

            # 过滤静止伪影与非物理超高速跳变
            speed_in = math.hypot(vx_in, vy_in)
            speed_out = math.hypot(vx_out, vy_out)
            if (speed_in < 2.5 and speed_out < 2.5) or max(speed_in, speed_out) < 4.0 or speed_in > 220.0 or speed_out > 220.0:
                continue

            # 过滤非物理单帧向下瞬移伪影
            if prev_dt == 1 and vy_in > 50.0 and (vy_in - prev_vy) > 35.0:
                continue

            # 过滤发球击球瞬间（连续 >=2 帧垂直抛球 vx 极小，突然被球拍横向击出）
            if prev_dt <= 2 and min(abs(vx_in), abs(prev_vx)) < 4.2 and abs(vx_in2) < 12.0 and max(abs(vx_out), abs(vx_in)) > 14.0:
                continue

            # 过滤跨 2 帧的球拍回击（水平方向发生反转）
            if prev_dt <= 2 and prev_vx * vx_out < 0 and abs(prev_vx) > 4.5 and abs(vx_out) > 12.0:
                continue

            # 分视角球拍击球与抛球过滤
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

            # 模态 1：标准或平顶 Y 轴局部极大值（下落 -> 反弹上升），统一使用跨视角冲量阈值 7.0
            eff_fall = max(vy_in, vy_in2, prev_vy if prev_dt <= 2 else vy_in)
            eff_rise = -min(vy_out, vy_out2, next_vy if dt_out == 1 else vy_out)
            if (y >= yp - 4.0 and y >= yn - 2.8) and eff_fall >= 2.0 and eff_rise >= 1.2:
                if vy_in >= -4.0 and vy_out <= 2.2 and (eff_fall + eff_rise) >= 7.0:
                    if dt_out == 1 or vy_out <= -4.0:
                        if abs(vx_out - vx_in) <= 32.0 or angle == "90度" or (vx_in * vx_out > 0 and vy_in >= 30.0):
                            is_landing = True
                            score = vy_in - vy_out

            # 模态 2：0度/45度 远台或中台深度方向反弹（球向画面上方飞行时重力减速 -> 触台向上急剧加速）
            if not is_landing and angle in ("0度", "45度"):
                best_vy_out = min(vy_out, vy_out2)
                min_prev_vy = min(prev_vy, vy_in2) if prev_dt <= 2 else prev_vy
                if dt_in == 1 and prev_dt <= 2 and prev_vx * vx_in > 0:
                    if min_prev_vy <= -1.8 and -8.0 <= vy_in <= 3.0 and (vy_in - prev_vy) >= -1.5:
                        if best_vy_out <= -11.0 and (vy_in - best_vy_out) >= 12.0:
                            if abs(vx_out - vx_in) <= 18.0 and vx_in * vx_out > 0:
                                is_landing = True
                                score = vy_in - best_vy_out
                elif dt_in == 1 and prev_dt > 2 and prev_vx * vx_in > 0 and -7.0 <= vy_in <= 1.0 and vy_out <= -12.0 and (vy_in - vy_out) >= 8.0:
                    if abs(vx_out - vx_in) <= 6.0 and vx_in * vx_out > 0:
                        is_landing = True
                        score = vy_in - vy_out

            # 模态 3：近台高速下落触台急剧减速（即使因纵向透视导致触台后 vy_out 仍微弱 >= 0）
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
                candidates.append((fid, float(x / sx), float(y / sy), score))

        # 时序状态仲裁：
        # 1. 同一落点跨相邻 2 帧平顶 (fid - cluster_start == 1)：保留瞬时冲量更大的真实起跳帧；
        # 2. 落点确认后的 2~7 帧不应期 (fid - out[-1][0] < 8)：抑制接球方球拍触球产生的二次拐点。
        selected: list[tuple[int, float, float, float]] = []
        cluster_start = -999
        for fid, x, y, sc in candidates:
            if selected and (fid - cluster_start) == 1:
                if sc > selected[-1][3]:
                    selected[-1] = (fid, x, y, sc)
            elif selected and (fid - selected[-1][0]) < 8:
                continue
            else:
                selected.append((fid, x, y, sc))
                cluster_start = fid

        # 坐标与帧号安全边界裁剪，确保 100% 通过 validate.py 校验
        max_f = max(0, self.n_frames - 1) if self.n_frames > 0 else 999999
        max_x = float(width) - 1e-3
        max_y = float(height) - 1e-3
        return [
            Landing(
                frame_id=int(min(max(0, fid), max_f)),
                x=float(min(max(0.0, x), max_x)),
                y=float(min(max(0.0, y), max_y)),
            )
            for fid, x, y, _ in selected
        ]
