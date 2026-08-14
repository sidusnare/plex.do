# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist inspection and mutation commands."""

from typing import List
import argparse
import sys

from plexapi.exceptions import NotFound
from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.accounts import server_for_user
from plexdo.cache import write_cache
from plexdo.console import output
from plexdo.constants import LOG, MediaItem
from plexdo.m3u import write_m3u
from plexdo.paths import add_prefix_argument, mapper_for
from plexdo.playlists import resolve_playlist
from plexdo.titles import display_title


def cmd_list_playlists(plex: PlexServer, args: argparse.Namespace) -> None:
    """List playlists for a given user."""
    user_plex = server_for_user(plex, args.user_id)
    rows = [
        {
            "ratingKey": int(pl.ratingKey),
            "title": pl.title,
            "items": pl.leafCount,
        }
        for pl in user_plex.playlists()
    ]
    write_cache(f"playlists.{args.user_id}", rows)
    output(rows, args)


def cmd_list_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """List items inside a specific playlist for a user."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    items: List[MediaItem] = list(playlist.items())
    rows = [
        {
            "index": i + 1,
            "ratingKey": int(item.ratingKey),
            "title": display_title(item),
        }
        for i, item in enumerate(items)
    ]
    output(rows, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(plex, args))


def cmd_export_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Export an existing playlist to an M3U file."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    items: List[MediaItem] = list(playlist.items())
    if not items:
        sys.exit(f"Playlist '{args.playlist}' is empty - nothing to export.")

    LOG.info("Exporting %d items from '%s' to %s", len(items), args.playlist, args.m3u)
    write_m3u(items, args.m3u, mapper_for(plex, args))
    print(f"Exported {len(items)} items to: {args.m3u}")


def cmd_remove_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Delete a playlist from a user's account."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    LOG.info("Removing playlist '%s' for user_id=%d", args.playlist, args.user_id)
    if args.dry_run:
        LOG.info("--dry-run: skipping playlist deletion.")
        return
    playlist.delete()
    print(f"Deleted playlist: {args.playlist!r}")


def cmd_append_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Append one or more items to an existing playlist."""
    user_plex = server_for_user(plex, args.user_id)
    playlist: Playlist = resolve_playlist(user_plex, args.playlist)

    rating_keys = [int(k) for k in args.rating_keys]
    new_items: List[MediaItem] = []
    for rk in rating_keys:
        try:
            new_items.append(user_plex.fetchItem(rk))
        except NotFound:
            sys.exit(f"ratingKey not found: {rk}")

    if not new_items:
        sys.exit("No items to append.")

    LOG.info("Appending %d item(s) to '%s'", len(new_items), args.playlist)

    preview_rows = [
        {
            "index": i + 1,
            "ratingKey": int(item.ratingKey),
            "title": display_title(item),
        }
        for i, item in enumerate(new_items)
    ]
    output(preview_rows, args)

    if args.dry_run:
        LOG.info("--dry-run: skipping append.")
        return

    playlist.addItems(new_items)
    LOG.info("Appended %d item(s) to '%s'.", len(new_items), args.playlist)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the playlist inspection and mutation subparsers."""
    p_lpl = sub.add_parser("list-playlists", parents=parents, help="List playlists for a user.")
    p_lpl.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")

    p_lp = sub.add_parser("list-playlist", parents=parents, help="List items in a specific playlist.")
    p_lp.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_lp.add_argument(
        "playlist", type=str,
        help="Playlist name (str) or ratingKey (int). Obtain either with list-playlists.",
    )
    p_lp.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_lp)

    p_ep = sub.add_parser("export-playlist", parents=parents, help="Export an existing playlist to an M3U file.")
    p_ep.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_ep.add_argument("playlist", help="To export. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_ep.add_argument(
        "m3u", metavar="PATH",
        help="Destination M3U file path.",
    )
    add_prefix_argument(p_ep)

    p_rp = sub.add_parser("remove-playlist", parents=parents, help="Delete a playlist from a user's account.")
    p_rp.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_rp.add_argument("playlist", help="To delete. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")

    p_ap = sub.add_parser(
        "append-playlist", parents=parents,
        help="Append one or more items to an existing playlist.",
    )
    p_ap.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_ap.add_argument("playlist", help="To append to. " + "Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_ap.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more item ratingKeys to append (int). Obtain with list-titles or list-show.",
    )


COMMANDS = {
    "list-playlists": cmd_list_playlists,
    "list-playlist": cmd_list_playlist,
    "export-playlist": cmd_export_playlist,
    "remove-playlist": cmd_remove_playlist,
    "append-playlist": cmd_append_playlist,
}

REQUIRES_PLEX = frozenset(COMMANDS)
