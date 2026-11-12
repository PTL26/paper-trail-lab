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
        ".nojekyll", "index.html", "lie-detector/index.html", "t1-explorer/index.html"]
    assert (out / "t1-explorer" / "index.html").read_bytes() == (ROOT / "t1-explorer" / "index.html").read_bytes()
    assert (out / "lie-detector" / "index.html").read_bytes() == (ROOT / "site" / "lie-detector" / "index.html").read_bytes()


def test_landing_page_is_self_contained_and_links_resolve(tmp_path):
    out = assemble(tmp_path)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert build.external_requests(html) == [] and build.plain_http(html) == []
    links = re.findall(r'href="([^"]+)"', html)
    local = [h for h in links if not h.startswith(("https://", "data:"))]
    assert sorted(set(local)) == ["lie-detector/", "t1-explorer/"]
    assert all((out / h / "index.html").is_file() for h in local)
    assert any(h == "https://github.com/PTL26/paper-trail-lab/tree/main/skills/pre-registration" for h in links)
    assert (ROOT / "skills" / "pre-registration" / "SKILL.md").is_file()
    assert "Not investment advice." in html and "CC BY 4.0" in html and "MIT" in html


def test_landing_page_content():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert "<title>Paper Trail Lab</title>" in html
    assert "/plugin marketplace add PTL26/paper-trail-lab" in html
    assert "/plugin install pre-registration@paper-trail-lab" in html
    assert ("Honest Arena — a pre-registered forward test of popular open-source AI trading agents — "
            "starts soon.") in html
    assert "EMAIL SIGN-UP PLACEHOLDER" in html  # replaced by the Substack link later
    assert "prefers-color-scheme: dark" in html and 'name="viewport"' in html


def test_lie_detector_page():
    html = (ROOT / "site" / "lie-detector" / "index.html").read_text(encoding="utf-8")
    assert '<div class="eyebrow">Paper Trail Lab / free tool</div>' in html
    assert "<title>Backtest Lie Detector</title>" in html
    assert build.plain_http(html) == []


def test_workflow_pins_actions_and_publishes_the_assembled_site():
    wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    uses = re.findall(r"uses:\s*(\S+)", wf)
    assert uses and all(re.fullmatch(r"actions/[\w-]+@[0-9a-f]{40}", u) for u in uses)
    assert "sh tools/build_site.sh _site" in wf and "path: _site" in wf
    assert "site/**" in wf and "t1-explorer/index.html" in wf
    assert "pages: write" in wf and "id-token: write" in wf


def test_no_page_loads_anything_from_a_third_party_host(tmp_path):
    out = assemble(tmp_path)
    pages = sorted(out.rglob("*.html"))
    assert len(pages) == 3
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert build.external_requests(html) == [], page.relative_to(out)
        assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
