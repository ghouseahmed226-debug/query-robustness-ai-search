# Summary of run

* collection: `nfcorpus` (3633 documents)
* queries analysed: 323
* valid rewrites analysed: 950 (by category: {'misspelling': 950}; by status: {'automatic_by_construction': 950})
* rewrites dropped before the run: {'status_not_allowed': 313}

## Original queries

| system | n_queries | ndcg@10 | ndcg@10_lo | ndcg@10_hi | recall@100 | mrr@10 |
|---|---|---|---|---|---|---|
| bm25 | 323 | 0.322 | 0.288 | 0.356 | 0.246 | 0.527 |
| lsa | 323 | 0.332 | 0.296 | 0.369 | 0.323 | 0.506 |
| rrf_bm25_lsa | 323 | 0.339 | 0.304 | 0.375 | 0.320 | 0.515 |

## Primary: nDCG@10 under each variation category

`rel` is the relative change of the mean (ratio of means over the queries that have a valid rewrite in the category); intervals are 95% cluster-bootstrap CIs over original queries; `p_holm` is Holm-adjusted over 3 tests.

| system | category | n_queries | n_rewrites | ndcg@10_orig | ndcg@10_rewrite | ndcg@10_delta | ndcg@10_delta_lo | ndcg@10_delta_hi | ndcg@10_rel | ndcg@10_rel_lo | ndcg@10_rel_hi | p_signflip | p_holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | misspelling | 318 | 950 | 0.3189 | 0.1581 | -0.1608 | -0.1908 | -0.1326 | -0.5042 | -0.5725 | -0.4369 | 0.0000 | 0.0000 |
| lsa | misspelling | 318 | 950 | 0.3292 | 0.1627 | -0.1665 | -0.1997 | -0.1340 | -0.5058 | -0.5752 | -0.4346 | 0.0000 | 0.0000 |
| rrf_bm25_lsa | misspelling | 318 | 950 | 0.3363 | 0.1675 | -0.1688 | -0.2009 | -0.1380 | -0.5019 | -0.5687 | -0.4341 | 0.0000 | 0.0000 |

## Secondary metrics

| system | category | recall@100_delta | recall@100_rel | mrr@10_delta | mrr@10_rel |
|---|---|---|---|---|---|
| bm25 | misspelling | -0.0852 | -0.3452 | -0.2552 | -0.4845 |
| lsa | misspelling | -0.1338 | -0.4144 | -0.2404 | -0.4757 |
| rrf_bm25_lsa | misspelling | -0.1295 | -0.4044 | -0.2389 | -0.4647 |

## Ranking stability (original vs rewrite ranking of the same system)

| system | category | overlap@10 | rbo_p0.9 |
|---|---|---|---|
| bm25 | misspelling | 0.405 | 0.473 |
| lsa | misspelling | 0.442 | 0.474 |
| rrf_bm25_lsa | misspelling | 0.435 | 0.466 |

## Descriptive breakdown by generator (no tests)

| system | generator | n_queries | n_rewrites | ndcg@10_delta | ndcg@10_delta_lo | ndcg@10_delta_hi | ndcg@10_rel |
|---|---|---|---|---|---|---|---|
| bm25 | NeighbCharSwap | 318 | 318 | -0.1575 | -0.1899 | -0.1271 | -0.4940 |
| bm25 | QWERTYCharSub | 315 | 315 | -0.1513 | -0.1832 | -0.1208 | -0.4791 |
| bm25 | RandomCharSub | 317 | 317 | -0.1699 | -0.2020 | -0.1389 | -0.5332 |
| lsa | NeighbCharSwap | 318 | 318 | -0.1685 | -0.2042 | -0.1334 | -0.5120 |
| lsa | QWERTYCharSub | 315 | 315 | -0.1579 | -0.1931 | -0.1246 | -0.4849 |
| lsa | RandomCharSub | 317 | 317 | -0.1692 | -0.2035 | -0.1347 | -0.5134 |
| rrf_bm25_lsa | NeighbCharSwap | 318 | 318 | -0.1684 | -0.2021 | -0.1359 | -0.5008 |
| rrf_bm25_lsa | QWERTYCharSub | 315 | 315 | -0.1613 | -0.1958 | -0.1290 | -0.4844 |
| rrf_bm25_lsa | RandomCharSub | 317 | 317 | -0.1724 | -0.2063 | -0.1391 | -0.5132 |

## Exploratory: hybrid vs component (difference in absolute nDCG@10 change)

| hybrid | component | category | n_queries | diff_in_absolute_ndcg@10_change | lo | hi |
|---|---|---|---|---|---|---|
| rrf_bm25_lsa | bm25 | misspelling | 318 | -0.0080 | -0.0209 | 0.0050 |
| rrf_bm25_lsa | lsa | misspelling | 318 | -0.0023 | -0.0109 | 0.0057 |

## Stability vs effectiveness (Spearman, RBO vs |change in nDCG@10|)

| system | n_pairs | spearman_rbo_vs_abs_delta_ndcg@10 | lo | hi |
|---|---|---|---|---|
| bm25 | 950 | -0.575 | -0.651 | -0.488 |
| lsa | 950 | -0.597 | -0.674 | -0.515 |
| rrf_bm25_lsa | 950 | -0.574 | -0.652 | -0.490 |
