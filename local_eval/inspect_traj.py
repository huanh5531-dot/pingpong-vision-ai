import sys, json
sys.path.insert(0, '/participant/pingpang')
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort
from core.dataset import load_manifest
from core.decoder import decode_video

IN_H, IN_W = 288, 512
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

def normalize(frame_rgb):
    x = cv2.resize(frame_rgb, (IN_W, IN_H), interpolation=cv2.INTER_LINEAR)
    x = x.astype(np.float32) / 255.0
    x = (x - _MEAN) / _STD
    return np.ascontiguousarray(x.transpose(2, 0, 1))

def decode_heat(heat, orig_w, orig_h, th=0.3):
    max_val = float(heat.max())
    if max_val <= th:
        return None
    # Global mask centroid (baseline style)
    mask = heat > max(th, 0.5 * max_val)
    ys, xs = np.nonzero(mask)
    w = heat[ys, xs].astype(np.float64)
    total = w.sum()
    cx = float((xs * w).sum() / total) * orig_w / IN_W
    cy = float((ys * w).sum() / total) * orig_h / IN_H

    # Local peak centroid (within 7x7 around argmax)
    py, px = np.unravel_index(np.argmax(heat), heat.shape)
    y0, y1 = max(0, py - 4), min(IN_H, py + 5)
    x0, x1 = max(0, px - 4), min(IN_W, px + 5)
    patch = heat[y0:y1, x0:x1]
    pmask = patch > th
    pys, pxs = np.nonzero(pmask)
    pw = patch[pys, pxs].astype(np.float64)
    ptotal = pw.sum()
    lcx = float(((pxs + x0) * pw).sum() / ptotal) * orig_w / IN_W
    lcy = float(((pys + y0) * pw).sum() / ptotal) * orig_h / IN_H

    return {
        "x": round(cx, 2), "y": round(cy, 2),
        "lx": round(lcx, 2), "ly": round(lcy, 2),
        "conf": round(max_val, 4)
    }

onnx_path = Path('/participant/pingpang/participant/weights/ball.onnx')
sess = ort.InferenceSession(str(onnx_path), providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
in_name = sess.get_inputs()[0].name
infer = lambda x: sess.run(None, {in_name: x})[0]

videos = load_manifest('/participant/pingpang/public_data/manifest.json')
gt_by_vid = {}
for line in open('/participant/pingpang/public_data/gt_public.jsonl'):
    if line.strip():
        r = json.loads(line)
        gt_by_vid.setdefault(r['video_id'], []).append(r)

blank = normalize(np.zeros((IN_H, IN_W, 3), np.uint8))
out_data = {}

for v in videos:
    buf = [blank, blank]
    ch0_map, ch1_map, ch2_map = {}, {}, {}
    heat_accum = {}  # frame_id -> list of heatmaps
    for fid, frame_rgb in decode_video(v, '/participant/pingpang/public_data', 'gpu'):
        buf.append(normalize(frame_rgb))
        buf = buf[-3:]
        inp = np.concatenate(buf, axis=0)[None]
        out = infer(inp)[0]  # (3, 288, 512) for [fid-2, fid-1, fid]
        for c_idx, target_fid in enumerate([fid - 2, fid - 1, fid]):
            if target_fid >= 0:
                heat_accum.setdefault(target_fid, []).append(out[c_idx])
        d1 = decode_heat(out[1], v.width, v.height, th=0.3)
        if d1 and fid - 1 >= 0:
            ch1_map[fid - 1] = d1

    fused_map = {}
    for tfid, hlist in heat_accum.items():
        avg_h = np.mean(hlist, axis=0)
        max_h = np.max(hlist, axis=0)
        df_avg = decode_heat(avg_h, v.width, v.height, th=0.25)
        df_max = decode_heat(max_h, v.width, v.height, th=0.3)
        if df_avg or df_max:
            fused_map[tfid] = {"avg": df_avg, "max": df_max}

    out_data[v.video_id] = {
        'angle': v.angle,
        'width': v.width,
        'height': v.height,
        'n_frames': v.n_frames,
        'ch1': ch1_map,
        'fused': fused_map,
        'gts': gt_by_vid[v.video_id]
    }
    print(f"Processed {v.video_id} ({v.angle}): {len(ch1_map)}/{v.n_frames} frames")

with open('/participant/output/public_trajs.json', 'w', encoding='utf-8') as f:
    json.dump(out_data, f, ensure_ascii=False)
print("Saved /participant/output/public_trajs.json")
