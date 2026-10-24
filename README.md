# Query-variation robustness of first-stage retrieval
### A reproducible pilot study on the Vaswani/NPL collection

[![CI](https://github.com/ghouseahmed226-debug/query-robustness-ai-search/actions/workflows/ci.yml/badge.svg)](https://github.com/ghouseahmed226-debug/query-robustness-ai-search/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-preprint-b31b1b)](https://github.com/ghouseahmed226-debug/query-robustness-ai-search)

> **Status: pilot study — not yet peer-reviewed.**
> This is a fully reproducible pilot. No human has yet validated the rewrites, and there is no neural retriever.
> A human author must read, verify and accept responsibility for anything submitted.
> See [`PUBLICATION_PLAN.md`](PUBLICATION_PLAN.md).

---

## What it does

Measures how three first-stage retrieval systems respond when the same information need is worded differently:

| Component | Detail |
|:--|:--|
| **Systems** | BM25 · LSA (TF-IDF + 300-d SVD) · RRF hybrid |
| **Collection** | Vaswani/NPL — 11,429 abstracts · 93 queries · 2,083 binary judgments |
| **Rewrite types** | Misspelling · Paraphrasing · Naturality · Word order (Penha et al., ECIR 2022) |
| **Rewrites kept** | 644 (from a larger candidate set, after automated review) |
| **Metrics** | nDCG@10 (primary) · Recall@100 · MRR@10 · top-10 overlap · RBO |
| **Statistics** | Paired cluster-bootstrap · sign-flip permutation · Holm correction (12 pre-specified tests) |

---

## Results at a glance

Relative change in **nDCG@10** vs. original query:

| System | nDCG@10 (original) | Misspelling | Paraphrasing | Naturality | Word order |
|:--|--:|--:|--:|--:|--:|
| **BM25** | **0.432** | −18.5% *** | −13.3% ** | −1.9% | 0.0% |
| LSA | 0.282 | −21.4% *** | −5.3% | −0.4% | 0.0% |
| RRF hybrid | 0.382 | −20.2% *** | −7.8% | +0.5% | 0.0% |

`***` p < 0.001 · `**` p < 0.01 after Holm correction across 12 tests.

**Key finding:** Misspellings cause large, statistically reliable drops across all systems.
Paraphrasing significantly hurts BM25 but not LSA or the hybrid after correction.
Word order is exactly zero by construction (these systems are bag-of-words).

> **Do not generalise** these results to neural dense retrievers, other collections or real user queries. See limitations in the manuscript.

---

## Reproduce

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[plots,test]"

# 2. Download data (check the collection's terms of use first)
python scripts/fetch_vaswani.py

# 3. Tests (85 tests; one skipped until collection is downloaded)
pytest

# 4. Run experiment
python scripts/run_experiment.py \
    --dataset vaswani --data-dir data/raw/vaswani \
    --rewrites data/rewrites/vaswani_rewrites.jsonl \
    --allowed-statuses automatic_by_construction llm_reviewed \
    --systems bm25 lsa rrf_bm25_lsa --out results/vaswani_rerun

# 5. Analyse
python scripts/analyze.py --run-dir results/vaswani_rerun

# 6. Verify it matches the shipped run
python scripts/compare_runs.py --reference results/vaswani_pilot --candidate results/vaswani_rerun
python scripts/verify_results.py

# 7. Build PDF manuscript (needs pandoc + pdflatex)
bash scripts/build_pdf.sh
```

The experiment runs in ~10 seconds on a single CPU.
Saved environment: Python 3.13.16, numpy 2.5.4, scipy 1.18.1, pandas 3.0.5, scikit-learn 1.9.1.
A reproduction in a clean virtual environment gave identical per-query tables and document order; LSA scores differed only in the 7th decimal.

---

## Repository map

| Path | Contents |
|:--|:--|
| `paper/manuscript_draft.pdf` | The manuscript PDF |
| `paper/arxiv_source/` | Self-contained LaTeX source for arXiv upload |
| `paper/literature_verification_log.md` | What was/wasn't read for each reference |
| `docs/ANALYSIS_PLAN.md` | Pre-registered analysis plan + amendments |
| `docs/LLM_REWRITE_PROTOCOL.md` | Rewrite generation & review protocol |
| `docs/RUN_BEIR_LOCALLY.md` | Guide to run the neural/BEIR experiments (next step) |
| `src/qvr/` | Package: BM25, LSA, RRF, metrics, statistics, audit tools |
| `scripts/` | All experiment, analysis and build scripts |
| `tests/` | 85 automated tests incl. cross-checks vs `pytrec_eval`, `ranx`, `bm25s`, `rbo` |
| `data/rewrites/` | All rewrites, review records, and human-audit blind sheet |
| `results/vaswani_pilot/` | Shipped run: per-query tables, rankings, summary, metadata |
| `results/verification_report.md` | Independent recomputation output |
| `legacy/` | Original starter script and kit, unchanged |

---

## What's still to do (contributions welcome)

1. **Human rewrite validation** — `data/rewrites/audit/vaswani_audit_blind.csv` is ready for two annotators. Use `scripts/audit_tool.py score` and `apply`. Report Cohen's κ.
2. **Neural dense retriever + BEIR datasets** — `docs/RUN_BEIR_LOCALLY.md` has the guide. This is the single biggest upgrade.
3. **Systematic literature search** — the current search was not systematic (Appendix A of manuscript).
4. **Citation verification** — `paper/literature_verification_log.md` flags references seen only through abstracts.

---

## Before submitting anywhere

- arXiv: AI tools may not be listed as authors. The author takes full responsibility. Self-submit only. Requires personal endorsement for first-time submitters (since Jan 2026).
- SIGIR 2027: abstract due ~14 Jan 2027, full paper ~21 Jan 2027, 9 pages, double-anonymous, author list locked at abstract deadline.
- See [`PUBLICATION_PLAN.md`](PUBLICATION_PLAN.md) for the full checklist and links.

---

## Known issues

- Spearman correlations reproduce only to ~1e-4 across implementations (ties broken by floating-point noise; no effect at 2 d.p.).
- Vaswani/NPL collection provenance and licence are unclear; the Glasgow page carries a caution.
- Rewrites cannot be regenerated (no separate prompt or seed recorded); they are stored verbatim.

---

## Cite this work

```bibtex
@software{ahmed2026qvr,
  author  = {Ahmed, Ghouse},
  title   = {Query-variation robustness of first-stage retrieval: a reproducible pilot},
  year    = {2026},
  url     = {https://github.com/ghouseahmed226-debug/query-robustness-ai-search},
  version = {0.1.0-pilot}
}
```

See [`CITATION.cff`](CITATION.cff) for full metadata. Add your ORCID and affiliation before publishing.

## Licence

Code: [MIT](LICENSE).
Data: The Vaswani/NPL collection is not included; check its terms before use.
