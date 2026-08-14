# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist building commands."""

from typing import Iterator, List, Optional, Tuple
import argparse
import datetime
import sys

from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show

from plexdo.accounts import server_for_user
from plexdo.airdates import episodes_in_same_season, prompt_for_date, resolve_episode_date
from plexdo.constants import LOG, MediaItem
from plexdo.convert import parse_date
from plexdo.m3u import write_m3u
from plexdo.paths import add_prefix_argument, mapper_for
from plexdo.playlists import finalize_playlist, resolve_playlist
from plexdo.titles import fetch_show, non_special_episodes, shuffle_list


def _round_robin(episode_lists: List[List[Episode]]) -> Iterator[Episode]:
    """Yield episodes in round-robin order across multiple lists."""
    queues = [list(eps) for eps in episode_lists if eps]
    while queues:
        exhausted = []
        for queue in queues:
            if queue:
                yield queue.pop(0)
            if not queue:
                exhausted.append(queue)
        for q in exhausted:
            queues.remove(q)


def cmd_build_interleaved(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build a round-robin interleaved playlist from multiple shows."""
    rating_keys = [int(k) for k in args.rating_keys]
    episode_lists: List[List[Episode]] = []

    for rk in rating_keys:
        show = fetch_show(plex, rk)
        eps = non_special_episodes(show)
        LOG.info("Show '%s': %d episodes", show.title, len(eps))
        episode_lists.append(eps)

    items: List[MediaItem] = list(_round_robin(episode_lists))
    finalize_playlist(plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(plex, args))


def _chronological_sort_key(
    item_date: Tuple[MediaItem, datetime.datetime]
) -> datetime.datetime:
    return item_date[1]


def _build_chronological_items(
    plex: PlexServer,
    rating_keys: List[int],
) -> List[Tuple[MediaItem, datetime.datetime]]:
    """Build (item, resolved_datetime) pairs for all given shows/movies."""
    dated_items: List[Tuple[MediaItem, datetime.datetime]] = []
    last_used_date: Optional[datetime.datetime] = None

    for rk in rating_keys:
        media_item = plex.fetchItem(rk)
        LOG.debug("Processing ratingKey=%d type=%s", rk, type(media_item).__name__)

        if isinstance(media_item, Show):
            all_eps = non_special_episodes(media_item)
            for ep in all_eps:
                season_peers = episodes_in_same_season(ep, all_eps)
                resolved = resolve_episode_date(ep, season_peers, last_used_date)
                last_used_date = resolved
                dated_items.append((ep, resolved))

        elif isinstance(media_item, Movie):
            dt = parse_date(media_item.originallyAvailableAt)
            if dt is None:
                dt = prompt_for_date(media_item, last_used_date)  # type: ignore[arg-type]
            last_used_date = dt
            dated_items.append((media_item, dt))

        else:
            sys.exit(
                f"ratingKey {rk} is type '{type(media_item).__name__}' "
                "- only Show and Movie are supported."
            )

    return dated_items


def cmd_build_chronological(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build a date-sorted playlist from shows and/or movies."""
    rating_keys = [int(k) for k in args.rating_keys]
    dated_items = _build_chronological_items(plex, rating_keys)

    dated_items.sort(key=_chronological_sort_key)
    items: List[MediaItem] = [item for item, _ in dated_items]

    finalize_playlist(plex, args.name, items, args)

    if args.m3u:
        write_m3u(items, args.m3u, mapper_for(plex, args))


def cmd_build_randomize(plex: PlexServer, args: argparse.Namespace) -> None:
    """Randomize a playlist and save to a new destination playlist."""
    user_plex = server_for_user(plex, args.user_id)
    src: Playlist = resolve_playlist(user_plex, args.source)

    all_items: List[MediaItem] = list(src.items())
    randomized: List[MediaItem] = shuffle_list(all_items)

    LOG.info("Randomized %d items", len(randomized))
    finalize_playlist(user_plex, args.dest, randomized, args)

    if args.m3u:
        write_m3u(randomized, args.m3u, mapper_for(user_plex, args))


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the playlist building subparsers."""
    p_bi = sub.add_parser(
        "build-interleaved", parents=parents,
        help="Round-robin interleaved playlist from multiple shows.",
    )
    p_bi.add_argument("name", help="Name for the new playlist (str).")
    p_bi.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more Show ratingKeys (int). Obtain with list-titles.",
    )
    p_bi.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help="Replace an existing playlist of the same name instead of failing.",
    )
    p_bi.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_bi)

    p_bc = sub.add_parser(
        "build-chronological", parents=parents,
        help="Date-sorted playlist from shows and/or movies.",
    )
    p_bc.add_argument("name", help="Name for the new playlist (str).")
    p_bc.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more Show/Movie ratingKeys (int). Obtain with list-titles.",
    )
    p_bc.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help="Replace an existing playlist of the same name instead of failing.",
    )
    p_bc.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_bc)

    p_br = sub.add_parser(
        "build-randomize", parents=parents,
        help="Randomize a source playlist into a new destination playlist.",
    )
    p_br.add_argument("user_id", metavar="USER", help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.")
    p_br.add_argument("source", help="Playlist name (str) or ratingKey (int). Obtain either with list-playlists.")
    p_br.add_argument("dest", help="Destination playlist title (str).")
    p_br.add_argument(
        "-o", "--overwrite", action="store_true", default=False,
        help="Replace an existing playlist of the same name instead of failing.",
    )
    p_br.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_br)


COMMANDS = {
    "build-interleaved": cmd_build_interleaved,
    "build-chronological": cmd_build_chronological,
    "build-randomize": cmd_build_randomize,
}

REQUIRES_PLEX = frozenset(COMMANDS)
