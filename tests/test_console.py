# SPDX-License-Identifier: GPL-3.0-or-later

"""Table rendering: alignment, encoding fallback, and control characters."""

import pytest

from plexdo.console import (_display_width as display_width, _pad as pad,
                            clean_text, output, print_table)


def test_clean_text_strips_the_carriage_returns_plex_metadata_carries():
    assert clean_text("Breaking Bad\r") == "Breaking Bad"


def test_display_width_counts_wide_glyphs_as_two_columns():
    assert display_width("ab") == 2
    assert display_width("\u5343\u3068") == 4          # CJK
    assert display_width("e\u0301") == 1               # combining acute


def test_pad_aligns_by_display_width_not_length():
    assert len(pad("\u5343", 4)) == 3                  # 2 columns + 2 spaces


def test_table_columns_line_up_with_mixed_width_titles(capsys):
    print_table([{"t": "Amelie"}, {"t": "\u5343\u3068\u5343\u5c0b"}, {"t": "Plain"}])
    lines = capsys.readouterr().out.splitlines()
    assert len({display_width(line) for line in lines}) == 1


def test_table_falls_back_to_ascii_when_the_console_cannot_encode_box_glyphs(
    capsys, monkeypatch
):
    """A legacy cp1252 console would otherwise abort with UnicodeEncodeError."""
    monkeypatch.setattr("plexdo.console._stdout_encoding", lambda: "cp1252")
    print_table([{"id": 1}])
    out = capsys.readouterr().out
    assert "+" in out and "\u250c" not in out


def test_unencodable_title_is_substituted_rather_than_crashing(capsys, monkeypatch):
    monkeypatch.setattr("plexdo.console._stdout_encoding", lambda: "ascii")
    print_table([{"t": "\u5343\u3068"}])
    assert "?" in capsys.readouterr().out


def test_output_dispatches_dict_to_the_metadata_renderer(capsys, args):
    args.format = "table"
    output({"a": 1}, args)
    assert "a" in capsys.readouterr().out


@pytest.mark.parametrize("fmt", ["json", "yaml", "csv"])
def test_output_honours_the_selected_format(capsys, args, fmt):
    args.format = fmt
    output([{"a": 1}], args)
    assert capsys.readouterr().out.strip()
