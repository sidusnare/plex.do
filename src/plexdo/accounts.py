# SPDX-License-Identifier: GPL-3.0-or-later

"""User lookup, per-user servers, and account classification."""

from typing import Any, List, Tuple
import argparse
import sys

from plexapi.myplex import MyPlexAccount, MyPlexUser
from plexapi.server import PlexServer

from plexdo.console import _cell
from plexdo.constants import LOG
from plexdo.convert import normalize_rating_key
from plexdo.identify import resolve_identifier


def _server_for_user(plex: PlexServer, user_id: int) -> PlexServer:
    """Return a PlexServer scoped to the given user.

    Pass user_id=0 to use the admin account (the token from config).
    For all other IDs, uses get_token(machineIdentifier) which works for
    both shared users and Plex Home managed users.
    """
    if user_id == 0:
        LOG.debug("user_id=0: using admin account")
        return plex
    account = plex.myPlexAccount()
    user: MyPlexUser = _find_user_by_id(account, user_id)
    token = user.get_token(plex.machineIdentifier)
    LOG.debug("Resolved token for user '%s' (id=%d)", user.title, user_id)
    return PlexServer(plex._baseurl, token)  # pylint: disable=protected-access


def _find_user_by_id(account: MyPlexAccount, user_id: int) -> MyPlexUser:
    """Locate a MyPlexUser by numeric id, failing fast if absent."""
    for user in account.users():
        if normalize_rating_key(user.id) == user_id:
            return user
    sys.exit(f"User ID not found: {user_id}")


def _is_restricted(user: MyPlexUser) -> bool:
    """Return True if the user is a restricted (managed) account.

    plexapi exposes `restricted` as the raw XML string rather than a bool,
    so a plain truth test would treat the common "0" value as True and
    mislabel every account as managed.
    """
    raw = getattr(user, "restricted", None)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() not in ("", "0", "false")


def _account_type(user: MyPlexUser) -> str:
    """Classify a user account as managed, home, friend, or shared."""
    if _is_restricted(user):
        return "managed"
    if getattr(user, "home", False):
        return "home"
    if getattr(user, "friend", False):
        return "friend"
    return "shared"


# Namespace attributes that hold a user identifier, resolved centrally in
# cli.main() so every command handler receives a plain numeric user ID.
USER_ID_ARGUMENTS = ("user_id", "user_a", "user_b", "source_user_id")


def _user_roster(plex: PlexServer) -> List[Tuple[int, str]]:
    """Return (id, title) for the admin account and every shared user."""
    account = plex.myPlexAccount()
    roster = [(0, _cell(getattr(account, "title", "") or "admin"))]
    roster.extend(
        (normalize_rating_key(user.id), _cell(user.title or ""))
        for user in account.users()
    )
    return roster


def resolve_user_identifier(roster: List[Tuple[int, str]], value: Any) -> int:
    """Resolve a numeric user ID or a user title to a numeric user ID."""
    return resolve_identifier(roster, value, "user", "list-users")


def resolve_user_arguments(plex: PlexServer, args: "argparse.Namespace") -> None:
    """Replace user ID/title arguments with numeric user IDs, in place.

    The roster is fetched once per invocation, so a command taking two user
    arguments costs a single extra API call rather than two.
    """
    present = [
        name for name in USER_ID_ARGUMENTS if getattr(args, name, None) is not None
    ]
    if not present:
        return
    roster = _user_roster(plex)
    for name in present:
        setattr(args, name, resolve_user_identifier(roster, getattr(args, name)))
