#!/usr/bin/env python
"""End-to-end BEIR experiment runner.

Orchestrates the full pipeline for one or more BEIR datasets:
  1. Download the dataset  (fetch_beir.py)
  2. Generate automatic rewrites  (make_rewrites.py automatic)
  3. Generate LLM rewrites via OpenAI-compatible API  (generate_beir_rewrites.py)
  4. Build candidate rewrite files  (make_rewrites.py llm)
  5. Build review packet for human annotation (make_rewrites.py packet)
  6. <<< PAUSE: human annotators fill in labels >>>
  7. Merge reviews into the final rewrite file  (make_rewrites.py merge)
  8. Run the retrieval experiment  (run_experiment.py)
  9. Analyse and summarise  (analyze.py)

Steps can be run individually using --steps, or the whole pipeline at once.
The pipeline always pauses before step 7 (merge) unless --skip-human-review
is passed (which means results use llm_reviewed status, not human_verified).

Usage examples
--------------
  # Full pipeline for SciFact + NFCorpus with a neural model
  python scripts/run_beir_pipeline.py \\
      --datasets scifact nfcorpus \\
      --model sentence-transformers/all-MiniLM-L6-v2 \\
      --llm-model gpt-4o-mini

  # Only download + automatic rewrites (no LLM key needed)
  python scripts/run_beir_pipeline.py \\
      --datasets scifact \\
      --steps download auto-rewrites \\
      --llm-model none

  # Skip download (data already there), run everything through analysis
  python scripts/run_beir_pipeline.py \\
      --datasets scifact \\
      --data-root data/raw/beir \\
      --steps auto-rewrites llm-rewrites candidate-file packet experiment analysis \\
      --model sentence-transformers/all-MiniLM-L6-v2 \\
      --llm-model gpt-4o-mini \\
      --skip-human-review

IMPORTANT
---------
Before running this script, add a dated section to docs/ANALYSIS_PLAN.md
describing: the datasets, the retrieval model name and revision, the rewrite
model, the allowed review statuses, and any deviations from sections 1-6.
Commit that plan before running.  The run_experiment step hashes the plan
file into run_metadata.json.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

VALID_STEPS = [
    "download",
    "auto-rewrites",
    "llm-rewrites",
    "candidate-file",
    "packet",
    "merge",
    "experiment",
    "analysis",
]

# Best models for each use-case (model name, query prefix, doc prefix)
RECOMMENDED_MODELS = {
    "all-minilm":  ("sentence-transformers/all-MiniLM-L6-v2", "", ""),
    "e5-small":    ("intfloat/e5-small-v2", "query: ", "passage: "),
    "e5-base":     ("intfloat/e5-base-v2", "query: ", "passage: "),
    "bge-small":   ("BAAI/bge-small-en-v1.5", "Represent this sentence: ", ""),
    "bge-base":    ("BAAI/bge-base-en-v1.5", "Represent this sentence: ", ""),
}


def run(cmd: list[str], label: str, check: bool = True) -> int:
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    print(f"{'='*70}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if check and result.returncode != 0:
        print(f"\nERROR: step '{label}' failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
    return result.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    # dataset selection
    ap.add_argument("--datasets", nargs="+",
                    choices=["scifact", "nfcorpus", "trec-covid", "fiqa", "arguana",
                             "webis-touche2020", "hotpotqa"],
                    default=["scifact", "nfcorpus"],
                    help="BEIR datasets to process (default: scifact nfcorpus)")
    ap.add_argument("--data-root", default="data/raw/beir",
                    help="Root directory for BEIR data (default: data/raw/beir)")

    # model selection
    ap.add_argument("--model",
                    default="sentence-transformers/all-MiniLM-L6-v2",
                    help="sentence-transformers model for dense retrieval. "
                         f"Shortcuts: {', '.join(RECOMMENDED_MODELS)}. "
                         "Default: all-MiniLM-L6-v2")
    ap.add_argument("--query-prefix", default=None,
                    help="Query prefix for the dense model (auto-set for known shortcuts)")
    ap.add_argument("--doc-prefix", default=None,
                    help="Document prefix for the dense model (auto-set for known shortcuts)")
    ap.add_argument("--batch-size", type=int, default=32)

    # LLM rewrite model
    ap.add_argument("--llm-model", default="gpt-4o-mini",
                    help="LLM model for rewrite generation (or 'none' to skip LLM rewrites)")
    ap.add_argument("--llm-base-url", default=None,
                    help="Override API base URL (e.g. http://localhost:11434/v1)")
    ap.add_argument("--llm-temperature", type=float, default=0.3)

    # pipeline control
    ap.add_argument("--steps", nargs="+", choices=VALID_STEPS, default=None,
                    help=f"Steps to run (default: all). Choices: {', '.join(VALID_STEPS)}")
    ap.add_argument("--skip-human-review", action="store_true",
                    help="Skip the human annotation pause; use llm_reviewed status (weaker evidence)")
    ap.add_argument("--systems", nargs="+",
                    default=["bm25", "dense", "rrf_bm25_dense"],
                    help="Retrieval systems (default: bm25 dense rrf_bm25_dense)")
    ap.add_argument("--top-k", type=int, default=100)
    ap.add_argument("--split", default="test")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--out-root", default="results/beir",
                    help="Root directory for results (default: results/beir)")

    args = ap.parse_args(argv)

    steps = set(args.steps if args.steps else VALID_STEPS)

    # resolve model shortcut
    model = args.model
    q_prefix = args.query_prefix or ""
    d_prefix = args.doc_prefix or ""
    if model in RECOMMENDED_MODELS:
        model, q_prefix, d_prefix = RECOMMENDED_MODELS[model]
        if args.query_prefix:
            q_prefix = args.query_prefix
        if args.doc_prefix:
            d_prefix = args.doc_prefix

    allowed_statuses = (["automatic_by_construction", "llm_reviewed"]
                        if args.skip_human_review else ["automatic_by_construction", "human_verified"])

    data_root = Path(args.data_root)
    out_root = Path(args.out_root)

    print("\n" + "="*70)
    print("  BEIR PIPELINE")
    print(f"  datasets : {', '.join(args.datasets)}")
    print(f"  model    : {model}")
    if q_prefix:
        print(f"  q-prefix : {q_prefix!r}")
    if d_prefix:
        print(f"  d-prefix : {d_prefix!r}")
    print(f"  llm      : {args.llm_model}")
    print(f"  steps    : {', '.join(s for s in VALID_STEPS if s in steps)}")
    print(f"  status   : {'llm_reviewed (no human check)' if args.skip_human_review else 'human_verified (will pause for annotation)'}")
    print("="*70)

    if not args.skip_human_review and "merge" in steps:
        print("\nNOTE: The pipeline will pause before 'merge' so you can run human annotation.")
        print("      Annotators should receive the blind packet (never the key).")
        print("      Use scripts/audit_tool.py once labels are collected.\n")

    for dataset in args.datasets:
        data_dir = data_root / dataset
        rewrite_dir = ROOT / "data" / "rewrites" / dataset
        rewrite_dir.mkdir(parents=True, exist_ok=True)
        result_dir = out_root / dataset
        result_dir.mkdir(parents=True, exist_ok=True)
        packet_dir = rewrite_dir / "review_packets"

        auto_out       = rewrite_dir / f"{dataset}_automatic.jsonl"
        llm_raw_out    = rewrite_dir / f"{dataset}_llm_raw.jsonl"
        llm_cand_out   = rewrite_dir / f"{dataset}_llm_candidates.jsonl"
        recheck_out    = rewrite_dir / f"{dataset}_author_recheck.jsonl"
        key_out        = rewrite_dir / f"{dataset}_review_key.jsonl"
        final_rewrites = rewrite_dir / f"{dataset}_rewrites.jsonl"

        print(f"\n{'#'*70}")
        print(f"#  Dataset: {dataset.upper()}")
        print(f"{'#'*70}")

        # ── 1. Download ───────────────────────────────────────────────────────
        if "download" in steps:
            run([sys.executable, str(SCRIPTS / "fetch_beir.py"),
                 dataset, "--out", str(data_root)],
                f"Download {dataset}")

        # ── 2. Automatic rewrites ─────────────────────────────────────────────
        if "auto-rewrites" in steps:
            run([sys.executable, str(SCRIPTS / "make_rewrites.py"),
                 "automatic",
                 "--dataset", "beir",
                 "--data-dir", str(data_dir),
                 "--split", args.split,
                 "--out", str(auto_out),
                 "--seed", str(args.seed)],
                f"Automatic rewrites: {dataset}")

        # ── 3. LLM rewrites ───────────────────────────────────────────────────
        if "llm-rewrites" in steps and args.llm_model.lower() != "none":
            llm_cmd = [sys.executable, str(SCRIPTS / "generate_beir_rewrites.py"),
                       "--data-dir", str(data_dir),
                       "--split", args.split,
                       "--model", args.llm_model,
                       "--temperature", str(args.llm_temperature),
                       "--out", str(llm_raw_out),
                       "--resume"]
            if args.llm_base_url:
                llm_cmd += ["--base-url", args.llm_base_url]
            run(llm_cmd, f"LLM rewrites: {dataset}")
        elif "llm-rewrites" in steps:
            print(f"\n  [SKIP] llm-rewrites for {dataset}: --llm-model=none")

        # ── 4. Build candidate file ───────────────────────────────────────────
        if "candidate-file" in steps and args.llm_model.lower() != "none" and llm_raw_out.exists():
            run([sys.executable, str(SCRIPTS / "make_rewrites.py"),
                 "llm",
                 "--dataset", "beir",
                 "--data-dir", str(data_dir),
                 "--split", args.split,
                 "--raw", str(llm_raw_out),
                 "--out", str(llm_cand_out)],
                f"Build LLM candidate file: {dataset}")

        # ── 5. Review packet ──────────────────────────────────────────────────
        if "packet" in steps and auto_out.exists() and llm_cand_out.exists():
            run([sys.executable, str(SCRIPTS / "make_rewrites.py"),
                 "packet",
                 "--automatic", str(auto_out),
                 "--llm", str(llm_cand_out),
                 "--packet-dir", str(packet_dir),
                 "--key", str(key_out),
                 "--seed", str(args.seed)],
                f"Build review packet: {dataset}")

            if not args.skip_human_review:
                print("\n" + "!"*70)
                print(f"  PAUSE: Human annotation needed for {dataset}")
                print(f"  Give annotators ONLY the files in: {packet_dir}")
                print(f"  Do NOT share the key: {key_out}")
                print(f"  When done, re-run with --steps merge experiment analysis")
                print("!"*70)
                print("\n  (use --skip-human-review to proceed with llm_reviewed status instead)")
                if len(args.datasets) > 1:
                    print(f"  Continuing to next dataset …")
                continue

        # ── 6. Author recheck (word-order) ────────────────────────────────────
        if auto_out.exists() and not recheck_out.exists():
            run([sys.executable, str(SCRIPTS / "make_rewrites.py"),
                 "recheck",
                 "--automatic", str(auto_out),
                 "--out", str(recheck_out)],
                f"Author recheck: {dataset}", check=False)

        # ── 7. Merge ──────────────────────────────────────────────────────────
        if "merge" in steps:
            label_files = sorted(packet_dir.glob("labels_*.jsonl")) if packet_dir.exists() else []
            if not label_files and not args.skip_human_review:
                print(f"\n  [SKIP] merge for {dataset}: no label files found in {packet_dir}")
                print(f"         Run annotation first, then re-run with --steps merge experiment analysis")
                continue
            if not label_files and args.skip_human_review:
                # use auto only
                merge_cmd = [sys.executable, str(SCRIPTS / "make_rewrites.py"),
                             "merge",
                             "--automatic", str(auto_out),
                             "--llm", str(llm_cand_out) if llm_cand_out.exists() else str(auto_out),
                             "--key", str(key_out) if key_out.exists() else str(auto_out),
                             "--reviews", str(auto_out),   # dummy — no review labels
                             "--out", str(final_rewrites)]
            else:
                merge_cmd = [sys.executable, str(SCRIPTS / "make_rewrites.py"),
                             "merge",
                             "--automatic", str(auto_out),
                             "--llm", str(llm_cand_out),
                             "--key", str(key_out),
                             "--reviews"] + [str(f) for f in label_files] + [
                             "--author-recheck", str(recheck_out),
                             "--out", str(final_rewrites)]
            if not final_rewrites.exists() or "merge" in steps:
                run(merge_cmd, f"Merge reviews: {dataset}", check=False)

        # ── 8. Experiment ─────────────────────────────────────────────────────
        if "experiment" in steps and (final_rewrites.exists() or auto_out.exists()):
            rewrites = final_rewrites if final_rewrites.exists() else auto_out
            exp_cmd = [sys.executable, str(SCRIPTS / "run_experiment.py"),
                       "--dataset", "beir",
                       "--data-dir", str(data_dir),
                       "--split", args.split,
                       "--rewrites", str(rewrites),
                       "--allowed-statuses"] + allowed_statuses + [
                       "--systems"] + args.systems + [
                       "--dense-model", model,
                       "--dense-batch-size", str(args.batch_size),
                       "--top-k", str(args.top_k),
                       "--out", str(result_dir)]
            if q_prefix:
                exp_cmd += ["--dense-query-prefix", q_prefix]
            if d_prefix:
                exp_cmd += ["--dense-doc-prefix", d_prefix]
            # ArguAna/Quora need --ignore-identical-ids
            if dataset in ("arguana", "quora"):
                exp_cmd.append("--ignore-identical-ids")
            run(exp_cmd, f"Experiment: {dataset}")

        # ── 9. Analysis ───────────────────────────────────────────────────────
        if "analysis" in steps and result_dir.exists():
            run([sys.executable, str(SCRIPTS / "analyze.py"),
                 "--run-dir", str(result_dir)],
                f"Analyse: {dataset}")

    print("\n" + "="*70)
    print("  PIPELINE COMPLETE")
    print(f"  Results are in: {out_root}")
    print("="*70)
    print()
    print("Next steps:")
    print("  1. Read results/<dataset>/analysis/summary.md for each dataset")
    print("  2. Compare BM25 nDCG@10 on original queries to published BEIR numbers")
    print("     (a big mismatch = data/tokenisation problem, not a finding)")
    print("  3. If you used --skip-human-review, plan the human annotation now")
    print("  4. Update docs/ANALYSIS_PLAN.md with actual counts and deviations")
    print("  5. Commit results and run: python scripts/compare_runs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
