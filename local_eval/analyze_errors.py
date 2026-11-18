import json, sys
sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open(r'D:\pingpang源文件汇总\participant\output\public_trajs.json', encoding='utf-8'))
preds_by_vid = {}
for line in open(r'D:\pingpang源文件汇总\participant\output\pingpang\predictions.jsonl', encoding='utf-8'):
    if line.strip():
        r = json.loads(line)
        preds_by_vid.setdefault(r['video_id'], []).append(r)

for vid, info in data.items():
    angle = info['angle']
    ch1 = {int(k): v for k, v in info['ch1'].items()}
    gts = [g for g in info['gts'] if g.get('valid', True)]
    preds = preds_by_vid.get(vid, [])
    
    missed = []
    for g in gts:
        hit = any(abs(p['frame_id'] - g['frame_id']) <= 1 and ((p['x']-g['x'])**2 + (p['y']-g['y'])**2)**0.5 <= 50 for p in preds)
        if not hit:
            missed.append(g)
    fps = []
    for p in preds:
        hit_g = any(abs(p['frame_id'] - g['frame_id']) <= 1 and ((p['x']-g['x'])**2 + (p['y']-g['y'])**2)**0.5 <= 50 for g in info['gts'])
        if not hit_g:
            fps.append(p)
    print(f"=== {vid} [{angle}] Missed={len(missed)}/{len(gts)}, FP={len(fps)}/{len(preds)} ===")
    for m in missed:
        gf = m['frame_id']
        print(f"  MISSED GT f={gf} ({m['x']:.1f}, {m['y']:.1f}):")
        for f in range(gf-3, gf+4):
            c = ch1.get(f)
            mark = " <-- GT" if f == gf else ""
            if c:
                dy = f"dy={c['y'] - ch1[f-1]['y']:+.1f}, dx={c['x'] - ch1[f-1]['x']:+.1f}" if (f-1) in ch1 else ""
                print(f"    f={f:3d}: ({c['x']:.1f}, {c['y']:.1f}, c={c['conf']:.2f}) {dy}{mark}")
            else:
                print(f"    f={f:3d}: None{mark}")
    for fp in fps:
        pf = fp['frame_id']
        print(f"  FALSE POS f={pf} ({fp['x']:.1f}, {fp['y']:.1f}):")
        for f in range(pf-3, pf+4):
            c = ch1.get(f)
            mark = " <-- FP" if f == pf else ""
            if c:
                dy = f"dy={c['y'] - ch1[f-1]['y']:+.1f}, dx={c['x'] - ch1[f-1]['x']:+.1f}" if (f-1) in ch1 else ""
                print(f"    f={f:3d}: ({c['x']:.1f}, {c['y']:.1f}, c={c['conf']:.2f}) {dy}{mark}")
            else:
                print(f"    f={f:3d}: None{mark}")
