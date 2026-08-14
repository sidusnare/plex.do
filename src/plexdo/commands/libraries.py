# SPDX-License-Identifier: GPL-3.0-or-later

"""Library listing and whole-library export commands."""

from typing import List, Optional
import argparse
import sys

from plexapi.server import PlexServer
from plexapi.video import Episode

from plexdo.cache import write_cache
from plexdo.console import output
from plexdo.constants import LOG
from plexdo.gallery import write_gallery_html
from plexdo.m3u import write_m3u
from plexdo.paths import add_prefix_argument, mapper_for
from plexdo.photos import collect_library_items, collect_photos
from plexdo.sections import resolve_section
from plexdo.sorting import apply_sort
from plexdo.titles import display_title, fetch_show, non_special_episodes


def cmd_list_libraries(plex: PlexServer, args: argparse.Namespace) -> None:
    """List all Plex libraries."""
    rows = [
        {
            "id": int(lib.key),
            "type": lib.type,
            "title": lib.title,
        }
        for lib in plex.library.sections()
    ]
    write_cache("libraries", rows)
    output(rows, args)


def cmd_list_titles(plex: PlexServer, args: argparse.Namespace) -> None:
    """List titles in a library, with optional album filter for photo libraries."""
    library_id = args.library_id
    section = resolve_section(plex, library_id)

    album: Optional[str] = getattr(args, "album", None)
    if album and section.type != "photo":
        LOG.warning("--album is only applicable to photo libraries; ignoring.")
        album = None

    if section.type == "photo":
        items = collect_photos(section, album)
    else:
        items = list(section.all())

    rows = [
        {
            "ratingKey": int(item.ratingKey),
            "title": display_title(item),
        }
        for item in items
    ]
    write_cache(f"titles.{library_id}", rows)
    output(rows, args)


def cmd_list_show(plex: PlexServer, args: argparse.Namespace) -> None:
    """List all episodes in a show, optionally exporting an M3U."""
    rating_key = int(args.rating_key)
    show = fetch_show(plex, rating_key)
    episodes: List[Episode] = non_special_episodes(show)

    rows = [
        {
            "index": i + 1,
            "ratingKey": int(ep.ratingKey),
            "season": ep.seasonNumber,
            "episode": ep.index,
            "title": display_title(ep),
        }
        for i, ep in enumerate(episodes)
    ]
    output(rows, args)

    if args.m3u:
        write_m3u(episodes, args.m3u, mapper_for(plex, args))  # type: ignore[arg-type]


def cmd_export_titles(plex: PlexServer, args: argparse.Namespace) -> None:
    """Export an entire library to an M3U file."""
    section = resolve_section(plex, args.library_id)

    LOG.info(
        "Collecting items from library '%s' (type=%s)", section.title, section.type
    )
    album: Optional[str] = getattr(args, "album", None)
    if album and section.type != "photo":
        LOG.warning("--album is only applicable to photo libraries; ignoring.")
        album = None

    items = collect_library_items(section, album)

    if not items:
        sys.exit(f"Library '{section.title}' contains no items.")

    sorted_items = apply_sort(items, args.sort)
    gallery_title = f"{section.title} - {album}" if album else section.title
    LOG.info(
        "Exporting %d item(s) sorted by '%s' to %s",
        len(sorted_items), args.sort, args.output_path,
    )
    if section.type == "photo":
        write_gallery_html(
            sorted_items, args.output_path, gallery_title, mapper_for(plex, args)
        )
    else:
        write_m3u(sorted_items, args.output_path, mapper_for(plex, args))
        print(f"Exported {len(sorted_items)} items to: {args.output_path}")


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the library-related subparsers."""
    sub.add_parser(
        "list-libraries", parents=parents,
        help="List all Plex libraries (id, type, title).",
    )

    p_lt = sub.add_parser("list-titles", parents=parents, help="List titles in a library.")
    p_lt.add_argument(
        "library_id", metavar="LIBRARY",
        help="Library ID (int) or library title (str). Obtain both with list-libraries.",
    )
    p_lt.add_argument(
        "--album", default=None, metavar="ALBUM",
        help="Photo libraries only: restrict listing to a single album name.",
    )

    p_ls = sub.add_parser(
        "list-show", parents=parents,
        help="List all episodes in a show (skipping specials), with optional M3U export.",
    )
    p_ls.add_argument(
        "rating_key", type=int,
        help="Show ratingKey (int). Obtain with list-titles.",
    )
    p_ls.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )
    add_prefix_argument(p_ls)

    p_et = sub.add_parser(
        "export-titles", parents=parents,
        help="Export an entire library to an M3U file or photo gallery.",
    )
    p_et.add_argument(
        "library_id", metavar="LIBRARY",
        help="Library ID (int) or library title (str). Obtain both with list-libraries.",
    )
    p_et.add_argument(
        "output_path", metavar="PATH",
        help=(
            "Output file path. M3U for show/movie libraries; "
            "HTML gallery for photo libraries."
        ),
    )
    p_et.add_argument(
        "--sort", choices=["alpha", "date", "random"], default="alpha",
        help=(
            "Sort order: 'alpha' = alphabetical by title/show+episode (default), "
            "'date' = by original air date (undated items last), "
            "'random' = randomised."
        ),
    )
    p_et.add_argument(
        "--album", default=None, metavar="ALBUM",
        help="Photo libraries only: restrict export to a single album name.",
    )
    add_prefix_argument(p_et)


COMMANDS = {
    "list-libraries": cmd_list_libraries,
    "list-titles": cmd_list_titles,
    "list-show": cmd_list_show,
    "export-titles": cmd_export_titles,
}

REQUIRES_PLEX = frozenset(COMMANDS)
