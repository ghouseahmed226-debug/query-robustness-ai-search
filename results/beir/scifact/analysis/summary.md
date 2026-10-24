# Summary of run

* collection: `scifact` (5183 documents)
* queries analysed: 300
* valid rewrites analysed: 894 (by category: {'misspelling': 894}; by status: {'automatic_by_construction': 894})
* rewrites dropped before the run: {'status_not_allowed': 582}

## Original queries

| system | n_queries | ndcg@10 | ndcg@10_lo | ndcg@10_hi | recall@100 | mrr@10 |
|---|---|---|---|---|---|---|
| bm25 | 300 | 0.684 | 0.640 | 0.725 | 0.928 | 0.646 |
| lsa | 300 | 0.542 | 0.496 | 0.587 | 0.888 | 0.501 |
| rrf_bm25_lsa | 300 | 0.619 | 0.576 | 0.661 | 0.935 | 0.569 |

## Primary: nDCG@10 under each variation category

`rel` is the relative change of the mean (ratio of means over the queries that have a valid rewrite in the category); intervals are 95% cluster-bootstrap CIs over original queries; `p_holm` is Holm-adjusted over 3 tests.

| system | category | n_queries | n_rewrites | ndcg@10_orig | ndcg@10_rewrite | ndcg@10_delta | ndcg@10_delta_lo | ndcg@10_delta_hi | ndcg@10_rel | ndcg@10_rel_lo | ndcg@10_rel_hi | p_signflip | p_holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | misspelling | 300 | 894 | 0.6837 | 0.6666 | -0.0171 | -0.0280 | -0.0065 | -0.0250 | -0.0407 | -0.0096 | 0.0014 | 0.0014 |
| lsa | misspelling | 300 | 894 | 0.5417 | 0.5115 | -0.0302 | -0.0468 | -0.0140 | -0.0558 | -0.0846 | -0.0266 | 0.0002 | 0.0006 |
| rrf_bm25_lsa | misspelling | 300 | 894 | 0.6187 | 0.5926 | -0.0261 | -0.0419 | -0.0115 | -0.0423 | -0.0664 | -0.0187 | 0.0007 | 0.0014 |

## Secondary metrics

| system | category | recall@100_delta | recall@100_rel | mrr@10_delta | mrr@10_rel |
|---|---|---|---|---|---|
| bm25 | misspelling | -0.0143 | -0.0154 | -0.0177 | -0.0274 |
| lsa | misspelling | -0.0047 | -0.0053 | -0.0343 | -0.0684 |
| rrf_bm25_lsa | misspelling | -0.0122 | -0.0131 | -0.0278 | -0.0489 |

## Ranking stability (original vs rewrite ranking of the same system)

| system | category | overlap@10 | rbo_p0.9 |
|---|---|---|---|
| bm25 | misspelling | 0.811 | 0.817 |
| lsa | misspelling | 0.822 | 0.807 |
| rrf_bm25_lsa | misspelling | 0.813 | 0.799 |

## Descriptive breakdown by generator (no tests)

| system | generator | n_queries | n_rewrites | ndcg@10_delta | ndcg@10_delta_lo | ndcg@10_delta_hi | ndcg@10_rel |
|---|---|---|---|---|---|---|---|
| bm25 | NeighbCharSwap | 300 | 300 | -0.0158 | -0.0308 | -0.0015 | -0.0231 |
| bm25 | QWERTYCharSub | 294 | 294 | -0.0201 | -0.0373 | -0.0039 | -0.0293 |
| bm25 | RandomCharSub | 300 | 300 | -0.0168 | -0.0329 | -0.0016 | -0.0245 |
| lsa | NeighbCharSwap | 300 | 300 | -0.0348 | -0.0575 | -0.0136 | -0.0643 |
| lsa | QWERTYCharSub | 294 | 294 | -0.0286 | -0.0483 | -0.0099 | -0.0526 |
| lsa | RandomCharSub | 300 | 300 | -0.0296 | -0.0529 | -0.0066 | -0.0547 |
| rrf_bm25_lsa | NeighbCharSwap | 300 | 300 | -0.0321 | -0.0548 | -0.0098 | -0.0519 |
| rrf_bm25_lsa | QWERTYCharSub | 294 | 294 | -0.0257 | -0.0440 | -0.0086 | -0.0414 |
| rrf_bm25_lsa | RandomCharSub | 300 | 300 | -0.0226 | -0.0436 | -0.0027 | -0.0365 |

## Exploratory: hybrid vs component (difference in absolute nDCG@10 change)

| hybrid | component | category | n_queries | diff_in_absolute_ndcg@10_change | lo | hi |
|---|---|---|---|---|---|---|
| rrf_bm25_lsa | bm25 | misspelling | 300 | -0.0091 | -0.0225 | 0.0038 |
| rrf_bm25_lsa | lsa | misspelling | 300 | 0.0041 | -0.0097 | 0.0179 |

## Stability vs effectiveness (Spearman, RBO vs |change in nDCG@10|)

| system | n_pairs | spearman_rbo_vs_abs_delta_ndcg@10 | lo | hi |
|---|---|---|---|---|
| bm25 | 894 | -0.303 | -0.370 | -0.229 |
| lsa | 894 | -0.407 | -0.473 | -0.342 |
| rrf_bm25_lsa | 894 | -0.373 | -0.440 | -0.303 |
