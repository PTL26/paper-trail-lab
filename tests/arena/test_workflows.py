"""The GitHub Actions workflows: no schedule enabled, pinned actions, no gh, minimal permissions."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"
DAILY, NETCHECK, WEEKLY = WF / "arena-daily.yml", WF / "arena-netcheck.yml", WF / "arena-weekly.yml"


def active_lines(p):
    return [l for l in p.read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]


def test_daily_schedule_is_the_pilot_only_cron():
    lines = active_lines(DAILY)
    assert any(re.match(r"\s*schedule\s*:", l) for l in lines)
    crons = [l for l in lines if "cron:" in l]
    assert len(crons) == 1 and '"15 21 * * 1-5"' in crons[0]
    text = "\n".join(lines)
    assert 'if [ "$EVENT" = "schedule" ]; then' in text
    assert "python -m arena.run --scheduled\n" in text   # no --phase, no --day on the scheduled path


def test_other_schedules_are_disabled():
    for p in (NETCHECK, WEEKLY):
        assert not any(re.match(r"\s*schedule\s*:", l) for l in active_lines(p)), p.name
        assert any("workflow_dispatch" in l for l in active_lines(p))


def test_actions_are_pinned_to_full_commit_shas():
    for p in (DAILY, NETCHECK, WEEKLY):
        for l in active_lines(p):
            m = re.search(r"uses:\s*(\S+)", l)
            if m:
                assert re.search(r"@[0-9a-f]{40}$", m.group(1)), l


def test_no_gh_cli_and_python_for_tradingagents():
    for p in (DAILY, NETCHECK, WEEKLY):
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


def test_daily_offers_pilot_by_default():
    text = DAILY.read_text()
    assert "options: [pilot, scored]" in text and "default: pilot" in text and "--phase" in text


def test_weekly_publishes_only_public_with_full_history():
    text = WEEKLY.read_text()
    assert "arena.publish" in text and "fetch-depth: 0" in text
    assert "outside arena-data/public" in text and "github-actions[bot]" in text
    assert "GOOGLE_API_KEY" not in text


def test_deadline_check_runs_only_after_a_push():
    text = DAILY.read_text()
    assert 'echo "pushed=true" >> "$GITHUB_OUTPUT"' in text
    assert "if: steps.commit.outputs.pushed == 'true'" in text
