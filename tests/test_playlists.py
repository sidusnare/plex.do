# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist creation guards and the copy naming rules."""

import pytest

from conftest import FakeItem, FakePlaylist, FakePlex
from plexdo.playlists import _resolve_dest_name, finalize_playlist

ITEMS = [FakeItem(1, "A"), FakeItem(2, "B")]


def plex_with(*titles):
    return FakePlex(playlists=[FakePlaylist(t, 900 + i) for i, t in enumerate(titles)])


def test_empty_playlist_is_refused(args):
    with pytest.raises(SystemExit):
        finalize_playlist(FakePlex(), "Mix", [], args)


def test_creates_when_the_name_is_free(args):
    plex = plex_with()
    assert finalize_playlist(plex, "Mix", ITEMS, args) == "created"
    assert plex.created == [("Mix", ITEMS)]


def test_name_collision_without_overwrite_creates_and_deletes_nothing(args):
    plex = plex_with("Mix")
    with pytest.raises(SystemExit) as exc:
        finalize_playlist(plex, "Mix", ITEMS, args)
    assert "--overwrite" in str(exc.value)
    assert plex.created == []
    assert not plex.playlists()[0].deleted


def test_overwrite_replaces_the_existing_playlist(args):
    args.overwrite = True
    plex = plex_with("Mix")
    assert finalize_playlist(plex, "Mix", ITEMS, args) == "replaced"
    assert plex.playlists()[0].deleted
    assert plex.created == [("Mix", ITEMS)]


def test_dry_run_touches_nothing(args):
    args.overwrite, args.dry_run = True, True
    plex = plex_with("Mix")
    finalize_playlist(plex, "Mix", ITEMS, args)
    assert plex.created == [] and not plex.playlists()[0].deleted


# --- copy destination naming --------------------------------------------

def test_free_name_is_used_as_is():
    assert _resolve_dest_name(plex_with(), "Mix") == ("Mix", False)


def test_taken_name_falls_back_to_admin_copy():
    assert _resolve_dest_name(plex_with("Mix"), "Mix") == ("Mix admin copy", False)


def test_both_names_taken_means_skip_rather_than_clobber():
    assert _resolve_dest_name(plex_with("Mix", "Mix admin copy"), "Mix") is None


def test_overwrite_targets_the_plain_name_and_reports_a_replacement():
    plex = plex_with("Mix", "Mix admin copy")
    assert _resolve_dest_name(plex, "Mix", True) == ("Mix", True)


def test_overwrite_on_an_empty_destination_is_not_a_replacement():
    assert _resolve_dest_name(plex_with(), "Mix", True) == ("Mix", False)
