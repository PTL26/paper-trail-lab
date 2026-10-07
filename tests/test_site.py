"""Tests for the published site: tools/build_site.sh output, the landing page and the Pages workflow."""

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "t1-explorer" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def assemble(tmp_path):
    out = tmp_path / "site"
    subprocess.run(["sh", str(ROOT / "tools" / "build_site.sh"), str(out)], check=True, capture_output=True)
    return out


def test_site_layout(tmp_path):
    out = assemble(tmp_path)
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        ".nojekyll", "index.html", "t1-explorer/index.html"]
    assert (out / "t1-explorer" / "index.html").read_bytes() == (ROOT / "t1-explorer" / "index.html").read_bytes()


def test_landing_page_is_self_contained_and_links_resolve(tmp_path):
    out = assemble(tmp_path)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert build.external_requests(html) == [] and build.plain_http(html) == []
    links = re.findall(r'href="([^"]+)"', html)
    local = [h for h in links if not h.startswith(("https://", "data:"))]
    assert local == ["t1-explorer/"] and (out / "t1-explorer" / "index.html").is_file()
    assert any(h.endswith("/skills/pre-registration") for h in links)
    assert (ROOT / "skills" / "pre-registration" / "SKILL.md").is_file()
    assert "Not investment advice." in html and "CC BY 4.0" in html and "MIT" in html


def test_workflow_pins_actions_and_publishes_the_assembled_site():
    wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    uses = re.findall(r"uses:\s*(\S+)", wf)
    assert uses and all(re.fullmatch(r"actions/[\w-]+@[0-9a-f]{40}", u) for u in uses)
    assert "sh tools/build_site.sh _site" in wf and "path: _site" in wf
    assert "pages: write" in wf and "id-token: write" in wf
