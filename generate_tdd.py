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
TEAL   = (0, 112, 112)

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

def add_bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet')
    if bold_prefix:
        r1 = p.add_run(bold_prefix)
        r1.bold = True
        r1.font.size = Pt(11)
        r2 = p.add_run(text)
        r2.font.size = Pt(11)
    else:
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

def add_code(doc, text):
    p = doc.add_paragraph()
    p.style = 'Normal'
    run = p.add_run(text)
    run.font.name = 'Courier New'
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0, 0, 139)
    p.paragraph_format.left_indent = Inches(0.3)
    shade_cell_para(p, 'F5F5F5')
    return p

def shade_cell_para(para, hex_color):
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    pPr.append(shd)

# ── COVER PAGE ────────────────────────────────────────────────────────────────
doc.add_paragraph()
doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('TECHNICAL DESIGN DOCUMENT')
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
    ('Document Version:', '1.0'),
    ('Date:', datetime.date.today().strftime('%d %B %Y')),
    ('Status:', 'Draft'),
    ('Prepared By:', 'jingyi-rere'),
    ('Based On:', 'BRD v3.0 — Auto Count Social Media Reach'),
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
        ('1.0', datetime.date.today().strftime('%d %B %Y'), 'jingyi-rere', 'Initial Technical Design Document based on BRD v3.0'),
    ],
    [0.7, 1.5, 1.5, 3.8]
)

doc.add_page_break()

# ── 1. SYSTEM OVERVIEW ────────────────────────────────────────────────────────
add_heading(doc, '1. System Overview', 1)
add_body(doc, (
    'The Auto Count Social Media Reach system is a Python-based automation tool that accepts video URLs '
    'from 7 social media platforms, extracts key video metrics using platform APIs and web scraping, '
    'and writes the structured data directly into the user\'s Lark Sheet via the Lark API. An AI module '
    'then analyses the collected data and generates performance insights and content recommendations.'
))

doc.add_paragraph()
add_heading(doc, '1.1 High-Level System Flow', 2)
add_body(doc, 'The system works in 4 simple steps:', italic=True)
make_table(doc,
    ['Step', 'What Happens', 'Who / What Does It'],
    [
        ('1', 'User pastes one or more video URLs', 'User (via simple web interface or input form)'),
        ('2', 'System identifies the platform and extracts: posted date, caption (no hashtags), view count', 'Platform Connector modules + AI caption cleaner'),
        ('3', 'System writes data into the correct Lark Sheet columns (A, D, E, F, G) — never touching B, C, H', 'Lark API Writer module'),
        ('4', 'AI analyses all collected data and outputs performance summary + recommendations', 'AI Analysis module (Claude API)'),
    ],
    [0.5, 3.5, 3.5]
)

# ── 2. SYSTEM ARCHITECTURE ────────────────────────────────────────────────────
add_heading(doc, '2. System Architecture', 1)
add_heading(doc, '2.1 Architecture Overview', 2)
add_body(doc, 'The system is built using a modular architecture with 5 core components:')

make_table(doc,
    ['Component', 'What It Does'],
    [
        ('1. Input Handler', 'Receives video URLs from the user, validates format, identifies platform'),
        ('2. Platform Connectors (x7)', 'One connector per platform — extracts posted date, caption, view count'),
        ('3. Data Processor', 'Cleans caption (removes hashtags), formats date, sets default Content Type'),
        ('4. Lark Sheet Writer', 'Connects to Lark API and writes data into correct columns'),
        ('5. AI Analysis Engine', 'Sends data to Claude API, receives performance summary + recommendations'),
    ],
    [2.5, 5.0]
)

add_heading(doc, '2.2 Architecture Diagram (Text)', 2)
add_body(doc, 'System flow from input to output:', italic=True)

diagram_lines = [
    '  [User] --pastes video URLs--> [Input Handler]',
    '                                      |',
    '              +------------------------+------------------------+',
    '              |            |           |          |            |',
    '    [Instagram]  [TikTok]  [YouTube]  [Facebook] [X] [RedNote] [Threads]',
    '    Connector   Connector  Connector  Connector  ...   ...      ...',
    '              |            |           |          |            |',
    '              +------------------------+------------------------+',
    '                                      |',
    '                            [Data Processor]',
    '                   (clean captions, format date, set defaults)',
    '                                      |',
    '                    +-----------------+------------------+',
    '                    |                                    |',
    '          [Lark Sheet Writer]                 [AI Analysis Engine]',
    '     (writes to columns A,D,E,F,G)      (performance summary + tips)',
    '                    |                                    |',
    '            [Lark Sheet Updated]              [Recommendations Output]',
]
for line in diagram_lines:
    add_code(doc, line)

doc.add_paragraph()

# ── 3. TECHNOLOGY STACK ───────────────────────────────────────────────────────
add_heading(doc, '3. Technology Stack', 1)
make_table(doc,
    ['Layer', 'Technology', 'Purpose', 'Why This Choice'],
    [
        ('Programming Language', 'Python 3.11+', 'Core system language', 'Wide library support, easy to maintain'),
        ('Web Scraping', 'Playwright / Selenium', 'Extract data from platforms without official API', 'Handles JavaScript-rendered pages on all 7 platforms'),
        ('Instagram API', 'Instagram Graph API', 'Official metric extraction for Instagram', 'Official and reliable for business accounts'),
        ('TikTok API', 'TikTok Research API', 'Official video data extraction', 'Official API for approved developers'),
        ('YouTube API', 'YouTube Data API v3', 'Official video stats extraction', 'Free, reliable, well-documented'),
        ('Facebook API', 'Meta Graph API', 'Official video metric extraction', 'Same API family as Instagram'),
        ('X API', 'X (Twitter) API v2', 'Official tweet/video metric extraction', 'Official and structured data'),
        ('RedNote / Threads', 'Web Scraping (Playwright)', 'No public API available', 'Only viable option for these platforms'),
        ('AI Engine', 'Claude API (Anthropic)', 'Generate performance summary and recommendations', 'Best-in-class language understanding'),
        ('Lark Integration', 'Lark Open API', 'Read and write to Lark Sheet', 'Official API, stable and secure'),
        ('Caption Cleaning', 'Python regex (re module)', 'Remove hashtags from captions', 'Fast, reliable, no extra dependencies'),
        ('User Interface', 'Streamlit (web app)', 'Simple UI for the user to paste links', 'Easy to build, runs in browser, no installation needed'),
        ('Environment Config', 'Python dotenv (.env file)', 'Store API keys securely', 'Industry standard for credential management'),
    ],
    [1.8, 2.0, 2.0, 1.7]
)

# ── 4. COMPONENT DESIGN ───────────────────────────────────────────────────────
add_heading(doc, '4. Component Design', 1)

add_heading(doc, '4.1 Input Handler', 2)
add_body(doc, 'Responsible for receiving and validating user input.')
make_table(doc,
    ['Function', 'Description'],
    [
        ('receive_urls()', 'Accepts a list of video URLs from the user interface'),
        ('validate_url(url)', 'Checks that the URL is a valid video link (not a profile or homepage)'),
        ('identify_platform(url)', 'Detects which platform the URL belongs to based on domain name'),
        ('route_to_connector(url, platform)', 'Sends each URL to the correct Platform Connector'),
    ],
    [2.5, 5.0]
)

add_body(doc, 'Platform identification logic (domain matching):', italic=True, color=GREY)
for line in [
    'instagram.com  -->  Instagram Connector',
    'tiktok.com     -->  TikTok Connector',
    'youtube.com / youtu.be  -->  YouTube Connector',
    'facebook.com   -->  Facebook Connector',
    'x.com / twitter.com  -->  X Connector',
    'xiaohongshu.com / rednote.com  -->  RedNote Connector',
    'threads.net    -->  Threads Connector',
]:
    add_code(doc, '  ' + line)
doc.add_paragraph()

add_heading(doc, '4.2 Platform Connectors', 2)
add_body(doc, 'Each platform has its own dedicated connector module. All connectors return the same standard data structure:')
add_code(doc, '  {')
add_code(doc, '    "platform":    "Instagram",')
add_code(doc, '    "url":         "https://www.instagram.com/reel/...",')
add_code(doc, '    "posted_date": "2026-05-01",')
add_code(doc, '    "caption":     "Raw caption text including #hashtags",')
add_code(doc, '    "view_count":  125000')
add_code(doc, '  }')
doc.add_paragraph()

make_table(doc,
    ['Platform', 'Access Method', 'Data Extracted', 'Notes'],
    [
        ('Instagram', 'Instagram Graph API', 'posted date, caption, Reels view count', 'Requires Business/Creator account connected to Meta app'),
        ('TikTok', 'TikTok Research API', 'posted date, description, video views', 'Requires TikTok developer account approval'),
        ('YouTube', 'YouTube Data API v3', 'published date, title, view count', 'Free quota: 10,000 units/day — sufficient for this use case'),
        ('Facebook', 'Meta Graph API', 'posted date, caption, video views', 'Same app as Instagram — shares access token'),
        ('X (Twitter)', 'X API v2', 'posted date, tweet text, video views', 'Free tier has rate limits; monitor usage'),
        ('RedNote', 'Playwright web scraping', 'posted date, caption, view count', 'No public API — scraping approach; may need manual login session'),
        ('Threads', 'Playwright web scraping', 'posted date, caption, view count', 'Limited API; scraping used as fallback'),
    ],
    [1.2, 1.8, 2.2, 2.3]
)

add_heading(doc, '4.3 Data Processor', 2)
add_body(doc, 'Cleans and formats raw data from connectors before writing to Lark Sheet.')
make_table(doc,
    ['Function', 'Input', 'Output', 'Rule'],
    [
        ('clean_caption(text)', 'Raw caption with hashtags', 'Caption without hashtags', 'Remove all words starting with #'),
        ('format_date(raw_date)', 'Platform date string', 'Formatted date (DD/MM/YYYY)', 'Standardise across all platforms'),
        ('set_content_type()', 'Nothing', '"Content Casual"', 'Always returns this default value'),
        ('handle_empty_caption(text)', 'Empty or None caption', '"No caption"', 'Fallback if caption is missing'),
    ],
    [2.0, 1.8, 1.8, 1.9]
)

add_body(doc, 'Hashtag removal logic:', italic=True, color=GREY)
add_code(doc, '  import re')
add_code(doc, '  def clean_caption(text):')
add_code(doc, '      if not text or text.strip() == "":')
add_code(doc, '          return "No caption"')
add_code(doc, '      cleaned = re.sub(r\'#\w+\', \'\', text)  # remove all #hashtags')
add_code(doc, '      return cleaned.strip()              # remove extra spaces')
doc.add_paragraph()

add_heading(doc, '4.4 Lark Sheet Writer', 2)
add_body(doc, 'Connects to the Lark Open API and writes data into the correct columns of the existing Lark Sheet.')
make_table(doc,
    ['Function', 'Description'],
    [
        ('connect_lark()', 'Authenticates with Lark API using stored credentials'),
        ('find_next_empty_row()', 'Scans the sheet to find the next available empty row'),
        ('write_row(row_data)', 'Writes data to columns A, D, E, F, G only — never touches B, C, H'),
        ('verify_write()', 'Reads back the written row to confirm data was saved correctly'),
    ],
    [2.5, 5.0]
)

add_body(doc, 'Column write mapping:', italic=True, color=GREY)
add_code(doc, '  Column A  <--  posted_date       (from Platform Connector)')
add_code(doc, '  Column B  <--  [SKIP - never write]')
add_code(doc, '  Column C  <--  [SKIP - never write]')
add_code(doc, '  Column D  <--  clean_caption()   (hashtags removed)')
add_code(doc, '  Column E  <--  "Content Casual"  (hardcoded default)')
add_code(doc, '  Column F  <--  url               (original video URL)')
add_code(doc, '  Column G  <--  view_count        (from Platform Connector)')
add_code(doc, '  Column H  <--  [SKIP - never write]')
doc.add_paragraph()

add_heading(doc, '4.5 AI Analysis Engine', 2)
add_body(doc, 'Uses the Claude API to analyse collected video metrics and generate recommendations.')
make_table(doc,
    ['Function', 'Description'],
    [
        ('prepare_analysis_data()', 'Formats all collected metrics into a structured prompt for Claude'),
        ('call_claude_api(prompt)', 'Sends data to Claude API and receives analysis response'),
        ('parse_recommendations(response)', 'Extracts top-performing videos, insights, and next-cycle recommendations'),
        ('output_summary()', 'Displays the analysis to the user in the interface'),
    ],
    [2.5, 5.0]
)

add_body(doc, 'What the AI analysis covers:', italic=True, color=GREY)
for item in [
    'Top 3 best-performing videos (by view count)',
    'Lowest performing videos and possible reasons',
    'Best performing platform this cycle',
    'Recommended content topics for next cycle',
    'Recommended posting patterns (based on posted dates vs performance)',
    'At least 3 specific, actionable content tips',
]:
    add_bullet(doc, item)

# ── 5. DATA FLOW ──────────────────────────────────────────────────────────────
add_heading(doc, '5. Data Flow', 1)
add_heading(doc, '5.1 Step-by-Step Data Flow', 2)
make_table(doc,
    ['Step', 'Action', 'Data In', 'Data Out'],
    [
        ('1', 'User submits video URLs', 'Raw URLs (list)', 'Validated URLs with platform labels'),
        ('2', 'Platform Connector runs', 'Video URL', 'Raw: posted_date, caption, view_count'),
        ('3', 'Data Processor cleans data', 'Raw extracted data', 'Clean: formatted date, caption without hashtags, "Content Casual"'),
        ('4', 'Lark Writer maps columns', 'Clean data object', 'Column mapping: A=date, D=caption, E=type, F=url, G=views'),
        ('5', 'Lark API writes to sheet', 'Column mapping', 'New row added to Lark Sheet'),
        ('6', 'AI Engine analyses data', 'All collected metrics', 'Performance summary + recommendations text'),
        ('7', 'Output shown to user', 'AI response', 'Summary displayed on screen'),
    ],
    [0.5, 2.0, 2.0, 3.0]
)

add_heading(doc, '5.2 Error Handling Flow', 2)
make_table(doc,
    ['Error Scenario', 'System Response', 'User Impact'],
    [
        ('Invalid or broken URL', 'Skip this URL, log error, continue to next', 'User sees error message for that specific link only'),
        ('Platform API rate limit hit', 'Wait and retry up to 3 times, then skip', 'Small delay; user notified if retry fails'),
        ('Caption is empty / missing', 'Write "No caption" in Column D', 'No disruption — handled gracefully'),
        ('Lark API connection fails', 'Retry once; if still fails, show error and stop', 'User notified to check Lark credentials'),
        ('RedNote scraping blocked', 'Notify user this link could not be processed', 'User can enter RedNote data manually'),
        ('Platform returns no view count', 'Write 0 in Column G and flag in error log', 'Data still saved; user can update manually'),
    ],
    [2.2, 2.5, 2.8]
)

# ── 6. LARK SHEET INTEGRATION ─────────────────────────────────────────────────
add_heading(doc, '6. Lark Sheet Integration', 1)

add_heading(doc, '6.1 Authentication', 2)
add_body(doc, 'The system connects to Lark using the Lark Open Platform API:')
for item in [
    'Create a Lark App on the Lark Open Platform (open.larksuite.com)',
    'Enable Sheets API permissions for the app',
    'Store App ID and App Secret securely in a .env file (never in the code)',
    'Use OAuth 2.0 token flow to get access token before each session',
]:
    add_bullet(doc, item)

add_heading(doc, '6.2 Sheet Access Setup', 2)
make_table(doc,
    ['Setting', 'Value'],
    [
        ('Lark Sheet ID', 'Obtained from the sheet URL — stored in .env file'),
        ('Sheet Name / Tab', 'The specific tab where video data is stored'),
        ('Write Columns', 'A, D, E, F, G only'),
        ('Protected Columns', 'B, C, H — system never reads or writes these'),
        ('Row Detection', 'System scans column F (Link) to find the next empty row'),
    ],
    [2.5, 5.0]
)

add_heading(doc, '6.3 Write Operation Safety Rules', 2)
for item in [
    'Before writing, system checks that target columns are B/C/H — if yes, ABORT and log error',
    'System always appends to a NEW row — never overwrites existing rows',
    'After writing, system reads back the row to verify data was saved correctly',
    'If verification fails, system retries once before alerting the user',
]:
    add_bullet(doc, item)

# ── 7. AI ANALYSIS DESIGN ─────────────────────────────────────────────────────
add_heading(doc, '7. AI Analysis Design', 1)

add_heading(doc, '7.1 Claude API Integration', 2)
add_body(doc, 'The system uses Anthropic\'s Claude API to generate performance insights.')
make_table(doc,
    ['Setting', 'Value'],
    [
        ('Model', 'claude-3-5-sonnet (latest)'),
        ('Trigger', 'After all video data has been written to Lark Sheet'),
        ('Input', 'Structured JSON of all collected metrics for the current session'),
        ('Output', 'Plain English summary + 3 or more actionable recommendations'),
        ('Language', 'English (can be extended to other languages later)'),
    ],
    [2.5, 5.0]
)

add_heading(doc, '7.2 Sample Prompt Structure', 2)
add_body(doc, 'The following prompt template is sent to Claude:', italic=True, color=GREY)
add_code(doc, '  You are a social media performance analyst.')
add_code(doc, '  Analyse the following video metrics and provide:')
add_code(doc, '  1. Top 3 best performing videos and why')
add_code(doc, '  2. Lowest performing video and possible reason')
add_code(doc, '  3. Best performing platform this cycle')
add_code(doc, '  4. At least 3 specific content recommendations for next cycle')
add_code(doc, '  Keep your response simple and easy to understand.')
add_code(doc, '')
add_code(doc, '  Video Data:')
add_code(doc, '  [{ platform, title, views, posted_date, url }, ...]')
doc.add_paragraph()

# ── 8. SECURITY DESIGN ────────────────────────────────────────────────────────
add_heading(doc, '8. Security Design', 1)
make_table(doc,
    ['Security Concern', 'How It Is Handled'],
    [
        ('API Keys & Credentials', 'Stored in .env file — never hardcoded in source code — .env added to .gitignore'),
        ('Lark Access Token', 'Generated fresh each session via OAuth; expires after 2 hours'),
        ('GitHub Repository', 'All sensitive files excluded via .gitignore (no API keys ever pushed)'),
        ('User Data', 'No user personal data is stored — only video metrics and URLs'),
        ('Platform Login Sessions', 'For scraping (RedNote/Threads), login session cookies stored locally and encrypted'),
    ],
    [2.5, 5.0]
)

# ── 9. PROJECT STRUCTURE ──────────────────────────────────────────────────────
add_heading(doc, '9. Project File Structure', 1)
add_body(doc, 'How the code will be organised in the GitHub repository:')
for line in [
    'Auto-Count-Social-MediaReach/',
    '|-- app.py                    # Main entry point (Streamlit UI)',
    '|-- connectors/',
    '|   |-- instagram.py          # Instagram connector',
    '|   |-- tiktok.py             # TikTok connector',
    '|   |-- youtube.py            # YouTube connector',
    '|   |-- facebook.py           # Facebook connector',
    '|   |-- twitter_x.py         # X (Twitter) connector',
    '|   |-- rednote.py            # RedNote connector',
    '|   |-- threads.py            # Threads connector',
    '|-- processor.py              # Caption cleaner + data formatter',
    '|-- lark_writer.py            # Lark Sheet API integration',
    '|-- ai_analysis.py            # Claude API integration',
    '|-- .env                      # API keys (NOT pushed to GitHub)',
    '|-- .gitignore                # Excludes .env and sensitive files',
    '|-- requirements.txt          # Python dependencies',
    '|-- BRD_Auto_Count_Social_Media_Reach.docx',
    '|-- TDD_Auto_Count_Social_Media_Reach.docx',
]:
    add_code(doc, '  ' + line)
doc.add_paragraph()

# ── 10. IMPLEMENTATION PLAN ───────────────────────────────────────────────────
add_heading(doc, '10. Implementation Plan', 1)
make_table(doc,
    ['Day', 'Phase', 'Tasks'],
    [
        ('Day 1', 'Setup + Core Connectors', 'Set up project structure, install dependencies, build YouTube + Instagram + TikTok connectors, test data extraction'),
        ('Day 2', 'Lark Integration', 'Build Lark Sheet Writer, map columns A/D/E/F/G, test writing to sheet, add column protection logic'),
        ('Day 3', 'Remaining Platforms', 'Build Facebook + X connectors, build RedNote + Threads scrapers, test all 7 connectors'),
        ('Day 4', 'AI Analysis + UI', 'Integrate Claude API for analysis, build Streamlit user interface, end-to-end testing'),
        ('Day 5', 'Polish + Launch', 'Error handling, batch input, performance testing, final review, push to GitHub'),
    ],
    [0.7, 2.0, 4.8]
)

# ── 11. DEPENDENCIES ──────────────────────────────────────────────────────────
add_heading(doc, '11. Dependencies & Libraries', 1)
make_table(doc,
    ['Library', 'Version', 'Purpose'],
    [
        ('streamlit', 'latest', 'User interface (web app)'),
        ('anthropic', 'latest', 'Claude API for AI analysis'),
        ('playwright', 'latest', 'Web scraping for RedNote and Threads'),
        ('google-api-python-client', 'latest', 'YouTube Data API v3'),
        ('requests', 'latest', 'HTTP calls to platform APIs'),
        ('python-dotenv', 'latest', 'Load API keys from .env file'),
        ('lark-oapi', 'latest', 'Official Lark Open API SDK'),
        ('re (built-in)', 'built-in', 'Regex for hashtag removal'),
        ('datetime (built-in)', 'built-in', 'Date formatting'),
    ],
    [2.5, 1.0, 4.0]
)

# ── 12. TESTING PLAN ──────────────────────────────────────────────────────────
add_heading(doc, '12. Testing Plan', 1)
make_table(doc,
    ['Test Type', 'What Is Tested', 'Pass Criteria'],
    [
        ('Unit Test', 'Caption cleaning (hashtag removal)', 'Zero hashtags remain in output'),
        ('Unit Test', 'Platform URL identification', 'Correct connector called for each of 7 platforms'),
        ('Unit Test', 'Column mapping', 'Data lands in correct Lark columns A, D, E, F, G'),
        ('Unit Test', 'Column protection', 'System never writes to columns B, C, or H'),
        ('Integration Test', 'End-to-end: URL to Lark Sheet', 'Full flow completes and Lark Sheet is updated correctly'),
        ('Accuracy Test', 'View count vs platform figure', '99% match for 20 sample videos'),
        ('Error Test', 'Invalid URL submitted', 'System skips gracefully and continues'),
        ('Error Test', 'Lark API disconnected', 'User receives clear error message'),
    ],
    [1.5, 2.8, 3.2]
)

# ── 13. SIGN-OFF ──────────────────────────────────────────────────────────────
add_heading(doc, '13. Sign-Off & Approval', 1)
add_body(doc, 'By signing below, the approver confirms that this Technical Design Document accurately represents the proposed technical approach for building the Auto Count Social Media Reach system.')
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
run = p.add_run('— End of Document — Version 1.0 —')
run.italic = True
run.font.size = Pt(9)
run.font.color.rgb = RGBColor(*GREY)

output_path = '/Users/jjjyyy/Auto-Count Social MediaReach/TDD_Auto_Count_Social_Media_Reach.docx'
doc.save(output_path)
print(f'Saved: {output_path}')
