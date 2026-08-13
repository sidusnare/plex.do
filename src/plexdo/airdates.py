# SPDX-License-Identifier: GPL-3.0-or-later

"""Air-date estimation for episodes missing originallyAvailableAt."""

from typing import List, Optional, Tuple
import datetime
import statistics

from plexapi.video import Episode

from plexdo.constants import LOG
from plexdo.convert import normalize_rating_key, parse_date


def _aired_dt(ep: Episode) -> Optional[datetime.datetime]:
    """Return parsed originallyAvailableAt, or None."""
    return parse_date(ep.originallyAvailableAt)


def _episodes_in_same_season(ep: Episode, all_eps: List[Episode]) -> List[Episode]:
    """Return all episodes in the same season as ep (excluding ep itself)."""
    return [
        e for e in all_eps
        if e.seasonNumber == ep.seasonNumber
        and normalize_rating_key(e.ratingKey) != normalize_rating_key(ep.ratingKey)
    ]


def _collect_neighbors(
    ep: Episode, season_eps: List[Episode]
) -> Tuple[List[datetime.datetime], List[datetime.datetime]]:
    """
    Return (prev_dates, next_dates) — up to 6 known dates on each side.
    Episodes are ordered by episodeNumber within the season.
    """
    ordered = sorted(
        (e for e in season_eps if e.index is not None),
        key=lambda e: e.index,
    )
    ep_index = ep.index or 0
    prev_dates: List[datetime.datetime] = []
    next_dates: List[datetime.datetime] = []

    for e in reversed(ordered):
        if e.index < ep_index:
            dt = _aired_dt(e)
            if dt is not None:
                prev_dates.append(dt)
            if len(prev_dates) >= 6:
                break

    for e in ordered:
        if e.index > ep_index:
            dt = _aired_dt(e)
            if dt is not None:
                next_dates.append(dt)
            if len(next_dates) >= 6:
                break

    return prev_dates, next_dates


def _median_interval(dates: List[datetime.datetime]) -> Optional[datetime.timedelta]:
    """Compute the median timedelta between adjacent sorted dates."""
    sorted_dates = sorted(dates)
    if len(sorted_dates) < 3:  # need ≥3 dates → ≥2 intervals
        return None
    intervals = [
        (sorted_dates[i + 1] - sorted_dates[i]).total_seconds()
        for i in range(len(sorted_dates) - 1)
    ]
    if len(intervals) < 2:
        return None
    return datetime.timedelta(seconds=statistics.median(intervals))


def _estimate_date(
    prev_dates: List[datetime.datetime],
    next_dates: List[datetime.datetime],
) -> Optional[datetime.datetime]:
    """Estimate a missing air date from neighboring known dates."""
    all_known = prev_dates + next_dates
    median_td = _median_interval(all_known)
    if median_td is None:
        return None

    estimates: List[datetime.datetime] = []
    if prev_dates:
        latest_prev = max(prev_dates)
        estimates.append(latest_prev + median_td)
    if next_dates:
        earliest_next = min(next_dates)
        estimates.append(earliest_next - median_td)

    if not estimates:
        return None
    if len(estimates) == 1:
        return estimates[0]
    avg_ts = sum(e.timestamp() for e in estimates) / len(estimates)
    return datetime.datetime.fromtimestamp(avg_ts)


def _prompt_for_date(ep: Episode, last_used: Optional[datetime.datetime]) -> datetime.datetime:
    """Interactively ask the user for a missing air date."""
    example = last_used.strftime("%Y-%m-%d") if last_used else "2000-01-01"
    prompt = (
        f"\nCannot resolve air date for: {ep.grandparentTitle} "
        f"S{ep.seasonNumber:02d}E{ep.index:02d} – {ep.title}\n"
        f"Enter date (YYYY-MM-DD) [example: {example}]: "
    )
    while True:
        raw = input(prompt).strip()
        try:
            return datetime.datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            print("Invalid format, please use YYYY-MM-DD.")


def _resolve_episode_date(
    ep: Episode,
    season_peers: List[Episode],
    last_used: Optional[datetime.datetime],
) -> datetime.datetime:
    """Return a resolved datetime for an episode, estimating or prompting if needed."""
    dt = _aired_dt(ep)
    if dt is not None:
        return dt

    prev_dates, next_dates = _collect_neighbors(ep, season_peers)
    estimated = _estimate_date(prev_dates, next_dates)
    if estimated is not None:
        LOG.info(
            "Estimated date for '%s' S%02dE%02d: %s",
            ep.grandparentTitle,
            ep.seasonNumber,
            ep.index,
            estimated.date(),
        )
        return estimated

    return _prompt_for_date(ep, last_used)
