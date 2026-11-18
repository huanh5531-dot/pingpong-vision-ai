# -*- coding: utf-8 -*-
r"""
Convert pingpong_project_proposal.md to a polished, professional Word (.docx) document
strictly following Chinese project declaration standards:
1. Replaces ASCII architecture diagram with high-res publication-grade flowchart images.
2. Fixes all LaTeX/math symbol leakage (e.g. $9\times 9$ -> 9×9, \Delta vy, L2, etc.).
3. Eliminates all bullet dots before major narrative paragraphs ("大段前不要加点").
4. Formats tables, formula callout cards, and section headings according to formal guidelines.
"""
import os
import re
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_table_borders(table, color="D3D3D3", sz="4", val="single"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:left w:val="none"/>
            <w:right w:val="none"/>
            <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:insideV w:val="none"/>
        </w:tblBorders>
    ''')
    tblPr.append(borders)

def clean_latex(text):
    """
    Sanitize raw LaTeX formulas and syntax into clean Unicode text.
    """
    if not text:
        return ""
    # Common replacements
    replacements = [
        (r'\$9\\times 9\$', '9×9'),
        (r'9\\times 9', '9×9'),
        (r'\\times', '×'),
        (r'\\Delta v_y', 'Δvy'),
        (r'\\Delta', 'Δ'),
        (r'\\mathcal\{L\}_2', 'L2'),
        (r'\\mathcal\{L\}', 'L'),
        (r'\\theta_\\text\{final\}', 'θ_final'),
        (r'\\theta_\\text\{orig\}', 'θ_orig'),
        (r'\\theta_\\text\{fine-tuned\}', 'θ_fine-tuned'),
        (r'\\theta', 'θ'),
        (r'\\alpha', 'α'),
        (r'\\gamma', 'γ'),
        (r'\\tau', 'τ'),
        (r'\\Omega', 'Ω'),
        (r'\\hat\{x\}', 'x̂'),
        (r'\\text\{Heat\}_i', 'Heat_i'),
        (r'\\text\{Heat\}', 'Heat'),
        (r'\\text\{.*?\}', lambda m: m.group(0)[6:-1]),
        (r'\\sum', 'Σ'),
        (r'\\cdot', '·'),
        (r'\\le', '≤'),
        (r'\\ge', '≥'),
        (r'\\mid', '|'),
        (r'\\quad', '  '),
        (r'\$t-2,\s*t-1,\s*t\$', 't-2, t-1, t'),
        (r'\$t\$', 't'),
        (r'\$v_x\$', 'vx'),
        (r'\$v_y\$', 'vy'),
        (r'\$x\$', 'x'),
        (r'\$y\$', 'y'),
        (r'\\frac\{(.*?)\}\{(.*?)\}', r'(\1) / (\2)'),
    ]
    for pattern, repl in replacements:
        if callable(repl):
            text = re.sub(pattern, repl, text)
        else:
            text = re.sub(pattern, repl, text)
    # Strip any lingering $
    text = text.replace('$', '')
    return text

def add_formatted_runs(paragraph, text, base_font_size=10.5, default_color=RGBColor(0x1e, 0x29, 0x3b)):
    """
    Parse inline bold **...** and inline code `...`, adding formatted runs.
    """
    text = clean_latex(text)
    
    # Split by bold **...** or inline code `...`
    pattern = r'(\*\*.*?\*\*|`.*?`)'
    parts = re.split(pattern, text)
    
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            bold_text = part[2:-2]
            r = paragraph.add_run(bold_text)
            r.font.name = '微软雅黑'
            r.font.size = Pt(base_font_size)
            r.font.bold = True
            r.font.color.rgb = RGBColor(0x0f, 0x17, 0x2a) # Darker for bold
            r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        elif part.startswith('`') and part.endswith('`'):
            code_text = part[1:-1]
            r = paragraph.add_run(f" {code_text} ")
            r.font.name = 'Consolas'
            r.font.size = Pt(base_font_size - 0.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor(0x02, 0x84, 0xc7) # Sky blue highlight for code
            r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        else:
            r = paragraph.add_run(part)
            r.font.name = '微软雅黑'
            r.font.size = Pt(base_font_size)
            r.font.color.rgb = default_color
            r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

def add_formula_card(doc, formula_lines):
    """
    Insert a dedicated, stylized formula callout card.
    """
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=100, bottom=100, left=180, right=180)
    
    # Left accent border
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="none"/>
            <w:left w:val="single" w:sz="24" w:space="0" w:color="0284C7"/>
            <w:bottom w:val="none"/>
            <w:right w:val="none"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.line_spacing = 1.3
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    
    full_text = "\n".join(clean_latex(l) for l in formula_lines)
    for idx, line in enumerate(formula_lines):
        clean_l = clean_latex(line)
        if idx > 0:
            p = cell.add_paragraph()
            p.paragraph_format.line_spacing = 1.25
            p.paragraph_format.space_after = Pt(2)
        r = p.add_run(clean_l)
        r.font.name = 'Consolas'
        r.font.size = Pt(10.0)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)
        r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_before = Pt(2)
    p_spacer.paragraph_format.space_after = Pt(4)

def parse_and_add_table(doc, raw_lines):
    rows_data = []
    for l in raw_lines:
        if re.match(r'^\s*\|?\s*:?-+:?\s*\|', l):
            continue
        parts = [c.strip() for c in l.strip().strip('|').split('|')]
        if parts:
            rows_data.append(parts)
            
    if not rows_data:
        return
        
    num_cols = max(len(r) for r in rows_data)
    table = doc.add_table(rows=len(rows_data), cols=num_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table, color="CBD5E1", sz="4")
    
    for r_idx, row in enumerate(rows_data):
        for c_idx in range(num_cols):
            val = row[c_idx] if c_idx < len(row) else ""
            cell = table.cell(r_idx, c_idx)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
            
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            
            if r_idx == 0:
                set_cell_background(cell, "1E3A8A")
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(clean_latex(val))
                r.font.name = '微软雅黑'
                r.font.size = Pt(9.5)
                r.font.bold = True
                r.font.color.rgb = RGBColor(0xff, 0xff, 0xff)
                r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            else:
                bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                set_cell_background(cell, bg)
                add_formatted_runs(p, val, base_font_size=9.0)

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_after = Pt(6)

def create_document():
    doc = Document()
    
    # Page setup - A4, normal margins
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = '微软雅黑'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x1e, 0x29, 0x3b)
    normal_style._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    CLR_PRIMARY = RGBColor(0x1e, 0x3a, 0x8a)  # Navy
    CLR_ACCENT = RGBColor(0x02, 0x84, 0xc7)   # Tech Blue
    CLR_DARK = RGBColor(0x0f, 0x17, 0x2a)     # Dark Slate
    CLR_MUTED = RGBColor(0x47, 0x55, 0x69)    # Muted Slate

    # Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(14)
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("“乒羽智瞳”")
    r_title.font.name = '微软雅黑'
    r_title.font.size = Pt(22)
    r_title.font.bold = True
    r_title.font.color.rgb = CLR_PRIMARY
    r_title._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(18)
    r_sub = p_sub.add_run("基于时空多模态热图融合与物理动力学守恒的乒乓球多视角落点检测与技战术分析系统")
    r_sub.font.name = '微软雅黑'
    r_sub.font.size = Pt(12.5)
    r_sub.font.bold = True
    r_sub.font.color.rgb = CLR_MUTED
    r_sub._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # Meta Callout Box
    tbl_meta = doc.add_table(rows=1, cols=1)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_meta = tbl_meta.cell(0, 0)
    set_cell_background(cell_meta, "F0FDF4")
    set_cell_margins(cell_meta, top=160, bottom=160, left=200, right=200)
    
    # Left green border
    tcPr_m = cell_meta._tc.get_or_add_tcPr()
    borders_m = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="none"/>
            <w:left w:val="single" w:sz="24" w:space="0" w:color="059669"/>
            <w:bottom w:val="none"/>
            <w:right w:val="none"/>
        </w:tcBorders>
    ''')
    tcPr_m.append(borders_m)

    p_m = cell_meta.paragraphs[0]
    p_m.paragraph_format.line_spacing = 1.35
    
    runs_data = [
        ("【参赛项目申报书 / 技术与商业方案报告】\n", True, CLR_PRIMARY),
        ("赛道方向：", True, CLR_DARK),
        ("2026 动感地带全国大学生 AI 创新大赛 · 体育视觉赛道（乒乓球多视角落点检测）\n", False, CLR_DARK),
        ("依托平台：", True, CLR_DARK),
        ("咪咕仝学 AI 创赛平台（2×RTX 4090 算力集群 / Docker 容器化交付）\n", False, CLR_DARK),
        ("团队规格：", True, CLR_DARK),
        ("5 人高校极客团队（1 名队长领衔，分工覆盖算法架构、模型微调、工程部署、数据分析与商业运营）\n", False, CLR_DARK),
        ("实战成果：", True, RGBColor(0x05, 0x96, 0x69)),
        ("官方公开验证集 Macro F1 = 0.9448（算法效果分 70.86 / 75.0）；29 个真实未见比赛盲测视频 F1 = 0.8792；预处理提速 13.6 倍。", True, RGBColor(0x05, 0x96, 0x69)),
    ]
    for text, bold, color in runs_data:
        r = p_m.add_run(text)
        r.font.name = '微软雅黑'
        r.font.size = Pt(9.5)
        r.font.bold = bold
        r.font.color.rgb = color
        r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_before = Pt(6)
    p_spacer.paragraph_format.space_after = Pt(6)

    # Read clean markdown content
    md_path = r'C:\Users\LENOVO\.gemini\antigravity\brain\45eb8651-a8aa-499d-8cfa-d4e66e108527\pingpong_project_proposal.md'
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    lines = md_text.split('\n')
    
    img_dir = r'D:\pingpang源文件汇总\local_eval'
    
    in_table = False
    table_lines = []
    in_code = False
    code_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Skip top title and quote block already handled
        if i < 15 and (line.startswith('# ') or line.startswith('> ') or line.startswith('---')):
            i += 1
            continue
            
        # Code block detection (for formulas or images)
        if line.startswith('```'):
            if in_code:
                # Flush code block
                in_code = False
                # If formula lines, add formula card
                if code_lines:
                    add_formula_card(doc, code_lines)
                code_lines = []
            else:
                in_code = True
                code_lines = []
            i += 1
            continue
            
        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # Image detection ![...](filename.png)
        img_match = re.match(r'!\[(.*?)\]\((.*?)\)', line)
        if img_match:
            caption_text = img_match.group(1)
            img_filename = img_match.group(2)
            img_path = os.path.join(img_dir, img_filename)
            if not os.path.exists(img_path):
                img_path = os.path.join(r'C:\Users\LENOVO\.gemini\antigravity\brain\45eb8651-a8aa-499d-8cfa-d4e66e108527', img_filename)
                
            if os.path.exists(img_path):
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(10)
                p_img.paragraph_format.space_after = Pt(4)
                r_img = p_img.add_run()
                # Determine display width
                disp_w = Inches(6.0) if 'architecture' in img_filename or 'business' in img_filename else Inches(6.2)
                r_img.add_picture(img_path, width=disp_w)
            i += 1
            continue

        # Caption line *图 x-x ...*
        cap_match = re.match(r'^\*(图\s*\d+-\d+.*?)\*$', line)
        if cap_match:
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_before = Pt(2)
            p_cap.paragraph_format.space_after = Pt(10)
            r_cap = p_cap.add_run(cap_match.group(1))
            r_cap.font.name = '微软雅黑'
            r_cap.font.size = Pt(9.0)
            r_cap.font.bold = True
            r_cap.font.color.rgb = CLR_MUTED
            r_cap._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            i += 1
            continue
            
        # Table detection
        if '|' in line and not line.startswith('>'):
            table_lines.append(line)
            if i + 1 < len(lines) and '|' in lines[i+1]:
                i += 1
                continue
            else:
                parse_and_add_table(doc, table_lines)
                table_lines = []
                i += 1
                continue
                
        # Heading 1 (e.g. ## 一、 ...)
        if line.startswith('## '):
            h_text = clean_latex(line[3:].strip())
            p_h = doc.add_paragraph()
            p_h.paragraph_format.space_before = Pt(18)
            p_h.paragraph_format.space_after = Pt(6)
            p_h.paragraph_format.keep_with_next = True
            r_h = p_h.add_run(h_text)
            r_h.font.name = '微软雅黑'
            r_h.font.size = Pt(15)
            r_h.font.bold = True
            r_h.font.color.rgb = CLR_PRIMARY
            r_h._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            i += 1
            continue
            
        # Heading 2 (e.g. ### 1.1 ...)
        if line.startswith('### '):
            h_text = clean_latex(line[4:].strip())
            p_h = doc.add_paragraph()
            p_h.paragraph_format.space_before = Pt(12)
            p_h.paragraph_format.space_after = Pt(4)
            p_h.paragraph_format.keep_with_next = True
            r_h = p_h.add_run(h_text)
            r_h.font.name = '微软雅黑'
            r_h.font.size = Pt(12.5)
            r_h.font.bold = True
            r_h.font.color.rgb = CLR_ACCENT
            r_h._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            i += 1
            continue
            
        # Heading 3 (e.g. #### 创新点 1...)
        if line.startswith('#### '):
            h_text = clean_latex(line[5:].strip())
            p_h = doc.add_paragraph()
            p_h.paragraph_format.space_before = Pt(9)
            p_h.paragraph_format.space_after = Pt(4)
            p_h.paragraph_format.keep_with_next = True
            r_h = p_h.add_run(h_text)
            r_h.font.name = '微软雅黑'
            r_h.font.size = Pt(11.0)
            r_h.font.bold = True
            r_h.font.color.rgb = CLR_DARK
            r_h._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            i += 1
            continue
            
        # Horizontal rule
        if line.strip() == '---':
            i += 1
            continue
            
        # Blank line
        if not line.strip():
            i += 1
            continue
            
        # Normal paragraph or numbered item
        clean_line = line.strip()
        
        # Strip any accidental leading bullet markers from source lines: "大段前不要加点"
        if clean_line.startswith('- ') or clean_line.startswith('* '):
            clean_line = clean_line[2:].strip()
            
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.3
        p.paragraph_format.space_after = Pt(4.5)
        
        # Check if line is a numbered item e.g. "1. " or "2. "
        m_num = re.match(r'^(\d+\.\s+)(.*)', clean_line)
        if m_num:
            p.paragraph_format.left_indent = Inches(0.2)
            r_num = p.add_run(m_num.group(1))
            r_num.font.name = '微软雅黑'
            r_num.font.bold = True
            r_num.font.color.rgb = CLR_PRIMARY
            r_num._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            add_formatted_runs(p, m_num.group(2))
        else:
            add_formatted_runs(p, clean_line)
            
        i += 1

    # Save to local workspace & conversation artifact path
    paths_to_save = [
        r'D:\pingpang源文件汇总\乒羽智瞳_项目申报书_动感地带AI大赛_优化版.docx',
        r'C:\Users\LENOVO\.gemini\antigravity\brain\45eb8651-a8aa-499d-8cfa-d4e66e108527\乒羽智瞳_项目申报书_动感地带AI大赛_优化版.docx',
        r'D:\pingpang源文件汇总\乒羽智瞳_项目申报书_动感地带AI大赛.docx',
        r'C:\Users\LENOVO\.gemini\antigravity\brain\45eb8651-a8aa-499d-8cfa-d4e66e108527\乒羽智瞳_项目申报书_动感地带AI大赛.docx',
    ]
    
    saved_paths = []
    for p in paths_to_save:
        try:
            doc.save(p)
            saved_paths.append(p)
            print(f"Saved: {p}")
        except PermissionError:
            print(f"File locked by open application (skipped): {p}")
        except Exception as e:
            print(f"Save error for {p}: {e}")
            
    print(f"\nDocument generation complete! Successfully saved to {len(saved_paths)} target(s).")

if __name__ == "__main__":
    create_document()
