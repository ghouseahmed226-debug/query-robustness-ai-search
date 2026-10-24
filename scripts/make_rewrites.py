#!/usr/bin/env python
"""Build the query-rewrite file in four steps. Nothing here marks a rewrite as human-verified.

1. ``automatic``  seeded character-level typos, word-order swaps and stop-word removal.
2. ``llm``        turn the LLM-written rewrites (one JSON line per query) into candidate records.
3. ``packet``     write a blind review packet (opaque ids, no category, no generator) plus a private key.
4. ``recheck``    second, conservative validity check made by the author for machine-made rewrites: word-order
                  swaps are valid only if they move function words only; manual objections can be added from a file.
5. ``merge``      attach the reviewer's labels, apply the recheck (unanimity), write the final rewrite file, a
                  reviewer-only variant for sensitivity analysis, summaries and the human-audit sheet.

Example (Vaswani pilot)::

    python scripts/make_rewrites.py automatic --dataset vaswani --data-dir data/raw/vaswani --out data/rewrites/vaswani_automatic.jsonl
    python scripts/make_rewrites.py llm --dataset vaswani --data-dir data/raw/vaswani --raw data/rewrites/vaswani_llm_raw.jsonl --out data/rewrites/vaswani_llm_candidates.jsonl
    python scripts/make_rewrites.py packet --automatic data/rewrites/vaswani_automatic.jsonl --llm data/rewrites/vaswani_llm_candidates.jsonl --packet-dir /tmp/review_packets --key data/rewrites/vaswani_review_key.jsonl
    python scripts/make_rewrites.py merge --automatic ... --llm ... --key ... --reviews /tmp/review_packets/labels_*.jsonl --out data/rewrites/vaswani_rewrites.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from qvr.data import load_beir, load_vaswani, natural_key
from qvr.rewrites import (
    AUTOMATIC,
    CATEGORY_OF_GENERATOR,
    LLM_REVIEWED,
    REVIEW_LABELS,
    UNREVIEWED,
    audit_sample,
    generate_automatic,
    merge_reviews,
    normalise_query,
    read_jsonl,
    swap_touches_only_function_words,
    write_audit_sheet,
    write_jsonl,
)
from qvr.text import Analyzer

TYPO_GENERATORS = ("NeighbCharSwap", "RandomCharSub", "QWERTYCharSub")
LLM_GENERATORS = ("LLM_NaturalQuestion", "LLM_Paraphrase", "LLM_SynonymSwap")


def load_collection(args):
    return load_vaswani(args.data_dir) if args.dataset == "vaswani" else load_beir(args.data_dir, args.split)


def cmd_automatic(args) -> int:
    coll = load_collection(args)
    queries = {q: coll.queries[q] for q in coll.judged_queries()}
    records, skipped = generate_automatic(queries, seed=args.seed)

    vocab: set[str] = set()
    for text in coll.doc_texts:
        vocab.update(Analyzer.tokenize(text))
    for r in records:
        if r["generator"] in TYPO_GENERATORS:
            old, new = r["original_query"].split(), r["query"].split()
            edited = [n for o, n in zip(old, new) if o != n]
            r["edited_token"] = edited[0] if edited else ""
            r["edited_token_in_collection_vocab"] = bool(edited) and edited[0] in vocab
    write_jsonl(args.out, records)

    per_gen = Counter(r["generator"] for r in records)
    print(f"{len(queries)} judged queries; wrote {len(records)} automatic candidates to {args.out}")
    for gen in per_gen:
        extra = ""
        if gen in TYPO_GENERATORS:
            n_vocab = sum(1 for r in records if r["generator"] == gen and r["edited_token_in_collection_vocab"])
            extra = f"  edited word is another word of the collection: {n_vocab}/{per_gen[gen]}"
        print(f"  {gen:16s} {per_gen[gen]:4d}{extra}")
    if skipped:
        print("  skipped:", {f"{g}:{why}": n for (g, why), n in skipped.items()})
    return 0


def cmd_llm(args) -> int:
    coll = load_collection(args)
    queries = {q: coll.queries[q] for q in coll.judged_queries()}
    raw = read_jsonl(args.raw)
    seen_qids = set()
    records, problems = [], []
    for line in raw:
        qid = str(line["qid"])
        if qid not in queries:
            problems.append(f"qid {qid} is not a judged query")
            continue
        if qid in seen_qids:
            problems.append(f"qid {qid} appears twice")
            continue
        seen_qids.add(qid)
        original = queries[qid]
        for gen in LLM_GENERATORS:
            text = line.get(gen)
            if not text:
                problems.append(f"qid {qid}: missing {gen}")
                continue
            new = " ".join(str(text).lower().split())
            if normalise_query(new) == normalise_query(original):
                problems.append(f"qid {qid}: {gen} is identical to the original")
                continue
            records.append({
                "qid": qid, "rewrite_id": f"{qid}__{gen}", "category": CATEGORY_OF_GENERATOR[gen], "generator": gen,
                "query": new, "original_query": original, "meaning_preserved": None, "review_status": UNREVIEWED,
            })
    missing = sorted(set(queries) - seen_qids, key=natural_key)
    if missing:
        problems.append(f"no LLM rewrites for qids: {missing}")
    write_jsonl(args.out, records)
    print(f"wrote {len(records)} LLM candidates for {len(seen_qids)} queries to {args.out}")
    for p in problems:
        print("  PROBLEM:", p)
    return 1 if problems and args.strict else 0


def cmd_packet(args) -> int:
    auto = read_jsonl(args.automatic)
    llm = read_jsonl(args.llm)
    to_review = [r for r in auto if r["review_status"] == UNREVIEWED] + llm
    typos = sorted((r for r in auto if r["review_status"] == AUTOMATIC), key=lambda r: r["rewrite_id"])
    rng = random.Random(args.seed)
    calibration = rng.sample(typos, min(args.calibration_typos, len(typos)))
    items = [(r, False) for r in to_review] + [(r, True) for r in calibration]
    items.sort(key=lambda t: t[0]["rewrite_id"])  # canonical order first so the shuffle is reproducible
    rng.shuffle(items)
    packet_dir = Path(args.packet_dir)
    packet_dir.mkdir(parents=True, exist_ok=True)
    key_rows, packet_rows = [], []
    for i, (r, is_cal) in enumerate(items, start=1):
        pid = f"p{i:04d}"
        packet_rows.append({"pair_id": pid, "original": r["original_query"], "rewrite": r["query"]})
        key_rows.append({"pair_id": pid, "rewrite_id": r["rewrite_id"], "calibration": is_cal})
    n_chunks = max(1, args.chunks)
    size = -(-len(packet_rows) // n_chunks)
    for c in range(n_chunks):
        write_jsonl(packet_dir / f"review_packet_{c + 1}.jsonl", packet_rows[c * size:(c + 1) * size])
    write_jsonl(args.key, key_rows)
    print(f"{len(packet_rows)} pairs ({len(calibration)} calibration typos mixed in) in {n_chunks} chunk(s) under {packet_dir}; key: {args.key}")
    return 0


def cmd_recheck(args) -> int:
    auto = read_jsonl(args.automatic)
    rows = []
    for r in auto:
        if r["generator"] == "RandomOrderSwap":
            ok = swap_touches_only_function_words(r["original_query"], r["query"])
            rows.append({"rewrite_id": r["rewrite_id"], "author_label": "equivalent" if ok else "not_equivalent",
                         "note": "only function words moved" if ok else "a content word was displaced (rule)",
                         "basis": "rule"})
    ids = {r["rewrite_id"] for r in auto}
    if args.manual:
        for item in read_jsonl(args.manual):
            if item["rewrite_id"] not in ids:
                raise SystemExit(f"manual recheck refers to unknown rewrite {item['rewrite_id']}")
            if item["author_label"] not in ("equivalent", "not_equivalent"):
                raise SystemExit(f"bad author_label {item['author_label']!r}")
            rows.append({**item, "basis": "manual"})
    write_jsonl(args.out, rows)
    n_bad = sum(1 for r in rows if r["author_label"] == "not_equivalent")
    print(f"wrote {len(rows)} recheck labels to {args.out} ({n_bad} not equivalent)")
    return 0


def cmd_merge(args) -> int:
    auto = read_jsonl(args.automatic)
    llm = read_jsonl(args.llm)
    key = {k["pair_id"]: k for k in read_jsonl(args.key)}
    label_of: dict[str, dict] = {}
    for path in args.reviews:
        for item in read_jsonl(path):
            pid = item["pair_id"]
            if pid not in key:
                raise SystemExit(f"{path}: unknown pair_id {pid}")
            if key[pid]["rewrite_id"] in label_of:
                raise SystemExit(f"{path}: duplicate label for {pid}")
            label = str(item["label"]).strip().lower()
            if label not in REVIEW_LABELS:
                raise SystemExit(f"{path}: invalid label {item['label']!r} for {pid}")
            label_of[key[pid]["rewrite_id"]] = {"rewrite_id": key[pid]["rewrite_id"], "label": label,
                                                "reviewer": args.reviewer, "note": item.get("note", "")}
    calibration_ids = {k["rewrite_id"] for k in key.values() if k["calibration"]}

    typo_records, candidates = [], []
    for r in auto + llm:
        (typo_records if r["review_status"] == AUTOMATIC else candidates).append(r)
    reviews_for_candidates = [v for rid, v in label_of.items() if rid not in calibration_ids]
    merged, stats = merge_reviews(candidates, reviews_for_candidates)
    recheck = {}
    if args.author_recheck:
        for item in read_jsonl(args.author_recheck):
            recheck[item["rewrite_id"]] = item  # a later (manual) entry overrides a rule entry for the same rewrite
    for r in merged:
        r["reviewer_only_meaning_preserved"] = r["meaning_preserved"]  # kept for the sensitivity analysis
        rc = recheck.get(r["rewrite_id"])
        if rc is not None:
            r["author_recheck_label"] = rc["author_label"]
            r["author_recheck_note"] = rc.get("note", "")
            r["author_recheck_basis"] = rc.get("basis", "")
            if rc["author_label"] != "equivalent":
                r["meaning_preserved"] = False if r["review_status"] == LLM_REVIEWED else r["meaning_preserved"]
    for r in typo_records:  # diagnostic only: the label never changes a typo's status or validity
        if r["rewrite_id"] in label_of:
            r["calibration_label"] = label_of[r["rewrite_id"]]["label"]
    final = sorted(typo_records + merged, key=lambda r: (natural_key(r["qid"]), r["generator"]))
    write_jsonl(args.out, final)
    if args.reviewer_only_out:  # sensitivity variant: validity from the blind reviewer alone
        liberal = []
        for r in final:
            r = dict(r)
            if "reviewer_only_meaning_preserved" in r:
                r["meaning_preserved"] = r["reviewer_only_meaning_preserved"]
            liberal.append(r)
        write_jsonl(args.reviewer_only_out, liberal)

    by_gen: dict[str, Counter] = defaultdict(Counter)
    for r in merged:
        by_gen[r["generator"]][r.get("review_label", "unreviewed")] += 1
    cal = Counter(r["calibration_label"] for r in typo_records if "calibration_label" in r)
    kept = [r for r in final if r["review_status"] in (AUTOMATIC, LLM_REVIEWED) and r["meaning_preserved"] is True]
    summary = {
        "n_records": len(final), "n_kept_for_analysis": len(kept),
        "labels_by_generator": {g: dict(c) for g, c in sorted(by_gen.items())},
        "typo_calibration_labels": dict(cal),
        "typo_share_with_edited_word_in_collection_vocab": {
            g: [sum(1 for r in typo_records if r["generator"] == g and r.get("edited_token_in_collection_vocab")),
                sum(1 for r in typo_records if r["generator"] == g)] for g in TYPO_GENERATORS},
        "kept_by_generator": dict(Counter(r["generator"] for r in kept)),
        "kept_by_category": dict(Counter(r["category"] for r in kept)),
        "unreviewed_candidates": stats.get("unreviewed", 0),
        "removed_by_author_recheck": dict(Counter(
            r["generator"] for r in merged
            if r.get("reviewer_only_meaning_preserved") is True and r["meaning_preserved"] is not True)),
        "reviewer_only_equivalent_by_generator": dict(Counter(
            r["generator"] for r in merged if r.get("reviewer_only_meaning_preserved") is True)),
    }
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_audit_sheet(args.audit, audit_sample(kept, per_category=args.audit_per_generator, seed=args.seed, by="generator"))
    print(json.dumps(summary, indent=2))
    print(f"final rewrite file: {args.out}; audit sheet: {args.audit}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_collection(p):
        p.add_argument("--dataset", choices=["vaswani", "beir"], required=True)
        p.add_argument("--data-dir", required=True)
        p.add_argument("--split", default="test")

    p = sub.add_parser("automatic")
    add_collection(p)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=13)
    p.set_defaults(fn=cmd_automatic)

    p = sub.add_parser("llm")
    add_collection(p)
    p.add_argument("--raw", required=True, help="jsonl: {qid, LLM_NaturalQuestion, LLM_Paraphrase, LLM_SynonymSwap}")
    p.add_argument("--out", required=True)
    p.add_argument("--strict", action="store_true", help="exit non-zero if anything is missing or identical")
    p.set_defaults(fn=cmd_llm)

    p = sub.add_parser("packet")
    p.add_argument("--automatic", required=True)
    p.add_argument("--llm", required=True)
    p.add_argument("--packet-dir", required=True, help="where the blind packet is written (keep it apart from the key)")
    p.add_argument("--key", required=True, help="private pair_id -> rewrite_id key (never shown to the reviewer)")
    p.add_argument("--calibration-typos", type=int, default=30)
    p.add_argument("--chunks", type=int, default=3)
    p.add_argument("--seed", type=int, default=13)
    p.set_defaults(fn=cmd_packet)

    p = sub.add_parser("recheck")
    p.add_argument("--automatic", required=True)
    p.add_argument("--manual", default=None, help="jsonl of manual objections: {rewrite_id, author_label, note}")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_recheck)

    p = sub.add_parser("merge")
    p.add_argument("--automatic", required=True)
    p.add_argument("--llm", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--reviews", nargs="+", required=True, help="reviewer label files: {pair_id, label, note}")
    p.add_argument("--author-recheck", default=None, help="output of the recheck step; a rewrite must pass both")
    p.add_argument("--reviewer-only-out", default=None, help="also write the variant that uses the blind reviewer alone")
    p.add_argument("--reviewer", default="blind LLM reviewer (Claude Haiku 5.5 agent)")
    p.add_argument("--out", required=True)
    p.add_argument("--summary", default=None)
    p.add_argument("--audit", default=None)
    p.add_argument("--audit-per-generator", type=int, default=15)
    p.add_argument("--seed", type=int, default=13)
    p.set_defaults(fn=cmd_merge)

    args = ap.parse_args(argv)
    if args.cmd == "merge":
        stem = Path(args.out).with_suffix("")
        args.summary = args.summary or f"{stem}_review_summary.json"
        args.audit = args.audit or f"{stem}_human_audit_sheet.csv"
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
