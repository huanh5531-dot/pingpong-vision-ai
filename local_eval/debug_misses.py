import json, sys
sys.stdout.reconfigure(encoding='utf-8')
from sim_new import data, build_clean_traj

for vid in ['v000001', 'v000010', 'v000019', 'v000028', 'v000037', 'v000038', 'v000057', 'v000066', 'v000075', 'v000085', 'v000094', 'v000095', 'v000106']:
    info = data[vid]
    traj = build_clean_traj(info)
    tmap = {f: (i, x, y, c) for i, (f, x, y, c) in enumerate(traj)}
    for g in info['gts']:
        if not g.get('valid', True): continue
        gf = g['frame_id']
        print(f"=== {vid} ({info['angle']}) GT f={gf} ({g['x']:.1f}, {g['y']:.1f}) ===")
        for f in range(gf - 2, gf + 3):
            if f in tmap:
                idx, x, y, c = tmap[f]
                xp, yp = (traj[idx-1][1], traj[idx-1][2]) if idx > 0 else (x, y)
                xn, yn = (traj[idx+1][1], traj[idx+1][2]) if idx+1 < len(traj) else (x, y)
                dt_in = f - traj[idx-1][0] if idx > 0 else 1
                dt_out = traj[idx+1][0] - f if idx+1 < len(traj) else 1
                vxi, vyi = (x - xp)/dt_in, (y - yp)/dt_in
                vxo, vyo = (xn - x)/dt_out, (yn - y)/dt_out
                mark = " <-- GT" if f == gf else ""
                print(f"  f={f:3d} (dt={dt_in},{dt_out}): pos=({x:.1f},{y:.1f}) c={c:.2f} | v_in=({vxi:+.1f},{vyi:+.1f}) v_out=({vxo:+.1f},{vyo:+.1f}){mark}")
            else:
                print(f"  f={f:3d}: MISSING in clean_traj")
