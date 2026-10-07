"""Evaluate a skill the skill-creator way: run each eval prompt with the skill installed, check
whether it triggered (Skill tool call in the stream) and grade the output against expectations.

  python tools/run_skill_evals.py skills/pre-registration [--model M] [--effort E]

Each case runs headless Claude Code in a fresh temporary directory that contains only
.claude/skills/<skill> (project settings only, no MCP servers, tools limited to Skill/Read/Glob).
Raw transcripts go to <skill>/evals/results/ (gitignored); a summary goes to
<skill>/evals/RESULTS.md.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

SKILL_NAME_KEYS = ("skill", "command", "name")


def parse_stream(lines: List[str], skill: str = "pre-registration") -> Tuple[bool, str]:
    """(skill invoked?, final result text) from Claude Code stream-json lines."""
    invoked, result = False, ""
    for raw in lines:
        try:
            ev = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []) or []:
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    args = block.get("input", {}) or {}
                    if any(str(args.get(k, "")).strip("/") == skill for k in SKILL_NAME_KEYS):
                        invoked = True
        elif ev.get("type") == "result":
            result = ev.get("result") or ""
    return invoked, result


def grade(case: Dict, invoked: bool, text: str) -> Tuple[bool, List[str]]:
    why: List[str] = []
    if invoked != case["should_trigger"]:
        why.append(f"trigger: expected {case['should_trigger']}, got {invoked}")
        return False, why
    low = text.lower()
    for term in case.get("expect_all", []):
        if term.lower() not in low:
            why.append(f"missing: {term}")
    for group in case.get("expect_any", []):
        if not any(t.lower() in low for t in group):
            why.append("missing one of: " + " / ".join(group))
    return not why, why


def run_case(skill_dir: Path, prompt: str, model: str, effort: str) -> List[str]:  # pragma: no cover
    with tempfile.TemporaryDirectory(prefix="skill-eval-") as tmp:
        dest = Path(tmp) / ".claude" / "skills" / skill_dir.name
        shutil.copytree(skill_dir, dest, ignore=shutil.ignore_patterns("evals"))
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        cmd = ["claude", "-p", "--model", model, "--effort", effort, "--output-format", "stream-json",
               "--verbose", "--setting-sources", "project", "--strict-mcp-config",
               "--tools", "Skill,Read,Glob", "--allowedTools", "Skill Read Glob",
               "--no-session-persistence"]
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tmp, env=env, timeout=900)
        return p.stdout.splitlines()


def main() -> int:  # pragma: no cover - drives the CLI
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="medium")
    a = ap.parse_args()
    skill_dir = Path(a.skill_dir).resolve()
    spec = json.loads((skill_dir / "evals" / "evals.json").read_text())
    out_dir = skill_dir / "evals" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in spec["cases"]:
        lines = run_case(skill_dir, case["prompt"], a.model, a.effort)
        (out_dir / f"{case['id']}.jsonl").write_text("\n".join(lines) + "\n")
        invoked, text = parse_stream(lines, spec["skill"])
        (out_dir / f"{case['id']}.md").write_text(text + "\n")
        ok, why = grade(case, invoked, text)
        rows.append((case, invoked, ok, why))
        print(f"{case['id']}: {'PASS' if ok else 'FAIL'} (triggered={invoked}) {'; '.join(why)}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = [f"# Eval results — {spec['skill']}", "",
          f"Run {stamp}; model `{a.model}`, effort `{a.effort}`; one run per case.", "",
          "| Case | Should trigger | Triggered | Result | Notes |", "|---|---|---|---|---|"]
    for case, invoked, ok, why in rows:
        md.append(f"| {case['id']} | {case['should_trigger']} | {invoked} | {'PASS' if ok else 'FAIL'} | "
                  f"{'; '.join(why) or '—'} |")
    passed = sum(r[2] for r in rows)
    md += ["", f"**{passed} of {len(rows)} cases passed.**", ""]
    (skill_dir / "evals" / "RESULTS.md").write_text("\n".join(md))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
