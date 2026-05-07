from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import datetime

doc = Document()

# ── Page margins ──────────────────────────────────────────────────────────────
section = doc.sections[0]
section.page_width  = Inches(8.5)
section.page_height = Inches(11)
section.left_margin   = Inches(1)
section.right_margin  = Inches(1)
section.top_margin    = Inches(1)
section.bottom_margin = Inches(1)

# ── Helper: set paragraph style safely ───────────────────────────────────────
def add_heading(doc, text, level, color=None):
    p = doc.add_paragraph()
    p.style = f'Heading {level}'
    run = p.add_run(text)
    if color:
        run.font.color.rgb = RGBColor(*color)
    return p

def add_body(doc, text, bold=False, italic=False):
    p = doc.add_paragraph()
    p.style = 'Normal'
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(11)
    return p

def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    run.font.size = Pt(11)
    return p

def add_numbered(doc, text):
    p = doc.add_paragraph(style='List Number')
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

def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        tag = OxmlElement(f'w:{edge}')
        tag.set(qn('w:val'), 'single')
        tag.set(qn('w:sz'), '4')
        tag.set(qn('w:space'), '0')
        tag.set(qn('w:color'), 'CCCCCC')
        tcBorders.append(tag)
    tcPr.append(tcBorders)

BLUE  = (31, 73, 125)
WHITE = (255, 255, 255)

# ═══════════════════════════════════════════════════════════════════════════════
# COVER / TITLE BLOCK
# ═══════════════════════════════════════════════════════════════════════════════
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('BUSINESS REQUIREMENTS DOCUMENT')
run.bold = True
run.font.size = Pt(22)
run.font.color.rgb = RGBColor(*BLUE)

p2 = doc.add_paragraph()
p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run2 = p2.add_run('Auto Count Social Media Reach')
run2.bold = True
run2.font.size = Pt(16)
run2.font.color.rgb = RGBColor(*BLUE)

doc.add_paragraph()

# Metadata table
meta = doc.add_table(rows=4, cols=2)
meta.alignment = WD_TABLE_ALIGNMENT.CENTER
widths = [Inches(2.2), Inches(5.3)]
labels = ['Document Version:', 'Date:', 'Status:', 'Prepared By:']
values = ['1.0', datetime.date.today().strftime('%d %B %Y'), 'Draft', 'Business Analyst']
for i, (lbl, val) in enumerate(zip(labels, values)):
    row = meta.rows[i]
    row.cells[0].width = widths[0]
    row.cells[1].width = widths[1]
    lc = row.cells[0].paragraphs[0].add_run(lbl)
    lc.bold = True
    lc.font.size = Pt(10)
    vc = row.cells[1].paragraphs[0].add_run(val)
    vc.font.size = Pt(10)
    shade_cell(row.cells[0], 'E2EFFF')
    set_cell_border(row.cells[0])
    set_cell_border(row.cells[1])

doc.add_paragraph()
doc.add_paragraph()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '1. Executive Summary', 1)
add_body(doc, (
    'This document defines the business requirements for an AI-assisted Social Media Reach '
    'Automation system. The system will replace the existing manual process of tracking social '
    'media performance metrics — including reach, views, and engagement — with an automated, '
    'centralised solution that ingests post links, extracts key metrics, consolidates data into '
    'a structured tracking sheet, and generates actionable performance insights.'
))

# ═══════════════════════════════════════════════════════════════════════════════
# 2. PROBLEM STATEMENT
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '2. Problem Statement', 1)

add_heading(doc, '2.1 Current State', 2)
add_body(doc, 'The existing process requires team members to perform the following steps manually:')
for item in [
    'Search across multiple social media platforms individually.',
    'Manually locate each post and record reach and view figures.',
    'Transcribe data into a tracking spreadsheet by hand.',
    'Compile and review results for reporting purposes.',
]:
    add_bullet(doc, item)

add_heading(doc, '2.2 Pain Points', 2)

pain_table = doc.add_table(rows=5, cols=3)
pain_table.alignment = WD_TABLE_ALIGNMENT.LEFT
col_widths = [Inches(0.6), Inches(2.5), Inches(4.4)]
headers = ['#', 'Pain Point', 'Impact']
rows_data = [
    ('1', 'Time-consuming manual searches', 'Hours spent per reporting cycle; opportunity cost on higher-value work'),
    ('2', 'Human error in data entry', 'Inaccurate metrics lead to flawed strategic decisions'),
    ('3', 'Inconsistent reporting format', 'Difficulty benchmarking performance across periods'),
    ('4', 'No automated analysis', 'Insights are slow to surface; recommendations lag behind the data'),
]
for j, h in enumerate(headers):
    cell = pain_table.rows[0].cells[j]
    cell.width = col_widths[j]
    run = cell.paragraphs[0].add_run(h)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(*WHITE)
    shade_cell(cell, '1F497D')
    set_cell_border(cell)

for i, (num, pt, impact) in enumerate(rows_data, 1):
    row = pain_table.rows[i]
    for j, val in enumerate([num, pt, impact]):
        row.cells[j].width = col_widths[j]
        row.cells[j].paragraphs[0].add_run(val).font.size = Pt(10)
        shade_cell(row.cells[j], 'F0F4FF' if i % 2 == 0 else 'FFFFFF')
        set_cell_border(row.cells[j])

doc.add_paragraph()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. BUSINESS OBJECTIVES
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '3. Business Objectives', 1)
for obj in [
    'Eliminate manual data entry for social media metrics collection.',
    'Reduce reporting time per cycle by at least 80%.',
    'Improve data accuracy and consistency across all platforms.',
    'Provide automated performance analysis and strategic recommendations.',
    'Enable faster, data-driven decision-making for content strategy.',
]:
    add_bullet(doc, obj)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. SCOPE
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '4. Scope', 1)

add_heading(doc, '4.1 In Scope', 2)
for item in [
    'Ingestion of post URLs from supported social media platforms.',
    'Automated extraction of reach, views, and engagement metrics.',
    'Consolidation of metrics into a centralised tracking sheet.',
    'AI-generated performance summaries and recommendations.',
    'Support for platforms: Facebook, Instagram, TikTok, LinkedIn, X (Twitter), YouTube.',
]:
    add_bullet(doc, item)

add_heading(doc, '4.2 Out of Scope', 2)
for item in [
    'Publishing or scheduling social media posts.',
    'Paid advertising metrics (focus is on organic reach only).',
    'Real-time streaming of live engagement data.',
    'Integration with third-party CRM or ERP systems (Phase 1).',
]:
    add_bullet(doc, item)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. STAKEHOLDERS
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '5. Stakeholders', 1)

sh_table = doc.add_table(rows=6, cols=3)
sh_table.alignment = WD_TABLE_ALIGNMENT.LEFT
sh_widths = [Inches(2.2), Inches(2.5), Inches(2.8)]
sh_headers = ['Stakeholder', 'Role', 'Interest / Responsibility']
sh_data = [
    ('Social Media Team', 'Primary User', 'Input post links; review tracking data and recommendations'),
    ('Content Strategist', 'Primary User', 'Consume performance analysis for planning'),
    ('Marketing Manager', 'Approver', 'Approve reporting outputs; strategic oversight'),
    ('IT / Development Team', 'Implementer', 'Build, deploy, and maintain the system'),
    ('Senior Leadership', 'Sponsor', 'Budget approval; review high-level performance dashboards'),
]
for j, h in enumerate(sh_headers):
    cell = sh_table.rows[0].cells[j]
    cell.width = sh_widths[j]
    run = cell.paragraphs[0].add_run(h)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(*WHITE)
    shade_cell(cell, '1F497D')
    set_cell_border(cell)

for i, (s, r, interest) in enumerate(sh_data, 1):
    row = sh_table.rows[i]
    for j, val in enumerate([s, r, interest]):
        row.cells[j].width = sh_widths[j]
        row.cells[j].paragraphs[0].add_run(val).font.size = Pt(10)
        shade_cell(row.cells[j], 'F0F4FF' if i % 2 == 0 else 'FFFFFF')
        set_cell_border(row.cells[j])

doc.add_paragraph()

# ═══════════════════════════════════════════════════════════════════════════════
# 6. FUNCTIONAL REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '6. Functional Requirements', 1)

func_sections = [
    ('6.1 Post Link Ingestion', [
        'FR-01: The system shall accept one or more social media post URLs via a centralised input interface.',
        'FR-02: The system shall validate that submitted URLs point to supported platforms.',
        'FR-03: The system shall support batch input of multiple links in a single session.',
        'FR-04: The system shall provide confirmation feedback upon successful URL submission.',
    ]),
    ('6.2 Metric Extraction', [
        'FR-05: The system shall automatically extract reach figures for each submitted post.',
        'FR-06: The system shall automatically extract view counts for each submitted post.',
        'FR-07: The system shall extract engagement metrics including likes, comments, shares, and saves where available.',
        'FR-08: The system shall timestamp the extraction date and time for each record.',
        'FR-09: The system shall handle platform-specific metric naming conventions and normalise them into a standard schema.',
    ]),
    ('6.3 Tracking Sheet Generation', [
        'FR-10: The system shall consolidate extracted metrics into a structured tracking sheet.',
        'FR-11: The tracking sheet shall include: Post URL, Platform, Post Date, Reach, Views, Likes, Comments, Shares, Engagement Rate, and Extraction Date.',
        'FR-12: The system shall support export of the tracking sheet in XLSX and CSV formats.',
        'FR-13: The system shall append new data to an existing tracking sheet without overwriting historical records.',
    ]),
    ('6.4 Performance Analysis', [
        'FR-14: The system shall generate an automated performance summary per reporting cycle.',
        'FR-15: The summary shall highlight top-performing posts by reach and engagement.',
        'FR-16: The system shall calculate average and aggregate metrics across the reporting period.',
        'FR-17: The system shall compare performance against the previous reporting cycle where data is available.',
    ]),
    ('6.5 Recommendations Engine', [
        'FR-18: The system shall produce AI-generated content strategy recommendations based on aggregated metrics.',
        'FR-19: Recommendations shall identify content formats, posting times, and topics with the highest engagement.',
        'FR-20: Recommendations shall be presented in plain language suitable for non-technical stakeholders.',
        'FR-21: The system shall allow users to export the analysis report as a PDF or Word document.',
    ]),
]

for section_title, items in func_sections:
    add_heading(doc, section_title, 2)
    for item in items:
        add_bullet(doc, item)

# ═══════════════════════════════════════════════════════════════════════════════
# 7. NON-FUNCTIONAL REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '7. Non-Functional Requirements', 1)

nfr_data = [
    ('NFR-01', 'Performance', 'Metric extraction for a batch of up to 50 posts shall complete within 2 minutes.'),
    ('NFR-02', 'Accuracy', 'Extracted metrics shall match platform-reported figures with 99% accuracy.'),
    ('NFR-03', 'Availability', 'The system shall maintain 99.5% uptime during business hours.'),
    ('NFR-04', 'Security', 'All API credentials and user data shall be encrypted at rest and in transit.'),
    ('NFR-05', 'Usability', 'A new user shall be able to submit links and retrieve a report within 5 minutes without training.'),
    ('NFR-06', 'Scalability', 'The system shall support processing of up to 500 posts per reporting cycle.'),
    ('NFR-07', 'Auditability', 'All data extraction events shall be logged with user ID, timestamp, and source URL.'),
    ('NFR-08', 'Maintainability', 'Platform adapters shall be independently updatable without system downtime.'),
]

nfr_table = doc.add_table(rows=len(nfr_data) + 1, cols=3)
nfr_table.alignment = WD_TABLE_ALIGNMENT.LEFT
nfr_widths = [Inches(1.0), Inches(1.5), Inches(5.0)]
nfr_headers = ['ID', 'Category', 'Requirement']
for j, h in enumerate(nfr_headers):
    cell = nfr_table.rows[0].cells[j]
    cell.width = nfr_widths[j]
    run = cell.paragraphs[0].add_run(h)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(*WHITE)
    shade_cell(cell, '1F497D')
    set_cell_border(cell)

for i, (nid, cat, req) in enumerate(nfr_data, 1):
    row = nfr_table.rows[i]
    for j, val in enumerate([nid, cat, req]):
        row.cells[j].width = nfr_widths[j]
        row.cells[j].paragraphs[0].add_run(val).font.size = Pt(10)
        shade_cell(row.cells[j], 'F0F4FF' if i % 2 == 0 else 'FFFFFF')
        set_cell_border(row.cells[j])

doc.add_paragraph()

# ═══════════════════════════════════════════════════════════════════════════════
# 8. ASSUMPTIONS & CONSTRAINTS
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '8. Assumptions & Constraints', 1)

add_heading(doc, '8.1 Assumptions', 2)
for item in [
    'The organisation holds valid API access or scraping permissions for each supported platform.',
    'Post URLs submitted are publicly accessible or the system is authenticated with appropriate platform accounts.',
    'Users have access to a web browser and stable internet connection.',
    'Reporting cycles are defined on a weekly or monthly basis.',
]:
    add_bullet(doc, item)

add_heading(doc, '8.2 Constraints', 2)
for item in [
    'Platform APIs may impose rate limits that affect extraction speed.',
    'Metric availability varies by platform (e.g., reach is not available on all platforms).',
    'The system must comply with each platform\'s Terms of Service regarding data access.',
    'Budget and timeline for Phase 1 are subject to management approval.',
]:
    add_bullet(doc, item)

# ═══════════════════════════════════════════════════════════════════════════════
# 9. SUCCESS CRITERIA
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '9. Success Criteria', 1)
for item in [
    'Reduction in manual reporting time by at least 80% within 3 months of go-live.',
    'Zero manual data entry required for supported platforms.',
    'Data accuracy rate of 99% or above validated against platform native dashboards.',
    'Positive usability feedback from at least 80% of team members.',
    'AI-generated recommendations rated as actionable by the content strategy team.',
]:
    add_bullet(doc, item)

# ═══════════════════════════════════════════════════════════════════════════════
# 10. GLOSSARY
# ═══════════════════════════════════════════════════════════════════════════════
add_heading(doc, '10. Glossary', 1)

glossary = [
    ('Reach', 'The number of unique accounts that have seen a post.'),
    ('Views', 'The total number of times a post has been displayed, including repeat views.'),
    ('Engagement Rate', 'Total interactions (likes, comments, shares, saves) divided by reach, expressed as a percentage.'),
    ('Tracking Sheet', 'A structured spreadsheet consolidating metrics from multiple posts and platforms.'),
    ('Reporting Cycle', 'A defined period (e.g., weekly, monthly) over which performance data is collected and analysed.'),
    ('Platform Adapter', 'A modular component responsible for extracting metrics from a specific social media platform.'),
]

g_table = doc.add_table(rows=len(glossary) + 1, cols=2)
g_table.alignment = WD_TABLE_ALIGNMENT.LEFT
g_widths = [Inches(2.0), Inches(5.5)]
for j, h in enumerate(['Term', 'Definition']):
    cell = g_table.rows[0].cells[j]
    cell.width = g_widths[j]
    run = cell.paragraphs[0].add_run(h)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(*WHITE)
    shade_cell(cell, '1F497D')
    set_cell_border(cell)

for i, (term, defn) in enumerate(glossary, 1):
    row = g_table.rows[i]
    row.cells[0].width = g_widths[0]
    row.cells[1].width = g_widths[1]
    t_run = row.cells[0].paragraphs[0].add_run(term)
    t_run.bold = True
    t_run.font.size = Pt(10)
    row.cells[1].paragraphs[0].add_run(defn).font.size = Pt(10)
    shade_cell(row.cells[0], 'F0F4FF' if i % 2 == 0 else 'FFFFFF')
    shade_cell(row.cells[1], 'F0F4FF' if i % 2 == 0 else 'FFFFFF')
    set_cell_border(row.cells[0])
    set_cell_border(row.cells[1])

doc.add_paragraph()

# ── Footer note ───────────────────────────────────────────────────────────────
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('— End of Document —')
run.italic = True
run.font.size = Pt(9)
run.font.color.rgb = RGBColor(128, 128, 128)

# ── Save ──────────────────────────────────────────────────────────────────────
output_path = '/Users/jjjyyy/Auto-Count Social MediaReach/BRD_Auto_Count_Social_Media_Reach.docx'
doc.save(output_path)
print(f'Saved: {output_path}')
