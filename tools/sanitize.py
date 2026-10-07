"""Copy a source file into this repo with placeholders applied, then run the PII guard on it.

  python tools/sanitize.py SRC DEST [--map MAPFILE]

Replacements, in order:
1. home paths (/Users/<name>, /home/<name>) -> <HOME>;
2. denylist literals -> the placeholder from the private map file (default
   ~/hbl_private/placeholders.txt, lines "literal => replacement"), else [redacted];
3. denylist regexes -> [redacted].
The result is checked with the same denylist; if anything still matches, nothing is written.
DEST must be inside the repo. Output reports counts only, never the replaced values.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

try:  # run as a module (tests) or as a script (tools/sanitize.py)
    from tools.pii_guard import Denylist, scan_text
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pii_guard import Denylist, scan_text  # type: ignore[no-redef]

DEFAULT_MAP = "~/hbl_private/placeholders.txt"
REPO_ROOT = Path(__file__).resolve().parents[1]
HOME_PATH = re.compile(r"(?<![\w.])/(?:Users|home)/[A-Za-z0-9._-]+")


class SanitizeError(RuntimeError):
    pass


def load_map(path: Optional[os.PathLike] = None) -> Dict[str, str]:
    p = Path(os.path.expanduser(str(path or DEFAULT_MAP)))
    if not p.is_file():
        return {}
    out = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=>" not in line:
            continue
        k, v = (s.strip() for s in line.split("=>", 1))
        out[k.lower()] = v
    return out


def sanitize_text(text: str, deny: Denylist, mapping: Dict[str, str]) -> Tuple[str, int]:
    count = 0
    text, n = HOME_PATH.subn("<HOME>", text)
    count += n
    for _entry, kind, rx in deny.patterns:
        if kind == "literal":
            def repl(m: "re.Match[str]") -> str:
                return mapping.get(m.group(0).lower(), "[redacted]")
            text, n = rx.subn(repl, text)
        else:
            text, n = rx.subn("[redacted]", text)
        count += n
    return text, count


def sanitize_file(src: Path, dest: Path, deny: Denylist, mapping: Dict[str, str],
                  repo_root: Path = REPO_ROOT) -> int:
    dest = Path(dest).resolve()
    root = Path(repo_root).resolve()
    if root != dest and root not in dest.parents:
        raise SanitizeError("destination is outside the repo")
    out, n = sanitize_text(Path(src).read_text(encoding="utf-8"), deny, mapping)
    hits = scan_text(out, deny, dest.name)
    if hits:
        raise SanitizeError(f"result still matches the denylist ({len(hits)} finding(s), e.g. {hits[0]}); "
                            "nothing written")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    return n


def main() -> int:  # pragma: no cover - CLI
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dest")
    ap.add_argument("--map", default=None)
    a = ap.parse_args()
    try:
        n = sanitize_file(Path(a.src), Path(a.dest), Denylist.load(), load_map(a.map))
    except (SanitizeError, FileNotFoundError) as exc:
        print(f"sanitize: {exc}", file=sys.stderr)
        return 1
    print(f"sanitize: wrote {Path(a.dest).name} ({n} replacement(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
