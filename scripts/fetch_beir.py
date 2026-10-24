#!/usr/bin/env python
"""Download and verify one or more BEIR datasets.

Downloads the standard .zip from the UKP TU-Darmstadt mirror, extracts it,
and verifies the expected file structure.  Prints SHA-256 checksums of the
three core files so they can be pinned in the analysis plan.

Supported datasets (subset most likely to be useful for this study):
  scifact  nfcorpus  trec-covid  fiqa  arguana  webis-touche2020

Usage
-----
    python scripts/fetch_beir.py scifact nfcorpus --out data/raw/beir

Each dataset lands in  <out>/<name>/  with corpus.jsonl, queries.jsonl,
qrels/test.tsv (and whatever else the zip contains).

The user is responsible for checking each dataset's own licence before
redistributing anything derived from it.  Licence links are printed on
download.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
import zipfile
from pathlib import Path

try:
    import urllib.request as _req
except ImportError:
    _req = None

# ── dataset registry ──────────────────────────────────────────────────────────
BASE_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets"

DATASETS: dict[str, dict] = {
    "scifact": {
        "zip": "scifact.zip",
        "licence": "https://github.com/allenai/scifact/blob/master/LICENSE",
        "note": "CC BY-NC 2.0 — check the AllenAI repo for exact terms",
        "expected_files": ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"],
    },
    "nfcorpus": {
        "zip": "nfcorpus.zip",
        "licence": "https://www.cl.uni-heidelberg.de/statnlpgroup/nfcorpus/",
        "note": "Non-commercial research use only — read the NFCorpus page",
        "expected_files": ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"],
    },
    "trec-covid": {
        "zip": "trec-covid.zip",
        "licence": "https://ir.nist.gov/covidSubmit/",
        "note": "CORD-19 terms apply; check the TREC-COVID page",
        "expected_files": ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"],
    },
    "fiqa": {
        "zip": "fiqa.zip",
        "licence": "https://sites.google.com/view/fiqa/home",
        "note": "Unknown / check FiQA homepage",
        "expected_files": ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"],
    },
    "arguana": {
        "zip": "arguana.zip",
        "licence": "https://aclanthology.org/P18-1023/",
        "note": "ArguAna dataset; check the paper for terms",
        "expected_files": ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"],
    },
    "webis-touche2020": {
        "zip": "webis-touche2020.zip",
        "licence": "https://webis.de/data/webis-touche2020-corpus-v2.html",
        "note": "Check the Webis page for terms",
        "expected_files": ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"],
    },
    "hotpotqa": {
        "zip": "hotpotqa.zip",
        "licence": "https://hotpotqa.github.io/",
        "note": "CC BY-SA 4.0",
        "expected_files": ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"],
    },
}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def download_with_progress(url: str, label: str) -> bytes:
    print(f"  downloading {label} …", end=" ", flush=True)
    with _req.urlopen(url, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        buf = io.BytesIO()
        downloaded = 0
        chunk = 1 << 16  # 64 KiB
        while True:
            block = resp.read(chunk)
            if not block:
                break
            buf.write(block)
            downloaded += len(block)
            if total:
                pct = downloaded / total * 100
                print(f"\r  downloading {label} … {pct:5.1f}%", end="", flush=True)
    print(f"\r  downloaded  {label}  ({downloaded / 1e6:.1f} MB)    ")
    return buf.getvalue()


def fetch_one(name: str, out_root: Path) -> dict:
    info = DATASETS[name]
    dest = out_root / name
    if dest.exists() and all((dest / f).exists() for f in info["expected_files"]):
        print(f"[{name}] already present at {dest} — skipping download")
    else:
        dest.mkdir(parents=True, exist_ok=True)
        url = f"{BASE_URL}/{info['zip']}"
        print(f"\n[{name}]")
        print(f"  licence: {info['licence']}")
        print(f"  note:    {info['note']}")
        data = download_with_progress(url, name)
        print(f"  extracting …", end=" ", flush=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # BEIR zips have a top-level directory whose name matches the dataset
            members = zf.namelist()
            top = members[0].split("/")[0]
            for member in members:
                # strip the top-level dir so files land in dest/
                rel = "/".join(member.split("/")[1:])
                if not rel:
                    continue
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if not member.endswith("/"):
                    target.write_bytes(zf.read(member))
        print("done")

    # verify
    missing = [f for f in info["expected_files"] if not (dest / f).exists()]
    if missing:
        print(f"  WARNING: expected files missing after extraction: {missing}", file=sys.stderr)
        return {"name": name, "path": str(dest), "status": "incomplete", "missing": missing}

    checksums = {f: sha256_file(dest / f) for f in info["expected_files"]}
    sizes = {f: (dest / f).stat().st_size for f in info["expected_files"]}
    print(f"[{name}] verified — SHA-256:")
    for f, h in checksums.items():
        print(f"    {h}  {f}  ({sizes[f]:,} bytes)")
    return {"name": name, "path": str(dest), "status": "ok", "sha256": checksums, "sizes": sizes}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datasets", nargs="+", choices=list(DATASETS),
                    metavar="DATASET",
                    help=f"one or more of: {', '.join(DATASETS)}")
    ap.add_argument("--out", default="data/raw/beir",
                    help="root directory; each dataset lands in <out>/<name>/  (default: data/raw/beir)")
    args = ap.parse_args(argv)

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    results = []
    for name in args.datasets:
        try:
            results.append(fetch_one(name, out_root))
        except Exception as exc:
            print(f"[{name}] FAILED: {exc}", file=sys.stderr)
            results.append({"name": name, "status": "error", "error": str(exc)})

    print("\n── summary ──────────────────────────────────────────────────────")
    ok = [r["name"] for r in results if r.get("status") == "ok"]
    bad = [r["name"] for r in results if r.get("status") != "ok"]
    if ok:
        print(f"  OK:     {', '.join(ok)}")
    if bad:
        print(f"  FAILED: {', '.join(bad)}")
    print()
    print("Pin the SHA-256 checksums above in docs/ANALYSIS_PLAN.md before running experiments.")
    print("Check each dataset's licence before redistributing derived data.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
