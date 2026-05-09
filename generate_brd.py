from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import datetime

doc = Document()

section = doc.sections[0]
section.page_width  = Inches(8.5)
section.page_height = Inches(11)
section.left_margin   = Inches(1)
section.right_margin  = Inches(1)
section.top_margin    = Inches(1)
section.bottom_margin = Inches(1)

BLUE   = (31, 73, 125)
LBLUE  = (68, 114, 196)
WHITE  = (255, 255, 255)
GREY   = (89, 89, 89)
GREEN  = (0, 112, 0)
ORANGE = (197, 90, 17)
RED    = (192, 0, 0)

def add_heading(doc, text, level):
    p = doc.add_paragraph()
    p.style = f'Heading {level}'
    p.add_run(text)
    return p

def add_body(doc, text, bold=False, italic=False, color=None):
    p = doc.add_paragraph()
    p.style = 'Normal'
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(11)
    if color:
        run.font.color.rgb = RGBColor(*color)
    return p

def add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    run.font.size = Pt(11)
    return p

def shade_cell(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)

def set_cell_border(cell, color='CCCCCC'):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        tag = OxmlElement(f'w:{edge}')
        tag.set(qn('w:val'), 'single')
        tag.set(qn('w:sz'), '4')
        tag.set(qn('w:space'), '0')
        tag.set(qn('w:color'), color)
        tcBorders.append(tag)
    tcPr.append(tcBorders)

def set_col_width(cell, width):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcW = OxmlElement('w:tcW')
    tcW.set(qn('w:w'), str(int(width * 1440)))
    tcW.set(qn('w:type'), 'dxa')
    tcPr.append(tcW)

def make_table(doc, headers, rows_data, col_widths, header_color='1F497D', alt_color='F0F4FF'):
    t = doc.add_table(rows=len(rows_data)+1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for j, h in enumerate(headers):
        cell = t.rows[0].cells[j]
        set_col_width(cell, col_widths[j])
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(*WHITE)
        shade_cell(cell, header_color)
        set_cell_border(cell, '1F497D')
    for i, row_data in enumerate(rows_data, 1):
        row = t.rows[i]
        fill = alt_color if i % 2 == 0 else 'FFFFFF'
        for j, val in enumerate(row_data):
            cell = row.cells[j]
            set_col_width(cell, col_widths[j])
            if isinstance(val, tuple):
                text, bold, color = val
                run = cell.paragraphs[0].add_run(str(text))
                run.bold = bold
                run.font.size = Pt(10)
                if color:
                    run.font.color.rgb = RGBColor(*color)
            else:
                run = cell.paragraphs[0].add_run(str(val))
                run.font.size = Pt(10)
            shade_cell(cell, fill)
            set_cell_border(cell)
    doc.add_paragraph()
    return t

# ── COVER PAGE ────────────────────────────────────────────────────────────────
doc.add_paragraph()
doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('BUSINESS REQUIREMENTS DOCUMENT')
run.bold = True
run.font.size = Pt(24)
run.font.color.rgb = RGBColor(*BLUE)

doc.add_paragraph()

p2 = doc.add_paragraph()
p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run2 = p2.add_run('Auto Count Social Media Reach')
run2.bold = True
run2.font.size = Pt(18)
run2.font.color.rgb = RGBColor(*LBLUE)

doc.add_paragraph()

p3 = doc.add_paragraph()
p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
run3 = p3.add_run('AI-Assisted Video Metrics Automation System')
run3.italic = True
run3.font.size = Pt(13)
run3.font.color.rgb = RGBColor(*GREY)

doc.add_paragraph()
doc.add_paragraph()

meta = doc.add_table(rows=5, cols=2)
meta.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, (lbl, val) in enumerate([
    ('Document Version:', '3.0'),
    ('Date:', datetime.date.today().strftime('%d %B %Y')),
    ('Status:', 'Draft'),
    ('Prepared By:', 'jingyi-rere'),
    ('Reviewed By:', 'Pending'),
]):
    set_col_width(meta.rows[i].cells[0], 2.2)
    set_col_width(meta.rows[i].cells[1], 4.3)
    lc = meta.rows[i].cells[0].paragraphs[0].add_run(lbl)
    lc.bold = True
    lc.font.size = Pt(10)
    vc = meta.rows[i].cells[1].paragraphs[0].add_run(val)
    vc.font.size = Pt(10)
    shade_cell(meta.rows[i].cells[0], 'D6E4F7')
    set_cell_border(meta.rows[i].cells[0])
    set_cell_border(meta.rows[i].cells[1])

doc.add_paragraph()
doc.add_paragraph()

add_heading(doc, 'Document Version History', 2)
make_table(doc,
    ['Version', 'Date', 'Author', 'Changes'],
    [
        ('1.0', '07 May 2026', 'jingyi-rere', 'Initial draft'),
        ('2.0', '09 May 2026', 'jingyi-rere', 'Added user stories, MoSCoW, As-Is vs To-Be, Risk Register, Roadmap'),
        ('3.0', datetime.date.today().strftime('%d %B %Y'), 'jingyi-rere', 'Updated: video content only, Lark Sheet output, exact column mapping A-H'),
    ],
    [0.7, 1.5, 1.5, 3.8]
)

doc.add_page_break()

# ── 1. EXECUTIVE SUMMARY ──────────────────────────────────────────────────────
add_heading(doc, '1. Executive Summary', 1)
add_body(doc, (
    'This document defines the business requirements for an AI-assisted Social Media Video Metrics '
    'Automation system. The system is designed for a single video content creator who manages video '
    'content across 7 social media platforms. Instead of manually visiting each platform and recording '
    'numbers, the user simply pastes video links into the system. The system automatically extracts key '
    'video performance metrics and writes them directly into the correct columns of the user\'s existing '
    'Lark Sheet. The system also generates AI-powered performance analysis and content recommendations '
    'for the next posting cycle.'
))

# ── 2. PROBLEM STATEMENT ──────────────────────────────────────────────────────
add_heading(doc, '2. Problem Statement', 1)

add_heading(doc, '2.1 As-Is Process (Current — Manual)', 2)
add_body(doc, 'Every reporting cycle, the user has to manually:')
make_table(doc,
    ['Step', 'Platform', 'What the User Does Manually'],
    [
        ('1', 'Instagram', 'Find each Reel, record view count, copy caption, note posted date'),
        ('2', 'TikTok', 'Find each video, record view count, copy caption, note posted date'),
        ('3', 'Facebook', 'Find each video, record view count, copy caption, note posted date'),
        ('4', 'YouTube', 'Find each video, record view count, copy title, note posted date'),
        ('5', 'X (Twitter)', 'Find each video, record view count, copy caption, note posted date'),
        ('6', 'RedNote', 'Find each video, record view count, copy caption, note posted date'),
        ('7', 'Threads', 'Find each video, record view count, copy caption, note posted date'),
        ('8', 'Lark Sheet', 'Type all data into correct columns A, D, E, F, G manually'),
    ],
    [0.5, 1.5, 5.5]
)

add_heading(doc, '2.2 To-Be Process (Future — Automated)', 2)
add_body(doc, 'With the new system, the user only needs to do ONE thing:')
make_table(doc,
    ['Step', 'What the User Does', 'What the System Does'],
    [
        ('1', 'Paste video links into the system', 'Validates each link and identifies the platform'),
        ('2', 'Wait', 'Extracts: posted date, caption (no hashtags), view count from all 7 platforms'),
        ('3', 'Done!', 'Writes data into correct Lark Sheet columns A, D, E, F, G automatically'),
    ],
    [0.5, 2.8, 4.2]
)

add_heading(doc, '2.3 Pain Points', 2)
make_table(doc,
    ['#', 'Pain Point', 'Impact'],
    [
        ('1', 'Opens 7 platforms manually every cycle', 'Very time-consuming'),
        ('2', 'Types data into wrong Lark column accidentally', 'Data errors that are hard to spot'),
        ('3', 'Removes hashtags from captions manually', 'Easy to miss some hashtags'),
        ('4', 'No automated performance analysis', 'Cannot quickly see which videos worked best'),
        ('5', 'Repetitive task takes time away from content creation', 'Less time for creative work'),
    ],
    [0.5, 3.0, 4.0]
)

# ── 3. BUSINESS OBJECTIVES ────────────────────────────────────────────────────
add_heading(doc, '3. Business Objectives', 1)
for obj in [
    'Save time — reduce reporting time by at least 80% per cycle.',
    'Automatically fill the correct Lark Sheet columns with accurate data.',
    'Extract video captions and remove all hashtags automatically.',
    'Default Content Type to "Content Casual" without manual selection.',
    'Generate AI-powered video performance summary and recommendations.',
    'Support all 7 platforms the user posts video content on.',
]:
    add_bullet(doc, obj)

# ── 4. USER STORIES ───────────────────────────────────────────────────────────
add_heading(doc, '4. User Stories', 1)
make_table(doc,
    ['ID', 'User Story'],
    [
        ('US-01', 'As a video content creator, I want to paste video links so the system fills my Lark Sheet automatically without me typing anything.'),
        ('US-02', 'As a user, I want the video posted date auto-filled in Column A so I do not have to look it up manually.'),
        ('US-03', 'As a user, I want the video caption (without hashtags) filled in Column D automatically.'),
        ('US-04', 'As a user, I want Column E (Content Type) to default to "Content Casual" so I do not have to select it every time.'),
        ('US-05', 'As a user, I want the video URL filled in Column F automatically.'),
        ('US-06', 'As a user, I want the view count filled in Column G (Reach) so I can track performance easily.'),
        ('US-07', 'As a user, I want the system to leave Columns B, C, and H completely untouched.'),
        ('US-08', 'As a user, I want AI recommendations so I know what type of videos to create next cycle.'),
    ],
    [0.8, 6.7]
)

# ── 5. LARK SHEET COLUMN MAPPING ──────────────────────────────────────────────
add_heading(doc, '5. Lark Sheet Column Mapping', 1)
add_body(doc, 'The system must write data into the existing Lark Sheet with these exact rules:')
doc.add_paragraph()

SYS = ('System fills automatically', False, GREEN)
IGN = ('User fills manually — DO NOT TOUCH', False, ORANGE)
DEF = ('System fills with default value', False, LBLUE)

make_table(doc,
    ['Column', 'Field Name', 'System Action', 'Details'],
    [
        ('A', 'Date',         SYS, 'Date the video was originally posted on the platform (not today\'s date)'),
        ('B', 'Week',         IGN, 'User fills manually — system must NOT write anything here'),
        ('C', 'PIC',          IGN, 'User fills manually — system must NOT write anything here'),
        ('D', 'Title',        SYS, 'Video caption extracted automatically. All hashtags removed. Write "No caption" if none found.'),
        ('E', 'Content Type', DEF, 'Auto-filled as "Content Casual" by default for every row'),
        ('F', 'Link',         SYS, 'The video URL as provided by the user'),
        ('G', 'Reach',        SYS, 'View count only (e.g. Reels view count shown on platform profile)'),
        ('H', 'Final Reach',  IGN, 'User fills manually — system must NOT write anything here'),
    ],
    [0.6, 1.3, 2.7, 3.0]
)

# ── 6. SUPPORTED PLATFORMS ────────────────────────────────────────────────────
add_heading(doc, '6. Supported Platforms', 1)
make_table(doc,
    ['Platform', 'Video Format', 'Column G — View Count Source', 'Column D — Caption Source'],
    [
        ('Instagram', 'Reels', 'Reels view count on profile', 'Post caption — hashtags removed'),
        ('TikTok', 'Video', 'Total video views', 'Video description — hashtags removed'),
        ('Facebook', 'Video / Reels', 'Video views', 'Post caption — hashtags removed'),
        ('YouTube', 'Video / Shorts', 'Total video views', 'Video title'),
        ('X (Twitter)', 'Video post', 'Video views / impressions', 'Tweet text — hashtags removed'),
        ('RedNote', 'Video', 'Video views', 'Post caption — hashtags removed'),
        ('Threads', 'Video post', 'Video views', 'Post caption — hashtags removed'),
    ],
    [1.2, 1.2, 2.4, 2.7]
)

# ── 7. FUNCTIONAL REQUIREMENTS ────────────────────────────────────────────────
add_heading(doc, '7. Functional Requirements', 1)
add_body(doc, 'Priority: M = Must Have   S = Should Have   C = Could Have', italic=True, color=GREY)
doc.add_paragraph()

M = ('M', False, GREEN)
S = ('S', False, LBLUE)
C = ('C', False, ORANGE)

make_table(doc,
    ['ID', 'Priority', 'Requirement'],
    [
        ('FR-01', M, 'Accept one or more video URLs as input from the user.'),
        ('FR-02', M, 'Identify which of the 7 platforms each URL belongs to.'),
        ('FR-03', M, 'Extract the original posted date of the video (Column A).'),
        ('FR-04', M, 'Extract the video caption and strip all hashtags (Column D). Write "No caption" if none found.'),
        ('FR-05', M, 'Auto-fill "Content Casual" as the default value for Column E.'),
        ('FR-06', M, 'Write the video URL into Column F.'),
        ('FR-07', M, 'Extract the video view count and write into Column G (Reach).'),
        ('FR-08', M, 'Never write to Columns B, C, or H under any circumstance.'),
        ('FR-09', M, 'Write all data into the correct new row in the existing Lark Sheet without overwriting other data.'),
        ('FR-10', M, 'Support all 7 platforms: Instagram, TikTok, Facebook, YouTube, X, RedNote, Threads.'),
        ('FR-11', S, 'Generate an AI performance summary showing best and worst performing videos.'),
        ('FR-12', S, 'Generate AI content recommendations for the next posting cycle.'),
        ('FR-13', S, 'If a link fails, notify the user with a clear error message and continue with remaining links.'),
        ('FR-14', C, 'Support batch input of multiple video links at once.'),
        ('FR-15', C, 'Compare current cycle performance against the previous cycle.'),
    ],
    [0.8, 0.8, 5.9]
)

# ── 8. NON-FUNCTIONAL REQUIREMENTS ───────────────────────────────────────────
add_heading(doc, '8. Non-Functional Requirements', 1)
make_table(doc,
    ['ID', 'Category', 'Requirement'],
    [
        ('NFR-01', 'Performance', 'Extract and fill data for up to 20 videos within 2 minutes.'),
        ('NFR-02', 'Accuracy', 'View counts must match platform figures with 99% accuracy.'),
        ('NFR-03', 'Data Integrity', 'System must never overwrite or delete data in Columns B, C, or H.'),
        ('NFR-04', 'Usability', 'User can complete a full reporting cycle in under 5 minutes with no training.'),
        ('NFR-05', 'Reliability', 'If one link fails, system continues processing all remaining links.'),
        ('NFR-06', 'Security', 'Lark API credentials must be stored securely and encrypted.'),
        ('NFR-07', 'Compatibility', 'Must integrate with Lark Sheet API without breaking existing sheet structure or formatting.'),
    ],
    [0.9, 1.6, 5.0]
)

# ── 9. RISK REGISTER ──────────────────────────────────────────────────────────
add_heading(doc, '9. Risk Register', 1)
H2 = ('High', False, RED)
M2 = ('Medium', False, ORANGE)
L2 = ('Low', False, GREEN)
make_table(doc,
    ['ID', 'Risk', 'Likelihood', 'Impact', 'Mitigation'],
    [
        ('R-01', 'Platform blocks automated data access', M2, H2, 'Use official APIs; have fallback scraping where permitted by ToS'),
        ('R-02', 'Platform layout or API changes break extraction', M2, H2, 'Modular connectors — fix one platform without affecting others'),
        ('R-03', 'System writes to wrong Lark column', L2, H2, 'Strict column mapping with automated validation tests before release'),
        ('R-04', 'Caption extraction leaves some hashtags behind', L2, M2, 'Use robust regex pattern to strip all hashtags; tested across all platforms'),
        ('R-05', 'RedNote has very limited API access', H2, M2, 'Research alternative access; document limitation and propose workaround'),
    ],
    [0.6, 2.3, 1.0, 0.8, 2.8]
)

# ── 10. ASSUMPTIONS & CONSTRAINTS ────────────────────────────────────────────
add_heading(doc, '10. Assumptions & Constraints', 1)

add_heading(doc, '10.1 Assumptions', 2)
for item in [
    'All video links provided belong to the user\'s own accounts.',
    'The Lark Sheet already exists with exactly the 8 columns (A to H) as defined in Section 5.',
    'The user has a stable internet connection when running the system.',
    'Videos will always have a caption — "No caption" fallback is a safety measure only.',
    '"Content Casual" is the appropriate default for the majority of the user\'s videos.',
]:
    add_bullet(doc, item)

add_heading(doc, '10.2 Constraints', 2)
for item in [
    'System must NEVER write to Columns B (Week), C (PIC), or H (Final Reach).',
    'Column A must reflect the original video posted date — not the date the system is run.',
    'Each platform\'s Terms of Service must be respected for all data access methods.',
    'RedNote may require a different technical approach due to limited API availability.',
    'Single user only in Phase 1 — no multi-user or team features.',
]:
    add_bullet(doc, item)

# ── 11. IMPLEMENTATION ROADMAP ───────────────────────────────────────────────
add_heading(doc, '11. Implementation Roadmap', 1)
make_table(doc,
    ['Phase', 'What Gets Built', 'Platforms Covered', 'Timeline'],
    [
        ('Phase 1\n(Core)', 'URL input, metric extraction, write to Lark Sheet columns A, D, E, F, G', 'Instagram, TikTok, YouTube', 'Days 1-2'),
        ('Phase 2', 'Add remaining platforms + AI performance analysis and recommendations', 'Facebook, X, RedNote, Threads', 'Days 3-4'),
        ('Phase 3', 'Batch input, error handling, performance comparison across cycles', 'All 7 platforms', 'Day 5'),
    ],
    [1.0, 3.3, 2.2, 1.0]
)

# ── 12. SUCCESS CRITERIA ─────────────────────────────────────────────────────
add_heading(doc, '12. Success Criteria', 1)
make_table(doc,
    ['Criteria', 'Target'],
    [
        ('Time saved per reporting cycle', 'At least 80% reduction vs current manual process'),
        ('Manual data entry required', 'Zero — system fills Columns A, D, E, F, G automatically'),
        ('Columns B, C, H protection', '100% — system never writes to these columns'),
        ('View count accuracy', '99% match with figures shown on each platform'),
        ('Caption accuracy', 'Correct caption extracted with zero hashtags remaining'),
        ('Platforms supported', 'All 7: Instagram, TikTok, Facebook, YouTube, X, RedNote, Threads'),
        ('AI recommendations', 'At least 3 actionable video content suggestions per reporting cycle'),
    ],
    [3.5, 4.0]
)

# ── 13. GLOSSARY ─────────────────────────────────────────────────────────────
add_heading(doc, '13. Glossary', 1)
make_table(doc,
    ['Term', 'Definition'],
    [
        ('Reach (Column G)', 'The view count of a video as displayed on the platform profile page.'),
        ('Caption', 'The text description written with a video post. Hashtags are removed before saving.'),
        ('Hashtag', 'Words starting with # used for discoverability on social media. Always removed from Column D.'),
        ('Lark Sheet', 'The spreadsheet tool inside Lark (Feishu) where the user tracks video performance.'),
        ('PIC', 'Person In Charge — filled manually by the user in Column C.'),
        ('Content Casual', 'The default content type category auto-filled in Column E for all videos.'),
        ('Final Reach', 'A manually calculated field in Column H — the system never touches this column.'),
        ('RedNote', 'Also known as Xiaohongshu — a Chinese social media and lifestyle platform.'),
        ('MoSCoW', 'Prioritisation method: Must Have, Should Have, Could Have, Would not Have this time.'),
    ],
    [2.0, 5.5]
)

doc.add_paragraph()

# ── 14. SIGN-OFF ─────────────────────────────────────────────────────────────
add_heading(doc, '14. Sign-Off & Approval', 1)
add_body(doc, 'By signing below, the approver confirms that this BRD accurately represents the requirements for the Auto Count Social Media Reach system.')
doc.add_paragraph()
make_table(doc,
    ['Role', 'Name', 'Signature', 'Date'],
    [
        ('Prepared By', 'jingyi-rere', '', ''),
        ('Reviewed By', '', '', ''),
        ('Approved By', '', '', ''),
    ],
    [2.0, 2.0, 2.0, 1.5]
)

doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('— End of Document — Version 3.0 —')
run.italic = True
run.font.size = Pt(9)
run.font.color.rgb = RGBColor(*GREY)

output_path = '/Users/jjjyyy/Auto-Count Social MediaReach/BRD_Auto_Count_Social_Media_Reach.docx'
doc.save(output_path)
print(f'Saved: {output_path}')
