# SPDX-License-Identifier: GPL-3.0-or-later

"""Resolution of a numeric ID or a human-readable title to a numeric ID.

Shared by user arguments (accounts) and library arguments (sections) so the
precedence rules, warnings, and error messages stay identical for both.
"""

from typing import Any, List, Tuple
import re
import sys

from plexdo.console import clean_text
from plexdo.constants import LOG


# (numeric id, title) pairs describing everything a value could refer to.
Roster = List[Tuple[int, str]]


def _titles_matching(roster: Roster, value: str) -> Roster:
    """Return roster entries whose title matches, preferring an exact match."""
    exact = [entry for entry in roster if entry[1] == value]
    if exact:
        return exact
    lowered = value.lower()
    return [entry for entry in roster if entry[1].lower() == lowered]


def resolve_identifier(
    roster: Roster, value: Any, kind: str, list_command: str
) -> int:
    """Resolve a numeric ID or a title to a numeric ID.

    *kind* names the thing being resolved ("user", "library") and
    *list_command* is the command that lists them, both used in messages.

    A value that is both a real ID and some other entry's title resolves to
    the ID, with a warning naming the entry that was not selected. Two entries
    sharing a title is unresolvable and aborts.
    """
    text = clean_text(value)
    matches = _titles_matching(roster, text)

    if len(matches) > 1:
        ids = ", ".join(str(item_id) for item_id, _ in matches)
        sys.exit(
            f"Ambiguous {kind} title {text!r}: it matches {kind} IDs {ids}. "
            f"Pass the numeric {kind} ID instead."
        )

    if re.fullmatch(r"-?\d+", text):
        number = int(text)
        if number in {item_id for item_id, _ in roster}:
            if matches and matches[0][0] != number:
                LOG.warning(
                    "%r is both a %s ID and the title of %s %d; matching the "
                    "%s ID. Pass %d to select the %s titled %r.",
                    text, kind, kind, matches[0][0], kind,
                    matches[0][0], kind, text,
                )
            return number
        if matches:
            # Not a real ID, but it is somebody's title, so use that.
            LOG.debug("%r is not a known %s ID; matched by title.", text, kind)
            return matches[0][0]
        # Unknown ID: return it so the downstream lookup reports it precisely.
        return number

    if matches:
        return matches[0][0]
    sys.exit(
        f"{kind.capitalize()} not found: {text!r}. Run `plexdo {list_command}` "
        f"to see available {kind} IDs and titles."
    )
