# SPDX-License-Identifier: GPL-3.0-or-later

"""Library rescan and scan-status commands."""

from typing import Any, Dict, List
import argparse
import sys

from plexapi.server import PlexServer

from plexdo.console import _cell, output
from plexdo.constants import LOG
from plexdo.sections import resolve_section


def _cancel_all_scans(plex: PlexServer) -> None:
    """Cancel any running or queued scan on every library section."""
    for section in plex.library.sections():
        try:
            section.cancelUpdate()
            LOG.debug("Cancelled scan on '%s'", section.title)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.debug("cancelUpdate on '%s' raised %s (may already be idle)", section.title, exc)


def _activity_rows(plex: PlexServer) -> List[Dict[str, Any]]:
    """Return scan-related activity rows from the Plex server."""
    rows = []
    for act in plex.activities:
        rows.append({
            "type":     _cell(getattr(act, "type",     "") or ""),
            "title":    _cell(getattr(act, "title",    "") or ""),
            "subtitle": _cell(getattr(act, "subtitle", "") or ""),
            "progress": getattr(act, "progress", ""),
            "uuid":     _cell(getattr(act, "uuid",     "") or ""),
        })
    return rows


def cmd_rescan(plex: PlexServer, args: argparse.Namespace) -> None:
    """Trigger a library rescan, optionally cancelling pending scans first."""
    if args.status:
        rows = _activity_rows(plex)
        if not rows:
            print("No active scan jobs.", file=sys.stderr)
        else:
            output(rows, args)
        return

    if args.library_id is None:
        sys.exit("library_id is required unless --status / -s is used.")

    section = resolve_section(plex, args.library_id)

    if args.now:
        LOG.info("Cancelling all pending scans before rescan.")
        if not args.dry_run:
            _cancel_all_scans(plex)

    LOG.info("Triggering rescan of library '%s' (id=%d)", section.title, args.library_id)
    if args.dry_run:
        LOG.info("--dry-run: skipping scan trigger.")
        return

    section.update()
    print(f"Rescan triggered for library: {section.title!r}")


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the rescan subparser."""
    parser = sub.add_parser(
        "rescan", parents=parents,
        help="Trigger a library rescan, with optional status view or flush-and-rescan.",
    )
    parser.add_argument(
        "library_id", metavar="LIBRARY", nargs="?", default=None,
        help="Library ID (int) or title (str). Obtain both with list-libraries. "
        "Required unless -s / --status is used.",
    )
    parser.add_argument(
        "-s", "--status", action="store_true", default=False,
        help="Print all active scan jobs with their type, progress, and subtitle.",
    )
    parser.add_argument(
        "-n", "--now", action="store_true", default=False,
        help="Cancel all pending scans on every library before triggering the rescan.",
    )


COMMANDS = {"rescan": cmd_rescan}

REQUIRES_PLEX = frozenset(COMMANDS)
