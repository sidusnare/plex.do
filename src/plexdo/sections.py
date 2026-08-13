# SPDX-License-Identifier: GPL-3.0-or-later

"""Library section lookup shared by the library, search, and sync commands."""

from typing import Any, List, Optional
import sys

from plexapi.exceptions import NotFound
from plexapi.server import PlexServer


def resolve_section(plex: PlexServer, library_id: int) -> Any:
    """Return one library section by ID, failing fast if it does not exist."""
    try:
        return plex.library.sectionByID(library_id)
    except NotFound:
        sys.exit(f"Library ID not found: {library_id}")


def resolve_sections(plex: PlexServer, library_id: Optional[int]) -> List[Any]:
    """Return one section when library_id is given, otherwise every section."""
    if library_id is not None:
        return [resolve_section(plex, library_id)]
    return list(plex.library.sections())
