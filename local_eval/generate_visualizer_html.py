# -*- coding: utf-8 -*-
"""
Generate the interactive, real-video-synced pingpong_visualizer.html plugin
with trajectory overlay, prominent landing annotations, live detection log panel,
and multi-speed playback controller.
"""
import json
import os

json_path = r'D:\pingpang源文件汇总\local_eval\vis_data.json'
if not os.path.exists(json_path):
    json_path = r'C:\Users\LENOVO\.gemini\antigravity\brain\45eb8651-a8aa-499d-8cfa-d4e66e108527\scratch\vis_data.json'

with open(json_path, 'r', encoding='utf-8') as f:
    vis_data_str = f.read()

html_template = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>乒羽智瞳 · 验证集真实视频轨迹与落点实时分析工作台</title>
  <style>
    :root {
      --bg-app: #070b14;
      --bg-panel: #0f1626;
      --bg-card: #162035;
      --bg-card-hover: #1d2a45;
      --border: #24324f;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --accent-green: #10b981;
      --accent-cyan: #38bdf8;
      --accent-amber: #fbbf24;
      --accent-rose: #f43f5e;
      --accent-indigo: #6366f1;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg-app);
      color: var(--text-main);
      font-family: "Microsoft YaHei", "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }

    /* Custom scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0a101d; }
    ::-webkit-scrollbar-thumb { background: #2c3c5c; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #3e5480; }

    /* Header */
    .top-header {
      background: linear-gradient(90deg, #0b1324 0%, #131d36 50%, #0b1324 100%);
      border-bottom: 1px solid var(--border);
      padding: 10px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      z-index: 30;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-icon {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: linear-gradient(135deg, #10b981, #0284c7);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
      flex-shrink: 0;
    }

    .brand-title-row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .brand h1 {
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0.3px;
      color: #ffffff;
    }

    .badge-f1-global {
      font-size: 11px;
      font-weight: 700;
      padding: 2px 9px;
      border-radius: 999px;
      background: rgba(16, 185, 129, 0.14);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.35);
    }

    .brand-sub {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .video-nav-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .btn-nav {
      background: var(--bg-card);
      color: var(--text-main);
      border: 1px solid var(--border);
      padding: 7px 12px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-nav:hover { background: var(--bg-card-hover); border-color: #3b5280; }

    select.video-select {
      background: #0a101d;
      color: #f8fafc;
      border: 1px solid #33476b;
      border-radius: 8px;
      padding: 7px 12px;
      font-size: 12.5px;
      font-family: "Microsoft YaHei", monospace;
      max-width: 430px;
      cursor: pointer;
      outline: none;
    }
    select.video-select:focus { border-color: var(--accent-cyan); }

    .angle-pill {
      padding: 5px 10px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 700;
      background: rgba(99, 102, 241, 0.18);
      color: #a5b4fc;
      border: 1px solid rgba(99, 102, 241, 0.35);
    }

    /* Main Layout: Left Video Stage + Right Side Panel */
    .workspace {
      flex: 1;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 420px;
      gap: 16px;
      padding: 14px 20px 18px;
      max-width: 1720px;
      width: 100%;
      margin: 0 auto;
      align-items: start;
    }

    @media (max-width: 1120px) {
      .workspace {
        grid-template-columns: 1fr;
      }
    }

    /* Left Column */
    .stage-col {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .video-stage {
      position: relative;
      width: 100%;
      aspect-ratio: 16 / 9;
      background: #05080f;
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow: hidden;
      box-shadow: 0 20px 45px rgba(0, 0, 0, 0.6);
    }

    .video-stage video,
    .video-stage canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    .video-stage video { z-index: 5; }
    .video-stage canvas { z-index: 10; pointer-events: none; }

    /* Top HUD inside video */
    .hud-top-left {
      position: absolute;
      top: 12px;
      left: 12px;
      z-index: 20;
      display: flex;
      flex-direction: column;
      gap: 6px;
      pointer-events: none;
    }

    .hud-pill {
      background: rgba(7, 11, 20, 0.78);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(148, 163, 184, 0.25);
      border-radius: 8px;
      padding: 5px 11px;
      font-size: 12px;
      font-family: Consolas, "Microsoft YaHei", monospace;
      color: #e2e8f0;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      width: fit-content;
    }

    .dot-live {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-green);
      box-shadow: 0 0 8px var(--accent-green);
    }

    .hud-bottom-left {
      position: absolute;
      bottom: 12px;
      left: 12px;
      z-index: 20;
      background: rgba(7, 11, 20, 0.78);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: 8px;
      padding: 6px 11px;
      font-size: 11px;
      display: flex;
      flex-direction: row;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      pointer-events: none;
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 7px;
      color: #cbd5e1;
    }

    .lg-dot { width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid #fff; flex-shrink: 0; }
    .lg-diamond { width: 9px; height: 9px; background: var(--accent-amber); transform: rotate(45deg); border: 1px solid #000; flex-shrink: 0; }
    .lg-line { width: 14px; height: 3px; border-radius: 2px; background: var(--accent-cyan); flex-shrink: 0; }

    /* Bottom-right video status/fallback pill */
    .video-source-bar {
      position: absolute;
      bottom: 12px;
      right: 12px;
      z-index: 25;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .source-status {
      font-size: 11px;
      padding: 5px 10px;
      border-radius: 8px;
      background: rgba(7, 11, 20, 0.85);
      border: 1px solid rgba(148, 163, 184, 0.25);
      color: #cbd5e1;
    }

    .btn-pick-file {
      font-size: 11px;
      padding: 5px 10px;
      border-radius: 8px;
      background: rgba(22, 32, 53, 0.9);
      border: 1px solid #33476b;
      color: #e2e8f0;
      cursor: pointer;
    }
    .btn-pick-file:hover { background: #243559; }

    /* Player Timeline Bar */
    .player-controls {
      background: var(--bg-panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .timeline-wrap {
      position: relative;
      height: 28px;
      display: flex;
      align-items: center;
    }

    .timeline-ticks {
      position: absolute;
      left: 0;
      right: 0;
      top: 0;
      height: 10px;
      pointer-events: none;
    }

    .tick-mark {
      position: absolute;
      top: 1px;
      width: 4px;
      height: 10px;
      border-radius: 2px;
      transform: translateX(-50%);
      pointer-events: auto;
      cursor: pointer;
    }
    .tick-tp { background: var(--accent-green); box-shadow: 0 0 6px var(--accent-green); }
    .tick-fp { background: var(--accent-rose); box-shadow: 0 0 6px var(--accent-rose); }
    .tick-fn { background: var(--accent-amber); box-shadow: 0 0 6px var(--accent-amber); }

    input[type="range"].scrubber {
      width: 100%;
      margin-top: 8px;
      accent-color: var(--accent-green);
      cursor: pointer;
      height: 6px;
    }

    .controls-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .btn-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .btn-primary {
      background: var(--accent-green);
      color: #052e16;
      border: none;
      padding: 8px 18px;
      border-radius: 9px;
      font-size: 13.5px;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.28);
      transition: transform 0.1s, background 0.15s;
    }
    .btn-primary:hover { background: #34d399; }
    .btn-primary:active { transform: scale(0.97); }

    .btn-ctrl {
      background: var(--bg-card);
      color: var(--text-main);
      border: 1px solid var(--border);
      padding: 7px 12px;
      border-radius: 8px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-ctrl:hover { background: var(--bg-card-hover); border-color: #3b5280; }

    .quick-landings-bar {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      padding-top: 4px;
      border-top: 1px solid rgba(36, 50, 79, 0.7);
    }

    .ql-label {
      font-size: 11.5px;
      color: var(--text-muted);
      margin-right: 4px;
      font-weight: 600;
    }

    .ql-chip {
      font-size: 11.5px;
      font-family: Consolas, monospace;
      padding: 4px 9px;
      border-radius: 7px;
      border: 1px solid var(--border);
      background: #0b111e;
      color: #e2e8f0;
      cursor: pointer;
      transition: all 0.15s;
    }
    .ql-chip:hover { transform: translateY(-1px); }
    .ql-chip.tp { border-color: rgba(16, 185, 129, 0.45); color: #34d399; background: rgba(16, 185, 129, 0.08); }
    .ql-chip.fp { border-color: rgba(244, 63, 94, 0.45); color: #fb7185; background: rgba(244, 63, 94, 0.08); }
    .ql-chip.fn { border-color: rgba(251, 191, 36, 0.45); color: #fcd34d; background: rgba(251, 191, 36, 0.08); }
    .ql-chip.active { box-shadow: 0 0 0 2px #fff; font-weight: 700; }

    /* Right Side Panel: Speed + Stats + Logs */
    .side-panel {
      display: flex;
      flex-direction: column;
      gap: 12px;
      height: calc(100vh - 96px);
      min-height: 620px;
      position: sticky;
      top: 14px;
    }

    @media (max-width: 1120px) {
      .side-panel {
        height: auto;
        position: static;
      }
    }

    .panel-card {
      background: var(--bg-panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .card-title {
      font-size: 13.5px;
      font-weight: 700;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 7px;
    }

    .speed-readout {
      font-family: Consolas, monospace;
      font-size: 13px;
      font-weight: 700;
      color: var(--accent-cyan);
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 2px 9px;
      border-radius: 6px;
    }

    /* Speed Buttons Grid */
    .speed-presets {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 5px;
    }

    .btn-speed {
      background: #0b111e;
      color: var(--text-muted);
      border: 1px solid var(--border);
      padding: 6px 0;
      border-radius: 7px;
      font-size: 12px;
      font-weight: 600;
      font-family: Consolas, monospace;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-speed:hover { color: #fff; border-color: #3b5280; }
    .btn-speed.active {
      background: var(--accent-cyan);
      color: #082f49;
      border-color: var(--accent-cyan);
      font-weight: 700;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.35);
    }

    .slider-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      color: var(--text-muted);
    }

    .slider-row input[type="range"] {
      flex: 1;
      accent-color: var(--accent-cyan);
      cursor: pointer;
    }

    .toggles-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 7px 10px;
      padding-top: 6px;
      border-top: 1px solid rgba(36, 50, 79, 0.65);
    }

    .toggle-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #cbd5e1;
      cursor: pointer;
      user-select: none;
    }
    .toggle-item input { accent-color: var(--accent-green); cursor: pointer; }

    /* Compact Metrics Row */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 7px;
    }

    .metric-box {
      background: #0a101d;
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 7px 6px;
      text-align: center;
    }
    .metric-label { font-size: 10.5px; color: var(--text-muted); }
    .metric-val { font-size: 15px; font-weight: 700; font-family: Consolas, monospace; margin-top: 2px; }
    .c-green { color: var(--accent-green); }
    .c-rose { color: var(--accent-rose); }
    .c-amber { color: var(--accent-amber); }
    .c-cyan { color: var(--accent-cyan); }

    /* Live Logs Panel */
    .log-card {
      flex: 1;
      min-height: 280px;
      overflow: hidden;
    }

    .log-filters {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .btn-filter {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 6px;
      border: 1px solid var(--border);
      background: #0a101d;
      color: var(--text-muted);
      cursor: pointer;
    }
    .btn-filter.active {
      background: rgba(16, 185, 129, 0.16);
      color: #34d399;
      border-color: rgba(16, 185, 129, 0.4);
      font-weight: 600;
    }

    .log-console {
      flex: 1;
      background: #070b14;
      border: 1px solid #1c2842;
      border-radius: 10px;
      padding: 8px;
      overflow-y: auto;
      font-family: Consolas, "Courier New", "Microsoft YaHei", monospace;
      font-size: 11.5px;
      line-height: 1.48;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .log-entry {
      padding: 4px 7px;
      border-radius: 6px;
      border-left: 3px solid transparent;
      word-break: break-all;
      cursor: pointer;
      transition: background 0.12s;
    }
    .log-entry:hover { background: rgba(255, 255, 255, 0.04); }

    .log-sys { color: #94a3b8; border-left-color: #475569; }
    .log-track { color: #93c5fd; border-left-color: #0284c7; }
    .log-fsm { color: #c4b5fd; border-left-color: #7c3aed; }
    .log-tp {
      background: rgba(16, 185, 129, 0.12);
      color: #6ee7b7;
      border-left-color: #10b981;
      font-weight: 600;
    }
    .log-fp {
      background: rgba(244, 63, 94, 0.12);
      color: #fda4af;
      border-left-color: #f43f5e;
      font-weight: 600;
    }
    .log-fn {
      background: rgba(251, 191, 36, 0.12);
      color: #fde68a;
      border-left-color: #f59e0b;
      font-weight: 600;
    }

    .log-fnum {
      display: inline-block;
      min-width: 46px;
      color: #38bdf8;
      font-weight: 700;
    }

    .log-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-dim);
    }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header class="top-header">
    <div class="brand">
      <div class="brand-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#06281e" stroke-width="2.3">
          <circle cx="12" cy="12" r="9"></circle>
          <path d="M12 3a9 9 0 0 1 9 9M3 12a9 9 0 0 1 9-9"></path>
          <circle cx="12" cy="12" r="3" fill="#06281e"></circle>
        </svg>
      </div>
      <div>
        <div class="brand-title-row">
          <h1>乒羽智瞳 · 验证集视频轨迹与落点分析台</h1>
          <span class="badge-f1-global">全验证集 15 视频 · Macro F1 = 0.9448 (TP=90, FP=8, FN=2)</span>
        </div>
        <div class="brand-sub">真实比赛原片同步回放 · 实时绘制运动轨迹并高亮注明触台落点 · 右侧配备多档调速与逐帧检测日志</div>
      </div>
    </div>

    <div class="video-nav-bar">
      <button id="btnPrevVid" class="btn-nav" title="切换到上一条验证视频">◀ 上一条</button>
      <select id="videoSelect" class="video-select"></select>
      <button id="btnNextVid" class="btn-nav" title="切换到下一条验证视频">下一条 ▶</button>
      <span id="videoBadge" class="angle-pill">0度视角</span>
    </div>
  </header>

  <!-- Main Workspace -->
  <main class="workspace">

    <!-- Left: Video Stage & Timeline Scrubber -->
    <section class="stage-col">
      <div class="video-stage" id="stageContainer">
        <video id="bgVideo" playsinline muted preload="auto"></video>
        <canvas id="viewCanvas" width="1920" height="1080"></canvas>

        <!-- HUD Top Left -->
        <div class="hud-top-left">
          <div class="hud-pill">
            <span class="dot-live" id="playIndicator"></span>
            <span>帧号: <b id="telemetryFrame" class="c-green">0</b> / <span id="telemetryTotal">124</span></span>
            <span style="color:#475569">|</span>
            <span>时间: <b id="telemetryTime" class="c-cyan">0.00</b>s</span>
            <span style="color:#475569">|</span>
            <span>FPS: <b id="telemetryFps">25</b></span>
          </div>
          <div class="hud-pill">
            <span>球心: (<b id="telemetryX" class="c-amber">--</b>, <b id="telemetryY" class="c-amber">--</b>)</span>
            <span style="color:#475569">|</span>
            <span>速度: <b id="telemetryV" style="color:#c4b5fd">--</b> px/f</span>
            <span style="color:#475569">|</span>
            <span>状态: <b id="telemetryState" class="c-green">准备就绪</b></span>
          </div>
        </div>

        <!-- HUD Bottom Left Compact Legend -->
        <div class="hud-bottom-left">
          <div class="legend-item"><span class="lg-line"></span><span>运动轨迹</span></div>
          <div class="legend-item"><span class="lg-dot" style="background:#10b981;"></span><span>落点 TP✓</span></div>
          <div class="legend-item"><span class="lg-dot" style="background:#f43f5e;"></span><span>误检 FP</span></div>
          <div class="legend-item"><span class="lg-diamond"></span><span>真值标靶 GT</span></div>
        </div>

        <!-- Bottom Right Source Status -->
        <div class="video-source-bar">
          <div class="source-status" id="videoSourceStatus">正在自动加载验证集原片...</div>
          <label for="videoFileInput" class="btn-pick-file" title="如本地路径异常可手动指定 MP4 文件">更换本地视频</label>
          <input type="file" id="videoFileInput" accept="video/mp4" style="display:none;">
        </div>
      </div>

      <!-- Scrubber & Main Play Controls -->
      <div class="player-controls">
        <div class="timeline-wrap" title="进度条上的彩色竖标指示所有触台落点帧号，点击可直达">
          <div class="timeline-ticks" id="timelineTicks"></div>
          <input type="range" id="frameSlider" class="scrubber" min="0" max="100" value="0">
        </div>

        <div class="controls-row">
          <div class="btn-group">
            <button id="btnPlay" class="btn-primary" title="播放/暂停 (空格键)">
              <span id="iconPlay">▶</span>
              <span id="textPlay">播放视频</span>
            </button>
            <button id="btnPrevFrame" class="btn-ctrl" title="后退一帧 (左方向键 ←)">◀ 上一帧</button>
            <button id="btnNextFrame" class="btn-ctrl" title="前进一帧 (右方向键 →)">下一帧 ▶</button>
            <button id="btnPrevLanding" class="btn-ctrl" title="跳转到上一个预测落点">⏮ 上一落点</button>
            <button id="btnNextLanding" class="btn-ctrl" title="跳转到下一个预测落点">下一落点 ⏭</button>
          </div>

          <div class="btn-group">
            <label class="toggle-item">
              <input type="checkbox" id="loopCheckbox" checked>
              <span>循环播放</span>
            </label>
          </div>
        </div>

        <!-- Quick Landing Jump Chips -->
        <div class="quick-landings-bar">
          <span class="ql-label">本片落点直达:</span>
          <div id="landingChipsContainer" style="display:flex; flex-wrap:wrap; gap:6px;"></div>
        </div>
      </div>
    </section>

    <!-- Right: Side Panel with Speed Controller, Metrics, & Live Log Console -->
    <aside class="side-panel">

      <!-- Card 1: Playback Speed & Layer Controls -->
      <div class="panel-card">
        <div class="card-header">
          <div class="card-title">
            <span>⚡ 播放速度调节与图层显示</span>
          </div>
          <span class="speed-readout" id="speedReadout">1.00× (原速 25fps)</span>
        </div>

        <div class="speed-presets" id="speedPresets">
          <button class="btn-speed" data-speed="0.1">0.1×</button>
          <button class="btn-speed" data-speed="0.25">0.25×</button>
          <button class="btn-speed" data-speed="0.5">0.5×</button>
          <button class="btn-speed active" data-speed="1">1.0×</button>
          <button class="btn-speed" data-speed="1.5">1.5×</button>
          <button class="btn-speed" data-speed="2">2.0×</button>
        </div>

        <div class="slider-row">
          <span style="min-width:56px;">倍速微调:</span>
          <input type="range" id="speedSlider" min="0.1" max="2.0" step="0.05" value="1.0">
          <span style="min-width:44px; text-align:right;" id="speedFpsText">25.0 fps</span>
        </div>

        <div class="slider-row">
          <span style="min-width:56px;">尾迹长度:</span>
          <input type="range" id="trailLenSlider" min="6" max="120" step="2" value="28">
          <span style="min-width:44px; text-align:right;" id="trailLenText">28 帧</span>
        </div>

        <div class="toggles-grid">
          <label class="toggle-item"><input type="checkbox" id="layerTrail" checked><span>标注飞行轨迹线</span></label>
          <label class="toggle-item"><input type="checkbox" id="layerLandingLabels" checked><span>画面注明落点标签</span></label>
          <label class="toggle-item"><input type="checkbox" id="layerGT" checked><span>显示官方真值标靶</span></label>
          <label class="toggle-item"><input type="checkbox" id="layerFutureLandings"><span>预显全片所有落点</span></label>
          <label class="toggle-item"><input type="checkbox" id="layerVectors" checked><span>显示球速矢量箭头</span></label>
          <label class="toggle-item"><input type="checkbox" id="layerROI"><span>显示台面门控 ROI</span></label>
        </div>
      </div>

      <!-- Card 2: Current Video Metrics -->
      <div class="panel-card" style="padding:11px 14px;">
        <div class="card-header">
          <div class="card-title">📊 当前视频评测指标</div>
          <span style="font-size:11px; color:var(--text-muted);" id="matchTitleLabel">--</span>
        </div>
        <div class="metrics-grid">
          <div class="metric-box">
            <div class="metric-label">命中 (TP)</div>
            <div class="metric-val c-green" id="statTP">0</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">误检 (FP)</div>
            <div class="metric-val c-rose" id="statFP">0</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">漏检 (FN)</div>
            <div class="metric-val c-amber" id="statFN">0</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">单片 F1</div>
            <div class="metric-val c-cyan" id="statF1">1.000</div>
          </div>
        </div>
      </div>

      <!-- Card 3: Live Event & Algorithm Log Console -->
      <div class="panel-card log-card">
        <div class="card-header">
          <div class="card-title">📜 实时检测日志面板</div>
          <div class="log-filters">
            <button class="btn-filter active" id="filterAll">全部日志</button>
            <button class="btn-filter" id="filterEvents">仅落点/告警</button>
            <button class="btn-filter" id="btnClearLog">清空</button>
          </div>
        </div>

        <div class="log-console" id="logConsole"></div>

        <div class="log-footer">
          <label class="toggle-item" style="font-size:11px;">
            <input type="checkbox" id="autoScrollLog" checked>
            <span>自动滚动跟踪最新日志</span>
          </label>
          <span>提示：点击任意日志行可跳转该帧</span>
        </div>
      </div>

    </aside>
  </main>

  <!-- Embedded Dataset -->
  <script>
    const VIS_DATA = __VIS_DATA__;
  </script>

  <script>
    const ROI_CONFIGS = {
      "0度":  { rx0: 0.35, rx1: 0.65, ry0: 0.25, ry1: 0.60 },
      "45度": { rx0: 0.25, rx1: 0.75, ry0: 0.35, ry1: 0.61 },
      "90度": { rx0: 0.37, rx1: 0.64, ry0: 0.38, ry1: 0.72 }
    };

    const VIDEO_IDS = Object.keys(VIS_DATA);
    let currentVid = VIDEO_IDS[0] || "v000001";
    let currentFrame = 0;
    let lastLoggedFrame = -1;
    let isPlaying = false;
    let playbackSpeed = 1.0;
    let trailLength = 28;
    let hasVideoFile = false;
    let rafId = null;
    let fallbackTimer = null;
    let logFilterMode = "all"; // "all" | "events"
    let logCount = 0;

    // DOM Elements
    const videoSelect = document.getElementById('videoSelect');
    const videoBadge = document.getElementById('videoBadge');
    const btnPrevVid = document.getElementById('btnPrevVid');
    const btnNextVid = document.getElementById('btnNextVid');

    const bgVideo = document.getElementById('bgVideo');
    const viewCanvas = document.getElementById('viewCanvas');
    const ctx = viewCanvas.getContext('2d');
    const videoSourceStatus = document.getElementById('videoSourceStatus');
    const videoFileInput = document.getElementById('videoFileInput');

    const frameSlider = document.getElementById('frameSlider');
    const timelineTicks = document.getElementById('timelineTicks');
    const landingChipsContainer = document.getElementById('landingChipsContainer');

    const btnPlay = document.getElementById('btnPlay');
    const iconPlay = document.getElementById('iconPlay');
    const textPlay = document.getElementById('textPlay');
    const playIndicator = document.getElementById('playIndicator');
    const btnPrevFrame = document.getElementById('btnPrevFrame');
    const btnNextFrame = document.getElementById('btnNextFrame');
    const btnPrevLanding = document.getElementById('btnPrevLanding');
    const btnNextLanding = document.getElementById('btnNextLanding');
    const loopCheckbox = document.getElementById('loopCheckbox');

    // Speed & Layer Elements
    const speedPresets = document.getElementById('speedPresets');
    const speedSlider = document.getElementById('speedSlider');
    const speedReadout = document.getElementById('speedReadout');
    const speedFpsText = document.getElementById('speedFpsText');
    const trailLenSlider = document.getElementById('trailLenSlider');
    const trailLenText = document.getElementById('trailLenText');

    const layerTrail = document.getElementById('layerTrail');
    const layerLandingLabels = document.getElementById('layerLandingLabels');
    const layerGT = document.getElementById('layerGT');
    const layerFutureLandings = document.getElementById('layerFutureLandings');
    const layerVectors = document.getElementById('layerVectors');
    const layerROI = document.getElementById('layerROI');

    // Telemetry & Stats
    const telemetryFrame = document.getElementById('telemetryFrame');
    const telemetryTotal = document.getElementById('telemetryTotal');
    const telemetryTime = document.getElementById('telemetryTime');
    const telemetryFps = document.getElementById('telemetryFps');
    const telemetryX = document.getElementById('telemetryX');
    const telemetryY = document.getElementById('telemetryY');
    const telemetryV = document.getElementById('telemetryV');
    const telemetryState = document.getElementById('telemetryState');

    const statTP = document.getElementById('statTP');
    const statFP = document.getElementById('statFP');
    const statFN = document.getElementById('statFN');
    const statF1 = document.getElementById('statF1');
    const matchTitleLabel = document.getElementById('matchTitleLabel');

    // Logs
    const logConsole = document.getElementById('logConsole');
    const filterAll = document.getElementById('filterAll');
    const filterEvents = document.getElementById('filterEvents');
    const btnClearLog = document.getElementById('btnClearLog');
    const autoScrollLog = document.getElementById('autoScrollLog');

    function appendLog(type, frameIdx, message) {
      const isEvent = (type === 'tp' || type === 'fp' || type === 'fn' || type === 'sys' || type === 'fsm');
      const div = document.createElement('div');
      div.className = `log-entry log-${type}`;
      div.dataset.isEvent = isEvent ? "1" : "0";
      if (logFilterMode === "events" && !isEvent) {
        div.style.display = "none";
      }

      const fLabel = frameIdx !== null ? `[F${String(frameIdx).padStart(4, '0')}]` : `[系统 ]`;
      div.innerHTML = `<span class="log-fnum">${fLabel}</span> ${message}`;
      if (frameIdx !== null) {
        div.onclick = () => {
          pause();
          seekTo(frameIdx);
        };
      }

      logConsole.appendChild(div);
      logCount++;
      while (logConsole.children.length > 350) {
        logConsole.removeChild(logConsole.firstChild);
      }

      if (autoScrollLog.checked) {
        logConsole.scrollTop = logConsole.scrollHeight;
      }
    }

    function applyLogFilter() {
      Array.from(logConsole.children).forEach(node => {
        if (logFilterMode === "events" && node.dataset.isEvent !== "1") {
          node.style.display = "none";
        } else {
          node.style.display = "";
        }
      });
      if (autoScrollLog.checked) {
        logConsole.scrollTop = logConsole.scrollHeight;
      }
    }

    function getVideoUrl(v) {
      if (!v || !v.rel_path) return "";
      const encodedRel = v.rel_path.split('/').map(seg => encodeURIComponent(seg)).join('/');
      if (window.location.protocol.startsWith('http')) {
        return '/' + encodedRel;
      }
      return './participant/pingpang/public_data/' + encodedRel;
    }

    function initDropdown() {
      videoSelect.innerHTML = "";
      VIDEO_IDS.forEach(vid => {
        const item = VIS_DATA[vid];
        const opt = document.createElement('option');
        opt.value = vid;
        const shortName = item.match_name ? item.match_name.slice(0, 18) : vid;
        opt.textContent = `${vid} [${item.angle}] ${shortName} (落点:${item.preds.length}, F1=${item.stats.f1.toFixed(3)})`;
        videoSelect.appendChild(opt);
      });
      videoSelect.value = currentVid;
      loadVideoData(currentVid);
    }

    function loadVideoData(vid) {
      pause();
      currentVid = vid;
      videoSelect.value = vid;
      currentFrame = 0;
      lastLoggedFrame = -1;
      const v = VIS_DATA[vid];
      if (!v) return;

      // Resize canvas coordinate buffer to match exact video dimensions
      viewCanvas.width = v.width;
      viewCanvas.height = v.height;

      videoBadge.textContent = `${v.angle}视角 · ${v.width}×${v.height} @ ${v.fps}fps`;
      matchTitleLabel.textContent = v.match_name || vid;
      telemetryFps.textContent = v.fps;
      telemetryTotal.textContent = v.n_frames - 1;

      frameSlider.min = 0;
      frameSlider.max = v.n_frames - 1;
      frameSlider.value = 0;

      // Update Stats
      statTP.textContent = v.stats.tp;
      statFP.textContent = v.stats.fp;
      statFN.textContent = v.stats.fn;
      statF1.textContent = v.stats.f1.toFixed(3);

      // Update speed readout for current video fps
      updateSpeedUI();

      // Build timeline ticks & quick landing chips
      buildTimelineAndChips(v);

      // Auto-load real MP4 video
      hasVideoFile = false;
      videoSourceStatus.textContent = "⏳ 正在加载真实比赛原片...";
      videoSourceStatus.style.color = "#93c5fd";
      const srcUrl = getVideoUrl(v);
      bgVideo.src = srcUrl;
      bgVideo.playbackRate = playbackSpeed;
      bgVideo.load();

      appendLog('sys', null, `切换至验证集视频 <b>${vid}</b> [${v.angle}] ${v.match_name || ''} (${v.n_frames}帧, ${v.fps}fps)`);
      appendLog('sys', null, `统计摘要：TP=${v.stats.tp}, FP=${v.stats.fp}, FN=${v.stats.fn}, F1=${v.stats.f1.toFixed(4)} | 点击 ▶ 播放自动追踪轨迹与落点`);

      renderFrame(0, false);
    }

    bgVideo.onloadeddata = () => {
      hasVideoFile = true;
      bgVideo.playbackRate = playbackSpeed;
      const v = VIS_DATA[currentVid];
      videoSourceStatus.textContent = `✓ 原片已就绪 (${v.width}×${v.height} · ${v.fps}fps)`;
      videoSourceStatus.style.color = "#34d399";
      appendLog('sys', null, `真实比赛原片加载成功，已激活音画帧级对齐模式 (${v.fps} fps)`);
      renderFrame(currentFrame, false);
    };

    bgVideo.onerror = () => {
      hasVideoFile = false;
      videoSourceStatus.textContent = "⚠ 未能直连原片，已启用 3D 球台仿真视图（或手动选文件）";
      videoSourceStatus.style.color = "#fbbf24";
      appendLog('sys', null, `提示：当前未能加载原片视频流，已切换为 3D 仿真球台轨迹回放（可通过 localhost 服务或右侧“更换本地视频”挂载）`);
      renderFrame(currentFrame, false);
    };

    function buildTimelineAndChips(v) {
      timelineTicks.innerHTML = "";
      landingChipsContainer.innerHTML = "";

      const events = [];
      v.preds.forEach((p, idx) => {
        events.push({
          seq: idx + 1,
          type: p.is_tp ? 'tp' : 'fp',
          frame_id: p.frame_id,
          x: p.x,
          y: p.y,
          mode: p.mode || '物理极值反弹',
          impulse: p.impulse || 0,
          error_px: p.error_px
        });
      });

      // Add missed valid GTs (FN)
      v.gts.forEach(g => {
        if (g.valid && !g.is_hit) {
          events.push({
            seq: '漏',
            type: 'fn',
            frame_id: g.frame_id,
            x: g.x,
            y: g.y,
            mode: '官方真值未检出 (FN)',
            impulse: 0,
            error_px: null
          });
        }
      });

      events.sort((a, b) => a.frame_id - b.frame_id);

      if (events.length === 0) {
        landingChipsContainer.innerHTML = '<span style="font-size:11.5px; color:#64748b;">本片段无触台落点</span>';
        return;
      }

      const maxF = Math.max(1, v.n_frames - 1);
      events.forEach(ev => {
        // Tick on scrubber bar
        const tick = document.createElement('div');
        tick.className = `tick-mark tick-${ev.type}`;
        tick.style.left = `${(ev.frame_id / maxF) * 100}%`;
        tick.title = `第 ${ev.frame_id} 帧: ${ev.type.toUpperCase()} (${ev.x.toFixed(0)}, ${ev.y.toFixed(0)})`;
        tick.onclick = () => { pause(); seekTo(ev.frame_id); };
        timelineTicks.appendChild(tick);

        // Quick jump chip
        const chip = document.createElement('button');
        chip.className = `ql-chip ${ev.type}`;
        chip.dataset.frame = ev.frame_id;
        const statusTxt = ev.type === 'tp' ? '✓' : (ev.type === 'fp' ? '误' : '漏');
        chip.textContent = `#${ev.seq} F${ev.frame_id} ${statusTxt}`;
        chip.title = `${ev.mode} | 坐标 (${ev.x.toFixed(0)}, ${ev.y.toFixed(0)})`;
        chip.onclick = () => { pause(); seekTo(ev.frame_id); };
        landingChipsContainer.appendChild(chip);
      });
    }

    function logFrameEvents(v, frameIdx) {
      if (frameIdx === lastLoggedFrame) return;

      // Never skip landing logs during normal forward playback even if animation ticks jump >4 frames
      const startF = (frameIdx > lastLoggedFrame && frameIdx - lastLoggedFrame <= 45)
        ? lastLoggedFrame + 1
        : frameIdx;
      for (let f = startF; f <= frameIdx; f++) {
        let hitLandingOnF = false;
        // Check predicted landings on exact frame f
        v.preds.forEach((p, idx) => {
          if (p.frame_id === f) {
            hitLandingOnF = true;
            if (p.is_tp) {
              const errStr = p.error_px !== null ? `误差 ${p.error_px}px` : '';
              appendLog('tp', f, `★ <b>[落点 #${idx + 1} · 命中 TP ✓]</b> (${p.x.toFixed(0)}, ${p.y.toFixed(0)}) | ${p.mode} | Δvy=${p.impulse} | ${errStr}`);
              appendLog('fsm', f + 1, `触发不应期保护窗口 (+2~+7 帧)，屏蔽球拍反拉二次拐点`);
            } else if (!p.is_ignored) {
              appendLog('fp', f, `⚠ <b>[落点 #${idx + 1} · 误检 FP]</b> (${p.x.toFixed(0)}, ${p.y.toFixed(0)}) | ${p.mode} | Δvy=${p.impulse} (无对应真值)`);
            }
          }
        });

        // Check missed GTs on exact frame f
        v.gts.forEach(g => {
          if (g.valid && !g.is_hit && g.frame_id === f) {
            appendLog('fn', f, `⚠ <b>[真值漏检 FN]</b> 官方落点 (${g.x.toFixed(0)}, ${g.y.toFixed(0)}) 未触发状态机阈值`);
          }
        });

        // Periodic trajectory log (every 5 frames)
        if (!hitLandingOnF && f % 5 === 0 && v.traj[f]) {
          const pt = v.traj[f];
          let prev = null, dt = 1;
          for (let d = 1; d <= 3; d++) {
            if (v.traj[f - d]) { prev = v.traj[f - d]; dt = d; break; }
          }
          let vStr = "速度 --";
          if (prev) {
            const vx = (pt.x - prev.x) / dt;
            const vy = (pt.y - prev.y) / dt;
            const spd = Math.hypot(vx, vy);
            vStr = `v=${spd.toFixed(1)} px/f (vx=${vx>=0?'+':''}${vx.toFixed(1)}, vy=${vy>=0?'+':''}${vy.toFixed(1)})`;
          }
          appendLog('track', f, `追踪球心 (${pt.x.toFixed(1)}, ${pt.y.toFixed(1)}) | ${vStr}`);
        }
      }
      lastLoggedFrame = frameIdx;
    }

    function drawRoundRect(x, y, w, h, r, fill, stroke, lineW=1.5) {
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, r);
      if (fill) {
        ctx.fillStyle = fill;
        ctx.fill();
      }
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = lineW;
        ctx.stroke();
      }
    }

    function drawLandingCallout(x, y, line1, line2, borderColor, bgColor, W, H, offsetIdx=0) {
      ctx.save();
      ctx.font = 'bold 26px "Microsoft YaHei", sans-serif';
      const w1 = ctx.measureText(line1).width;
      ctx.font = 'bold 19px Consolas, "Microsoft YaHei", monospace';
      const w2 = line2 ? ctx.measureText(line2).width : 0;
      const boxW = Math.max(w1, w2) + 32;
      const boxH = line2 ? 74 : 44;

      // Smart flip to avoid overflowing edges
      const preferRight = (x < W * 0.62);
      const preferUp = (y > H * 0.30);
      const shiftX = preferRight ? 46 : -(46 + boxW);
      const shiftY = preferUp ? -(78 + boxH + offsetIdx * 82) : (48 + offsetIdx * 82);

      let bx = Math.min(Math.max(18, x + shiftX), W - boxW - 18);
      let by = Math.min(Math.max(76, y + shiftY), H - boxH - 18);

      // Leader line
      const anchorX = preferRight ? bx : bx + boxW;
      const anchorY = by + boxH / 2;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(anchorX, anchorY);
      ctx.strokeStyle = borderColor;
      ctx.lineWidth = 3.2;
      ctx.stroke();

      // Callout box with crisp glow border
      ctx.shadowColor = 'rgba(0, 0, 0, 0.55)';
      ctx.shadowBlur = 12;
      drawRoundRect(bx, by, boxW, boxH, 10, bgColor, borderColor, 2.8);
      ctx.shadowBlur = 0;

      // Texts
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 26px "Microsoft YaHei", sans-serif';
      ctx.fillText(line1, bx + 16, by + 32);
      if (line2) {
        ctx.fillStyle = '#e2e8f0';
        ctx.font = 'bold 19px Consolas, "Microsoft YaHei", monospace';
        ctx.fillText(line2, bx + 16, by + 60);
      }
      ctx.restore();
    }

    function renderFrame(frameIdx, emitLogs=true) {
      const v = VIS_DATA[currentVid];
      if (!v) return;

      frameIdx = Math.max(0, Math.min(v.n_frames - 1, Math.round(frameIdx)));
      currentFrame = frameIdx;
      frameSlider.value = frameIdx;

      if (emitLogs && isPlaying) {
        logFrameEvents(v, frameIdx);
      }

      // Highlight active quick chip
      Array.from(landingChipsContainer.children).forEach(ch => {
        const f = parseInt(ch.dataset.frame);
        if (Math.abs(f - frameIdx) <= 2) {
          ch.classList.add('active');
        } else {
          ch.classList.remove('active');
        }
      });

      // Update Top-left HUD
      telemetryFrame.textContent = frameIdx;
      telemetryTime.textContent = (frameIdx / v.fps).toFixed(2);

      const pt = v.traj[frameIdx];
      if (pt) {
        telemetryX.textContent = pt.x.toFixed(1);
        telemetryY.textContent = pt.y.toFixed(1);
        let prevPt = null, dt = 1;
        for (let d = 1; d <= 3; d++) {
          if (v.traj[frameIdx - d]) { prevPt = v.traj[frameIdx - d]; dt = d; break; }
        }
        if (prevPt) {
          const vx = (pt.x - prevPt.x) / dt;
          const vy = (pt.y - prevPt.y) / dt;
          telemetryV.textContent = Math.hypot(vx, vy).toFixed(1);
          if (vy > 1.5) {
            telemetryState.textContent = "下落逼近台面";
            telemetryState.style.color = "#38bdf8";
          } else if (vy < -1.5) {
            telemetryState.textContent = "触台起跳上升";
            telemetryState.style.color = "#a5b4fc";
          } else {
            telemetryState.textContent = "水平飞行拐点";
            telemetryState.style.color = "#34d399";
          }
        } else {
          telemetryV.textContent = "--";
        }
      } else {
        telemetryX.textContent = "--";
        telemetryY.textContent = "--";
        telemetryV.textContent = "--";
        telemetryState.textContent = "遮挡/出画外推";
        telemetryState.style.color = "#64748b";
      }

      const activeLanding = v.preds.find(p => Math.abs(p.frame_id - frameIdx) <= 2);
      if (activeLanding) {
        telemetryState.textContent = activeLanding.is_tp ? "★ 触台落点爆发 (TP ✓)" : "⚠ 候选落点 (FP)";
        telemetryState.style.color = activeLanding.is_tp ? "#10b981" : "#f43f5e";
      }

      const W = viewCanvas.width;
      const H = viewCanvas.height;
      ctx.clearRect(0, 0, W, H);

      if (!hasVideoFile) {
        drawSimulatedCourt(v.angle, W, H);
      }

      // 1. ROI Overlay
      if (layerROI.checked) {
        const roi = ROI_CONFIGS[v.angle] || ROI_CONFIGS["45度"];
        const rx = roi.rx0 * W, ry = roi.ry0 * H;
        const rw = (roi.rx1 - roi.rx0) * W, rh = (roi.ry1 - roi.ry0) * H;
        ctx.save();
        ctx.strokeStyle = 'rgba(244, 63, 94, 0.55)';
        ctx.lineWidth = 2.5;
        ctx.setLineDash([10, 6]);
        ctx.strokeRect(rx, ry, rw, rh);
        ctx.fillStyle = 'rgba(244, 63, 94, 0.04)';
        ctx.fillRect(rx, ry, rw, rh);
        ctx.fillStyle = 'rgba(253, 164, 175, 0.9)';
        ctx.font = 'bold 18px "Microsoft YaHei", sans-serif';
        ctx.fillText(`[${v.angle}] 球台空间物理门控域 (ROI)`, rx + 12, ry + 26);
        ctx.restore();
      }

      // 2. Dynamic Ball Trajectory Comet Trail
      if (layerTrail.checked) {
        const pts = [];
        const startF = Math.max(0, frameIdx - trailLength);
        for (let f = startF; f <= frameIdx; f++) {
          if (v.traj[f]) pts.push({ f, x: v.traj[f].x, y: v.traj[f].y });
        }
        if (pts.length > 1) {
          ctx.save();
          for (let i = 1; i < pts.length; i++) {
            const p0 = pts[i - 1];
            const p1 = pts[i];
            if (p1.f - p0.f > 5) continue; // Do not connect across long occlusion gaps
            const ratio = i / pts.length;
            ctx.beginPath();
            ctx.moveTo(p0.x, p0.y);
            ctx.lineTo(p1.x, p1.y);
            ctx.strokeStyle = `rgba(56, 189, 248, ${0.18 + ratio * 0.82})`;
            ctx.lineWidth = 2.5 + ratio * 6.5;
            ctx.lineCap = 'round';
            ctx.stroke();

            // Subtle breadcrumb nodes
            if (i % 2 === 0 && ratio > 0.3) {
              ctx.beginPath();
              ctx.arc(p1.x, p1.y, 2.5 + ratio * 2, 0, Math.PI * 2);
              ctx.fillStyle = `rgba(224, 242, 254, ${ratio * 0.85})`;
              ctx.fill();
            }
          }
          ctx.restore();
        }
      }

      // 3. Ground Truth Markers (Diamond Targets)
      if (layerGT.checked) {
        v.gts.forEach(g => {
          const isReached = g.frame_id <= frameIdx || layerFutureLandings.checked;
          if (!isReached && Math.abs(g.frame_id - frameIdx) > 2) return;

          const isActiveWindow = (frameIdx >= g.frame_id - 2 && frameIdx <= g.frame_id + 14);
          ctx.save();
          ctx.translate(g.x, g.y);
          ctx.rotate(Math.PI / 4);
          const sz = isActiveWindow ? 12 : 8;
          ctx.fillStyle = g.valid ? 'rgba(251, 191, 36, 0.92)' : 'rgba(148, 163, 184, 0.7)';
          ctx.fillRect(-sz, -sz, sz * 2, sz * 2);
          ctx.strokeStyle = '#000000';
          ctx.lineWidth = 2;
          ctx.strokeRect(-sz, -sz, sz * 2, sz * 2);
          ctx.restore();

          // Missed GT highlight alert (FN)
          if (g.valid && !g.is_hit && isActiveWindow && layerLandingLabels.checked) {
            drawLandingCallout(
              g.x, g.y,
              `⚠ 真值漏检 (FN) · 第 ${g.frame_id} 帧`,
              `人工真值 (${g.x.toFixed(0)}, ${g.y.toFixed(0)})`,
              '#f59e0b', 'rgba(120, 53, 15, 0.88)', W, H, 1
            );
          }
        });
      }

      // 4. Predicted Landings & Explicit Labels
      let latestActivePredIdx = -1;
      v.preds.forEach((p, idx) => {
        if (frameIdx >= p.frame_id - 1 && frameIdx <= p.frame_id + 15) {
          latestActivePredIdx = idx;
        }
      });

      v.preds.forEach((p, idx) => {
        const isReached = (p.frame_id <= frameIdx) || layerFutureLandings.checked;
        if (!isReached && Math.abs(p.frame_id - frameIdx) > 2) return;

        const isActivePulse = (idx === latestActivePredIdx);
        const colMain = p.is_tp ? '#10b981' : '#f43f5e';
        const colGlow = p.is_tp ? 'rgba(16, 185, 129, ' : 'rgba(244, 63, 94, ';

        ctx.save();
        if (isActivePulse) {
          // Animated pulsing wave based on age
          const age = Math.max(0, frameIdx - p.frame_id);
          const r1 = 22 + age * 2.2;
          const alpha = Math.max(0.15, 0.85 - age * 0.045);
          ctx.beginPath();
          ctx.arc(p.x, p.y, r1, 0, Math.PI * 2);
          ctx.strokeStyle = `${colGlow}${alpha})`;
          ctx.lineWidth = 4.5;
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(p.x, p.y, 18, 0, Math.PI * 2);
          ctx.fillStyle = `${colGlow}0.32)`;
          ctx.fill();
        }

        // Solid Landing Center Marker
        ctx.beginPath();
        ctx.arc(p.x, p.y, isActivePulse ? 11 : 8, 0, Math.PI * 2);
        ctx.fillStyle = colMain;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // Compact persistent pin badge for earlier bounces, big callout ONLY for latest active bounce!
        if (layerLandingLabels.checked) {
          if (isActivePulse) {
            const tagTitle = p.is_tp
              ? `★ 落点 #${idx + 1} · 命中 TP ✓ (第 ${p.frame_id} 帧)`
              : `⚠ 落点 #${idx + 1} · 误检 FP (第 ${p.frame_id} 帧)`;
            const errTxt = p.error_px !== null ? `误差:${p.error_px}px` : '无真值';
            const tagSub = `(${p.x.toFixed(0)},${p.y.toFixed(0)}) | ${p.mode || ''} | ${errTxt}`;
            const bgRgba = p.is_tp ? 'rgba(6, 78, 59, 0.92)' : 'rgba(136, 19, 55, 0.92)';
            drawLandingCallout(p.x, p.y, tagTitle, tagSub, colMain, bgRgba, W, H, 0);
          } else {
            // Compact tag so court stays readable
            const pinTxt = `#${idx + 1} F${p.frame_id}${p.is_tp ? '✓' : '✗'}`;
            ctx.font = 'bold 20px Consolas, sans-serif';
            const tw = ctx.measureText(pinTxt).width + 16;
            drawRoundRect(p.x + 14, p.y - 16, tw, 28, 6, 'rgba(15, 23, 42, 0.88)', colMain, 1.8);
            ctx.fillStyle = '#ffffff';
            ctx.fillText(pinTxt, p.x + 22, p.y + 5);
          }
        }
        ctx.restore();
      });

      // 5. Current Ball Target Reticle & Velocity Vector
      if (pt) {
        ctx.save();
        // Outer reticle ring
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 16, 0, Math.PI * 2);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.2;
        ctx.stroke();

        // Center luminous ball highlight
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 7, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.shadowColor = '#38bdf8';
        ctx.shadowBlur = 14;
        ctx.fill();

        // Velocity Vector Arrow
        if (layerVectors.checked && v.traj[frameIdx - 1]) {
          const prev = v.traj[frameIdx - 1];
          const vx = (pt.x - prev.x) * 2.4;
          const vy = (pt.y - prev.y) * 2.4;
          if (Math.hypot(vx, vy) > 4) {
            ctx.shadowBlur = 0;
            ctx.beginPath();
            ctx.moveTo(pt.x, pt.y);
            ctx.lineTo(pt.x + vx, pt.y + vy);
            ctx.strokeStyle = '#fbbf24';
            ctx.lineWidth = 3.2;
            ctx.stroke();

            const ang = Math.atan2(vy, vx);
            ctx.beginPath();
            ctx.moveTo(pt.x + vx, pt.y + vy);
            ctx.lineTo(pt.x + vx - 12 * Math.cos(ang - Math.PI / 6), pt.y + vy - 12 * Math.sin(ang - Math.PI / 6));
            ctx.lineTo(pt.x + vx - 12 * Math.cos(ang + Math.PI / 6), pt.y + vy - 12 * Math.sin(ang + Math.PI / 6));
            ctx.closePath();
            ctx.fillStyle = '#fbbf24';
            ctx.fill();
          }
        }
        ctx.restore();
      }
    }

    function drawSimulatedCourt(angle, W, H) {
      ctx.fillStyle = '#090e1a';
      ctx.fillRect(0, 0, W, H);
      ctx.save();
      const poly = (pts) => {
        ctx.beginPath();
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
        ctx.closePath();
        ctx.fillStyle = '#1e3a8a';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 4;
        ctx.stroke();
      };
      if (angle === "0度") {
        poly([[720, 420], [1200, 420], [1420, 680], [500, 680]]);
      } else if (angle === "90度") {
        poly([[650, 620], [1270, 620], [1270, 645], [650, 645]]);
      } else {
        poly([[640, 430], [1180, 450], [1350, 660], [680, 640]]);
      }
      ctx.restore();
    }

    // Precision Video-Synced Render Loop
    function syncLoop() {
      if (!isPlaying) return;
      const v = VIS_DATA[currentVid];
      if (!v) return;

      if (hasVideoFile) {
        if (bgVideo.ended) {
          if (loopCheckbox.checked) {
            bgVideo.currentTime = 0;
            lastLoggedFrame = -1;
            bgVideo.play().catch(() => {});
          } else {
            pause();
            return;
          }
        }
        const f = Math.min(v.n_frames - 1, Math.max(0, Math.floor(bgVideo.currentTime * v.fps + 0.25)));
        renderFrame(f, true);
        rafId = requestAnimationFrame(syncLoop);
      }
    }

    function startFallbackTimer() {
      if (fallbackTimer) clearInterval(fallbackTimer);
      const v = VIS_DATA[currentVid];
      const intervalMs = (1000 / v.fps) / playbackSpeed;
      fallbackTimer = setInterval(() => {
        if (!isPlaying || hasVideoFile) return;
        if (currentFrame >= v.n_frames - 1) {
          if (loopCheckbox.checked) {
            lastLoggedFrame = -1;
            renderFrame(0, true);
          } else {
            pause();
          }
          return;
        }
        renderFrame(currentFrame + 1, true);
      }, intervalMs);
    }

    function play() {
      if (isPlaying) return;
      const v = VIS_DATA[currentVid];
      if (currentFrame >= v.n_frames - 1) {
        seekTo(0);
        lastLoggedFrame = -1;
      }

      isPlaying = true;
      textPlay.textContent = "暂停";
      iconPlay.textContent = "❚❚";
      playIndicator.style.background = "#10b981";

      if (hasVideoFile) {
        bgVideo.playbackRate = playbackSpeed;
        bgVideo.play().then(() => {
          rafId = requestAnimationFrame(syncLoop);
        }).catch(() => {
          startFallbackTimer();
        });
      } else {
        startFallbackTimer();
      }
    }

    function pause() {
      isPlaying = false;
      textPlay.textContent = "播放视频";
      iconPlay.textContent = "▶";
      if (rafId) cancelAnimationFrame(rafId);
      if (fallbackTimer) clearInterval(fallbackTimer);
      if (hasVideoFile && !bgVideo.paused) {
        bgVideo.pause();
      }
    }

    function seekTo(frameIdx, logNow=true) {
      const v = VIS_DATA[currentVid];
      if (!v) return;
      const target = Math.max(0, Math.min(v.n_frames - 1, Math.round(frameIdx)));
      currentFrame = target;
      if (logNow) {
        lastLoggedFrame = target - 1;
        logFrameEvents(v, target);
      } else {
        lastLoggedFrame = target;
      }
      if (hasVideoFile) {
        // Offset slightly into the frame duration to prevent floor rounding jitter
        bgVideo.currentTime = (target + 0.15) / v.fps;
      }
      renderFrame(target, false);
    }

    function updateSpeedUI() {
      const v = VIS_DATA[currentVid] || { fps: 25 };
      const effFps = (v.fps * playbackSpeed).toFixed(1);
      let tag = "";
      if (playbackSpeed <= 0.25) tag = " (超慢逐帧精看)";
      else if (playbackSpeed < 1.0) tag = " (慢放分析)";
      else if (playbackSpeed === 1.0) tag = ` (原速 ${v.fps}fps)`;
      else tag = " (快进)";

      speedReadout.textContent = `${playbackSpeed.toFixed(2)}×${tag}`;
      speedFpsText.textContent = `${effFps} fps`;
      speedSlider.value = playbackSpeed;

      Array.from(speedPresets.children).forEach(btn => {
        const s = parseFloat(btn.dataset.speed);
        if (Math.abs(s - playbackSpeed) < 0.01) btn.classList.add('active');
        else btn.classList.remove('active');
      });
    }

    function setPlaybackSpeed(newSpeed, logChange=true) {
      playbackSpeed = Math.min(2.0, Math.max(0.1, newSpeed));
      updateSpeedUI();
      if (hasVideoFile) {
        bgVideo.playbackRate = playbackSpeed;
      } else if (isPlaying) {
        startFallbackTimer();
      }
      if (logChange) {
        appendLog('sys', currentFrame, `播放倍速已调节至 <b>${playbackSpeed.toFixed(2)}×</b>`);
      }
    }

    // Event Bindings
    btnPlay.onclick = () => { if (isPlaying) pause(); else play(); };
    btnPrevFrame.onclick = () => { pause(); seekTo(currentFrame - 1); };
    btnNextFrame.onclick = () => { pause(); seekTo(currentFrame + 1); };

    btnPrevLanding.onclick = () => {
      pause();
      const v = VIS_DATA[currentVid];
      const prevs = v.preds.filter(p => p.frame_id < currentFrame);
      if (prevs.length > 0) {
        const target = prevs[prevs.length - 1].frame_id;
        seekTo(target);
        appendLog('sys', target, `已定位至上一落点帧 F${target}`);
      } else {
        seekTo(0);
      }
    };

    btnNextLanding.onclick = () => {
      pause();
      const v = VIS_DATA[currentVid];
      const nexts = v.preds.filter(p => p.frame_id > currentFrame);
      if (nexts.length > 0) {
        const target = nexts[0].frame_id;
        seekTo(target);
        appendLog('sys', target, `已定位至下一落点帧 F${target}`);
      }
    };

    frameSlider.oninput = (e) => {
      pause();
      seekTo(parseInt(e.target.value), false);
    };

    // Speed Preset Buttons & Slider
    speedPresets.onclick = (e) => {
      const btn = e.target.closest('.btn-speed');
      if (!btn) return;
      setPlaybackSpeed(parseFloat(btn.dataset.speed));
    };

    speedSlider.oninput = (e) => {
      setPlaybackSpeed(parseFloat(e.target.value), false);
    };
    speedSlider.onchange = (e) => {
      setPlaybackSpeed(parseFloat(e.target.value), true);
    };

    // Trail length slider
    trailLenSlider.oninput = (e) => {
      trailLength = parseInt(e.target.value);
      trailLenText.textContent = `${trailLength} 帧`;
      renderFrame(currentFrame, false);
    };

    // Layer Checkboxes
    [layerTrail, layerLandingLabels, layerGT, layerFutureLandings, layerVectors, layerROI].forEach(cb => {
      cb.onchange = () => renderFrame(currentFrame, false);
    });

    // Video Selector & Prev/Next Video
    videoSelect.onchange = (e) => loadVideoData(e.target.value);

    btnPrevVid.onclick = () => {
      const idx = VIDEO_IDS.indexOf(currentVid);
      const prevIdx = (idx - 1 + VIDEO_IDS.length) % VIDEO_IDS.length;
      loadVideoData(VIDEO_IDS[prevIdx]);
    };

    btnNextVid.onclick = () => {
      const idx = VIDEO_IDS.indexOf(currentVid);
      const nextIdx = (idx + 1) % VIDEO_IDS.length;
      loadVideoData(VIDEO_IDS[nextIdx]);
    };

    // Log Filters
    filterAll.onclick = () => {
      logFilterMode = "all";
      filterAll.classList.add('active');
      filterEvents.classList.remove('active');
      applyLogFilter();
    };
    filterEvents.onclick = () => {
      logFilterMode = "events";
      filterEvents.classList.add('active');
      filterAll.classList.remove('active');
      applyLogFilter();
    };
    btnClearLog.onclick = () => {
      logConsole.innerHTML = "";
    };

    // Manual Fallback Video File Input
    videoFileInput.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      bgVideo.src = url;
      bgVideo.load();
      appendLog('sys', null, `已手动挂载本地视频文件：${file.name}`);
    };

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.code === 'Space') {
        e.preventDefault();
        btnPlay.click();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        btnPrevFrame.click();
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        btnNextFrame.click();
      }
    });

    // Boot
    initDropdown();
  </script>
</body>
</html>
"""

final_html = html_template.replace('__VIS_DATA__', vis_data_str)

out_targets = [
    r'D:\pingpang源文件汇总\pingpong_visualizer.html',
    r'C:\Users\LENOVO\.gemini\antigravity\brain\45eb8651-a8aa-499d-8cfa-d4e66e108527\pingpong_visualizer.html'
]
for out_p in out_targets:
    with open(out_p, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"Generated visualizer HTML at {out_p}, size: {os.path.getsize(out_p)} bytes")
