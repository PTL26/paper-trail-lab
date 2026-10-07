"""Integration tests: the real git hooks in tools/hooks, run by git in a throwaway repo.

The hooks read the denylist from HBL_DENYLIST (a synthetic file here), so these tests never
touch the owner's private denylist.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTC = "2026-10-07T10:00:00+0000"


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    shutil.copytree(ROOT / "tools", r / "tools")
    deny = tmp_path / "deny.txt"
    deny.write_text("Zorblax\nre:\\bZQ\\d{3}\\b\n", encoding="utf-8")
    env = {**os.environ, "HBL_DENYLIST": str(deny)}
    run = lambda *a, **kw: subprocess.run(a, cwd=r, env={**env, **kw.pop("env", {})},  # noqa: E731
                                          capture_output=True, text=True, **kw)
    run("git", "init", "-q")
    run("git", "config", "user.name", "Test Bot")
    run("git", "config", "user.email", "test@example.invalid")
    run("git", "config", "core.hooksPath", "tools/hooks")
    return r, run


def commit(run, msg="add", utc=True):
    extra = {"GIT_AUTHOR_DATE": UTC, "GIT_COMMITTER_DATE": UTC} if utc else {}
    return run("git", "commit", "-m", msg, env=extra)


def test_clean_utc_commit_passes(repo):
    r, run = repo
    (r / "a.md").write_text("hello\n")
    run("git", "add", "a.md")
    res = commit(run)
    assert res.returncode == 0, res.stderr
    assert run("git", "log", "--format=%ad|%cd").stdout.strip() == "Wed Oct 7 10:00:00 2026 +0000|Wed Oct 7 10:00:00 2026 +0000"


def test_denylisted_content_is_blocked_without_echoing_value(repo):
    r, run = repo
    (r / "a.md").write_text("line one\nby Zorblax\n")
    run("git", "add", "a.md")
    res = commit(run)
    assert res.returncode != 0
    assert "a.md:2" in res.stderr and "entry #1" in res.stderr
    assert "Zorblax" not in res.stderr + res.stdout


def test_denylisted_file_name_is_blocked(repo):
    r, run = repo
    (r / "zorblax.md").write_text("clean\n")
    run("git", "add", "zorblax.md")
    assert commit(run).returncode != 0


def test_absolute_path_is_blocked(repo):
    r, run = repo
    (r / "a.md").write_text("see /Us" + "ers/" + "someone/x\n")
    run("git", "add", "a.md")
    assert commit(run).returncode != 0


def test_image_with_exif_is_blocked(repo):
    r, run = repo
    (r / "pic.jpg").write_bytes(b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00rest")
    run("git", "add", "pic.jpg")
    res = commit(run)
    assert res.returncode != 0 and "metadata" in res.stderr


def test_non_utc_commit_is_blocked(repo):
    r, run = repo
    (r / "a.md").write_text("hello\n")
    run("git", "add", "a.md")
    res = commit(run, utc=False)
    assert res.returncode != 0 and "git cu" in res.stderr


def test_commit_message_is_scanned(repo):
    r, run = repo
    (r / "a.md").write_text("hello\n")
    run("git", "add", "a.md")
    res = commit(run, msg="fix for ZQ123")
    assert res.returncode != 0 and "commit message" in res.stderr


def test_missing_denylist_blocks(repo):
    r, run = repo
    (r / "a.md").write_text("hello\n")
    run("git", "add", "a.md")
    res = run("git", "commit", "-m", "x",
              env={"HBL_DENYLIST": str(r / "missing.txt"), "GIT_AUTHOR_DATE": UTC, "GIT_COMMITTER_DATE": UTC})
    assert res.returncode != 0 and "denylist" in res.stderr
