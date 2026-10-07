"""Unit tests for tools/pii_guard.py.

Every sensitive-looking sample is assembled at run time from fragments, so this file itself
passes the guard it tests.
"""

import pytest

from tools.pii_guard import (
    Denylist,
    has_media_metadata,
    is_utc_env,
    scan_name,
    scan_text,
)

HOME = "/Us" + "ers/" + "someone"
TZ = "+0" + "3:00"
ACCOUNT = "D" + "U" + "1234567"
LT_CHAR = chr(0x0105)  # a Lithuanian letter, built at run time


def make(tmp_path, *lines):
    p = tmp_path / "deny.txt"
    p.write_text("\n".join(["# comment", "", *lines]) + "\n", encoding="utf-8")
    return Denylist.load(p)


def test_literals_match_case_insensitive_on_word_boundaries(tmp_path):
    d = make(tmp_path, "Zorblax")
    assert scan_text("met zorblax today", d)
    assert scan_text("ZORBLAX.", d)
    assert not scan_text("zorblaxian empire", d)  # word continues -> no match
    assert not scan_text("superzorblax", d)
    assert scan_text("zorblax_db and zorblax-notes", d)  # '_' and '-' separate words


def test_literal_with_non_word_edges(tmp_path):
    d = make(tmp_path, "/opt/zorb", "user@zorb.example")
    assert scan_text("path /opt/zorb/x", d)
    assert scan_text("mail user@zorb.example now", d)


def test_regex_entries_used_as_written(tmp_path):
    d = make(tmp_path, r"re:\bZQ\d{3}\b")
    assert scan_text("id ZQ123 here", d)
    assert not scan_text("id zq123 here", d)  # regex is case-sensitive as written


def test_hits_report_line_and_entry_but_never_the_value(tmp_path):
    d = make(tmp_path, "Zorblax", r"re:\bZQ\d{3}\b")
    hits = scan_text("ok\nZorblax\nZQ999", d)
    assert [(h.line, h.entry, h.kind) for h in hits] == [(2, 1, "literal"), (3, 2, "regex")]
    assert all("Zorblax" not in str(h) and "ZQ999" not in str(h) for h in hits)


def test_builtin_absolute_path_check_without_denylist_entry(tmp_path):
    d = make(tmp_path, "unrelated")
    hits = scan_text(f"see {HOME}/file.txt", d)
    assert hits and hits[0].kind == "absolute-path"
    assert scan_text("/ho" + "me/" + "bob/x", d)
    assert not scan_text("relative/path and ~/notes.md", d)


def test_sample_categories_with_realistic_regexes(tmp_path):
    d = make(tmp_path, r"re:[+-]0[23]:?00\b", r"re:\b(DU[O0]?|U)\d{6,8}\b", "re:[" + chr(0x0105) + chr(0x010D) + "]")
    assert scan_text(f"2026-10-07T10:00:00{TZ}", d)
    assert scan_text(f"account {ACCOUNT}", d)
    assert scan_text(f"tekstas {LT_CHAR}", d)
    assert not scan_text("2026-10-07T10:00:00+0000", d)


def test_scan_name_checks_paths(tmp_path):
    d = make(tmp_path, "Zorblax")
    assert scan_name("docs/zorblax_notes.md", d)
    assert not scan_name("docs/notes.md", d)


def test_missing_denylist_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        Denylist.load(tmp_path / "nope.txt")


def test_media_metadata_detection():
    assert has_media_metadata("a.jpg", b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00rest")
    assert has_media_metadata("a.png", b"\x89PNG\r\n\x1a\n....tEXtAuthor\x00x")
    assert has_media_metadata("a.pdf", b"%PDF-1.4 << /Author (x) >>")
    assert not has_media_metadata("a.png", b"\x89PNG\r\n\x1a\n....IDATxxxx")
    assert not has_media_metadata("a.txt", b"Exif")  # only media files are checked


@pytest.mark.parametrize(
    ("env", "ok"),
    [
        ({"GIT_AUTHOR_DATE": "2026-10-07T10:00:00+0000", "GIT_COMMITTER_DATE": "2026-10-07T10:00:00+0000"}, True),
        ({"GIT_AUTHOR_DATE": "2026-10-07T10:00:00+0000"}, False),
        ({"GIT_AUTHOR_DATE": "2026-10-07T10:00:00" + TZ.replace(":", ""),
          "GIT_COMMITTER_DATE": "2026-10-07T10:00:00+0000"}, False),
        ({}, False),
    ],
)
def test_is_utc_env(env, ok):
    assert is_utc_env(env) is ok
