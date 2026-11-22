"""PII guard: blocks private strings, absolute home paths, media metadata and non-UTC commits.

The denylist is read at run time from HBL_DENYLIST, else ~/hbl_private/denylist.txt. It is
referenced by path and never copied into the repo. A missing denylist fails closed.

Denylist format: one entry per line; '#' comments and blank lines are ignored. Plain lines are
literals, matched case-insensitively on word boundaries (a boundary is any
character that is not a letter or digit, so '_' and '-' separate words). Lines starting with 're:' are Python
regular expressions, used as written.

Findings name the file, line and denylist entry number, never the matched text.

Usage (hooks): pii_guard.py staged | pii_guard.py message <file> | pii_guard.py files <path>...
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_DENYLIST = "~/hbl_private/denylist.txt"
# Content of these files is not scanned (file names still are): age ciphertext and
# OpenTimestamps proofs are random-looking bytes that decode to stray letters and trip
# single-character regex entries. Every other file, binaries and images included, is scanned.
CONTENT_EXEMPT_EXT = (".age", ".ots")
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".heic", ".pdf"}
# Built-in checks that do not depend on the denylist.
ABSOLUTE_PATH = re.compile(r"(?<![\w.])/(?:Users|home)/[A-Za-z0-9._-]+|\b[A-Za-z]:\\Users\\[A-Za-z0-9._-]+")
MEDIA_MARKERS = (b"Exif\x00", b"http://ns.adobe.com/xap", b"tEXt", b"iTXt", b"zTXt", b"eXIf",
                 b"/Author", b"/Creator", b"GPSLatitude")


@dataclass(frozen=True)
class Hit:
    where: str
    line: int
    entry: int  # 1-based denylist entry number; 0 for built-in checks
    kind: str  # "literal" | "regex" | "absolute-path" | "media-metadata" | "file-name"

    def __str__(self) -> str:
        loc = f"{self.where}:{self.line}" if self.line else self.where
        ref = f"denylist entry #{self.entry} ({self.kind})" if self.entry else self.kind
        return f"{loc} matches {ref}"


class Denylist:
    def __init__(self, patterns: List[Tuple[int, str, "re.Pattern[str]"]]):
        self.patterns = patterns

    @classmethod
    def load(cls, path: Optional[os.PathLike] = None) -> "Denylist":
        p = Path(os.path.expanduser(str(path or os.environ.get("HBL_DENYLIST") or DEFAULT_DENYLIST)))
        if not p.is_file():
            raise FileNotFoundError(f"denylist not found ({p.name}); refusing to continue")
        patterns = []
        n = 0
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            n += 1
            if line.startswith("re:"):
                patterns.append((n, "regex", re.compile(line[3:])))
            else:
                # word boundary = not a letter or digit ('_' and '-' separate words, as in file names)
                patterns.append((n, "literal", re.compile(r"(?<![^\W_])" + re.escape(line) + r"(?![^\W_])", re.I)))
        return cls(patterns)


def scan_text(text: str, deny: Denylist, where: str = "<text>") -> List[Hit]:
    hits = []
    for ln, line in enumerate(text.splitlines(), 1):
        for entry, kind, rx in deny.patterns:
            if rx.search(line):
                hits.append(Hit(where, ln, entry, kind))
        if ABSOLUTE_PATH.search(line):
            hits.append(Hit(where, ln, 0, "absolute-path"))
    return hits


def scan_name(name: str, deny: Denylist) -> List[Hit]:
    return [Hit(name, 0, h.entry, "file-name" if h.entry else h.kind) for h in scan_text(name, deny, name)]


def has_media_metadata(name: str, data: bytes) -> bool:
    if Path(name).suffix.lower() not in MEDIA_EXT:
        return False
    return any(m in data for m in MEDIA_MARKERS)


def is_utc_env(env: Dict[str, str]) -> bool:
    dates = [env.get("GIT_AUTHOR_DATE", ""), env.get("GIT_COMMITTER_DATE", "")]
    return all(d.endswith("+0000") for d in dates)


def scan_blob(name: str, data: bytes, deny: Denylist) -> List[Hit]:
    hits = scan_name(name, deny)
    if name.lower().endswith(CONTENT_EXEMPT_EXT):
        return hits
    if has_media_metadata(name, data):
        hits.append(Hit(name, 0, 0, "media-metadata (strip it before committing)"))
    hits += scan_text(data.decode("utf-8", errors="replace"), deny, name)
    return hits


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def staged_hits(deny: Denylist) -> List[Hit]:
    names = [n for n in _git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").decode().split("\0") if n]
    hits = []
    for n in names:
        hits += scan_blob(n, _git("show", f":{n}"), deny)
    for var in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        ident = _git("var", var).decode()
        hits += [Hit(f"commit identity ({var})", 0, h.entry, h.kind) for h in scan_text(ident, deny)]
    return hits


def _report(hits: List[Hit], what: str) -> int:
    if not hits:
        return 0
    print(f"PII guard: {what} blocked ({len(hits)} finding(s)):", file=sys.stderr)
    for h in hits[:50]:
        print(f"  {h}", file=sys.stderr)
    if len(hits) > 50:
        print(f"  ... {len(hits) - 50} more", file=sys.stderr)
    return 1


def main(argv: List[str]) -> int:
    try:
        deny = Denylist.load()
    except (FileNotFoundError, re.error) as exc:
        print(f"PII guard: cannot load the denylist: {exc}", file=sys.stderr)
        return 1
    if argv[:1] == ["staged"]:
        if not is_utc_env(dict(os.environ)):
            print("PII guard: commit refused — timestamps must be UTC. Commit with `git cu` "
                  "(sets GIT_AUTHOR_DATE / GIT_COMMITTER_DATE with +0000).", file=sys.stderr)
            return 1
        return _report(staged_hits(deny), "commit")
    if argv[:1] == ["message"] and len(argv) == 2:
        text = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
        body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
        return _report(scan_text(body, deny, "commit message"), "commit message")
    if argv[:1] == ["files"]:
        hits = []
        for f in argv[1:]:
            if not Path(f).is_file():  # e.g. a path deleted in this commit
                continue
            hits += scan_blob(f, Path(f).read_bytes(), deny)
        return _report(hits, "files")
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
