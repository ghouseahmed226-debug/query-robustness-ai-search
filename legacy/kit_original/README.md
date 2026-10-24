# Query Robustness Research Kit

## Working title
**Beyond Average Retrieval Scores: A Reproducible Cross-Domain Study of Query-Variation Robustness**

This is a research starter kit, not a completed or validated research paper. It intentionally contains no fabricated experimental results. Run the experiments, inspect the outputs, and replace every marked placeholder in the manuscript with actual findings before submission.

## Research question
How do meaning-preserving query variations affect the effectiveness and ranking stability of sparse, dense, and hybrid retrieval systems across public information-retrieval datasets?

## Important novelty warning
Query-variation robustness has prior work, including Penha et al. (ECIR 2022) and Hagen, Scells, and Potthast (Findings of EMNLP 2024). This kit does not claim the question is novel. The contribution must be narrowed after reading these papers and comparing their released code, transformations, models, datasets, and metrics.

## Quick start
Recommended Python 3.10 or 3.11.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Run a small lexical-only smoke test:
```bash
python src/run_experiment.py --dataset scifact --max-queries 100 --methods bm25 --output-dir results/smoke
```

The first run downloads the chosen BEIR dataset, so network access is required. Depending on the dataset and settings, downloads and indexing can take time. The script defaults to original queries and deterministic lexical rewrites only; it does NOT pretend these rewrites are human-validated semantic paraphrases.

For the main study, create a validated rewrite JSONL file (schema below) and run:
```bash
python src/run_experiment.py --dataset scifact --rewrite-file data/validated_rewrites.jsonl --methods bm25 --output-dir results/scifact
```

The dataset loader and metric behavior can vary by package version; inspect output and package docs. Do not compare metrics from incompatible qrels or test splits.

## Rewrite file schema
One JSON object per line:
```json
{"qid":"query-id","rewrite_id":"q1_r1","category":"paraphrase","query":"rewritten query","meaning_preserved":true,"review_status":"human_verified"}
```
Use only rewrites that preserve the original information need. Record how they were generated, the model/version or annotator process, and how they were checked. Do not use a single LLM judge as unquestionable ground truth.

## Suggested staged experiment
1. Smoke test one dataset and BM25.
2. Validate that queries and qrels align.
3. Add dense retrieval only after checking hardware and model-download requirements.
4. Add hybrid fusion after both baselines run.
5. Evaluate multiple datasets and report each separately, not only an average.
6. Use paired query-level comparisons and bootstrap confidence intervals.
7. Hold out entire datasets/domains if training a degradation predictor.
8. Preserve logs, package versions, configs, and raw outputs.

## Publication ethics
- Do not invent results, citations, human annotation, or novelty.
- Cite prior work accurately and follow dataset/model licenses.
- If you are submitting to a peer-reviewed venue, check its current AI-use and authorship policies.
- An arXiv preprint is not peer review or conference acceptance.
- A human author must review, understand, and take responsibility for the work.
