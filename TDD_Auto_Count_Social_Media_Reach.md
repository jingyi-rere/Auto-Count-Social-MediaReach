# Technical Design Document
## Auto Count Social Media Reach — AI-Assisted Video Metrics Automation System

**Version:** 3.5 | **Date:** 21 May 2026 | **Status:** Final | **Prepared By:** jingyi-rere
**Based On:** BRD v5.5

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 3.0 | 13 May 2026 | jingyi-rere | Watcher daemon, yt-dlp, Firefox+Vision, atomic Lark write, 283 tests |
| 3.1 | 13 May 2026 | jingyi-rere | Architecture paragraph, cohort timeline, tracking plan, risks |
| 3.2 | 13 May 2026 | jingyi-rere | Pytest evidence reference, Vision latency note, Claude API cost estimate |
| 3.3 | 18 May 2026 | jingyi-rere | Instagram: reel page screenshot before Escape; watcher 3 min; flow diagram corrected |
| 3.4 | 18 May 2026 | jingyi-rere | 3-min interval reason added; 283 tests updated for Instagram arch; latency = 5 URLs ~15-20 min |
| 3.5 | 21 May 2026 | jingyi-rere | TikTok → Firefox+DOM; X (Twitter) added; watcher threading clarified; Phase 4 rollback added |

---

## 1. System Overview

The user pastes video URLs into Column F of Lark Bitable, then runs `python watcher.py` once.
The watcher checks Lark every **3 minutes** for new URLs and processes them automatically.

**Why 3 minutes:** Reduced from 5 minutes for faster user feedback. The watcher runs
sequentially — each cycle completes fully before sleeping, so no overlap between cycles
is possible. With Instagram taking 2–4 min per URL, a 5-minute sleep meant users waited
up to 9 minutes between paste and result. 3 minutes keeps that gap under 7 minutes.

Each URL is routed to the best extraction method:
- **yt-dlp** (YouTube): fast, exact numbers, no browser needed
- **Firefox + DOM** (TikTok, X/Twitter): reads data directly from page DOM and embedded JSON; no Vision needed
- **Firefox + Claude Haiku Vision** (Instagram, RedNote): persistent login session + screenshot

All extracted data is written to columns A, D, E, G in a single atomic Lark API call.
A hard allowlist in `lark_writer.py` ensures no other columns can ever be written to.

---

## 1.0 Architecture & Approach

**Two-track extraction pipeline:**

**Track 1 — YouTube (yt-dlp)**
- Passes URL to yt-dlp; retrieves title, upload date, view count from platform CDN metadata
- No browser launched; under 10 seconds per video
- Exact numbers — no Vision needed

**Track 2 — TikTok / X (Firefox + DOM)**
- Firefox navigates to the post URL; dismisses login popup
- **TikTok:** caption from `[data-e2e="browse-video-desc"]`; date from `<time>` or body text; view count from `"playCount"` embedded in page `<script>` JSON
- **X (Twitter):** caption from `[data-testid="tweetText"]`; date from `<time datetime>`; view count from post page rounded display or analytics modal (if logged in as post owner)
- No Vision needed — all data read from DOM

**Track 3 — Instagram / RedNote (Firefox + Claude Vision)**
- Persistent Firefox context (Playwright) with saved login session
- Dismisses popups, loads real page
- **Instagram two-screenshot approach:**
  1. Navigate to reel URL → capture screenshot AND `page.url` BEFORE pressing Escape
     (Escape can close the viewer and change `page.url` to the profile grid)
  2. Navigate to profile reels grid → capture screenshot for view count
     (view count only visible on desktop profile grid, not on reel page itself)
  3. Send both screenshots to Claude Haiku Vision for extraction
- **RedNote:** single screenshot of video page → send to Vision
- Each screenshot compressed to <4.5MB if needed
- Vision returns JSON: `{posted_date, caption, view_count}`

**Post-extraction:**
- Strip all hashtags (Unicode-aware regex — handles EN, Malay, Chinese, emoji tags)
- Single atomic Lark API call: write A, D, E, G
- Retry: 3 attempts with 2s / 4s / 8s exponential backoff
- Log all activity to `logs/auto_count.log`

---

## 1.1 Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| YouTube extraction | yt-dlp | Exact numbers, no browser, <10 sec — no Vision needed |
| TikTok extraction | Firefox + DOM | yt-dlp blocked by TikTok bot detection; DOM + embedded `playCount` JSON is reliable |
| X (Twitter) extraction | Firefox + DOM | Caption from `tweetText`; rounded view count from post page without login |
| Instagram/RedNote extraction | Firefox + Claude Haiku Vision | No public API; scraping blocked; UI changes break selectors |
| Instagram view count location | Profile reels grid (not reel page) | View count only visible on desktop grid, not on reel page |
| Screenshot timing (Instagram) | Before Escape key | Escape can close viewer and change page.url to profile grid — URL/screenshot must match |
| Vision model | claude-haiku-4-5 | Sufficient accuracy for numbers/dates; faster and cheaper than Sonnet |
| Watcher interval | 3 minutes | Watcher is single-threaded (cycles run sequentially, no overlap); 3 min balances responsiveness vs Instagram 2–4 min processing time |
| Column allowlist | Hard exception in code | Prevents any future bug from writing to wrong column |
| PIC filter | LARK_PIC_FILTER env var | Shared Lark table — only process rows where PIC = "TAN JING YI" |

**Test coverage for Instagram architecture:**
283 automated tests updated to match the two-screenshot approach.
`test_browser_reader.py` mocks assert that the reel page screenshot is captured before Escape,
and that `page.url` is read immediately after `goto()` returns.

---

## 2. System Architecture

### 2.1 Component Overview

```
watcher.py (daemon, every 3 min)
    └── lark_reader.py      → fetch rows where F has URL, A or G empty, PIC = TAN JING YI
    └── processor.py        → route URL to correct extractor
         ├── metadata_reader.py  → yt-dlp (YouTube only)
         └── browser_reader.py   → Firefox (TikTok/X: DOM; Instagram/RedNote: DOM+Vision)
              └── vision_extract.py  → Claude Haiku API (screenshots → JSON)
    └── lark_writer.py      → write A, D, E, G (hard allowlist enforced)
    └── reporter.py         → log summary to console
    └── logger.py           → rotating log file
```

### 2.2 System Flow

```
User pastes URL into Column F
         ↓
watcher.py polls every 3 min
         ↓
lark_reader.get_new_rows() → [(record_id, url), ...]
         ↓
processor.process(record_id, url)
         ↓
          Is YouTube?
         /          \
       YES           NO
        ↓             ↓
     yt-dlp     Is TikTok or X?
  (title, date,   /         \
   view_count)  YES           NO (Instagram/RedNote)
                 ↓             ↓
          browser_reader    browser_reader.py
          Firefox+DOM       Firefox opens URL
          (caption, date,   Takes screenshot(s)
           view_count from  For Instagram:
           DOM/script JSON)   1. Reel page → screenshot BEFORE Escape
                              2. Profile grid → screenshot for view count
                            vision_extract.py → Claude Haiku
                              (screenshot → JSON)
         \                /
          processor merges result
                  ↓
         strip hashtags (Unicode regex)
                  ↓
         lark_writer.write_row(record_id, date, caption, view_count)
         (single atomic API call — columns A, D, E, G only)
                  ↓
         logger + reporter
```

---

## 3. Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Browser automation | Playwright (Firefox) | 1.44.0 |
| YouTube/TikTok extraction | yt-dlp | latest |
| Vision AI | Claude Haiku (claude-haiku-4-5) | via Anthropic API |
| Lark integration | lark-oapi | 1.3.5 |
| Environment config | python-dotenv | 1.0.1 |
| Test framework | pytest | 8.2.0 |
| Language | Python | 3.9+ |

---

## 4. Detailed Component Design

### 4.1 lark_reader.py

- `get_new_rows()`: returns rows where Column F has URL but Column A or G is empty
- `_pic_matches()`: filters by PIC field — only returns rows where PIC = LARK_PIC_FILTER ("TAN JING YI")
- `_extract_url()`: handles plain string / dict / list-of-dicts URL formats from Lark API
- Pagination: handles Lark's page_token for tables >100 rows

### 4.2 lark_writer.py — Hard Column Allowlist

```python
ALLOWED_COLUMNS = {FIELD_DATE, FIELD_CAPTION, FIELD_CONTENT_TYPE, FIELD_VIEWS}

def write_row(record_id, **kwargs):
    for key in kwargs:
        if key not in ALLOWED_COLUMNS:
            raise ValueError(f"Column '{key}' is not in the write allowlist")
```

Tested by `tests/test_lark_writer.py` — 11 tests covering every allowed and disallowed column.

### 4.3 browser_reader.py — Instagram Key Logic

```python
async def extract_instagram(url):
    await page.goto(url)
    # CRITICAL: capture before any keyboard action
    # Escape can close the reel viewer and navigate away
    reel_url = page.url          # captured immediately after goto()
    reel_screenshot = screenshot()  # captured before pressing Escape

    # Navigate to profile grid for view count
    profile_url = build_profile_reels_url(reel_url)
    await page.goto(profile_url)
    grid_screenshot = screenshot()

    return await vision_extract(reel_screenshot, grid_screenshot)
```

### 4.4 vision_extract.py

- Sends screenshot(s) to Claude Haiku (`claude-haiku-4-5`) via Anthropic API
- Compresses image to <4.5MB if needed (base64 overhead limit)
- Structured prompt returns JSON: `{posted_date, caption, view_count}`
- Validates response structure before returning

### 4.5 processor.py

- Routes URL: `youtube.com` / `youtu.be` → yt-dlp; `tiktok.com` / `x.com` / `twitter.com` → Firefox+DOM; `instagram.com` / `xiaohongshu.com` / `xhslink.com` → Firefox+Vision
- Strips hashtags: `re.sub(r'#[\w\u00C0-\u024F\u4e00-\u9fff]+', '', caption)`
- Merges results and calls `lark_writer.write_row()`

---

## 5. Data Flow

```
Input:  Lark Column F URL (string)
            ↓
        URL router (processor.py)
            ↓
Track 1: yt-dlp → dict{title, upload_date, view_count}
Track 2: Firefox → screenshot(s) → Claude Vision → dict{posted_date, caption, view_count}
            ↓
        Hashtag strip (Unicode regex)
            ↓
Output: Lark write → Column A (date), D (caption), E ("Content Casual"), G (view count)
```

---

## 6. Column Allowlist Enforcement

Hard exception raised for any write attempt outside {A, D, E, G}:
- Tested: `test_write_to_B_raises`, `test_write_to_C_raises`, `test_write_to_F_raises`, `test_write_to_H_raises`
- Confirmed safe: `test_write_to_A_succeeds`, `test_write_to_D_succeeds`, `test_write_to_E_succeeds`, `test_write_to_G_succeeds`

---

## 8. Claude Vision Integration

- Model: `claude-haiku-4-5` (not Sonnet — sufficient for numbers/dates, 3× cheaper)
- Input: base64-encoded PNG/JPEG screenshot, <4.5MB
- Prompt: structured JSON extraction prompt with field definitions
- Output: `{posted_date: "YYYY-MM-DD", caption: "...", view_count: 12345}`
- Latency: ~2–4 minutes per Instagram URL (Vision API + browser load)
- **Batch estimate:** 5 Instagram URLs ≈ 15–20 minutes total
  For large batches, run the watcher during a break; don't wait at the terminal

---

## 9. Error Handling

| Error | Handling |
|-------|---------|
| Vision returns malformed JSON | Retry once; log error; skip row |
| yt-dlp extraction fails | Log error; skip row; retry next cycle |
| Lark API error | Retry 3× with exponential backoff (2s/4s/8s) |
| Firefox login expired | Friendly error: "Please log in to Instagram again" |
| URL not recognized | Skip with log: "Unknown platform for URL: ..." |
| Screenshot too large | Auto-compress to <4.5MB before sending |

---

## 10. Security Design

- API keys loaded from `.env` via `python-dotenv` — never hardcoded
- Instagram shortcode validated against allowlist (alphanumeric + underscore + hyphen only)
- Prompt-injection resistance: Vision prompt is system-defined, user data is image only
- Column allowlist prevents injection via Lark field names
- `.env` is git-ignored; `.env.template` (no secrets) committed instead

---

## 13. Testing Plan

| File | Tests | Coverage |
|------|-------|---------|
| test_positive_cases.py | 47 | Happy path for all 4 platforms |
| test_negative_cases.py | 55 | Invalid URLs, empty fields, malformed Vision response |
| test_browser_reader.py | 38 | Instagram two-screenshot flow; screenshot before Escape |
| test_vision_extract.py | 28 | Vision response parsing, compression, retry |
| test_processor.py | 22 | URL routing, hashtag stripping |
| test_lark_writer.py | 11 | Column allowlist enforcement |
| test_lark_writer_extended.py | 18 | Timestamp conversion, date edge cases |
| test_lark_reader.py | 14 | PIC filter, URL extraction, pagination |
| test_security.py | 24 | Shortcode validation, prompt injection, env secrets |
| test_performance.py | 14 | Latency thresholds, token cost |
| test_uiux.py | 12 | Field formatting, date format, caption truncation |
| **TOTAL** | **283** | All mocked — no real network calls |

---

## 14. requirements.txt (Pinned)

```
playwright==1.44.0
anthropic==0.28.0
lark-oapi==1.3.5
python-dotenv==1.0.1
pytest==8.2.0
```

---

*End of Document — Version 3.4*
