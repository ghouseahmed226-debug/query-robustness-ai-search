# Reproduction check

Reference run: `results/vaswani_pilot`. Re-run: `results/vaswani_rerun`. Written by `scripts/compare_runs.py`.

| | reference | re-run |
|:--|:--|:--|
| Python | 3.13.16 | 3.13.16 |
| numpy | 2.5.4 | 1.26.4 |
| pandas | 3.0.5 | 3.0.6 |
| scikit-learn | 1.9.1 | 1.9.1 |
| scipy | 1.18.1 | 1.17.1 |
| snowballstemmer | 3.1.1 | 3.1.1 |

## Per-query tables

| file | result | max abs difference |
|:--|:--|--:|
| `per_query_original.csv` | agree (279 rows, 5 numeric columns) | 0.00e+00 |
| `per_query_rewrites.csv` | agree (1932 rows, 10 numeric columns) | 0.00e+00 |
| `queries_used.csv` | agree (93 rows, 3 numeric columns) | 0.00e+00 |

The rewrite file used is byte-identical in the two runs.

## Saved rankings

| system | ranked lists | lists with a different document order | max abs score difference | max relative score difference |
|:--|--:|--:|--:|--:|
| bm25 | 737 | 0 | 7.11e-15 | 4.23e-16 |
| lsa | 737 | 0 | 1.79e-07 | 2.83e-07 |
| rrf_bm25_lsa | 737 | 0 | 0.00e+00 | 0.00e+00 |

**Overall: the re-run reproduces the shipped per-query results and ranking order.** Differences in stored scores of the order of 1e-7 are floating-point differences between library versions (BLAS, SVD); they do not change any ranking here.
