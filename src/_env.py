"""Shared dotenv loader — always resolves .env relative to the project root."""
from pathlib import Path
from dotenv import load_dotenv

# Project root = parent of this file's directory (src/)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=True)
