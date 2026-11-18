import json
from sim_new import build_clean_traj

with open(r'D:\pingpang源文件汇总\participant\output\public_trajs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

info = data['v000066']
traj = build_clean_traj(info)
print("traj around 35..42:", [x for x in traj if 30 <= x[0] <= 45])
