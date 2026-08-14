# SPDX-License-Identifier: GPL-3.0-or-later

"""Value coercion helpers for rating keys and dates."""

from typing import Any, Optional
import datetime

from plexdo.constants import DateInput


def normalize_rating_key(raw: Any) -> int:
    """Cast any ratingKey representation to int."""
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ratingKey: {raw!r}") from exc


def parse_date(value: DateInput) -> Optional[datetime.datetime]:
    """Normalize a date-like value to datetime.datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date string: {value!r}")
    raise TypeError(f"Unsupported date type: {type(value)}")


def _format_duration(milliseconds: Optional[int]) -> str:
    """Convert milliseconds to a human-readable H:MM:SS string."""
    if milliseconds is None:
        return ""
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"
