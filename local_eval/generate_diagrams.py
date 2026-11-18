# -*- coding: utf-8 -*-
"""
Generate high-resolution, publication-grade flowchart and diagram images for:
1. End-to-end Algorithm & Business Architecture (图 2-1)
2. Commercial Monetization Matrix (图 3-1)
3. Project Milestone Timeline (图 4-1)
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import os

# Configure fonts
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def create_architecture_flowchart(save_path):
    fig = plt.figure(figsize=(9.2, 10.4), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Color Palette
    CLR_STAGE_BG = '#F0F9FF'     # Light sky blue
    CLR_STAGE_BORDER = '#0284C7' # Sky blue border
    CLR_ACCENT_BG = '#F0FDF4'    # Mint/Light Green
    CLR_ACCENT_BORDER = '#059669'# Green border
    CLR_PURPLE_BG = '#FAF5FF'    # Light Purple
    CLR_PURPLE_BORDER = '#7C3AED'# Purple border
    CLR_ORANGE_BG = '#FFF7ED'    # Warm amber
    CLR_ORANGE_BORDER = '#EA580C'# Orange border
    CLR_TEXT_DARK = '#0F172A'    # Slate 900
    CLR_TEXT_MUTED = '#475569'   # Slate 600

    def draw_card(x, y, w, h, title, subtitle_lines, bg_col, border_col, title_col=CLR_TEXT_DARK, title_size=11, sub_size=8.8, badge_text=None, badge_bg=None):
        shadow = FancyBboxPatch((x+0.4, y-0.4), w, h, boxstyle="round,pad=0.2,rounding_size=1.2",
                                facecolor='#000000', edgecolor='none', alpha=0.06, zorder=1)
        ax.add_patch(shadow)
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=1.2",
                             facecolor=bg_col, edgecolor=border_col, linewidth=1.6, zorder=2)
        ax.add_patch(box)
        
        if badge_text and badge_bg:
            b_w = len(badge_text)*1.4 + 2.5
            badge = FancyBboxPatch((x + 2, y + h - 2.2), b_w, 2.0,
                                   boxstyle="round,pad=0.1,rounding_size=0.6",
                                   facecolor=badge_bg, edgecolor='none', zorder=3)
            ax.add_patch(badge)
            ax.text(x + 2 + b_w/2, y + h - 1.2, badge_text,
                    ha='center', va='center', color='white', fontsize=7.5, fontweight='bold', zorder=4)

        t_y = y + h - 2.8 if badge_text else y + h - 2.2
        ax.text(x + w/2, t_y, title, ha='center', va='center', color=title_col,
                fontsize=title_size, fontweight='bold', zorder=3)
        
        line_spacing = 2.1
        start_y = t_y - 2.3
        for i, line in enumerate(subtitle_lines):
            ax.text(x + w/2, start_y - i * line_spacing, line,
                    ha='center', va='center', color=CLR_TEXT_MUTED, fontsize=sub_size, zorder=3)

    def draw_arrow(x, y_start, y_end, label=None):
        ax.annotate('', xy=(x, y_end), xytext=(x, y_start),
                    arrowprops=dict(facecolor='#0284C7', edgecolor='#0284C7', width=2.0,
                                   headwidth=7.0, headlength=7.0, shrink=0.08), zorder=5)
        if label:
            ax.text(x + 1.2, (y_start + y_end)/2, label, ha='left', va='center',
                    color='#0284C7', fontsize=8, fontweight='bold', zorder=6)

    # 1. Top Input Card
    draw_card(18, 90, 64, 8,
              "比赛视频输入流 (1080p, 60fps · 单目通用视频)",
              ["支持 0°纵向、45°斜向、90°侧向等多机位赛事转播，兼容普通手机手持拍摄视频"],
              '#F8FAFC', '#64748B', title_col='#1E293B', title_size=11, sub_size=8.5)
    
    draw_arrow(50, 90, 83)

    # 2. Stage 1 Card
    draw_card(12, 73, 76, 10,
              "阶段一：工程预处理加速 (cv2.LUT 浮点预计算查表)",
              ["• 构建 256 色阶标准化查找表，底层 C++ 内存直连，单帧耗时降至 0.136 ms",
               "• 处理速度相比传统逐像素归一化提速 13.6 倍，数值完全保持 IEEE-754 位级零误差"],
              CLR_STAGE_BG, CLR_STAGE_BORDER, title_col=CLR_STAGE_BORDER, title_size=11, sub_size=8.5,
              badge_text="耗时缩减 92.6%", badge_bg='#0284C7')

    draw_arrow(50, 73, 66)

    # 3. Stage 2 Card
    draw_card(12, 56, 76, 10,
              "阶段二：轻量高分辨率骨干网络特征提取 (HRNet)",
              ["• 高低分辨率分支全程并行交互，避免小目标深层下采样空间细节损失",
               "• 维持乒乓球亚像素级高空间精度，参数量精简至 5.3 MB，实现高速低功耗推理"],
              CLR_PURPLE_BG, CLR_PURPLE_BORDER, title_col=CLR_PURPLE_BORDER, title_size=11, sub_size=8.5,
              badge_text="高分辨率表征", badge_bg='#7C3AED')

    draw_arrow(50, 56, 49)

    # 4. Stage 3 Card
    draw_card(12, 39, 76, 10,
              "阶段三：3 通道跨滑动窗口时空热图融合与解码",
              ["• 流式队列实时汇聚连续帧推理热图 [t-2, t-1, t]，折返顶点检出率提至 98.04%",
               "• 9×9 局部自适应截断加权质心解码，有效过滤球台反光白条与拍边白斑干扰"],
              CLR_ORANGE_BG, CLR_ORANGE_BORDER, title_col=CLR_ORANGE_BORDER, title_size=11, sub_size=8.5,
              badge_text="漏检率降低 62.5%", badge_bg='#EA580C')

    draw_arrow(50, 39, 32)

    # 5. Stage 4 Card
    draw_card(12, 22, 76, 10,
              "阶段四：物理运动学多视角自适应落点状态机 (Kinematics FSM)",
              ["• 跨分辨率尺度归一化 (sx, sy)，构建 3 模态动力学判定 (极值/深度/高速减速)",
               "• 融合发球垂直过滤、球员反拉过滤与 2~7 帧不应期抑制，实现精准触台落点解算"],
              CLR_ACCENT_BG, CLR_ACCENT_BORDER, title_col=CLR_ACCENT_BORDER, title_size=11, sub_size=8.5,
              badge_text="Macro F1 = 0.9448", badge_bg='#059669')

    # Bifurcated arrows
    ax.annotate('', xy=(28, 16), xytext=(50, 22),
                arrowprops=dict(facecolor='#1E3A8A', edgecolor='#1E3A8A', width=2.0,
                               headwidth=6.0, headlength=6.0, shrink=0.08), zorder=5)
    ax.annotate('', xy=(72, 16), xytext=(50, 22),
                arrowprops=dict(facecolor='#0D9488', edgecolor='#0D9488', width=2.0,
                               headwidth=6.0, headlength=6.0, shrink=0.08), zorder=5)

    # 6. Dual Output Cards (B-end & C-end)
    draw_card(6, 3, 41, 13,
              "B端：数字鹰眼 & 专业战术SaaS",
              ["• 3D 轨迹重构与触台落点热区大屏",
               "• 逐拍出台率、深浅控制力统计复盘",
               "• 咪咕体育赛事直播鹰眼即时特效"],
              '#EFF6FF', '#1E3A8A', title_col='#1E3A8A', title_size=10.5, sub_size=8.0,
              badge_text="专业竞技 & 智慧场馆", badge_bg='#1E3A8A')

    draw_card(53, 3, 41, 13,
              "C端：咪咕“星屿”小程序轻量私教",
              ["• 手机录像即拍即传，10 秒快速解算",
               "• 个人落台击球点诊断与能力雷达",
               "• 专属高光轨迹短视频与社交裂变"],
              '#F0FDF4', '#0D9488', title_col='#0D9488', title_size=10.5, sub_size=8.0,
              badge_text="大众普及 & 社交裂变", badge_bg='#0D9488')

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)
    print(f"Architecture flowchart saved to: {save_path}")

def create_business_matrix_chart(save_path):
    fig = plt.figure(figsize=(9.2, 5.8), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    CLR_TEXT_DARK = '#0F172A'

    def draw_box(x, y, w, h, title, items, bg_col, border_col):
        shadow = FancyBboxPatch((x+0.3, y-0.3), w, h, boxstyle="round,pad=0.2,rounding_size=1.0",
                                facecolor='#000000', edgecolor='none', alpha=0.05, zorder=1)
        ax.add_patch(shadow)
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=1.0",
                             facecolor=bg_col, edgecolor=border_col, linewidth=1.6, zorder=2)
        ax.add_patch(box)
        
        banner = FancyBboxPatch((x, y + h - 6.5), w, 6.5, boxstyle="round,pad=0.1,rounding_size=0.8",
                                facecolor=border_col, edgecolor='none', zorder=3)
        ax.add_patch(banner)
        ax.text(x + w/2, y + h - 3.25, title, ha='center', va='center', color='white',
                fontsize=10.5, fontweight='bold', zorder=4)
        
        line_spacing = 4.2
        start_y = y + h - 10.5
        for i, it in enumerate(items):
            ax.text(x + 2.5, start_y - i * line_spacing, it, ha='left', va='center',
                    color=CLR_TEXT_DARK, fontsize=8.2, zorder=4)

    # Top Header Box
    top_box = FancyBboxPatch((20, 84), 60, 12, boxstyle="round,pad=0.2,rounding_size=1.0",
                             facecolor='#1E3A8A', edgecolor='#1E3A8A', zorder=2)
    ax.add_patch(top_box)
    ax.text(50, 91.5, "“乒羽智瞳” 商业化变现矩阵与生态联动", ha='center', va='center',
            color='white', fontsize=12.5, fontweight='bold', zorder=3)
    ax.text(50, 86.8, "以 AI 视觉落点算法为核心，打通‘专业竞技 + 大众消费 + 赛事转播’三位一体盈利闭环",
            ha='center', va='center', color='#93C5FD', fontsize=8.5, zorder=3)

    for target_x in [17, 50, 83]:
        ax.annotate('', xy=(target_x, 74), xytext=(50, 84),
                    arrowprops=dict(facecolor='#0284C7', edgecolor='#0284C7', width=1.8,
                                   headwidth=5.5, headlength=5.5, shrink=0.05), zorder=5)

    col_w = 28
    col_h = 67
    
    # Col 1: B端
    draw_box(3, 6, col_w, col_h,
             "B端 · 专业竞技与智慧场馆",
             ["【目标客户】",
              "全国 4000+ 乒乓青训基地、",
              "省市体校、高校高水平运动队",
              "",
              "【产品形态】",
              "• 逐拍落点深浅统计分析 SaaS",
              "• 球员长期技战术成长档案库",
              "• 智慧场馆落区演播大屏一体机",
              "",
              "【盈利模式】",
              "• 机构版 SaaS：2~5 万元/年",
              "• 定制化科研复盘系统交付"],
             '#EFF6FF', '#1E3A8A')

    # Col 2: C端
    draw_box(36, 6, col_w, col_h,
             "C端 · 咪咕“星屿”小程序",
             ["【目标用户】",
              "8500 万大众乒乓爱好者、",
              "业余球友、青少年学员与家长",
              "",
              "【核心功能】",
              "• 手机视频上传 10 秒即时回传",
              "• 专属击球控制力与落台雷达",
              "• AI 自动剪辑炫酷轨迹短视频",
              "",
              "【盈利模式】",
              "• Freemium 免费基础计数",
              "• 高阶诊断月卡：19.9~29.9 元/月",
              "• 连续包年优惠：199 元/年"],
             '#F0FDF4', '#0D9488')

    # Col 3: M端
    draw_box(69, 6, col_w, col_h,
             "M端 · 赛事转播与硬件赋能",
             ["【合作对象】",
              "咪咕视频、体育赛事版权方、",
              "发球机/智能乒乓球桌制造商",
              "",
              "【合作模式】",
              "• 咪咕体育赛事直播即时鹰眼",
              "  特效授权与争议球判定回放",
              "• 嵌入式算法 SDK 硬件赋能：",
              "  联合发球机厂商打造精准测试",
              "",
              "【盈利模式】",
              "• 赛事转播技术服务与特效授权",
              "• 智能硬件内嵌算法授权分成"],
             '#FAF5FF', '#7C3AED')

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)
    print(f"Business matrix chart saved to: {save_path}")

def create_timeline_chart(save_path):
    fig = plt.figure(figsize=(9.2, 2.7), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 30)
    ax.axis('off')

    steps = [
        ('9月20日 · 需求发布', '赛题调研与基线复现\n环境搭建与折返漏检分析', '#1E3A8A', '#EFF6FF'),
        ('10月5日 · 算法突破', '3通道时空融合架构\nMargin Loss难例微调', '#0284C7', '#F0F9FF'),
        ('10月20日 · 初赛提交', 'Docker镜像规范构建\n验证集F1=0.9448达标', '#0D9488', '#F0FDF4'),
        ('11月中旬 · 评审复盘', '星屿小程序原型开发\n多视频轨迹可视化插件', '#7C3AED', '#FAF5FF'),
        ('12月 · 决赛答辩', '实物路演与商业落地\n青训机构与转播商试点', '#EA580C', '#FFF7ED')
    ]

    x_start = 2
    box_w = 17.5
    box_h = 24
    gap = 2.1

    for i, (title, sub, border_c, bg_c) in enumerate(steps):
        x = x_start + i * (box_w + gap)
        y = 3
        shadow = FancyBboxPatch((x+0.2, y-0.2), box_w, box_h, boxstyle='round,pad=0.2,rounding_size=1.0',
                                facecolor='#000000', edgecolor='none', alpha=0.06, zorder=1)
        ax.add_patch(shadow)
        box = FancyBboxPatch((x, y), box_w, box_h, boxstyle='round,pad=0.2,rounding_size=1.0',
                             facecolor=bg_c, edgecolor=border_c, linewidth=1.5, zorder=2)
        ax.add_patch(box)
        
        banner = FancyBboxPatch((x, y + box_h - 6.5), box_w, 6.5, boxstyle='round,pad=0.1,rounding_size=0.8',
                                facecolor=border_c, edgecolor='none', zorder=3)
        ax.add_patch(banner)
        ax.text(x + box_w/2, y + box_h - 3.25, title, ha='center', va='center', color='white',
                fontsize=8.2, fontweight='bold', zorder=4)
        
        lines = sub.split('\n')
        ax.text(x + box_w/2, y + 11.5, lines[0], ha='center', va='center', color='#1E293B', fontsize=7.5, fontweight='bold', zorder=4)
        ax.text(x + box_w/2, y + 6.8, lines[1], ha='center', va='center', color='#64748B', fontsize=7.0, zorder=4)
        
        if i < 4:
            arr_x_start = x + box_w + 0.3
            arr_x_end = arr_x_start + gap - 0.6
            ax.annotate('', xy=(arr_x_end, y + box_h/2), xytext=(arr_x_start, y + box_h/2),
                        arrowprops=dict(facecolor='#94A3B8', edgecolor='#94A3B8', width=1.4,
                                       headwidth=4.5, headlength=4.5, shrink=0.05), zorder=5)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight', pad_inches=0.08)
    plt.close(fig)
    print(f"Timeline chart saved to: {save_path}")

if __name__ == '__main__':
    out_dir = r'D:\pingpang源文件汇总\local_eval'
    p1 = os.path.join(out_dir, 'flowchart_architecture.png')
    p2 = os.path.join(out_dir, 'flowchart_business.png')
    p3 = os.path.join(out_dir, 'timeline_milestones.png')
    create_architecture_flowchart(p1)
    create_business_matrix_chart(p2)
    create_timeline_chart(p3)
