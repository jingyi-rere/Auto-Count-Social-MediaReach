"""
setup.py — First-time setup for Auto Count Social Media Reach.

Run once after cloning:
    python setup.py

Guides you through:
  1. Lark app credentials
  2. Column name detection (connects to your table)
  3. Your name / PIC filter
  4. Instagram / RedNote / X login (optional)

Creates or updates .env so watcher.py works immediately.
"""

import os
import sys
import re
import subprocess
from pathlib import Path

# ── Colour helpers (no external deps) ────────────────────────────────────────

BOLD  = "\033[1m"
GREEN = "\033[32m"
CYAN  = "\033[36m"
YELLOW= "\033[33m"
RED   = "\033[31m"
DIM   = "\033[2m"
RESET = "\033[0m"

def h(text):   return f"{BOLD}{CYAN}{text}{RESET}"
def ok(text):  return f"{GREEN}✓{RESET}  {text}"
def warn(text):return f"{YELLOW}!{RESET}  {text}"
def err(text): return f"{RED}✗{RESET}  {text}"
def dim(text): return f"{DIM}{text}{RESET}"

def banner(step, total, title):
    width = 60
    bar = f"─" * width
    print(f"\n{CYAN}{bar}{RESET}")
    print(f"{BOLD}  Step {step}/{total} — {title}{RESET}")
    print(f"{CYAN}{bar}{RESET}")

def ask(prompt, default="", secret=False):
    """Prompt and return stripped input. Shows default in brackets."""
    suffix = f" [{dim(default)}]" if default else ""
    try:
        if secret:
            import getpass
            val = getpass.getpass(f"  {prompt}{suffix}: ")
        else:
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

# ── .env read/write ───────────────────────────────────────────────────────────

ENV_PATH = Path(__file__).parent / ".env"
TEMPLATE_PATH = Path(__file__).parent / ".env.template"


def _load_env() -> dict:
    """Read existing .env into a dict (preserves comments/order via list)."""
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
    """
    Merge `values` into .env.
    Preserves existing comments and structure from .env.template.
    Overwrites any key that appears in `values`.
    Appends new keys at the end.
    """
    # Start from template lines as skeleton
    if TEMPLATE_PATH.exists():
        lines = TEMPLATE_PATH.read_text().splitlines()
    else:
        lines = []

    written_keys = set()
    out_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        # Uncommented key=value line
        if "=" in stripped:
            k = stripped.split("=", 1)[0].lstrip("#").strip()
            if k in values:
                out_lines.append(f"{k}={values[k]}")
                written_keys.add(k)
                continue
        # Commented-out key that we now have a value for
        m = re.match(r"^#\s*([A-Z_]+)=", stripped)
        if m:
            k = m.group(1)
            if k in values:
                out_lines.append(f"{k}={values[k]}")
                written_keys.add(k)
                continue
        out_lines.append(line)

    # Append any keys not in the template
    extra = {k: v for k, v in values.items() if k not in written_keys}
    if extra:
        out_lines.append("")
        out_lines.append("# ── Auto-detected field names ──────────────────────")
        for k, v in extra.items():
            out_lines.append(f"{k}={v}")

    ENV_PATH.write_text("\n".join(out_lines) + "\n")


# ── Lark connection check ─────────────────────────────────────────────────────

def _try_connect(app_id, app_secret, app_token, table_id, domain):
    """Return (field_names_list, error_str). One of them will be None."""
    try:
        import lark_oapi as lark
        from lark_oapi.api.bitable.v1 import ListAppTableFieldRequest

        client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .domain(domain)
            .build()
        )
        req = (
            ListAppTableFieldRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .build()
        )
        resp = client.bitable.v1.app_table_field.list(req)
        if not resp.success():
            return None, f"Lark error {resp.code}: {resp.msg}"
        names = [f.field_name for f in (resp.data.items or [])]
        return names, None
    except Exception as exc:
        return None, str(exc)


# ── Field mapping helper ──────────────────────────────────────────────────────

def _pick_field(fields: list, label: str, default: str, required=True) -> str:
    """
    Show numbered list of fields. User types a number or presses Enter for default.
    """
    # Try to auto-match default in the discovered list (case-insensitive)
    auto = next((f for f in fields if f.lower() == default.lower()), None)
    if auto:
        suggested = auto
    else:
        # Best fuzzy suggestion
        suggested = default

    print(f"\n  {BOLD}{label}{RESET}")
    for i, name in enumerate(fields, 1):
        marker = f"  {GREEN}←{RESET}" if name == auto else ""
        print(f"    {dim(str(i)+'. ')}{name}{marker}")

    while True:
        val = ask(f"Enter number (or type name)", default=suggested)
        # Number?
        if val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(fields):
                return fields[idx]
            print(err(f"  Please enter 1–{len(fields)}"))
            continue
        # Exact name in list?
        if val in fields:
            return val
        # Not in list — if not required, allow custom
        if not required:
            return val
        # Warn but allow override
        if val:
            confirm = ask_yn(f"  '{val}' not found in table — use it anyway?", default=False)
            if confirm:
                return val
        if not val and not required:
            return ""


# ── Step 1: Check environment ─────────────────────────────────────────────────

def step_check_env():
    banner(1, 5, "Checking your environment")

    # Python version
    major, minor = sys.version_info[:2]
    if major < 3 or minor < 9:
        print(err(f"Python {major}.{minor} is too old. Need 3.9+."))
        sys.exit(1)
    print(ok(f"Python {major}.{minor}"))

    # Required packages
    missing = []
    for pkg in ("lark_oapi", "playwright", "anthropic", "dotenv"):
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            # dotenv ships as python-dotenv
            if pkg == "dotenv":
                try:
                    import dotenv  # noqa
                except ImportError:
                    missing.append("python-dotenv")
            else:
                missing.append(pkg)
    if missing:
        print(warn(f"Missing packages: {', '.join(missing)}"))
        if ask_yn("  Install now with pip?"):
            subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
        else:
            print(err("Install packages first, then re-run setup.py"))
            sys.exit(1)
    print(ok("All required packages found"))


# ── Step 2: Lark credentials ──────────────────────────────────────────────────

def step_credentials(existing: dict) -> dict:
    banner(2, 5, "Lark credentials")
    print(dim("  Find these in your Lark Open Platform app and Bitable URL."))
    print(dim("  (https://open.larksuite.com → your app → Credentials & Basic Info)"))
    print()

    # Detect domain (LarkSuite vs Feishu)
    existing_domain = existing.get("LARK_DOMAIN", "https://open.larksuite.com")

    vals = {}
    vals["LARK_APP_ID"]     = ask("Lark App ID",     existing.get("LARK_APP_ID", ""))
    vals["LARK_APP_SECRET"] = ask("Lark App Secret", existing.get("LARK_APP_SECRET", ""), secret=True)

    print()
    print(dim("  From your Bitable URL:"))
    print(dim("  https://xxx.larksuite.com/base/APP_TOKEN?table=TABLE_ID"))
    print()
    vals["LARK_APP_TOKEN"]  = ask("App Token  (base/XXXXXX)",  existing.get("LARK_APP_TOKEN", ""))
    vals["LARK_TABLE_ID"]   = ask("Table ID   (?table=XXXXXX)", existing.get("LARK_TABLE_ID", ""))

    # Domain
    print()
    is_feishu = ask_yn("  Are you using Feishu (飞书) instead of Lark?", default=False)
    vals["LARK_DOMAIN"] = "https://open.feishu.cn" if is_feishu else "https://open.larksuite.com"

    # Anthropic key
    print()
    print(dim("  Claude API key from https://console.anthropic.com"))
    vals["ANTHROPIC_API_KEY"] = ask("Anthropic API Key", existing.get("ANTHROPIC_API_KEY", ""), secret=True)

    return vals


# ── Step 3: Detect column names ───────────────────────────────────────────────

FIELD_DEFAULTS = {
    "LARK_FIELD_LINK":         "Link",
    "LARK_FIELD_DATE":         "Date",
    "LARK_FIELD_CAPTION":      "Title",
    "LARK_FIELD_CONTENT_TYPE": "Content Type",
    "LARK_FIELD_VIEWS":        "Reach",
    "LARK_FIELD_PIC":          "PIC",
}

FIELD_LABELS = {
    "LARK_FIELD_LINK":         "Video / Post URL column  (the link to the social media post)",
    "LARK_FIELD_DATE":         "Date column              (posted date — will be auto-filled)",
    "LARK_FIELD_CAPTION":      "Caption / Title column   (video description — will be auto-filled)",
    "LARK_FIELD_CONTENT_TYPE": "Content Type column      (e.g. 'Content Casual' — auto-filled if empty)",
    "LARK_FIELD_VIEWS":        "Views / Reach column     (view count — will be auto-filled)",
    "LARK_FIELD_PIC":          "PIC column               (person in charge — used to filter rows)",
}


def step_fields(creds: dict, existing: dict) -> dict:
    banner(3, 5, "Detect column names")
    print("  Connecting to your Lark table to read column names...")

    fields, error = _try_connect(
        creds["LARK_APP_ID"],
        creds["LARK_APP_SECRET"],
        creds["LARK_APP_TOKEN"],
        creds["LARK_TABLE_ID"],
        creds["LARK_DOMAIN"],
    )

    if error:
        print(err(f"Could not connect: {error}"))
        print(warn("Skipping auto-detect — you can re-run 'python reconfigure.py' later."))
        return {}

    print(ok(f"Connected! Found {len(fields)} column(s): {', '.join(fields[:6])}{'...' if len(fields) > 6 else ''}"))
    print()

    # Auto-match: if all defaults exist exactly in the table, skip manual picking
    all_match = all(FIELD_DEFAULTS[k] in fields for k in FIELD_DEFAULTS)
    if all_match:
        print(ok("All default column names match your table — no changes needed."))
        return {k: v for k, v in FIELD_DEFAULTS.items()}

    # Some don't match — guide user through each
    print(warn("Some column names differ. Please pick the right one for each:"))
    result = {}
    for env_key, label in FIELD_LABELS.items():
        default = existing.get(env_key, FIELD_DEFAULTS[env_key])
        result[env_key] = _pick_field(fields, label, default)

    return result


# ── Step 4: PIC name ──────────────────────────────────────────────────────────

def step_pic(existing: dict) -> dict:
    banner(4, 5, "Your name (PIC filter)")
    print(dim("  The watcher only processes rows assigned to you."))
    print(dim("  Enter your name exactly as it appears in the PIC column of Lark."))
    print()
    pic = ask("Your name in Lark (PIC)", existing.get("LARK_PIC_FILTER", ""))
    return {"LARK_PIC_FILTER": pic}


# ── Step 5: Instagram / RedNote / X login ─────────────────────────────────────

def step_login():
    banner(5, 5, "Social media login (Instagram, RedNote, X)")
    print(dim("  The watcher uses a saved Firefox session to extract data."))
    print(dim("  You need to log in once — sessions are saved permanently."))
    print()
    do_login = ask_yn("  Log into Instagram / RedNote / X now?")
    if do_login:
        try:
            subprocess.run([sys.executable, "login_once.py"], check=True)
        except subprocess.CalledProcessError:
            print(warn("Login script exited with an error — you can run 'python login_once.py' again later."))
    else:
        print(dim("  Skipped. Run 'python login_once.py' when you're ready."))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}  Auto Count Social Media Reach — Setup{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")

    if ENV_PATH.exists():
        print()
        print(ok(".env already exists — will update only what you change."))

    existing = _load_env()

    step_check_env()

    creds = step_credentials(existing)
    fields = step_fields(creds, existing)
    pic    = step_pic(existing)

    # Merge everything and write
    all_vals = {**creds, **fields, **pic}
    _write_env(all_vals)
    print()
    print(ok(f".env written to {ENV_PATH}"))

    step_login()

    # Done
    print()
    print(f"{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}  Setup complete!{RESET}")
    print(f"{BOLD}{GREEN}{'='*60}{RESET}")
    print()
    print(f"  Start the watcher:  {BOLD}python watcher.py{RESET}")
    print()
    print(dim("  Tip: columns changing next quarter? Run 'python reconfigure.py'"))
    print()


if __name__ == "__main__":
    main()
