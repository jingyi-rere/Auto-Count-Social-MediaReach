"""
reconfigure.py — Re-detect column names when the Lark table layout changes.

Run this at the start of each quarter (or whenever columns are renamed/moved):
    python reconfigure.py

Connects to your existing Lark table, shows current columns,
and lets you re-map the six field names in .env.
Credentials stay unchanged — only field names are updated.
"""

import os
import sys
import re
from pathlib import Path

# ── Colour helpers ────────────────────────────────────────────────────────────

BOLD  = "\033[1m"
GREEN = "\033[32m"
CYAN  = "\033[36m"
YELLOW= "\033[33m"
RED   = "\033[31m"
DIM   = "\033[2m"
RESET = "\033[0m"

def ok(text):  return f"{GREEN}✓{RESET}  {text}"
def warn(text):return f"{YELLOW}!{RESET}  {text}"
def err(text): return f"{RED}✗{RESET}  {text}"
def dim(text): return f"{DIM}{text}{RESET}"

def ask(prompt, default=""):
    suffix = f" [{dim(default)}]" if default else ""
    try:
        val = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)
    return val if val else default

def ask_yn(prompt, default=True):
    opts = "Y/n" if default else "y/N"
    try:
        val = input(f"  {prompt} [{opts}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)
    if not val:
        return default
    return val.startswith("y")

# ── .env helpers ──────────────────────────────────────────────────────────────

ENV_PATH = Path(__file__).parent / ".env"
TEMPLATE_PATH = Path(__file__).parent / ".env.template"


def _load_env() -> dict:
    if not ENV_PATH.exists():
        return {}
    result = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def _write_env(values: dict):
    if TEMPLATE_PATH.exists():
        lines = TEMPLATE_PATH.read_text().splitlines()
    elif ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()
    else:
        lines = []

    written_keys = set()
    out_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        if "=" in stripped:
            k = stripped.split("=", 1)[0].lstrip("#").strip()
            if k in values:
                out_lines.append(f"{k}={values[k]}")
                written_keys.add(k)
                continue
        m = re.match(r"^#\s*([A-Z_]+)=", stripped)
        if m:
            k = m.group(1)
            if k in values:
                out_lines.append(f"{k}={values[k]}")
                written_keys.add(k)
                continue
        out_lines.append(line)

    extra = {k: v for k, v in values.items() if k not in written_keys}
    if extra:
        out_lines.append("")
        out_lines.append("# ── Auto-detected field names ──────────────────────")
        for k, v in extra.items():
            out_lines.append(f"{k}={v}")

    ENV_PATH.write_text("\n".join(out_lines) + "\n")


# ── Lark field detection ──────────────────────────────────────────────────────

FIELD_KEYS = {
    "LARK_FIELD_LINK":         "Video URL column             (the social media post link)",
    "LARK_FIELD_DATE":         "Date column                  (posted date — auto-filled)",
    "LARK_FIELD_CAPTION":      "Caption / Title column       (video description — auto-filled)",
    "LARK_FIELD_CONTENT_TYPE": "Content Type column          (e.g. 'Content Casual' — auto-filled if empty)",
    "LARK_FIELD_VIEWS":        "Views / Reach column         (view count — auto-filled)",
    "LARK_FIELD_PIC":          "PIC column                   (person in charge)",
    "LARK_FIELD_WEEK":         "Week column                  (e.g. 'W11' — used for same-week view refresh)",
}

FIELD_DEFAULTS = {
    "LARK_FIELD_LINK":         "Link",
    "LARK_FIELD_DATE":         "Date",
    "LARK_FIELD_CAPTION":      "Title",
    "LARK_FIELD_CONTENT_TYPE": "Content Type",
    "LARK_FIELD_VIEWS":        "Reach",
    "LARK_FIELD_PIC":          "PIC",
    "LARK_FIELD_WEEK":         "Week",
}


def _fetch_fields(env: dict) -> list:
    import lark_oapi as lark
    from lark_oapi.api.bitable.v1 import ListAppTableFieldRequest

    client = (
        lark.Client.builder()
        .app_id(env["LARK_APP_ID"])
        .app_secret(env["LARK_APP_SECRET"])
        .domain(env.get("LARK_DOMAIN", "https://open.larksuite.com"))
        .build()
    )
    req = (
        ListAppTableFieldRequest.builder()
        .app_token(env["LARK_APP_TOKEN"])
        .table_id(env["LARK_TABLE_ID"])
        .build()
    )
    resp = client.bitable.v1.app_table_field.list(req)
    if not resp.success():
        raise RuntimeError(f"Lark error {resp.code}: {resp.msg}")
    return [f.field_name for f in (resp.data.items or [])]


def _pick_field(fields: list, label: str, current: str) -> str:
    auto = next((f for f in fields if f.lower() == current.lower()), None)

    print(f"\n  {BOLD}{label}{RESET}  {dim('(currently: '+current+')')}")
    for i, name in enumerate(fields, 1):
        marker = f"  {GREEN}← current{RESET}" if name == auto else ""
        print(f"    {dim(str(i)+'. ')}{name}{marker}")

    while True:
        val = ask("Enter number (or type name)", default=current)
        if val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(fields):
                return fields[idx]
            print(err(f"  Please enter 1–{len(fields)}"))
            continue
        if val in fields:
            return val
        if val:
            if ask_yn(f"  '{val}' not in table — use anyway?", default=False):
                return val


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}  Auto Count — Reconfigure Column Names{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print()

    if not ENV_PATH.exists():
        print(err(".env not found — run 'python setup.py' first."))
        sys.exit(1)

    env = _load_env()

    required = ("LARK_APP_ID", "LARK_APP_SECRET", "LARK_APP_TOKEN", "LARK_TABLE_ID")
    missing = [k for k in required if not env.get(k) or env[k].startswith("your_")]
    if missing:
        print(err(f"Missing credentials in .env: {', '.join(missing)}"))
        print(warn("Run 'python setup.py' to enter them."))
        sys.exit(1)

    print("  Connecting to Lark table...")
    try:
        fields = _fetch_fields(env)
    except Exception as exc:
        print(err(f"Connection failed: {exc}"))
        sys.exit(1)

    print(ok(f"Found {len(fields)} column(s): {', '.join(fields[:6])}{'...' if len(fields) > 6 else ''}"))
    print()

    # Check if anything actually changed
    all_match = all(
        env.get(k, FIELD_DEFAULTS[k]) in fields
        for k in FIELD_KEYS
    )
    if all_match:
        print(ok("All current field names still exist in the table — nothing to change."))
        if not ask_yn("  Remap anyway?", default=False):
            print()
            print(dim("  No changes made."))
            return

    print(warn("Map each column to the correct field in your table:"))

    updated = {}
    for env_key, label in FIELD_KEYS.items():
        current = env.get(env_key, FIELD_DEFAULTS[env_key])
        updated[env_key] = _pick_field(fields, label, current)

    # Show summary of changes
    changed = {k: v for k, v in updated.items() if v != env.get(k, FIELD_DEFAULTS[k])}
    print()
    if changed:
        print(f"  {BOLD}Changes:{RESET}")
        for k, v in changed.items():
            old = env.get(k, FIELD_DEFAULTS[k])
            print(f"    {dim(k)}: {old} → {GREEN}{v}{RESET}")
    else:
        print(dim("  No changes from current settings."))

    print()
    if ask_yn("  Save to .env?"):
        _write_env(updated)
        print(ok(".env updated"))
        print()
        print(f"  Restart the watcher to pick up the new column names:")
        print(f"    {BOLD}python watcher.py{RESET}")
    else:
        print(dim("  Cancelled — nothing saved."))
    print()


if __name__ == "__main__":
    main()
