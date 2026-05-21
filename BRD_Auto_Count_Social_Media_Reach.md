# Business Requirements Document
## Auto Count Social Media Reach — AI-Assisted Video Metrics Automation System

**Version:** 5.5 | **Date:** 21 May 2026 | **Status:** Final | **Prepared By:** jingyi-rere

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 5.0 | 13 May 2026 | jingyi-rere | Watcher daemon, yt-dlp, Firefox+Vision, 283 tests |
| 5.1 | 13 May 2026 | jingyi-rere | Pain metrics, AI justification, 33 hrs/year value, AC-01–AC-10 |
| 5.2 | 13 May 2026 | jingyi-rere | Phase 1/2 scope clarified, baseline 40 min/week, accuracy thresholds aligned |
| 5.3 | 18 May 2026 | jingyi-rere | Instagram view count from reel screenshot before Escape; watcher 3 min |
| 5.4 | 18 May 2026 | jingyi-rere | Defensive baseline note removed (stated upfront); Phase 2 moved to Appendix A |
| 5.5 | 21 May 2026 | jingyi-rere | TikTok → Firefox+DOM (not yt-dlp); X (Twitter) added; live 5-platform test confirmed |

---

## 1. Executive Summary

A video content creator at ricebowlmy spends ~40 minutes every week manually collecting
performance data (posted date, caption, view count) from 4 platforms (Instagram, YouTube,
TikTok, RedNote) and typing it into Lark Bitable. This system eliminates that 40 minutes.

The user pastes video URLs into Lark Column F. A background watcher detects new URLs within
3 minutes and auto-fills: posted date (Column A), caption without hashtags (Column D),
content type (Column E), and view count (Column G).

Claude AI Vision is required — not optional — because Instagram, TikTok, and RedNote have
no public API, block scrapers, and change UI regularly. Only Vision can read any screenshot
regardless of platform, language, or UI version.

**Projected outcome:** 38 minutes saved per week ≈ 33 hours per year, near-zero errors.

---

## 2. Hard Rules (NEVER Violate)

| Rule | Description |
|------|-------------|
| RULE-01 | Only write to Lark columns A, D, E, G. Writing to B, C, F, H raises an exception. |
| RULE-02 | Never overwrite Column F. User pastes URLs there — system never touches it. |
| RULE-03 | Never append new rows. Always write into the existing row. |
| RULE-04 | Strip ALL hashtags from caption (Unicode-aware) before writing to Column D. |
| RULE-05 | Column E must always be exactly "Content Casual" — hardcoded, no exceptions. |

---

## 3. Problem Statement

### 3.1 Time Breakdown (10 videos/week)

| Task (per video) | Time | Specific Problem |
|------------------|------|-----------------|
| Open platform, find the video | ~1 min | Instagram grid paginated; RedNote UI in Chinese |
| Read and copy the caption | ~1 min | Long captions, overlaid text |
| Remove hashtags manually | ~1 min | 15–25 tags in EN/Malay/Chinese; easy to miss hidden tags |
| Note the view count | ~30 sec | Instagram hides view counts on desktop |
| Type data into Lark Bitable | ~30 sec | 4 fields, typos happen (10,000 → 1,000) |
| **TOTAL per video** | **~4 min** | |
| **TOTAL per week (10 videos)** | **~40 min** | 40 min of pure manual data entry every week |

### 3.2 Why Simple Automation Cannot Solve This

- Instagram, TikTok, RedNote have no public API for view counts
- All three platforms actively block headless browsers and scrapers
- UI layouts change without notice — hardcoded selectors break within days
- Content is in multiple languages (EN, Malay, Chinese) — regex extraction fails
- Only AI Vision can read any screenshot regardless of platform or UI version

---

## 4. Why AI (Not Just Automation)

| Approach | Result |
|----------|--------|
| Platform APIs | Instagram and RedNote have no public API for view counts |
| CSS scraping | Blocked by anti-bot measures; selectors change with every UI update |
| yt-dlp (YouTube/TikTok only) | Works perfectly for YouTube and TikTok — used in this system |
| Claude Vision (Instagram/RedNote) | Reads any screenshot regardless of language or UI version |

---

## 5. Quantified Value

| Metric | Value |
|--------|-------|
| Time saved per video | ~4 minutes |
| Videos per week | ~10 |
| Time saved per week | ~38 minutes |
| Weeks per year | 52 |
| **Total hours saved per year** | **~33 hours** |
| Error rate (manual) | ~5% typos/misreads |
| Error rate (automated) | <1% (Vision occasionally misreads) |

---

## 6. Business Objectives

- BO-01: Eliminate manual data entry for 4 platforms
- BO-02: Auto-fill Lark Bitable within 3 minutes of URL paste
- BO-03: Zero risk of overwriting user data (Column F, H protected)
- BO-04: System must work without any platform API key
- BO-05: Maintainable by a non-developer user (run.py one-command start)

---

## 7. User Stories

| ID | As a… | I want… | So that… |
|----|-------|---------|----------|
| US-01 | Content creator | URLs auto-detected when pasted | I don't start a run manually per video |
| US-02 | Content creator | Caption auto-cleaned of hashtags | I can search/filter captions in Lark |
| US-03 | Content creator | View count filled automatically | I save 30 sec per video of platform navigation |
| US-04 | Content creator | Posted date extracted correctly | My Lark timeline stays accurate |
| US-05 | Content creator | System to never touch Column H | My manual calculations are never overwritten |

---

## 8. Lark Sheet Column Mapping

| Column | Field | Written By | Notes |
|--------|-------|-----------|-------|
| A | Date | System | Posted date (YYYY-MM-DD) |
| B | Title | User | NOT touched by system |
| C | Content Type | User | NOT touched by system |
| D | Caption | System | Hashtags stripped |
| E | Content Type | System | Always "Content Casual" |
| F | Link | User | URL pasted by user — NEVER overwritten |
| G | Reach | System | View count as integer |
| H | Final Reach | User | Manual calculation — NEVER touched |

---

## 9. How the System Works

1. User pastes video URL into Column F of Lark Bitable
2. watcher.py polls Lark every 3 minutes for rows where F has URL but A or G is empty
3. For YouTube/TikTok: yt-dlp fetches title, date, view count (no browser needed, <10 sec)
4. For Instagram/RedNote: Firefox loads the page using saved login session
5. Instagram: two-screenshot approach — reel page screenshot (before Escape) for caption+date; profile grid for view count
6. RedNote: single screenshot of video page for all three fields
7. Screenshot sent to Claude Haiku Vision → returns JSON {posted_date, caption, view_count}
8. Hashtags stripped with Unicode-aware regex
9. Single atomic Lark API call writes A, D, E, G — with retry (3 attempts, 2s/4s/8s backoff)

---

## 10. Supported Platforms (Current Scope)

| Platform | Method | Notes |
|----------|--------|-------|
| YouTube | yt-dlp | Exact numbers, no browser, <10 sec |
| TikTok | Firefox + DOM | Caption/date from DOM elements; view count from embedded page JSON (`playCount`) |
| Instagram | Firefox + DOM + Claude Vision | DOM for caption/date; two-screenshot for view count (reel page before Escape + profile grid) |
| X (Twitter) | Firefox + DOM | Caption from `tweetText`; date from `<time>`; view count from post page or analytics |
| RedNote | Firefox + Claude Vision | Single screenshot of video page |

### Appendix A: Future Scope (Not Built)

| Platform | Status | Blocker |
|----------|--------|---------|
| Facebook | Not built | No public API; login wall varies by account type |
| X (Twitter) | Not built | API access requires paid tier |
| Threads | Not built | No API; UI too new/unstable for reliable Vision |

---

## 11. Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Detect new URLs in Column F within one watcher cycle (≤3 min) | Must Have |
| FR-02 | Extract posted date, caption, view count for all 4 platforms | Must Have |
| FR-03 | Strip all hashtags from caption before writing | Must Have |
| FR-04 | Write to columns A, D, E, G only | Must Have |
| FR-05 | Never overwrite existing data in A, D, E, G | Must Have |
| FR-06 | Log all activity to logs/auto_count.log | Should Have |
| FR-07 | Retry failed Lark writes up to 3 times | Should Have |
| FR-08 | Display human-readable errors if extraction fails | Should Have |

---

## 12. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | Processing time per URL (YouTube/TikTok) | <10 seconds |
| NFR-02 | Processing time per URL (Instagram/RedNote) | <3 minutes |
| NFR-03 | View count accuracy | >99% for yt-dlp; >95% for Vision |
| NFR-04 | System uptime | Runs until manually stopped |
| NFR-05 | Test coverage | 283 automated tests, 0 failures |

---

## 13. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Instagram UI change | Medium | High | Vision reads screenshots — no CSS selectors to break |
| Vision misreads number | Low | Medium | User spot-checks weekly; value is time-saving not 100% accuracy |
| yt-dlp blocked | Low | High | Fallback: manual entry (unchanged from current process) |
| Lark API rate limit | Low | Medium | Retry with exponential backoff |
| Firefox login session expires | Medium | Medium | User re-logs in manually; session persists via profile |

---

## 16. Acceptance Criteria

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| AC-01 | URL detection | New URL processed within 3 min of paste |
| AC-02 | Date accuracy | Matches platform display date |
| AC-03 | View count accuracy | Within 1% for yt-dlp; within 5% for Vision |
| AC-04 | Caption accuracy | Exact caption minus hashtags |
| AC-05 | Column protection | Columns B, C, F, H never written |
| AC-06 | Hashtag removal | Zero hashtags remain in Column D |
| AC-07 | Content type | Column E always "Content Casual" |
| AC-08 | No duplicate writes | Row with existing A+G skipped |
| AC-09 | Error logging | All failures written to log file |
| AC-10 | PIC filter | Only processes rows where PIC = "TAN JING YI" |

---

*End of Document — Version 5.4*
