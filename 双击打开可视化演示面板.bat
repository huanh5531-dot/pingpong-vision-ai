@echo off
chcp 65001 >nul
title 乒羽智瞳 - 验证集可视化分析服务
echo 正在启动本地可视化服务器 (http://127.0.0.1:8765/)，稍候将自动打开浏览器...
python "D:\pingpang源文件汇总\local_eval\visualizer_server.py" --open
pause
