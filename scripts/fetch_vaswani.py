#!/usr/bin/env python
"""Download the Vaswani/NPL files used by the pilot and verify their SHA-256.

The files come from the PyTerrier repository at a pinned commit (``tests/fixtures/vaswani_npl``). Two checksums are
checked: the md5 identifiers that PyTerrier 1.1.2 itself lists for the Vaswani corpus, topics and qrels
(``pyterrier/datasets/_builtin.py``, ``irds_mirror(...)`` entries), and the SHA-256 of the files used for the reported
results. Neither is a checksum published by the collection's original authors (none was found).

The repository does not contain the collection: neither the ir_datasets page nor the Glasgow IR group page for NPL
states a licence or redistribution terms, so the files are fetched rather than copied.

    python scripts/fetch_vaswani.py [--out data/raw/vaswani]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

COMMIT = "2459d8780138d8a7976b7af1bd1e2f467fdc6a02"
BASE = f"https://raw.githubusercontent.com/terrier-org/pyterrier/{COMMIT}/tests/fixtures/vaswani_npl"
# local name -> (path in the PyTerrier repository, md5 listed by PyTerrier 1.1.2, sha256 of the files used in the pilot)
FILES = {
    "doc-text.trec": ("corpus/doc-text.trec", "a059e713c50350e39999467c8c73b7c5",
                      "117ae7491647cb9725621bad52969a78307de19b1757852a0a2383659a856d36"),
    "query-text.trec": ("query-text.trec", "3a624be2b0ef7c9534cf848891679bec",
                        "fef998db14818f74a22b2fb2be06425d5fb0dbd83ed9841fa0440e0a5477da7b"),
    "qrels": ("qrels", "6acb6db9969da8b8c6c23c09551af8d9",
              "1b3ed6a43752c7a7becb0dbd1614d662791bb7825b60182fd36be24d480ea447"),
}


def digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/vaswani")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, (remote, want_md5, want_sha) in FILES.items():
        dest = out / name
        if dest.exists() and digest(dest, "md5") == want_md5 and digest(dest, "sha256") == want_sha:
            print(f"ok       {name} (already present, checksums match)")
            continue
        url = f"{BASE}/{remote}"
        with tempfile.NamedTemporaryFile(dir=out, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(tmp_path, "wb") as f:
                f.write(resp.read())
            got_md5, got_sha = digest(tmp_path, "md5"), digest(tmp_path, "sha256")
            if (got_md5, got_sha) != (want_md5, want_sha):
                print(f"MISMATCH {name}: expected md5 {want_md5} / sha256 {want_sha}, got {got_md5} / {got_sha}; "
                      "not installed", file=sys.stderr)
                return 1
            tmp_path.replace(dest)
            print(f"ok       {name} downloaded and verified")
        finally:
            tmp_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
