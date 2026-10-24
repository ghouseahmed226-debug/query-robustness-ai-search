# Running the neural and BEIR experiments on your own machine

What was **not** possible in the cloud sandbox used for the pilot: downloading BEIR datasets and model weights
(the shell can only reach package registries and GitHub). The code for those runs is written and unit-tested with a
stub encoder, but **no neural model and no BEIR dataset has been run**. Anything in the manuscript about them is
therefore a plan, not a result.

## 0. Decide and write down the design first

Edit `docs/ANALYSIS_PLAN.md` (add a dated section 10) **before running**, and commit it. At minimum fix: the datasets,
the exact model name and revision, the query/document prefixes, the rewrite file, the allowed review statuses, and
whether anything differs from sections 1-6. The run records the SHA-256 of the plan file in `run_metadata.json`.
Choosing the model after seeing results, or trying several and reporting one, is the main way a study like this goes wrong.

## 1. Environment

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dense,plots,test]"
pytest                                                    # 85 tests; takes a few seconds
```

`sentence-transformers` pulls in PyTorch. A GPU is optional for small collections (SciFact, NFCorpus) but encoding the
corpus is much faster with one.

## 2. Data

Download the BEIR datasets you chose and unzip them so that each folder contains `corpus.jsonl`, `queries.jsonl` and
`qrels/test.tsv`. The original kit's script downloaded from
`https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/<name>.zip`; that address was not reachable from the
sandbox, so it is untested here. The BEIR repository README lists the current links. Check the counts printed in
`run_metadata.json` against the dataset table in the BEIR paper (Thakur et al., 2021) and check each dataset's licence
before redistributing anything derived from it.

For the Vaswani pilot, `python scripts/fetch_vaswani.py` downloads and verifies the three files.

## 3. Rewrites for a new dataset

```bash
# typos, word-order swaps, stop-word removal (seeded, no model needed)
python scripts/make_rewrites.py automatic --dataset beir --data-dir /path/to/scifact --split test \
    --out data/rewrites/scifact_automatic.jsonl
```

For the three LLM-written categories, produce one JSON line per judged query,
`{"qid": "...", "LLM_NaturalQuestion": "...", "LLM_Paraphrase": "...", "LLM_SynonymSwap": "..."}`, with the generator you
chose. Record the model name and version, the exact prompt and the decoding settings in a new file next to this one,
because the pilot could not (see `docs/LLM_REWRITE_PROTOCOL.md`). Then

```bash
python scripts/make_rewrites.py llm --dataset beir --data-dir /path/to/scifact --raw scifact_llm_raw.jsonl \
    --out data/rewrites/scifact_llm_candidates.jsonl --strict
```

**Validity.** For anything you want to call validated, have humans label the rewrites rather than an LLM:
`scripts/audit_tool.py blind --all` writes a blind sheet of every candidate, annotators fill `human_label`, and
`scripts/audit_tool.py apply --annotator "Name"` turns the labelled rows into `human_verified` records. Use more than one
annotator on at least a subset and report their agreement (`audit_tool.py score` gives kappa against the LLM reviewer; for
two humans use `qvr.audit.cohen_kappa`). If you use an LLM reviewer instead (`make_rewrites.py packet` / `merge`),
the results are `llm_reviewed` and must be reported that way.

## 4. Run

```bash
python scripts/run_experiment.py --dataset beir --data-dir /path/to/scifact --split test \
    --rewrites data/rewrites/scifact_rewrites_human.jsonl --allowed-statuses human_verified \
    --systems bm25 dense rrf_bm25_dense \
    --dense-model sentence-transformers/all-MiniLM-L6-v2 \
    --out results/scifact
python scripts/analyze.py --run-dir results/scifact
```

* Add `--dense-query-prefix`/`--dense-doc-prefix` only if the model requires them (E5 models expect `"query: "` and
  `"passage: "`); the code never guesses.
* `--ignore-identical-ids` is for ArguAna and Quora only (BEIR convention).
* Use a local folder for `--dense-model` if the machine is offline; the path is recorded in the run metadata.
* Every ranking is saved under `results/<run>/rankings/`, so metrics can be recomputed without re-encoding.
* `python scripts/run_experiment.py --help` lists every option.

## 5. What to check before believing the numbers

1. `pytest` passes on the machine that ran the experiment.
2. `run_metadata.json`: counts of documents, queries, judgments and rewrites per category are what you expect, the
   rewrite statuses are what you intended, and no query is missing.
3. nDCG@10 of BM25 on the original queries is in the range other BM25 implementations report for that dataset
   (a gross mismatch means a data or tokenisation problem, not a finding).
4. A category with few rewrites (as with word order in the pilot, n = 8) is reported as inconclusive, not as "no effect".
5. Report every dataset separately, with the intervals, whatever the outcome.

## 6. Sending results back

The files worth keeping are `results/<run>/run_metadata.json`, `per_query_original.csv`, `per_query_rewrites.csv`,
`rewrites_used.jsonl`, `analysis/` and (small enough to commit) `rankings/*.jsonl.gz`.
