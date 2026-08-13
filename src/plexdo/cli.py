# plex.do - a command-line interface for Plex Media Server.
# Copyright (C) 2026 plex.do contributors
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level argument parsing and command dispatch."""

import argparse
import sys
from typing import List, Optional

from plexdo.accounts import resolve_user_arguments
from plexdo.commands import build_registry, register_all
from plexdo.config import connect_plex, load_config
from plexdo.logs import configure_logging
from plexdo.security import scrub_password_argument


def _add_global_flags(
    parser: argparse.ArgumentParser, suppress: bool = False
) -> None:
    """Add the flags accepted by every command.

    When *suppress* is set the flags default to ``argparse.SUPPRESS`` instead
    of ``False``. That matters for the copies inherited by each subparser: a
    subparser parses into its own namespace and then copies every attribute
    onto the main one, so ordinary ``False`` defaults would clobber a flag
    that was given before the subcommand. With SUPPRESS the attribute only
    exists when the flag was actually passed, so either position works.
    """
    default = argparse.SUPPRESS if suppress else False
    parser.add_argument(
        "--json", action="store_true", default=default,
        help="Output machine-readable JSON instead of tables.",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=default,
        help="Print high-level progress to stderr.",
    )
    parser.add_argument(
        "--debug", action="store_true", default=default,
        help="Print detailed internal logs to stderr.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=default, dest="dry_run",
        help="Show what would happen without mutating Plex.",
    )


def _global_flags_parent() -> argparse.ArgumentParser:
    """Return a parent parser supplying the global flags to every subcommand."""
    parent = argparse.ArgumentParser(add_help=False)
    _add_global_flags(parent, suppress=True)
    return parent


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="plex.do",
        description="Interact with a Plex Media Server via plexapi.",
        epilog=(
            "Global flags (--json, --verbose, --debug, --dry-run) may be given "
            "either before or after the command name."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_global_flags(parser)
    parents: List[argparse.ArgumentParser] = [_global_flags_parent()]
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    register_all(sub, parents)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the ``plex.do`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    configure_logging(args.verbose, args.debug)
    scrub_password_argument(args)

    handlers, needs_plex = build_registry()
    handler = handlers.get(args.command)
    if handler is None:
        sys.exit(f"Unknown command: {args.command}")

    if args.command in needs_plex:
        plex = connect_plex(load_config())
        # Commands receive numeric user IDs; titles are resolved here so no
        # handler has to care which form the user typed.
        resolve_user_arguments(plex, args)
        handler(plex, args)
    else:
        handler(None, args)
