# SPDX-License-Identifier: GPL-3.0-or-later

"""Config file loading, token reading, and permission checks."""

from pathlib import Path
from typing import Optional
import configparser
import os
import sys

from plexapi.server import PlexServer

from plexdo.constants import CONFIG_PATH, LOG, PERMISSIVE_MODE_MASK


def check_file_permissions(path: Path, label: str) -> None:
    """Warn if a secret-bearing file is readable by group or other.

    Emitted at WARNING level so it surfaces without --verbose, and on stderr
    so it can never contaminate --json output.
    """
    if os.name == "nt":
        # Windows has no POSIX mode bits; os.stat synthesises 0o666, which
        # would trip this check on every run with advice (chmod) that cannot
        # help. Access there is governed by ACLs instead.
        LOG.debug("Skipping POSIX permission check for %s on Windows", path)
        return
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    leaked = mode & PERMISSIVE_MODE_MASK
    if leaked:
        LOG.warning(
            "SECURITY: %s at %s has mode %04o — readable by %s. "
            "Tighten it with: chmod 600 %s",
            label, path, mode & 0o7777,
            "group and others" if leaked & 0o007 else "group",
            path,
        )


def config_optional(cfg: configparser.ConfigParser, key: str) -> Optional[str]:
    """Return a stripped optional value from the [plex] section, or None."""
    value = cfg.get("plex", key, fallback=None)
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_config() -> configparser.ConfigParser:
    """Load and return the INI config, failing fast if absent."""
    if not CONFIG_PATH.exists():
        sys.exit(
            f"Config not found: {CONFIG_PATH}\n"
            "Run `plex.do write-config-example` to create a template."
        )
    check_file_permissions(CONFIG_PATH, "config file")
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    LOG.debug("Loaded config from %s", CONFIG_PATH)
    return cfg


def read_token(token_path_raw: str) -> str:
    """Expand path and read Plex token, failing fast if absent."""
    token_path = Path(token_path_raw).expanduser()
    if not token_path.exists():
        sys.exit(f"Token file not found: {token_path}")
    check_file_permissions(token_path, "token file")
    token = token_path.read_text(encoding="utf-8").strip()
    LOG.debug("Token loaded from %s", token_path)
    return token


def connect_plex(cfg: configparser.ConfigParser) -> PlexServer:
    """Create and return a connected PlexServer instance."""
    url = cfg.get("plex", "url")
    token_path = cfg.get("plex", "token_path")
    token = read_token(token_path)
    LOG.info("Connecting to Plex at %s", url)
    return PlexServer(url, token)
