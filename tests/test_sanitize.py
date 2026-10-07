"""Unit tests for tools/sanitize.py (placeholders applied, then the same denylist check)."""

import pytest

from tools.pii_guard import Denylist
from tools.sanitize import SanitizeError, load_map, sanitize_text, sanitize_file

HOME = "/Us" + "ers/" + "someone"


def deny(tmp_path, *lines):
    p = tmp_path / "deny.txt"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Denylist.load(p)


def test_mapped_literal_gets_its_placeholder_case_insensitive(tmp_path):
    d = deny(tmp_path, "Zorblax", "Quuxbot")
    m = {"zorblax": "the owner", "quuxbot": "the bot"}
    out, n = sanitize_text("Approved by Zorblax; QUUXBOT ran.", d, m)
    assert out == "Approved by the owner; the bot ran." and n == 2


def test_unmapped_literal_and_regex_become_redacted(tmp_path):
    d = deny(tmp_path, "Zorblax", r"re:\bZQ\d{3}\b")
    out, n = sanitize_text("Zorblax ZQ123", d, {})
    assert out == "[redacted] [redacted]" and n == 2


def test_word_boundary_respected(tmp_path):
    d = deny(tmp_path, "Zorblax")
    out, n = sanitize_text("zorblaxian", d, {})
    assert out == "zorblaxian" and n == 0


def test_home_paths_become_placeholder(tmp_path):
    d = deny(tmp_path, "unrelated")
    out, _ = sanitize_text(f"file {HOME}/proj/x.csv here", d, {})
    assert out == "file <HOME>/proj/x.csv here"


def test_load_map_parses_arrow_lines(tmp_path):
    p = tmp_path / "map.txt"
    p.write_text("# c\nZorblax => the owner\n\nQuuxbot=>the bot\n", encoding="utf-8")
    assert load_map(p) == {"zorblax": "the owner", "quuxbot": "the bot"}
    assert load_map(tmp_path / "missing.txt") == {}


def test_sanitize_file_writes_clean_copy_inside_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    src = tmp_path / "src.md"
    src.write_text("Owner Zorblax wrote this.\n", encoding="utf-8")
    d = deny(tmp_path, "Zorblax")
    n = sanitize_file(src, repo / "docs" / "out.md", d, {"zorblax": "the owner"}, repo_root=repo)
    assert n == 1
    assert (repo / "docs" / "out.md").read_text() == "Owner the owner wrote this.\n"


def test_sanitize_file_refuses_destination_outside_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    src = tmp_path / "src.md"
    src.write_text("clean\n", encoding="utf-8")
    with pytest.raises(SanitizeError, match="outside the repo"):
        sanitize_file(src, tmp_path / "elsewhere.md", deny(tmp_path, "x"), {}, repo_root=repo)


def test_sanitize_file_refuses_when_a_placeholder_reintroduces_a_hit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    src = tmp_path / "src.md"
    src.write_text("Zorblax\n", encoding="utf-8")
    d = deny(tmp_path, "Grumble", "Zorblax")  # the placeholder is only checked after all replacements
    with pytest.raises(SanitizeError, match="still matches"):
        sanitize_file(src, repo / "x.md", d, {"zorblax": "grumble"}, repo_root=repo)
    assert not (repo / "x.md").exists()  # nothing written
