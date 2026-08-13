# SPDX-License-Identifier: GPL-3.0-or-later

"""Completion cache written as a side effect of list commands."""

from typing import Any, Dict, List
import json

from plexdo.constants import CACHE_DIR, LOG


def _write_cache(name: str, data: List[Dict[str, Any]]) -> None:
    """Atomically write data to the completion cache, silently ignoring errors."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{name}.json"
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(cache_file)
        LOG.debug("Cache updated: %s", cache_file)
    except OSError:
        pass
