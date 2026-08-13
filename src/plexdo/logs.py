# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging configuration (stderr only, never stdout)."""

import logging
import sys


def configure_logging(verbose: bool, debug: bool) -> None:
    """Configure logging to stderr only (never stdout)."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)
