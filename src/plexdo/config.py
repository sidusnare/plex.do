# SPDX-License-Identifier: GPL-3.0-or-later

"""Config file loading, token reading, and permission checks."""

from functools import lru_cache
from pathlib import Path
from typing import Optional
import configparser
import os
import re
import sys

from plexapi.server import PlexServer

from plexdo.constants import CONFIG_PATH, LOG, PERMISSIVE_MODE_MASK
from plexdo.tokens import admin_token


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


def _expand_environment(cfg: configparser.ConfigParser) -> None:
    """Expand $VAR and ${VAR} in every [plex] value, in place.

    os.path.expandvars leaves an unset variable as literal text, which would
    surface later as a baffling "no such file" for a path like
    "$XDG_RUNTIME_DIR/.plex.token", so an unresolved name is warned about here.
    """
    if not cfg.has_section("plex"):
        return
    for key, raw in cfg.items("plex"):
        expanded = os.path.expandvars(raw)
        if expanded != raw:
            LOG.debug("Expanded environment variables in [plex] %s", key)
        for name in re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", expanded):
            LOG.warning(
                "[plex] %s references $%s, which is not set; leaving it "
                "literal. Set it, or use an absolute path in %s.",
                key, name, CONFIG_PATH,
            )
        cfg.set("plex", key, expanded)


def section_optional(
    cfg: configparser.ConfigParser, section: str, key: str
) -> Optional[str]:
    """Return a stripped optional value from any section, or None."""
    value = cfg.get(section, key, fallback=None)
    if value is None:
        return None
    value = value.strip()
    return value or None


@lru_cache(maxsize=1)
def cached_config() -> configparser.ConfigParser:
    """Return the parsed config, reading the file at most once per process.

    Memoised so the fallback login path can reach the per-user sections
    without re-reading the file, and re-emitting its permission warning, once
    per user in a loop.
    """
    return load_config()


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
    # interpolation=None: a password containing "%" would otherwise raise
    # InterpolationSyntaxError before it could ever be used.
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(CONFIG_PATH, encoding="utf-8")
    _expand_environment(cfg)
    LOG.debug("Loaded config from %s", CONFIG_PATH)
    return cfg


def token_store_path(cfg: configparser.ConfigParser) -> Path:
    """Return the expanded path of the JSON token store."""
    return Path(cfg.get("plex", "token_path")).expanduser()


def read_token(token_path_raw: str, username: Optional[str] = None) -> str:
    """Return the admin token from the JSON token store."""
    token_path = Path(token_path_raw).expanduser()
    if not token_path.exists():
        sys.exit(
            f"Token file not found: {token_path}\n"
            "Run `plex.do login` to authenticate and create it."
        )
    check_file_permissions(token_path, "token file")
    token = admin_token(token_path, username)
    if not token:
        sys.exit(
            f"No admin token in {token_path}.\n"
            "Run `plex.do login` to authenticate, or set [plex] username to "
            "the account whose token should be used."
        )
    LOG.debug("Admin token loaded from %s", token_path)
    return token


def connect_plex(cfg: configparser.ConfigParser) -> PlexServer:
    """Create and return a connected PlexServer instance."""
    url = cfg.get("plex", "url")
    token_path = cfg.get("plex", "token_path")
    token = read_token(token_path, config_optional(cfg, "username"))
    LOG.info("Connecting to Plex at %s", url)
    return PlexServer(url, token)
