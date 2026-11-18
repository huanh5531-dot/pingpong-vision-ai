import json

with open(r'D:\pingpang源文件汇总\participant\output\public_trajs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for vid, f_range in [('v000106', range(0, 12)), ('v000094', range(75, 85)), ('v000057', range(55, 67)), ('v000001', range(82, 91)), ('v000028', range(28, 39)), ('v000066', range(0, 8))]:
    info = data[vid]
    ch1 = {int(k): v for k, v in info['ch1'].items()}
    fused = {int(k): v for k, v in info['fused'].items()}
    print(f"=== {vid} ({info['angle']}) ===")
    for f in f_range:
        c1 = ch1.get(f)
        fm = fused.get(f, {}).get('max')
        fa = fused.get(f, {}).get('avg')
        print(f"  f={f:3d}: c1={c1} | fm={fm} | fa={fa}")
