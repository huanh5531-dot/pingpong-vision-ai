import json
from sim_new import build_clean_traj

with open(r'D:\pingpang源文件汇总\participant\output\public_trajs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

cases = [
    ('v000001', range(14, 26)),
    ('v000010', range(20, 30)),
    ('v000010', range(55, 82)),
    ('v000038', range(20, 63)),
    ('v000047', range(1, 56)),
    ('v000066', range(20, 42)),
    ('v000066', range(80, 92)),
    ('v000094', range(35, 46)),
    ('v000106', range(65, 73)),
    ('v000106', range(154, 162)),
]

for vid, fr in cases:
    info = data[vid]
    traj = build_clean_traj(info)
    gts = [g['frame_id'] for g in info['gts']]
    print(f"=== {vid} ({info['angle']}) GTs={gts} range={fr.start}..{fr.stop-1} ===")
    for i, (fid, x, y, c) in enumerate(traj):
        if fid in fr:
            xp, yp = (traj[i-1][1], traj[i-1][2]) if i > 0 else (x, y)
            dt1 = (fid - traj[i-1][0]) if i > 0 else 1
            xn, yn = (traj[i+1][1], traj[i+1][2]) if i+1 < len(traj) else (x, y)
            dt2 = (traj[i+1][0] - fid) if i+1 < len(traj) else 1
            vxi, vyi = (x - xp)/dt1, (y - yp)/dt1
            vxo, vyo = (xn - x)/dt2, (yn - y)/dt2
            mark = " <-- GT" if fid in gts else ""
            print(f"  f={fid:3d} (dt={dt1},{dt2}): ({x:6.1f},{y:5.1f}) c={c:.2f} | vin=({vxi:+6.1f},{vyi:+6.1f}) vout=({vxo:+6.1f},{vyo:+6.1f}){mark}")
