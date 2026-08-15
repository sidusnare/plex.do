# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared constants, type aliases, and the package logger."""

from pathlib import Path
from typing import Union
import datetime
import logging

from plexapi.audio import Track
from plexapi.photo import Photo
from plexapi.video import Episode, Movie



DateInput = Union[str, datetime.date, datetime.datetime, None]


MediaItem = Union[Episode, Movie, Track, Photo]


CONFIG_PATH = Path("~/.local/etc/plexdo.ini").expanduser()


CACHE_DIR = Path("~/.cache/plexdo").expanduser()


LOG = logging.getLogger("plexdo")


# Group/other permission bits; any set on a secret file triggers a warning.
PERMISSIVE_MODE_MASK = 0o077


# Template written by `write-config-example` and echoed by its --help output.
CONFIG_EXAMPLE = (
    "[plex]\n"
    "url = http://localhost:32400\n"
    "\n"
    "# Values may contain environment variables as $VAR or ${VAR}, and ~ for\n"
    "# your home directory. XDG_RUNTIME_DIR is a private, user-only tmpfs on\n"
    "# most Linux systems, which suits a secret -- but it is cleared at logout,\n"
    "# so you will need to run `plexdo login` again after each reboot. Point\n"
    "# token_path somewhere persistent if you would rather not.\n"
    "token_path = $XDG_RUNTIME_DIR/.plex.token\n"
    "\n"
    "# Optional credentials used by `plexdo login`.\n"
    "# The password is stored in plaintext, so keep this file mode 0600.\n"
    "# Supplying --username on the command line ignores the password below.\n"
    "# username = you@example.com\n"
    "# password = your-plex-password\n"
    "\n"
    "# Per-user credentials, one section per user ID (see `plexdo\n"
    "# list-users`). These are used only when the server refuses the\n"
    "# admin-issued token for that user, which happens when nothing has been\n"
    "# shared with them. The resulting token is saved to token_path, so the\n"
    "# login happens once rather than on every run.\n"
    "#\n"
    "# [99]\n"
    "# username = bob@example.com\n"
    "# password = bobs-plex-password\n"
)
