# SPDX-License-Identifier: GPL-3.0-or-later

"""Completion cache written as a side effect of list commands."""

from pathlib import Path
from typing import Any, Dict, List
import json

from plexdo.config import cached_config, config_optional
from plexdo.constants import CONFIG_PATH, DEFAULT_CACHE_DIR, LOG


def cache_dir() -> Path:
    """Return the completion cache directory.

    [plex] cache_dir overrides the platform default. The config is only
    consulted when it exists, so this stays usable before `plexdo login` has
    ever been run.
    """
    if CONFIG_PATH.exists():
        configured = config_optional(cached_config(), "cache_dir")
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_CACHE_DIR


def write_cache(name: str, data: List[Dict[str, Any]]) -> None:
    """Atomically write data to the completion cache, silently ignoring errors."""
    try:
        directory = cache_dir()
        directory.mkdir(parents=True, exist_ok=True)
        cache_file = directory / f"{name}.json"
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(cache_file)
        LOG.debug("Cache updated: %s", cache_file)
    except OSError:
        pass
