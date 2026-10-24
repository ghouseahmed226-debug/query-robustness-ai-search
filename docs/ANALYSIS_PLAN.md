# Pre-specified analysis plan (pilot)

Written 2026-10-17, **before any retrieval run had been executed**. This is an internal plan, not an
external preregistration. Every deviation made after this point is recorded in the "Deviations" log at the
bottom, with the reason. The SHA-256 of this file is stored in each `run_metadata.json`.

## 0. Scope and what this pilot can and cannot support

* One collection only (Vaswani / NPL, 11,429 abstracts, 93 queries, binary judgments).
* Systems that can be run without internet access to model hubs: BM25, a non-neural latent-semantic (LSA)
  dense baseline, and their RRF hybrid. **No neural dense retriever is run in this environment.**
* The pilot can show whether the pipeline works and give a *preliminary, collection-specific* picture of
  how these three systems react to the query-variation categories. It cannot support claims about neural
  dense retrievers, about other domains, or about "cross-domain" behaviour.
* RQ3 (domain effects) and RQ4 (held-out-domain degradation predictor) are **out of scope** for the pilot.

## 1. Systems (fixed before running; none is tuned on the evaluation queries)

| id | system | specification |
|----|--------|---------------|
| `bm25` | BM25 | own sparse-matrix implementation; Lucene-style IDF `ln(1 + (N-df+0.5)/(df+0.5))`; k1 = 1.2, b = 0.75 (Elasticsearch defaults, as used for BEIR's BM25 baseline); analyzer = lowercase, `[a-z0-9]+` tokens, Lucene's 33-word English stop list, Porter stemming; title + text concatenated into one field; query-term multiplicity counted; documents with score 0 are not returned |
| `lsa` | non-neural dense baseline | TF-IDF (sublinear tf, same analyzer) -> truncated SVD, 300 dimensions, `random_state = 0`, L2-normalised, exact cosine search; queries whose vector is all-zero return an empty ranking |
| `rrf_bm25_lsa` | hybrid | Reciprocal Rank Fusion, k = 60, over the top-100 lists of `bm25` and `lsa`, output depth 100 |

Retrieval depth is 100 for every system. A neural bi-encoder and its RRF hybrid are specified in code but
are **not** part of the pilot; if run later they are added as extra systems under this same plan.

## 2. Query variations

Categories follow the four meaning-preserving classes of Penha et al. (2022): *misspelling*, *ordering*,
*naturality*, *paraphrasing*. The two semantics-changing classes (generalisation/specialisation, aspect
change) are not studied.

| category | generator id | how produced | validity rule |
|----------|--------------|--------------|----------------|
| misspelling | `NeighbCharSwap`, `RandomCharSub`, `QWERTYCharSub` | seeded character edit of one word with > 3 letters (own re-implementation, not Penha et al.'s code) | valid by construction unless identical to the original after lower-casing |
| ordering | `RandomOrderSwap` | seeded swap of two words with different surface forms | automatic + independent LLM review |
| naturality | `RemoveStopWords` | deterministic removal of NLTK English stop words | independent blind LLM review (see amendment A1) |
| naturality | `LLM_NaturalQuestion` | rewritten as a natural-language question by the generating LLM | independent blind LLM review |
| paraphrasing | `LLM_Paraphrase`, `LLM_SynonymSwap` | generating LLM | independent blind LLM review |

* Global seed for all automatic generators: 13.
* LLM rewrites: generator = Claude Sonnet 5.5 (interactive session; sampling settings not exposed). The
  prompt/protocol is stored in `docs/LLM_REWRITE_PROTOCOL.md`.
* Review: a separate Claude agent instance sees only (original, rewrite) pairs, blind to category and to
  the generator's intent, and labels each `equivalent` / `broader` / `narrower` / `different`. Only
  `equivalent` rewrites enter the analysis. Generator and reviewer are the same model family, so shared
  blind spots are possible; this is a stated limitation.
* **No rewrite in this pilot is human-verified.** `review_status` is therefore `automatic_by_construction`
  or `llm_reviewed`, never `human_verified`. A stratified random sample is exported for human audit
  (`data/rewrites/human_audit_sheet.csv`); agreement between the human audit and the LLM review must be
  reported when that audit is done.
* Rewrites identical to the original after lower-casing/whitespace normalisation are discarded.

## 3. Outcomes

Primary: **nDCG@10** (linear gain, log2 discount; judged-relevant = rel > 0).
Secondary: Recall@100, MRR@10 (binary relevance rel > 0), overlap@10 (|top10 ∩ top10'| / 10), RBO
(p = 0.9, extrapolated, depth 100, Webber et al. 2010) between the original-query ranking and the
rewrite ranking of the same system.
Queries without any judged-relevant document are excluded from all effectiveness computations.

## 4. Estimands

For system *s* and category *c*, let Q_c be the original queries with at least one valid rewrite in *c*.
For q in Q_c let m0_q be the metric for the original query and m̄_q the mean metric over q's valid rewrites
in *c* (so each query contributes once per category however many rewrites it has).

* Absolute change: Δ(s,c) = mean over Q_c of (m̄_q − m0_q).
* **Relative change (primary):** R(s,c) = mean(m̄_q) / mean(m0_q) − 1, a ratio of means over Q_c.
* Stability: mean over Q_c of the per-query mean overlap@10 and RBO.

## 5. Inference

* 95% percentile cluster-bootstrap CIs, resampling *original queries* (rewrites of one query are never
  treated as independent); B = 10,000; seed 20261017.
* Two-sided sign-flip permutation test on d_q = m̄_q − m0_q (200,000 random sign flips; p = (k+1)/(B+1)).
* Multiplicity: Holm correction over the primary family = all (system × category) tests of nDCG@10
  (3 systems × 4 categories = 12 tests), α = 0.05. All other p-values are descriptive.
* Hybrid-vs-component comparison (**exploratory**, CI only, no test): per-query paired difference in
  absolute nDCG@10 change between `rrf_bm25_lsa` and each component, per category.
* Stability vs effectiveness: Spearman correlation between RBO and |ΔnDCG@10| over (query, rewrite) pairs,
  per system, with a cluster-bootstrap CI.
* Results are interpreted through CIs. A category whose CI covers 0 is reported as "no reliable change
  detected", never as "no effect".

## 6. Cross-checks that must pass before any number is reported

1. Own nDCG@10 / Recall@100 / MRR@10 equal `pytrec_eval` and `ranx` outputs on the same runs (tolerance 1e-9).
2. Own BM25 scores equal `bm25s` (Lucene variant, same tokens, k1 = 1.2, b = 0.75) to float tolerance.
3. Own RBO equals the `rbo` package on random lists, and satisfies the analytic identities
   (identical lists -> 1, disjoint lists -> 0).
4. Bootstrap CI for a mean agrees with the analytical t-interval within Monte-Carlo error on a large sample;
   sign-flip p-value agrees with `scipy.stats.permutation_test` on a small sample.
5. Collection counts (documents, queries, judged pairs) agree with the published description of the
   collection, and downloaded files match the checksums published by PyTerrier/ir_datasets.

## 7. Amendments made before the first retrieval run

These were made on 2026-10-18, after the code and tests were finished and **before any retrieval run on the
pilot queries**; no result had been seen. They are listed so that the change history is transparent.

* **A1.** `RemoveStopWords` was first specified as valid by construction. Stop-word removal can delete negations
  and quantifiers (for example *not*, *no*, *only*, *all*, *more than*), so it now goes through the same blind
  review as ordering and LLM rewrites. Only rewrites labelled `equivalent` enter the analysis.
* **A2.** The human-audit sheet is stratified by generator (not only by category) so that the typo and
  stop-word generators are audited as well.
* **A3.** Descriptive diagnostics are added and reported but not used to exclude anything: the share of typo
  rewrites whose edited word is another word that occurs in the collection (possible meaning change), and the
  reviewer's labels for a random sample of typo rewrites mixed blindly into the review packet.

## 8. Deviations

*(none at time of writing)*

## 9. Post-run record (appended 2026-10-20, after `results/vaswani_pilot` had been produced)

**Nothing above this heading has been edited since the pilot run.** The first 8,130 bytes of this file are the plan
exactly as it stood when the pilot ran; they hash to
`6d31b030288b1c854fc895cdd19f207717ba67923db996be12aa75dd31fbaf08`, the value stored as `analysis_plan_sha256` in
`results/vaswani_pilot/run_metadata.json`. Check with:

```bash
head -c 8130 docs/ANALYSIS_PLAN.md | sha256sum
```

Order of events, from file timestamps and the session transcript: plan written 2026-10-17; amendments A1-A3
2026-10-18; blind review and author recheck finished 2026-10-19; **first retrieval run on the pilot queries
2026-10-20 06:02 UTC** (`created_utc` in `run_metadata.json`). No retrieval output on the pilot queries had been
looked at before the plan, A1-A4 and the validity rule below were fixed. (The retrieval code was exercised only on a
synthetic collection; the real collection was loaded before the run only to check its counts in `tests/test_data.py` and
to compute the typo-vocabulary diagnostic of A3.)

### 9.1 Amendment A4 - conservative author recheck of machine-made rewrites (decided 2026-10-19, before the run)

This rule was decided and applied before the first retrieval run but was written into this file only afterwards.
Section 2 says "only `equivalent` rewrites enter the analysis" (reviewer's label). The executed rule is stricter:

* The blind reviewer labelled 47 of the 93 `RandomOrderSwap` rewrites `equivalent`. Reading them, the author judged
  this too lenient: for example the reviewer accepted
  `number representation in binary machines` -> `number in representation binary machines` and
  `derivation of the components of the electrical conductivity in the upper atmosphere` ->
  `derivation of the components of the electrical conductivity in atmosphere upper the`.
* **Rule (`swap_touches_only_function_words` in `src/qvr/rewrites.py`):** a word-order swap is accepted only if every
  word that moved is an NLTK English stop word (a function word). Result: 9 of 93 swaps pass the rule, 84 fail.
* One manual objection, recorded in `data/rewrites/vaswani_author_recheck_manual.jsonl`: query 69 `RemoveStopWords`
  drops *off* from the compound *cut off* (`variable cut slope`).
* **Unanimity:** a `RandomOrderSwap` or `RemoveStopWords` rewrite enters the analysis only if the reviewer and the
  recheck both say `equivalent`. Effect: ordering rewrites kept = 8 of 93 (reviewer alone: 47; one of the 9
  rule-passing swaps was labelled `different` by the reviewer); stop-word removal kept = 80 of 83 (reviewer alone: 81).
  Total kept = 644 of 734 (typos 279, `LLM_NaturalQuestion` 92, `LLM_Paraphrase` 93, `LLM_SynonymSwap` 92,
  `RemoveStopWords` 80, `RandomOrderSwap` 8).
* **Sensitivity analysis (added; not in the original plan):** the same run repeated with the reviewer's labels only
  (`data/rewrites/vaswani_rewrites_reviewer_only.jsonl`, 684 rewrites, ordering n = 47) is in
  `results/vaswani_pilot_reviewer_only`. Every effectiveness estimate for misspelling and paraphrasing is
  identical to the main run and naturality moves by at most 0.0009 in relative change; ordering is exactly 0
  in both (all three pilot systems ignore word order by construction).
* The recheck is by the same assistant that wrote the code and the LLM rewrites. It is not an independent human check.

### 9.2 A5 - who the reviewer was

The plan says "a separate Claude agent instance". The labels used come from three sequential agents launched with
the `haiku` model setting on 2026-10-19; the reviewer string stored in the data is
`blind LLM reviewer (Claude Haiku 5.5 agent)`. Four earlier attempts with the default (larger) model setting stopped
on usage-limit errors and returned no labels; none of their output was used. Whether the serving model matched the
label cannot be verified from inside the session. The reviewer prompt is reproduced verbatim in
`docs/LLM_REWRITE_PROTOCOL.md`.

### 9.3 Deviations from sections 1-6

* **D1** - the executed validity rule is stricter than section 2 (A4 above).
* **D2** - cross-check 5 (collection counts and checksums) was done; this records what it does and does not establish.
  Counts agree with ir_datasets' description of Vaswani (11,429 documents, 93 queries, 2,083 binary judgments; page
  fetched 2026-10-20) and with `run_metadata.json`. At download (2026-10-17) the md5 of the three files
  (`a059e713...` corpus, `3a624be2...` topics, `6acb6db9...` qrels) equalled the md5 identifiers that PyTerrier 1.1.2
  lists for them (`pyterrier/datasets/_builtin.py`, lines 466, 469, 472). They were not compared with the original
  archive (ir_datasets 0.6.3 lists md5 `23e56070...` for `npl.tar.gz` on the Glasgow site, which was not fetched), and
  no checksum from the collection's original authors was found. The SHA-256 values in `run_metadata.json` pin the
  exact files used; `scripts/fetch_vaswani.py` re-downloads them from the pinned PyTerrier commit and re-checks both.
* **D3** - the audit sheet written by `make_rewrites.py merge` is `data/rewrites/vaswani_rewrites_human_audit_sheet.csv` (section 2
  gives a shorter name); it shows the reviewer's label and the generator, so a blind version (`data/rewrites/audit/vaswani_audit_blind.csv`,
  200 rewrites, kept and dropped) was produced with `scripts/audit_tool.py` and should be preferred for a human audit.
* **D4** - no deviation in systems, metrics, estimands, bootstrap/permutation settings, multiplicity family, seeds or
  retrieval depth.

Where each section-6 cross-check lives in the test suite (79 tests, all passing on 2026-10-20): (1)
`tests/test_metrics.py`; (2) `tests/test_bm25.py`; (3) `tests/test_stability.py`, `tests/test_pipeline.py`; (4)
`tests/test_stats.py`; (5) `run_metadata.json` plus D2.

## 10. Record after the manuscript was built (appended 2026-10-23)

Nothing in sections 1-9 was changed. The pilot results (`results/vaswani_pilot`, `results/vaswani_pilot_reviewer_only`) and the code that produced
them are unchanged since 2026-10-20; `scripts/verify_results.py` checks the code, rewrite-file, plan-prefix and raw-data hashes against
`run_metadata.json`. After the run, the following were added without touching the analysis: the manuscript builder (`scripts/build_paper.py`, which fills every
experimental number from the result files and asserts each data-dependent sentence), the independent recomputation (`scripts/verify_results.py`, which does
not import `qvr`), the audit tool and blind audit sheet, the figure script, the fetch script and the documents in `docs/`.

* **E1 (finding of the independent check, no change made).** The Spearman correlations between RBO and |change in nDCG@10| are computed on unrounded values, so
  exact ties in the nDCG@10 change are split by floating-point noise (differences of about 1e-17). Ranking the values rounded to 12 decimals gives correlations that differ by
  at most about 7e-5 (fourth decimal; the manuscript reports two decimals). The pipeline was left as it ran; `verify_results.py` accepts agreement within 1e-4 for these three numbers and says why.
* **E2 (what was and was not pre-specified).** The primary family, the secondary measures (Recall@100, MRR@10, overlap@10, RBO), the hybrid-versus-component comparison and the
  RBO-versus-effectiveness correlation are in sections 3-5 of the plan. The by-generator table is **not** described in the plan's text: it is produced by the same analysis code that
  existed, and is hashed in `run_metadata.json`, at the time of the run, but it was not pre-specified and is descriptive only. The reviewer-only sensitivity run is recorded in 9.1 as an
  addition. The typo-vocabulary diagnostic is A3. The secondary-measure intervals and all by-generator intervals are uncorrected, as the manuscript says.
* **E3 (terminology).** Where this plan and the other documents say "the author" (for example "author recheck" in A4), they mean the AI assistant that carried out the study. No human has yet reviewed or verified the work; the human author or authors of any submission are still to be named.
