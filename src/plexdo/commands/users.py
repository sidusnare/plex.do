# SPDX-License-Identifier: GPL-3.0-or-later

"""User listing command."""

from typing import List
import argparse

from plexapi.server import PlexServer

from plexdo.accounts import _account_type
from plexdo.cache import _write_cache
from plexdo.console import output
from plexdo.convert import normalize_rating_key


def cmd_list_users(plex: PlexServer, args: argparse.Namespace) -> None:
    """List managed/home users visible to the admin token."""
    account = plex.myPlexAccount()
    rows = [
        {
            "id": normalize_rating_key(u.id),
            "type": _account_type(u),
            "title": u.title,
        }
        for u in account.users()
    ]
    _write_cache("users", rows)
    output(rows, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the user listing subparser."""
    sub.add_parser("list-users", parents=parents, help="List all managed/home users (id, type, title).")


COMMANDS = {"list-users": cmd_list_users}

REQUIRES_PLEX = frozenset(COMMANDS)
