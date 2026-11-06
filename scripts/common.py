"""
Shared utilities for ads-optimizer scripts.
Loads .env (skill root -> scripts dir -> cwd), formats money/tables, no heavy deps.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]

# Zero-decimal currencies: Meta budgets in these are expressed in whole units, not cents.
ZERO_DECIMAL_CURRENCIES = {
    "VND", "JPY", "KRW", "CLP", "ISK", "PYG", "UGX", "VUV",
}


def _manual_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env() -> None:
    candidates = [
        SKILL_ROOT / ".env",
        SKILL_ROOT / "scripts" / ".env",
        Path.cwd() / ".env",
    ]
    try:
        from dotenv import load_dotenv  # type: ignore
        for p in candidates:
            if p.exists():
                load_dotenv(p, override=False)
    except ImportError:
        for p in candidates:
            if p.exists():
                _manual_env(p)


load_env()


def _init_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_init_stdout()


def fmt_money(value, decimals: int = None) -> str:
    """Format a money amount with thousand separators. Auto-decimals for zero-decimal currencies is caller's choice; default 2."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "-"
    if decimals is None:
        decimals = 0 if abs(value - round(value)) < 0.005 else 2
    return f"{value:,.{decimals}f}"


def fmt_num(value) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "-"


def pct(part, whole) -> str:
    if not whole:
        return "-"
    return f"{(part / whole) * 100:.1f}%"


def ratio(part, whole) -> float:
    return (part / whole) if whole else 0.0


def print_table(rows, headers, echo: bool = True) -> str:
    """Minimal fixed-width table printer (no external deps). Returns the text; prints unless echo=False."""
    if not rows:
        text = "  (no rows)"
    else:
        widths = [len(str(h)) for h in headers]
        str_rows = [[("" if c is None else str(c)) for c in row] for row in rows]
        for row in str_rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
        out_lines = ["  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)),
                     "  ".join("-" * w for w in widths)]
        for row in str_rows:
            out_lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        text = "\n".join(out_lines)
    if echo:
        print(text)
    return text


def date_window(days: int, end_offset: int = 1):
    """Return (start_iso, end_iso) ending yesterday by default (partial-day data misleads)."""
    end = date.today() - timedelta(days=end_offset)
    start = end - timedelta(days=max(days, 1) - 1)
    return start.isoformat(), end.isoformat()


def previous_window(start_iso: str, end_iso: str):
    """Return (prev_start_iso, prev_end_iso) of the same length immediately before."""
    end = date.fromisoformat(end_iso)
    start = date.fromisoformat(start_iso)
    span = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    return prev_start.isoformat(), prev_end.isoformat()


def cpa(spend: float, conversions: float) -> float:
    return (spend / conversions) if conversions else 0.0


def ensure_reports_dir() -> Path:
    out = Path.cwd() / "reports"
    out.mkdir(exist_ok=True)
    return out


def env_str(name: str) -> str:
    return (os.getenv(name) or "").strip()


def is_placeholder(value: str) -> bool:
    """True when a value is missing or still the template placeholder from .env.example."""
    value = (value or "").strip()
    return (not value) or value.lower().startswith("your_")
