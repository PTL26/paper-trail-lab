"""The GitHub Actions workflows: no schedule enabled, pinned actions, no gh, minimal permissions."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"
DAILY, NETCHECK = WF / "arena-daily.yml", WF / "arena-netcheck.yml"


def active_lines(p):
    return [l for l in p.read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]


def test_schedule_is_disabled():
    for p in (DAILY, NETCHECK):
        assert not any(re.match(r"\s*schedule\s*:", l) for l in active_lines(p)), p.name
        assert any("workflow_dispatch" in l for l in active_lines(p))


def test_actions_are_pinned_to_full_commit_shas():
    for p in (DAILY, NETCHECK):
        for l in active_lines(p):
            m = re.search(r"uses:\s*(\S+)", l)
            if m:
                assert re.search(r"@[0-9a-f]{40}$", m.group(1)), l


def test_no_gh_cli_and_python_for_tradingagents():
    for p in (DAILY, NETCHECK):
        text = "\n".join(active_lines(p))
        assert not re.search(r"(^|\s)gh\s", text)
        assert "--python 3.12" in text


def test_daily_commits_only_arena_data_with_a_bot_identity_and_utc():
    text = DAILY.read_text()
    assert "contents: write" in text and "github-actions[bot]" in text and "TZ: UTC" in text
    assert "ARENA_AGE_KEY: ${{ secrets.ARENA_AGE_KEY }}" in text
    assert "arena.run deadline" in text
    assert "outside arena-data" in text  # the path guard before committing


def test_netcheck_makes_no_llm_calls_and_needs_no_google_key():
    text = NETCHECK.read_text()
    assert "GOOGLE_API_KEY" not in text and "permissions:\n  contents: read" in text
