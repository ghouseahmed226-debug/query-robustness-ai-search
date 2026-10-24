# Summary of run

* collection: `vaswani` (11429 documents)
* queries analysed: 93
* valid rewrites analysed: 684 (by category: {'naturality': 173, 'paraphrasing': 185, 'misspelling': 279, 'ordering': 47}; by status: {'llm_reviewed': 405, 'automatic_by_construction': 279})
* rewrites dropped before the run: {'not_meaning_preserved': 50}

## Original queries

| system | n_queries | ndcg@10 | ndcg@10_lo | ndcg@10_hi | recall@100 | mrr@10 |
|---|---|---|---|---|---|---|
| bm25 | 93 | 0.432 | 0.375 | 0.489 | 0.601 | 0.685 |
| lsa | 93 | 0.282 | 0.232 | 0.334 | 0.495 | 0.506 |
| rrf_bm25_lsa | 93 | 0.382 | 0.326 | 0.437 | 0.570 | 0.642 |

## Primary: nDCG@10 under each variation category

`rel` is the relative change of the mean (ratio of means over the queries that have a valid rewrite in the category); intervals are 95% cluster-bootstrap CIs over original queries; `p_holm` is Holm-adjusted over 12 tests.

| system | category | n_queries | n_rewrites | ndcg@10_orig | ndcg@10_rewrite | ndcg@10_delta | ndcg@10_delta_lo | ndcg@10_delta_hi | ndcg@10_rel | ndcg@10_rel_lo | ndcg@10_rel_hi | p_signflip | p_holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | misspelling | 93 | 279 | 0.4318 | 0.3518 | -0.0800 | -0.1143 | -0.0491 | -0.1853 | -0.2538 | -0.1209 | 0.0000 | 0.0001 |
| bm25 | naturality | 93 | 173 | 0.4318 | 0.4239 | -0.0079 | -0.0227 | 0.0048 | -0.0183 | -0.0505 | 0.0117 | 0.2754 | 1.0000 |
| bm25 | ordering | 47 | 47 | 0.3898 | 0.3898 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| bm25 | paraphrasing | 93 | 185 | 0.4318 | 0.3745 | -0.0573 | -0.0892 | -0.0273 | -0.1327 | -0.1966 | -0.0669 | 0.0004 | 0.0038 |
| lsa | misspelling | 93 | 279 | 0.2824 | 0.2219 | -0.0605 | -0.0886 | -0.0363 | -0.2142 | -0.2965 | -0.1378 | 0.0000 | 0.0001 |
| lsa | naturality | 93 | 173 | 0.2824 | 0.2810 | -0.0013 | -0.0091 | 0.0066 | -0.0048 | -0.0321 | 0.0236 | 0.7414 | 1.0000 |
| lsa | ordering | 47 | 47 | 0.2618 | 0.2618 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| lsa | paraphrasing | 93 | 185 | 0.2824 | 0.2673 | -0.0150 | -0.0399 | 0.0098 | -0.0533 | -0.1323 | 0.0371 | 0.2434 | 1.0000 |
| rrf_bm25_lsa | misspelling | 93 | 279 | 0.3815 | 0.3045 | -0.0771 | -0.1058 | -0.0513 | -0.2020 | -0.2670 | -0.1420 | 0.0000 | 0.0001 |
| rrf_bm25_lsa | naturality | 93 | 173 | 0.3815 | 0.3835 | 0.0020 | -0.0062 | 0.0102 | 0.0053 | -0.0156 | 0.0280 | 0.6355 | 1.0000 |
| rrf_bm25_lsa | ordering | 47 | 47 | 0.3566 | 0.3566 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| rrf_bm25_lsa | paraphrasing | 93 | 185 | 0.3815 | 0.3518 | -0.0297 | -0.0539 | -0.0059 | -0.0778 | -0.1346 | -0.0169 | 0.0166 | 0.1329 |

## Secondary metrics

| system | category | recall@100_delta | recall@100_rel | mrr@10_delta | mrr@10_rel |
|---|---|---|---|---|---|
| bm25 | misspelling | -0.0635 | -0.1057 | -0.0633 | -0.0925 |
| bm25 | naturality | -0.0141 | -0.0234 | -0.0046 | -0.0068 |
| bm25 | ordering | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| bm25 | paraphrasing | -0.0426 | -0.0710 | -0.0545 | -0.0797 |
| lsa | misspelling | -0.0595 | -0.1203 | -0.0955 | -0.1889 |
| lsa | naturality | 0.0005 | 0.0011 | -0.0039 | -0.0076 |
| lsa | ordering | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| lsa | paraphrasing | -0.0273 | -0.0552 | -0.0310 | -0.0613 |
| rrf_bm25_lsa | misspelling | -0.0548 | -0.0962 | -0.0896 | -0.1396 |
| rrf_bm25_lsa | naturality | -0.0087 | -0.0154 | -0.0024 | -0.0037 |
| rrf_bm25_lsa | ordering | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| rrf_bm25_lsa | paraphrasing | -0.0322 | -0.0565 | -0.0143 | -0.0222 |

## Ranking stability (original vs rewrite ranking of the same system)

| system | category | overlap@10 | rbo_p0.9 |
|---|---|---|---|
| bm25 | misspelling | 0.658 | 0.651 |
| bm25 | naturality | 0.870 | 0.867 |
| bm25 | ordering | 1.000 | 1.000 |
| bm25 | paraphrasing | 0.554 | 0.528 |
| lsa | misspelling | 0.686 | 0.665 |
| lsa | naturality | 0.911 | 0.908 |
| lsa | ordering | 1.000 | 1.000 |
| lsa | paraphrasing | 0.615 | 0.587 |
| rrf_bm25_lsa | misspelling | 0.671 | 0.639 |
| rrf_bm25_lsa | naturality | 0.901 | 0.889 |
| rrf_bm25_lsa | ordering | 1.000 | 1.000 |
| rrf_bm25_lsa | paraphrasing | 0.595 | 0.557 |

## Descriptive breakdown by generator (no tests)

| system | generator | n_queries | n_rewrites | ndcg@10_delta | ndcg@10_delta_lo | ndcg@10_delta_hi | ndcg@10_rel |
|---|---|---|---|---|---|---|---|
| bm25 | LLM_NaturalQuestion | 92 | 92 | -0.0075 | -0.0294 | 0.0131 | -0.0174 |
| bm25 | LLM_Paraphrase | 93 | 93 | -0.0370 | -0.0701 | -0.0044 | -0.0856 |
| bm25 | LLM_SynonymSwap | 92 | 92 | -0.0792 | -0.1239 | -0.0387 | -0.1852 |
| bm25 | NeighbCharSwap | 93 | 93 | -0.0781 | -0.1182 | -0.0405 | -0.1808 |
| bm25 | QWERTYCharSub | 93 | 93 | -0.0951 | -0.1340 | -0.0577 | -0.2201 |
| bm25 | RandomCharSub | 93 | 93 | -0.0669 | -0.1069 | -0.0321 | -0.1550 |
| bm25 | RandomOrderSwap | 47 | 47 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| bm25 | RemoveStopWords | 81 | 81 | 0.0008 | -0.0058 | 0.0079 | 0.0018 |
| lsa | LLM_NaturalQuestion | 92 | 92 | -0.0030 | -0.0150 | 0.0086 | -0.0109 |
| lsa | LLM_Paraphrase | 93 | 93 | 0.0025 | -0.0235 | 0.0276 | 0.0087 |
| lsa | LLM_SynonymSwap | 92 | 92 | -0.0337 | -0.0696 | -0.0002 | -0.1212 |
| lsa | NeighbCharSwap | 93 | 93 | -0.0603 | -0.0925 | -0.0312 | -0.2134 |
| lsa | QWERTYCharSub | 93 | 93 | -0.0706 | -0.1066 | -0.0382 | -0.2499 |
| lsa | RandomCharSub | 93 | 93 | -0.0506 | -0.0823 | -0.0234 | -0.1793 |
| lsa | RandomOrderSwap | 47 | 47 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| lsa | RemoveStopWords | 81 | 81 | -0.0006 | -0.0089 | 0.0081 | -0.0023 |
| rrf_bm25_lsa | LLM_NaturalQuestion | 92 | 92 | 0.0042 | -0.0093 | 0.0174 | 0.0110 |
| rrf_bm25_lsa | LLM_Paraphrase | 93 | 93 | -0.0035 | -0.0312 | 0.0238 | -0.0092 |
| rrf_bm25_lsa | LLM_SynonymSwap | 92 | 92 | -0.0571 | -0.0933 | -0.0242 | -0.1515 |
| rrf_bm25_lsa | NeighbCharSwap | 93 | 93 | -0.0761 | -0.1116 | -0.0436 | -0.1995 |
| rrf_bm25_lsa | QWERTYCharSub | 93 | 93 | -0.0860 | -0.1225 | -0.0529 | -0.2253 |
| rrf_bm25_lsa | RandomCharSub | 93 | 93 | -0.0691 | -0.1018 | -0.0395 | -0.1811 |
| rrf_bm25_lsa | RandomOrderSwap | 47 | 47 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| rrf_bm25_lsa | RemoveStopWords | 81 | 81 | -0.0004 | -0.0076 | 0.0082 | -0.0011 |

## Exploratory: hybrid vs component (difference in absolute nDCG@10 change)

| hybrid | component | category | n_queries | diff_in_absolute_ndcg@10_change | lo | hi |
|---|---|---|---|---|---|---|
| rrf_bm25_lsa | bm25 | misspelling | 93 | 0.0030 | -0.0142 | 0.0211 |
| rrf_bm25_lsa | bm25 | naturality | 93 | 0.0099 | -0.0025 | 0.0241 |
| rrf_bm25_lsa | bm25 | ordering | 47 | 0.0000 | 0.0000 | 0.0000 |
| rrf_bm25_lsa | bm25 | paraphrasing | 93 | 0.0276 | 0.0047 | 0.0513 |
| rrf_bm25_lsa | lsa | misspelling | 93 | -0.0166 | -0.0329 | -0.0010 |
| rrf_bm25_lsa | lsa | naturality | 93 | 0.0034 | -0.0038 | 0.0110 |
| rrf_bm25_lsa | lsa | ordering | 47 | 0.0000 | 0.0000 | 0.0000 |
| rrf_bm25_lsa | lsa | paraphrasing | 93 | -0.0146 | -0.0350 | 0.0048 |

## Stability vs effectiveness (Spearman, RBO vs |change in nDCG@10|)

| system | n_pairs | spearman_rbo_vs_abs_delta_ndcg@10 | lo | hi |
|---|---|---|---|---|
| bm25 | 684 | -0.699 | -0.764 | -0.626 |
| lsa | 684 | -0.630 | -0.694 | -0.564 |
| rrf_bm25_lsa | 684 | -0.703 | -0.763 | -0.635 |
