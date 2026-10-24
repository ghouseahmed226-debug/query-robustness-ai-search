#!/usr/bin/env python
"""Human validity audit of query rewrites.

1. ``blind``  draw a stratified sample (or everything) and write a blind sheet for the annotator plus a private key.
2. (annotator fills the ``human_label`` column with equivalent / broader / narrower / different)
3. ``score``  agreement between the human and the labels used in the analysis (validity of the analysis set,
              false-drop rate, agreement and Cohen's kappa against the blind LLM reviewer).
4. ``apply``  write a new rewrite file in which every human-labelled rewrite becomes ``human_verified``. This is the
              only code path that sets that status; it needs ``--annotator``.

Example::

    python scripts/audit_tool.py blind --rewrites data/rewrites/vaswani_rewrites.jsonl --out-prefix audit/vaswani --per-generator 15
    # give audit/vaswani_blind.csv to the annotator, keep audit/vaswani_key.csv away from them
    python scripts/audit_tool.py score --blind audit/vaswani_blind_filled.csv --key audit/vaswani_key.csv
    python scripts/audit_tool.py apply --rewrites data/rewrites/vaswani_rewrites.jsonl \
        --blind audit/vaswani_blind_filled.csv --key audit/vaswani_key.csv --annotator "Your Name" \
        --out data/rewrites/vaswani_rewrites_human.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qvr.audit import (
    BLIND_FIELDS,
    KEY_FIELDS,
    apply_human_labels,
    audit_markdown,
    make_blind_sheet,
    read_csv_rows,
    score_audit,
    write_csv_rows,
)
from qvr.rewrites import read_jsonl, write_jsonl


def cmd_blind(args) -> int:
    records = read_jsonl(args.rewrites)
    blind, key = make_blind_sheet(records, per_generator=None if args.all else args.per_generator, seed=args.seed)
    write_csv_rows(f"{args.out_prefix}_blind.csv", blind, BLIND_FIELDS)
    write_csv_rows(f"{args.out_prefix}_key.csv", key, KEY_FIELDS)
    print(f"{len(blind)} rewrites in {args.out_prefix}_blind.csv (give this to the annotator); "
          f"key in {args.out_prefix}_key.csv (keep it away from the annotator)")
    return 0


def cmd_score(args) -> int:
    report = score_audit(read_csv_rows(args.blind), read_csv_rows(args.key))
    text = audit_markdown(report)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        Path(args.out).with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


def cmd_apply(args) -> int:
    new, n = apply_human_labels(read_jsonl(args.rewrites), read_csv_rows(args.blind), read_csv_rows(args.key),
                                args.annotator)
    write_jsonl(args.out, new)
    print(f"{n} rewrites marked human_verified by {args.annotator!r}; wrote {len(new)} records to {args.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("blind")
    p.add_argument("--rewrites", required=True)
    p.add_argument("--out-prefix", required=True)
    p.add_argument("--per-generator", type=int, default=15)
    p.add_argument("--all", action="store_true", help="take every candidate rewrite instead of a sample")
    p.add_argument("--seed", type=int, default=13)
    p.set_defaults(fn=cmd_blind)
    p = sub.add_parser("score")
    p.add_argument("--blind", required=True, help="the annotator's filled sheet")
    p.add_argument("--key", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("apply")
    p.add_argument("--rewrites", required=True)
    p.add_argument("--blind", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--annotator", required=True, help="who judged the rewrites; stored as 'human: NAME'")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_apply)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
