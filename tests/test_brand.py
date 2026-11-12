"""Public-facing files carry the Paper Trail Lab brand, not the old name."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = re.compile(r"honest[\s_-]*bot[\s_-]*lab|honestbotlab", re.I)


def test_no_old_brand_in_tracked_or_new_files():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    hits = [f for f in files if f != "tests/test_brand.py" and (ROOT / f).is_file()
            and OLD.search((ROOT / f).read_text(encoding="utf-8", errors="replace"))]
    assert hits == []
