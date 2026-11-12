"""The pre-registration skill is installable as a Claude Code plugin from this repo's marketplace.

  /plugin marketplace add PTL26/paper-trail-lab
  /plugin install pre-registration@paper-trail-lab
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def test_marketplace_manifest():
    m = load(ROOT / ".claude-plugin" / "marketplace.json")
    assert m["name"] == "paper-trail-lab" and NAME.fullmatch(m["name"])
    assert m["owner"]["name"] == "Paper Trail Lab" and set(m["owner"]) <= {"name", "url"}
    assert m["description"]
    assert [p["name"] for p in m["plugins"]] == ["pre-registration"]
    entry = m["plugins"][0]
    assert entry["source"] == "./skills/pre-registration" and ".." not in entry["source"]
    assert (ROOT / entry["source"] / "SKILL.md").is_file()
    assert "version" not in entry  # plugin.json is the single source of the version


def test_plugin_manifest_matches_entry_and_skill():
    root = ROOT / "skills" / "pre-registration"
    p = load(root / ".claude-plugin" / "plugin.json")
    assert p["name"] == "pre-registration" and NAME.fullmatch(p["name"])
    assert p["version"] and p["description"] and p["license"] == "MIT"
    assert p["author"]["name"] == "Paper Trail Lab" and "email" not in p["author"]
    assert p["repository"] == "https://github.com/PTL26/paper-trail-lab"
    # SKILL.md at the plugin root and no skills/ dir: loads as a single skill, no `skills` key needed
    assert (root / "SKILL.md").is_file() and not (root / "skills").exists() and "skills" not in p
    front = (root / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
    assert re.search(r"^name: pre-registration$", front, re.M)
