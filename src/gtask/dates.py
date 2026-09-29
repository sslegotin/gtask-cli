"""Due-date parsing for CLI input and conversion to/from the API's RFC 3339 form."""

import re
from datetime import date, timedelta

from .errors import UsageError

_RELATIVE = re.compile(r"\+(\d+)d")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_due(text: str, today: date | None = None) -> date:
    today = today or date.today()
    value = text.strip().lower()
    if value == "today":
        return today
    if value == "tomorrow":
        return today + timedelta(days=1)
    if m := _RELATIVE.fullmatch(value):
        return today + timedelta(days=int(m.group(1)))
    if _ISO.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise UsageError(f"Invalid date {text!r}: use YYYY-MM-DD, today, tomorrow, or +Nd")


def to_api(d: date) -> str:
    return f"{d.isoformat()}T00:00:00.000Z"


def from_api(value: str | None) -> str:
    return value[:10] if value else ""
