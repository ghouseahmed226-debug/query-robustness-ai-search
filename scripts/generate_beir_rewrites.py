#!/usr/bin/env python
"""Generate query rewrites for a BEIR dataset using an LLM (OpenAI-compatible API).

Produces a JSONL file with one line per judged query containing:
  {qid, LLM_NaturalQuestion, LLM_Paraphrase, LLM_SynonymSwap}

These are the three fields expected by  scripts/make_rewrites.py llm.
The automatic rewrites (typos, word-order swaps) need no LLM: run
  python scripts/make_rewrites.py automatic --dataset beir ...
for those.

The script calls the API in batches, retries on transient errors, and
writes a JSONL log of every prompt+response so the run is auditable.
All decoding settings are recorded in the output header and in the log.

Usage
-----
    # Set your API key
    export OPENAI_API_KEY=sk-...          # or use --api-key
    # or for a local model via Ollama / LM Studio:
    export OPENAI_BASE_URL=http://localhost:11434/v1

    python scripts/generate_beir_rewrites.py \\
        --data-dir data/raw/beir/scifact \\
        --model gpt-4o-mini \\
        --out data/rewrites/scifact_llm_raw.jsonl \\
        --log data/rewrites/scifact_llm_log.jsonl

Notes
-----
* Write the rewrite protocol (model, version, exact prompt, decoding
  settings, date) into docs/LLM_REWRITE_PROTOCOL.md before running.
  This script prints a draft entry for you to paste in.
* The --dry-run flag shows the first prompt without calling the API.
* Cost estimate is printed at the start (tokens are approximated as
  len(text)//4; actual billing may differ).
* The OpenAI package is optional; install with:  pip install openai
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from qvr.data import load_beir

# ── prompt template ───────────────────────────────────────────────────────────
# Produces all three variants in one call per query to save round-trips.
SYSTEM_PROMPT = """\
You are a search-query rewriting assistant for an information retrieval research study.
For each query I give you, produce exactly three rewritten versions that preserve the
original meaning.  Return ONLY a JSON object with these three keys:
  "LLM_NaturalQuestion"  - rephrase as a natural spoken question (how/what/why…)
  "LLM_Paraphrase"       - paraphrase using different words; same intent
  "LLM_SynonymSwap"      - replace content words with synonyms; keep the structure

Rules:
- Every rewrite must be answerable by the same set of documents as the original.
- Do NOT change the topic, scope, or specificity.
- Keep rewrites concise (under 30 words).
- Output ONLY the JSON object, no explanation, no markdown fences.\
"""

USER_TEMPLATE = 'Original query: "{query}"\n\nReturn the JSON object with the three rewrites.'


def build_prompt(query: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(query=query)},
    ]


def call_api(client, model: str, messages: list[dict], temperature: float,
             max_tokens: int, retries: int = 5) -> tuple[str, dict]:
    """Call the API and return (text_content, usage_dict). Retries on server errors."""
    delay = 2.0
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            } if resp.usage else {}
            return content, usage
        except Exception as exc:
            err = str(exc)
            if attempt == retries - 1:
                raise
            if any(code in err for code in ("429", "500", "502", "503", "504")):
                print(f"    transient error (attempt {attempt + 1}): {err[:80]}; retrying in {delay:.0f}s …",
                      file=sys.stderr)
                time.sleep(delay)
                delay = min(delay * 2, 60)
            else:
                raise


def parse_response(text: str, qid: str) -> dict | None:
    """Parse the JSON response; return None and print a warning on failure."""
    try:
        obj = json.loads(text)
        required = {"LLM_NaturalQuestion", "LLM_Paraphrase", "LLM_SynonymSwap"}
        missing = required - set(obj)
        if missing:
            print(f"  WARNING qid={qid}: missing keys {missing} in response", file=sys.stderr)
            return None
        return {k: str(obj[k]).strip() for k in required}
    except json.JSONDecodeError as exc:
        print(f"  WARNING qid={qid}: JSON parse error: {exc}\n    response: {text[:200]}", file=sys.stderr)
        return None


def estimate_cost(queries: dict, model: str) -> None:
    """Very rough cost estimate (not billing-accurate)."""
    sys_tokens = len(SYSTEM_PROMPT) // 4
    avg_query_tokens = sum(len(q) for q in queries.values()) // (4 * max(len(queries), 1))
    prompt_tokens = (sys_tokens + avg_query_tokens + 30) * len(queries)
    completion_tokens = 80 * len(queries)  # ~80 tokens per response
    print(f"  estimated tokens: ~{prompt_tokens:,} prompt + ~{completion_tokens:,} completion "
          f"for {len(queries)} queries")
    print(f"  (this is approximate; check your provider's billing page for the model '{model}')")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True,
                    help="BEIR dataset folder (corpus.jsonl, queries.jsonl, qrels/test.tsv)")
    ap.add_argument("--split", default="test")
    ap.add_argument("--model", default="gpt-4o-mini",
                    help="Model name recognised by the API (default: gpt-4o-mini)")
    ap.add_argument("--api-key", default=None,
                    help="API key (or set OPENAI_API_KEY env var)")
    ap.add_argument("--base-url", default=None,
                    help="Override API base URL (e.g. http://localhost:11434/v1 for Ollama)")
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--out", required=True,
                    help="Output JSONL: one line per query with qid + three rewrite fields")
    ap.add_argument("--log", default=None,
                    help="Audit log JSONL: every prompt + raw response (default: <out>.log.jsonl)")
    ap.add_argument("--resume", action="store_true",
                    help="Skip qids already present in --out (for resuming interrupted runs)")
    ap.add_argument("--max-queries", type=int, default=None,
                    help="Process only the first N queries (for testing)")
    ap.add_argument("--batch-delay", type=float, default=0.2,
                    help="Seconds to wait between API calls (default 0.2 — increase if rate-limited)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the first prompt and exit without calling the API")
    ap.add_argument("--retries", type=int, default=5)
    args = ap.parse_args(argv)

    # ── load collection ───────────────────────────────────────────────────────
    coll = load_beir(args.data_dir, args.split)
    judged = coll.judged_queries()
    if args.max_queries:
        judged = judged[:args.max_queries]
    queries = {q: coll.queries[q] for q in judged}

    # ── dry-run ───────────────────────────────────────────────────────────────
    if args.dry_run:
        sample_qid = next(iter(queries))
        sample_q = queries[sample_qid]
        msgs = build_prompt(sample_q)
        print(f"Dataset : {coll.name}  ({len(judged)} judged queries)")
        print(f"Model   : {args.model}  T={args.temperature}  max_tokens={args.max_tokens}")
        print(f"\n── sample prompt for qid={sample_qid} ──────────────────────────")
        for m in msgs:
            print(f"[{m['role']}]\n{m['content']}\n")
        return 0

    # ── import openai ─────────────────────────────────────────────────────────
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: the 'openai' package is not installed.  Run:  pip install openai", file=sys.stderr)
        return 1

    client_kwargs: dict = {}
    if args.api_key:
        client_kwargs["api_key"] = args.api_key
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    client = OpenAI(**client_kwargs)

    # ── paths ─────────────────────────────────────────────────────────────────
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = Path(args.log) if args.log else out_path.with_suffix(".log.jsonl")

    # ── resume support ────────────────────────────────────────────────────────
    already_done: set[str] = set()
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    already_done.add(json.loads(line)["qid"])
        print(f"Resuming: {len(already_done)} qids already in {out_path}")

    todo = {q: queries[q] for q in queries if q not in already_done}
    if not todo:
        print("All queries already processed.  Nothing to do.")
        return 0

    # ── run info ──────────────────────────────────────────────────────────────
    run_info = {
        "script": "generate_beir_rewrites.py",
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
        "dataset": coll.name,
        "split": args.split,
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "base_url": args.base_url or "(default OpenAI)",
        "n_queries_total": len(queries),
        "n_queries_todo": len(todo),
        "system_prompt": SYSTEM_PROMPT,
        "user_template": USER_TEMPLATE,
    }

    print("\n── generate_beir_rewrites ────────────────────────────────────────")
    print(f"  dataset  : {coll.name}  ({len(coll.doc_ids):,} docs, {len(judged)} judged queries)")
    print(f"  model    : {args.model}  T={args.temperature}  max_tokens={args.max_tokens}")
    print(f"  queries  : {len(todo)} to process  ({len(already_done)} already done)")
    estimate_cost(todo, args.model)
    print(f"  output   : {out_path}")
    print(f"  log      : {log_path}")
    print()
    print("IMPORTANT: Before you continue, make sure you have written the rewrite")
    print("protocol into docs/LLM_REWRITE_PROTOCOL.md and committed it.")
    print()

    # ── draft protocol note ───────────────────────────────────────────────────
    print("── draft protocol entry (paste into docs/LLM_REWRITE_PROTOCOL.md) ──")
    print(f"""
## BEIR rewrite run: {coll.name} ({datetime.now().strftime('%Y-%m-%d')})

- Model: {args.model}
- Temperature: {args.temperature}
- max_tokens: {args.max_tokens}
- Base URL: {args.base_url or 'OpenAI default'}
- Dataset: {coll.name}, split={args.split}
- Prompt: see system_prompt in {log_path}
- Output: {out_path}
- Log: {log_path}
- Queries processed: {len(todo)} of {len(queries)} judged queries

[Add: model version / API snapshot date, any manual changes made after generation]
""")

    # ── main loop ─────────────────────────────────────────────────────────────
    n_ok = 0
    n_fail = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    with open(out_path, "a", encoding="utf-8") as out_f, \
         open(log_path, "a", encoding="utf-8") as log_f:

        # write run header to log
        log_f.write(json.dumps({"__run_info__": run_info}) + "\n")

        for i, (qid, query) in enumerate(todo.items(), 1):
            messages = build_prompt(query)
            print(f"  [{i:4d}/{len(todo)}] qid={qid:12s}  {query[:60]}", end=" … ", flush=True)

            try:
                raw_text, usage = call_api(
                    client, args.model, messages,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    retries=args.retries,
                )
                total_prompt_tokens += usage.get("prompt_tokens", 0)
                total_completion_tokens += usage.get("completion_tokens", 0)
            except Exception as exc:
                print(f"FAILED: {exc}", file=sys.stderr)
                log_f.write(json.dumps({"qid": qid, "query": query,
                                        "error": str(exc), "status": "api_error"}) + "\n")
                n_fail += 1
                continue

            parsed = parse_response(raw_text, qid)

            # write to log regardless of parse success (for auditing)
            log_f.write(json.dumps({
                "qid": qid, "query": query,
                "messages": messages, "raw_response": raw_text,
                "parsed": parsed, "usage": usage,
                "status": "ok" if parsed else "parse_error",
            }) + "\n")

            if parsed is None:
                print("parse error")
                n_fail += 1
                continue

            row = {"qid": qid, **parsed}
            out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print("ok")
            n_ok += 1

            if args.batch_delay and i < len(todo):
                time.sleep(args.batch_delay)

    # ── summary ───────────────────────────────────────────────────────────────
    print(f"\n── done ──────────────────────────────────────────────────────────")
    print(f"  ok:        {n_ok}")
    print(f"  failed:    {n_fail}")
    print(f"  tokens:    ~{total_prompt_tokens:,} prompt + ~{total_completion_tokens:,} completion")
    print(f"  output:    {out_path}")
    print(f"  log:       {log_path}")
    print()
    print("Next step:  python scripts/make_rewrites.py llm \\")
    print(f"    --dataset beir --data-dir {args.data_dir} \\")
    print(f"    --raw {out_path} \\")
    print(f"    --out {out_path.parent / (coll.name + '_llm_candidates.jsonl')} --strict")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
