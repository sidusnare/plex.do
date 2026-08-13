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


CONFIG_PATH = Path("~/.local/etc/plex.do.ini").expanduser()


CACHE_DIR = Path("~/.cache/plex.do").expanduser()


LOG = logging.getLogger("plex.do")


# Group/other permission bits; any set on a secret file triggers a warning.
PERMISSIVE_MODE_MASK = 0o077


# Template written by `write-config-example` and echoed by its --help output.
CONFIG_EXAMPLE = (
    "[plex]\n"
    "url = http://localhost:32400\n"
    "token_path = ~/usr/tmp/.fsec/plex_token\n"
    "\n"
    "# Optional credentials used by `plex.do login`.\n"
    "# The password is stored in plaintext, so keep this file mode 0600.\n"
    "# Supplying --username on the command line ignores the password below.\n"
    "# username = you@example.com\n"
    "# password = your-plex-password\n"
)
