# Query-variation robustness of first-stage retrieval: a reproducible pilot (Vaswani)

> **Read this first.**
> This repository is a **pilot study, not a finished or reviewed paper.** The code, the query rewrites, the experiments,
> the analysis and the manuscript were produced by an AI system (Claude) in one working session. No human has yet read,
> verified or approved them. A human must be the accountable author of anything that is submitted, and must make the
> arXiv submission themselves (see "Before anything is submitted" below).
> The pilot has **no neural retriever**, uses **one small old collection**, and **no rewrite is human-verified**.

## What it does

It measures how three first-stage retrieval systems react when the same search request is worded differently:

* three systems: **BM25**; a **non-neural** latent-semantic retriever (**LSA**: TF-IDF followed by a 300-dimensional truncated SVD);
  and the **reciprocal-rank-fusion (RRF) hybrid** of the two;
* on the **Vaswani/NPL** collection ({{m:collection/n_docs|int}} abstracts, {{m:collection/n_queries|int}} queries, {{m:collection/n_qrels_pairs|int}} binary judgments);
* under the four meaning-preserving categories of Penha et al. (ECIR 2022): misspelling, paraphrasing, naturality, word order,
  with {{m:counts/rewrites_kept|int}} kept rewrites;
* with nDCG@10 (primary), Recall@100, MRR@10, top-10 overlap and rank-biased overlap, paired cluster-bootstrap intervals,
  sign-flip permutation tests and Holm correction over 12 pre-specified tests.

## Results at a glance

Relative change in nDCG@10 versus the original query (95% intervals and all other numbers are in the manuscript):

| System | nDCG@10 on original queries | Misspelling | Paraphrasing | Naturality | Word order |
|:--|--:|--:|--:|--:|--:|
| BM25 | {{b:bm25/ndcg@10|f3}} | {{p:bm25/misspelling/ndcg@10_rel|pct1}} | {{p:bm25/paraphrasing/ndcg@10_rel|pct1}} | {{p:bm25/naturality/ndcg@10_rel|pct1}} | {{p:bm25/ordering/ndcg@10_rel|pct1}} (n = {{p:bm25/ordering/n_rewrites|int}}, zero by construction) |
| LSA (non-neural) | {{b:lsa/ndcg@10|f3}} | {{p:lsa/misspelling/ndcg@10_rel|pct1}} | {{p:lsa/paraphrasing/ndcg@10_rel|pct1}} | {{p:lsa/naturality/ndcg@10_rel|pct1}} | {{p:lsa/ordering/ndcg@10_rel|pct1}} |
| RRF hybrid | {{b:rrf_bm25_lsa/ndcg@10|f3}} | {{p:rrf_bm25_lsa/misspelling/ndcg@10_rel|pct1}} | {{p:rrf_bm25_lsa/paraphrasing/ndcg@10_rel|pct1}} | {{p:rrf_bm25_lsa/naturality/ndcg@10_rel|pct1}} | {{p:rrf_bm25_lsa/ordering/ndcg@10_rel|pct1}} |

* Misspellings: all three Holm-adjusted p-values are below 0.001.
* Paraphrasing: BM25 is significant after correction ({{p:bm25/paraphrasing/p_holm|peq}}); LSA and the hybrid are not
  (hybrid: uncorrected {{p:rrf_bm25_lsa/paraphrasing/p_signflip|peq}}, Holm {{p:rrf_bm25_lsa/paraphrasing/p_holm|peq}}).
* Naturality: no reliable change. Word order: exactly zero because these systems ignore word order; it says nothing about word order.
* Paraphrasing moves the top ten results more than misspelling does but costs less effectiveness: ranking stability is not a proxy for harm.

**Do not read this as evidence about neural dense retrievers, other collections or real user queries.** See the limitations in the manuscript.

## About a "95%+ accuracy" target

There is no accuracy figure of that kind in this study, and none can honestly be produced by it. Retrieval quality is measured by
nDCG@10, Recall@100 and MRR@10; the best system here (BM25) reaches nDCG@10 = {{b:bm25/ndcg@10|f3}} on this collection, and the question
the study asks is how much those scores *change* under rewording, not how high they can be pushed. Tuning anything on the
evaluation queries to raise a number would invalidate the result, so it was not done, and no "95%" claim is made anywhere in
the repository.

## Repository map

| path | what it is |
|:--|:--|
| `paper/manuscript_draft.pdf`, `paper/manuscript_draft.md` | the manuscript (the `.md` is generated from `paper/manuscript_template.md`; every experimental number is filled in from the result files) |
| `paper/arxiv_source/` | LaTeX source (`main.tex`, `main.bbl`, `references.bib`, figure) that compiles stand-alone with `pdflatex` |
| `paper/literature_verification_log.md` | what was checked for each reference, how it was read, and what is still unverified |
| `docs/ANALYSIS_PLAN.md` | the analysis plan written before the run, plus amendments and deviations (the first 8,130 bytes are the plan as it stood at the run) |
| `docs/LLM_REWRITE_PROTOCOL.md` | how the rewrites were produced and reviewed, with the reviewer prompt verbatim |
| `docs/STARTER_CODE_REVIEW.md` | defects found in the starter script this work began from |
| `docs/RUN_BEIR_LOCALLY.md` | how to run the neural and BEIR experiments that could not be run here |
| `src/qvr/` | the package: BM25, LSA/dense search, RRF, metrics, stability measures, statistics, rewrite handling, audit tools |
| `scripts/` | `fetch_vaswani.py`, `make_rewrites.py`, `run_experiment.py`, `analyze.py`, `audit_tool.py`, `make_figure.py`, `build_paper.py`, `build_pdf.sh`, `verify_results.py`, `compare_runs.py` |
| `tests/` | {{x:n_tests|int}} automated tests, including cross-checks against `pytrec_eval`, `ranx`, `bm25s` and `rbo`, and a bug-injection harness (`tests/mutation/`) |
| `data/rewrites/` | the rewrites (all candidates with their review records), reviewer packets and labels, and a blind sheet for a human audit |
| `results/vaswani_pilot/` | the main run: per-query tables, every saved ranking, summary tables, `run_metadata.json` |
| `results/vaswani_pilot_reviewer_only/` | the same run with the reviewer's labels only (sensitivity analysis) |
| `results/verification_report.md` | output of the independent recomputation (`scripts/verify_results.py`) |
| `results/reproduction_check.md` | output of `scripts/compare_runs.py` for a re-run in a fresh environment against the shipped run |
| `legacy/` | the original starter script and the original kit documents, unchanged |

The Vaswani files are **not** included (no licence was found on the pages consulted); `scripts/fetch_vaswani.py` downloads them from
a pinned PyTerrier commit and checks the checksums. Whoever runs it is responsible for checking the terms of use.

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[plots,test]"
python scripts/fetch_vaswani.py                             # downloads and verifies the collection into data/raw/vaswani
pytest                                                      # {{x:n_tests|int}} tests (one is skipped until the collection has been downloaded)
python scripts/run_experiment.py --dataset vaswani --data-dir data/raw/vaswani \
    --rewrites data/rewrites/vaswani_rewrites.jsonl --allowed-statuses automatic_by_construction llm_reviewed \
    --systems bm25 lsa rrf_bm25_lsa --out results/vaswani_rerun
python scripts/analyze.py --run-dir results/vaswani_rerun
python scripts/compare_runs.py --reference results/vaswani_pilot --candidate results/vaswani_rerun   # does the re-run match the shipped one?
python scripts/verify_results.py                            # independent recomputation of the shipped results
bash scripts/build_pdf.sh                                   # manuscript.md + PDF + arXiv-style source (needs pandoc and pdflatex)
```

The run takes about {{m:total_runtime_s|f2}} seconds on one CPU. Saved environment: Python {{m:python|pyver}}, numpy {{m:packages/numpy|str}}, scipy {{m:packages/scipy|str}},
pandas {{m:packages/pandas|str}}, scikit-learn {{m:packages/scikit-learn|str}}. The commands above were run once more from a clean copy of the repository in a new virtual environment, which installed other
library versions (see the table in `results/reproduction_check.md`). The per-query tables came out identical, every saved ranking had the same
document order, and only the stored LSA scores differed, in about the seventh decimal. The bootstrap and permutation results depend on the
seeds stored in `analysis_parameters.json`.

## Still to do (nothing below has been done)

1. **Human validation of the rewrites.** `data/rewrites/audit/vaswani_audit_blind.csv` is a blind sheet of 200 rewrites. Give *only* that
   file to annotators (keep `vaswani_audit_key.csv` away from them), then use `scripts/audit_tool.py score` and `apply`. Use at least two annotators on a subset and report agreement.
2. **Neural dense retrievers and BEIR datasets** with the hybrid of each; follow `docs/RUN_BEIR_LOCALLY.md` and write the design into the analysis plan *before* running.
3. **A systematic literature search** with a written protocol; the one behind the manuscript was not systematic (Appendix A of the manuscript).
4. **Re-check every citation** against the cited paper, especially the claims that rest on abstracts or a page summariser.

## Before anything is submitted

Checked on arXiv's own pages on 22 October 2026 (re-check at submission time):

* arXiv's policy (blog post of 31 January 2023) is that generative AI tools should not be listed as authors, that the authors take
  full responsibility for all contents irrespective of how they were generated, and that significant use of such tools should be reported.
  The manuscript's "AI assistance" section is a draft for the human author to rewrite truthfully.
* arXiv's submission page says "Authors are expected to self-submit", asks for TeX/LaTeX source (PDFs generated from TeX are not accepted) and an
  irrevocable licence to distribute. `paper/arxiv_source/` is built for that.
* Since 21 January 2026 an institutional email address alone no longer qualifies a new author for endorsement: a first-time submitter needs
  personal endorsement from an established arXiv author in the same endorsement domain, and arXiv staff cannot waive this.
* The October 2025 rule that computer-science surveys and position papers need prior peer review does not apply to empirical research papers like this one.
* A preprint is not peer review. A decision to submit a pilot of this scope, instead of first extending it, belongs to the human author (`PUBLICATION_PLAN.md`).

## Known issues

* Spearman correlations are reproducible only to about 1e-4 across implementations, because exact ties in the nDCG@10 change are split by floating-point noise in the pipeline's values (no effect at the two decimals reported).
* The collection's provenance and licence are unclear; the Glasgow page for it carries a caution about the collection.
* The rewrites written by the AI assistant cannot be regenerated (no separate prompt or seed was recorded); they are stored verbatim.

## Licence and citation

No licence file has been added because that is a decision for the owner of the repository; until one is added, default copyright applies. If you use anything here, cite the manuscript once its authors have
finalised it, and cite the data sources and papers listed in `paper/references.bib`.
