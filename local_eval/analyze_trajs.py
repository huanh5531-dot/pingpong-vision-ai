import json, sys
sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open(r'D:\pingpang源文件汇总\participant\output\public_trajs.json', encoding='utf-8'))

for vid, info in data.items():
    if info['angle'] != '0度':
        continue
    print(f"================ {vid} ({info['angle']}) ================")
    ch1 = {int(k): v for k, v in info['ch1'].items()}
    fused = {int(k): v for k, v in info['fused'].items()}
    for g in info['gts']:
        gf = g['frame_id']
        print(f"--- GT frame={gf}, valid={g['valid']}, pos=({g['x']:.1f}, {g['y']:.1f}) ---")
        for f in range(gf - 4, gf + 5):
            c1 = ch1.get(f)
            fm = fused.get(f, {}).get('max')
            fa = fused.get(f, {}).get('avg')
            mark = " <<< GT" if f == gf else ""
            c1_str = f"({c1['x']:.1f}, {c1['y']:.1f}, c={c1['conf']:.2f})" if c1 else "None"
            fa_str = f"({fa['lx']:.1f}, {fa['ly']:.1f}, c={fa['conf']:.2f})" if fa else "None"
            dy_str = ""
            if f - 1 in ch1 and f in ch1:
                dy_str = f"dy={ch1[f]['y'] - ch1[f-1]['y']:+.1f}, dx={ch1[f]['x'] - ch1[f-1]['x']:+.1f}"
            print(f"  f={f:3d}: ch1={c1_str:28s} | {dy_str:20s} | fused_avg={fa_str}{mark}")
