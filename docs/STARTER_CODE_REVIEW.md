# Review of the original starter code (`legacy/run_experiment_original.py`)

The starter script was kept unchanged in `legacy/`. It is a BM25-only scaffold built on BEIR's Elasticsearch wrapper.
It was **not** run: the sandbox has no Elasticsearch and cannot reach BEIR's dataset server. The BEIR statements below
come from reading the source of `beir==2.2.0` (downloaded from PyPI, not executed); line numbers refer to that file
version. The kit's `requirements.txt` asks for `beir>=2.0.0`, so other versions may differ.

## Defects that would have changed or blocked results

| # | where | problem | consequence |
|---|---|---|---|
| 1 | starter l.12, l.82 | `BM25Search(..., hostname="localhost", initialize=True)` needs a running Elasticsearch server | cannot run without one; BM25 is Elasticsearch's, not an inspectable reference |
| 2 | starter l.105-109; BEIR `bm25_search.py` l.64-67 | each rewrite is retrieved with `retriever.retrieve(corpus, {qid: rewrite})` and `initialize=True`, so `search()` re-indexes the whole corpus (plus a 2 s sleep) on every call | hours of indexing for a few hundred rewrites |
| 3 | BEIR `bm25_search.py` l.31, l.85-87; starter l.84-85, l.108-110 | `BM25Search.results` is one dict that is updated and returned by every call; `base_results` is that same object | the original-query rankings are overwritten by rewrite rankings as the loop runs, so the "original" summary written at the end (l.119) is computed on a mixture; each per-rewrite score (l.110) is a mean over **all** queries in the dict, not over the rewrite |
| 4 | BEIR `bm25_search.py` l.80-85 | `self.results[query_id] = scores` sits inside the loop over hits | a rewrite that returns no hit at all (for example a typo that matches nothing) does not overwrite the old entry, so the stale original ranking would be scored as if it were the rewrite's: misspellings would look harmless exactly when they hurt most. (A query with no hit at all is also absent from the results, and `pytrec_eval`, like `trec_eval` without `-c`, scores only queries that are in the run, so such a query is left out of the mean instead of scoring 0.) |
| 5 | starter l.110, l.115, l.125; BEIR `evaluation.py` l.69-122 | `EvaluateRetrieval.evaluate` returns `(ndcg, map, recall, precision)`; the starter names the fourth value `mrr` and reads the key `"MRR@10"`, which does not exist (the key is `"P@10"`) | MRR@10 is silently NaN/None in every output; real MRR needs `evaluate_custom(..., metric="mrr")` |
| 6 | starter l.42 | `--methods` accepts only `bm25`; there is no dense or hybrid code | RQ2 (sparse vs dense vs hybrid) cannot be answered |
| 7 | starter l.58-61 | queries are the first `--max-queries` (default 100) of the *string-sorted* ids that have qrels | a silent, non-random truncation that depends on id formatting |
| 8 | BEIR `evaluation.py` l.69-79 | `ignore_identical_ids=True` is the default: documents whose id equals the query id are dropped from evaluation | harmless for most BEIR sets, but silent; it matters for ArguAna and Quora |
| 9 | starter l.64-77, l.119-134 | only per-rewrite rows and one original summary are written: no per-query original table, no changes relative to the original, no stability measure, no intervals, no tests; nothing records package versions | the analysis the manuscript describes does not exist in the code |
| 10 | README | says the script "defaults to original queries and deterministic lexical rewrites only", but no rewrite generation exists in the script: without `--rewrite-file` there are no rewrites at all (l.16-19) | the README promises a feature that is not there |
| 11 | `requirements.txt` | `rank-bm25`, `ir-measures`, `scipy` and `tqdm` are never imported by the script | misleading dependency list |

Items 3-5 interact: the starter would have produced plausible-looking numbers that are wrong in a direction that
flatters robustness, with no error message.

## What was kept from the kit

* The rewrite-file schema (`qid, rewrite_id, category, query, meaning_preserved, review_status`) and the rule that only
  `human_verified` rewrites are accepted **by default** (`scripts/run_experiment.py` keeps that default; weaker statuses
  must be requested with `--allowed-statuses` and are written into `run_metadata.json`).
* The kit's stance: no invented results, no invented citations, no single LLM judge as ground truth.

## What replaced the starter

`src/qvr/` (package, 85 tests): own sparse BM25 (checked against `bm25s`), exact dense search over pluggable encoders
(non-neural LSA here, sentence-transformers optional), RRF fusion, nDCG@10 / Recall@100 / MRR@10 (checked against
`pytrec_eval` and `ranx`), overlap@10 and RBO (checked against the `rbo` package), cluster bootstrap, sign-flip
permutation tests and Holm correction. One index per system is built once; every query and rewrite is a fresh,
independent search, and each ranking is saved. A bug-injection check (`tests/mutation/run_mutants.py`, log in `tests/mutation/mutation_check_log.txt`, re-run on
2026-10-21) made 23 deliberate one-line breakages across the metric, BM25, stability, fusion, ranking, statistics,
analysis, run and rewrite-loading code; the tests caught 22. The survivor (`M01b`) is an equivalent mutant: the base
of nDCG's logarithm cancels in nDCG/IDCG, so changing it cannot change any result.
