# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist copying commands."""

from typing import List
import argparse

from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.accounts import UserAccessError, _server_for_user
from plexdo.constants import LOG, MediaItem
from plexdo.convert import normalize_rating_key
from plexdo.playlists import _copy_playlist_to, _resolve_playlist


def cmd_copy_playlist_all_users(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to all managed users."""
    src_plex = _server_for_user(plex, args.source_user_id)
    src: Playlist = _resolve_playlist(src_plex, args.source_playlist)

    src_items: List[MediaItem] = list(src.items())
    account = plex.myPlexAccount()

    for user in account.users():
        user_id = normalize_rating_key(user.id)
        if user_id == args.source_user_id:
            LOG.info("Skipping source user '%s' (id=%d)", user.title, user_id)
            continue
        LOG.info("Copying to user '%s' (id=%d)", user.title, user_id)
        try:
            user_plex = _server_for_user(plex, user_id)
            _copy_playlist_to(
                src_items, user_plex, args.source_playlist, args,
                f"user {user.title!r} (id={user_id})",
            )
        except UserAccessError as exc:
            LOG.warning("Skipping user '%s': %s", user.title, exc.summary)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.warning("Failed for user '%s': %s", user.title, exc)


def cmd_copy_playlist_to_user(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to a specific user under a given name."""
    src_plex = _server_for_user(plex, args.source_user_id)
    src: Playlist = _resolve_playlist(src_plex, args.source_playlist)

    src_items: List[MediaItem] = list(src.items())
    user_plex = _server_for_user(plex, args.user_id)
    _copy_playlist_to(
        src_items, user_plex, args.dest, args, f"user id={args.user_id}"
    )


_SRC_UID_HELP = (
    "Source user ID (int) or user title (str); use 0 for the admin "
    "account. Obtain both with list-users."
)
_OVERWRITE_HELP = (
    "Overwrite an existing playlist of the same name on the destination "
    "instead of appending ' admin copy'."
)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the playlist copying subparsers."""
    p_all = sub.add_parser(
        "copy-playlist-all-users", parents=parents,
        help="Copy a playlist from any user to all managed users.",
    )
    p_all.add_argument("source_user_id", metavar="USER", help=_SRC_UID_HELP)
    p_all.add_argument("source_playlist", help="Source. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_all.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help=_OVERWRITE_HELP,
    )

    p_one = sub.add_parser(
        "copy-playlist-to-user", parents=parents,
        help="Copy a playlist from any user to a specific user.",
    )
    p_one.add_argument("source_user_id", metavar="USER", help=_SRC_UID_HELP)
    p_one.add_argument("source_playlist", help="Source. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_one.add_argument("user_id", metavar="USER", help="Target " + "User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_one.add_argument("dest", help="Destination playlist title (str).")
    p_one.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help=_OVERWRITE_HELP,
    )


COMMANDS = {
    "copy-playlist-all-users": cmd_copy_playlist_all_users,
    "copy-playlist-to-user": cmd_copy_playlist_to_user,
}

REQUIRES_PLEX = frozenset(COMMANDS)
