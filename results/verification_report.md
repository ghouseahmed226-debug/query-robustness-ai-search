# Independent verification report

Produced by `scripts/verify_results.py`, which recomputes the reported numbers from the saved rankings and the relevance judgments without using the `qvr` package. See the docstring of the script for what each check does.

| result | check | detail |
|:--|:--|:--|
| PASS | collection: queries with judgments | 93 / 93 |
| PASS | collection: judged pairs | 2083 |
| PASS | per-query ndcg@10 recomputed from rankings | max abs diff 1.11e-16 |
| PASS | per-query recall@100 recomputed from rankings | max abs diff 1.11e-16 |
| PASS | per-query mrr@10 recomputed from rankings | max abs diff 5.55e-17 |
| PASS | per-query overlap@10 recomputed from rankings | max abs diff 0.00e+00 |
| PASS | RBO(p=0.9) recomputed for pairs of full-length rankings | 1932 pairs, max abs diff 1.11e-16 |
| PASS | every kept rewrite has a ranking for every system | 1932 |
| PASS | baseline means (nDCG@10, Recall@100, MRR@10) | max abs diff 0.00e+00 |
| PASS | primary table: number of queries per category |  |
| PASS | primary table: original / rewrite means of nDCG@10 | max abs diff 1.11e-16 |
| PASS | primary table: relative changes | max abs diff 1.94e-16 |
| PASS | primary table: overlap@10 | max abs diff 1.11e-16 |
| PASS | by-generator table: relative changes | max abs diff 3.61e-16 |
| PASS | hybrid-minus-component differences | max abs diff 9.41e-17 |
| PASS | Spearman(RBO, |delta nDCG@10|) point estimates (tolerance 1e-4, see note) | max abs diff 2.5e-05 as computed, 7.1e-05 with ties resolved by rounding; the pipeline ranks unrounded values, so exact ties are split by floating-point noise |
| PASS | 95% cluster-bootstrap intervals re-estimated with another seed (20,000 resamples) | max endpoint difference 0.0020 (Monte-Carlo tolerance 0.012) |
| PASS | sign-flip p-values re-estimated with another seed (400,000 flips) | max abs diff 0.0021 |
| PASS | Holm-adjusted p-values and decisions | max abs diff 0.0007 |
| PASS | analysis plan: first 8,130 bytes hash to the value stored at run time |  |
| PASS | rewrite file hash equals the value stored at run time |  |
| PASS | code files that produced the run are unchanged since the run |  |
| PASS | raw Vaswani files match the checksums recorded at run time |  |
| PASS | paper/manuscript_draft.md equals a fresh build from the template and the result files |  |
| PASS | README.md equals a fresh build from docs/README_template.md and the result files |  |
| PASS | all data-dependent sentences of the manuscript hold |  |
| PASS | test count quoted in the manuscript equals the number of collected tests | manuscript [85], collected 85 |
| PASS | full test suite passes | 85 passed, 960 warnings in 7.24s |

28 of 28 checks passed.
