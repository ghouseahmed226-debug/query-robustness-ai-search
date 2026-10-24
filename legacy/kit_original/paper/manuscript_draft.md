# Beyond Average Retrieval Scores: A Reproducible Cross-Domain Study of Query-Variation Robustness

**Authors:** [Add only people who made a substantial scholarly contribution and agree to authorship]  
**Affiliation:** [Institution or independent researcher affiliation, if appropriate]  
**Status:** Research manuscript draft — not ready for submission until experiments, literature review, and citations are verified.

## Abstract

Search systems are often evaluated using a fixed set of queries, although users may express the same information need in different ways. This study investigates how meaning-preserving query variations affect retrieval effectiveness and ranking stability across sparse, dense, and hybrid retrieval systems on public information-retrieval benchmarks. We plan to evaluate original queries and validated rewrites across multiple domains using nDCG@10, Recall@100, MRR@10 where applicable, and ranking-stability measures. Paired statistical analysis will estimate the uncertainty of observed changes. The intended contribution is a controlled, reproducible analysis of the interaction between transformation type, retrieval method, and domain. The precise novelty claim will be finalized only after a systematic comparison with existing query-variation robustness research. **Results are not yet available and must not be inferred or fabricated.**

**Keywords:** information retrieval; query variation; retrieval robustness; BM25; dense retrieval; hybrid search; evaluation; reproducibility

## 1. Introduction

Information retrieval systems map a user's query to a ranked list of documents. In practice, a single information need can be expressed with different words, syntax, levels of specificity, or paraphrases. A system that performs well on one formulation may behave differently when the wording changes, even when the intended information need is preserved.

Standard retrieval benchmarks provide essential common test collections, but a fixed query set cannot by itself characterize sensitivity to alternative formulations. Earlier work has studied query variability and retrieval consistency, and later work has investigated robustness of transformer-based retrieval models to query variations. Consequently, this paper does not treat query robustness as a new problem. Instead, it asks whether a carefully controlled, cross-domain analysis can identify reproducible interactions among transformation categories, retrieval families, and domains that are not adequately covered by prior evaluations.

The study will use public datasets and fixed retrieval baselines. It will preserve original relevance judgments, validate rewritten queries, report results per dataset, and separate retrieval effectiveness from ranking stability. The final contribution statement will be revised after reading the closest prior work and comparing the exact experimental scope.

### Research questions

- **RQ1:** How does retrieval effectiveness change under meaning-preserving query variations?
- **RQ2:** Do sparse, dense, and hybrid methods respond differently to transformation categories?
- **RQ3:** Does the effect vary across domains?
- **RQ4 (optional):** Can query-level features predict retrieval degradation on a held-out domain?

### Contributions (to be completed after validation)

Do not retain this section as a claim until the experiments are complete. Potential contributions, if supported, include:
1. A reproducible evaluation protocol for specified query-variation categories.
2. A cross-domain, paired comparison of specified retrieval methods.
3. An error analysis showing when retrieval effectiveness changes and whether ranking stability predicts those changes.
4. A tested degradation predictor that generalizes to unseen domains, if RQ4 is pursued.

## 2. Related Work

### 2.1 Query variability and ranking consistency

UQV100 is a test collection created to study query variability. Research on retrieval consistency has also developed metrics for comparing rankings produced for query variations. This work establishes that query formulation and ranking stability have been studied before. The present study must explain exactly how its transformations, evaluation design, or analysis differ.

### 2.2 Cross-domain retrieval evaluation

BEIR provides a heterogeneous benchmark for evaluating information retrieval systems across different tasks and domains. It is suitable for controlled cross-dataset evaluation, but using BEIR alone is not a novelty claim. Dataset selection, split discipline, query-variation design, and comparison with prior work must be justified.

### 2.3 Robustness of neural retrieval

Prior studies have examined robustness to typos and paraphrases, including work on transformer retrieval models and methods that align rankings across query variations. A recent study in Findings of EMNLP 2024 revisits robustness across modern dense retrievers and instruction-tuned language models. These are close related works and must be read in full before fixing the final research gap.

### 2.4 Gap and positioning

**Pending systematic review.** The defensible gap is not yet established. Before claiming one, create a comparison table covering the closest papers' datasets, transformation types, retrieval systems, metrics, statistical tests, released artifacts, and limitations. If the intended design is already covered, narrow the research question or choose a different topic.

## 3. Data and Materials

### 3.1 Candidate datasets

The primary candidate is BEIR. The final dataset list will be selected after checking dataset availability, licenses, query/relevance-label suitability, corpus size, and computational requirements. A small pilot should use two datasets; the main experiment should use a justified set of domains.

UQV100 and publicly released query-variation resources will be assessed as potential complementary resources. They must not be merged blindly with BEIR because topic IDs, corpus documents, queries, and relevance judgments may not align.

### 3.2 Query-variation construction

Each variation will have a query ID, rewrite ID, transformation category, source method, and validation status. Candidate categories include paraphrase, lexical substitution, syntactic change, and harder transformations that remain meaning-preserving. The final categories must be informed by prior work.

A sample of variations will be independently reviewed for preservation of the original information need. Invalid, ambiguous, or meaning-changing rewrites will be excluded under a documented rule. If an LLM generates rewrites, its name/version, prompt, decoding settings, and filtering process will be recorded. LLM judgments will not be treated as unquestionable ground truth.

### 3.3 Data splits and leakage

Official benchmark splits and relevance judgments will be respected. Any model or predictor tuned on some datasets will be evaluated on held-out datasets when the goal is to measure domain generalization. All exclusions and preprocessing steps will be logged.

## 4. Methods

### 4.1 Retrieval baselines

- **BM25:** lexical retrieval baseline.
- **Dense retrieval:** one fixed, documented pretrained embedding retriever.
- **Hybrid retrieval:** fusion of BM25 and dense rankings using Reciprocal Rank Fusion (RRF).
- **Optional cross-encoder:** included only if compute and time permit.

Model versions, tokenization, index settings, top-k cutoffs, hardware, and software versions will be reported. All methods will use comparable document collections and the same relevance judgments.

### 4.2 Evaluation

Primary effectiveness metrics:
- nDCG@10
- Recall@100
- MRR@10 where the task and judgments make it meaningful

For each query and rewrite, the analysis will calculate absolute and relative metric changes from the original query. Ranking stability will be reported separately using a preselected overlap or rank-sensitive metric. Stability is not a replacement for relevance: different rankings can be equally relevant.

### 4.3 Statistical analysis

Use paired query-level comparisons. Estimate uncertainty with paired bootstrap confidence intervals or an appropriate paired statistical test. Correct for multiple comparisons where appropriate. Report per-dataset results and avoid relying solely on one macro-average. Any predictor of degradation will use held-out domains and a prespecified evaluation protocol.

### 4.4 Reproducibility

Release scripts, environment versions, experiment configuration, and results where licensing permits. If datasets cannot be redistributed, provide instructions for obtaining them and scripts to recreate the derived data. Record random seeds where applicable and preserve run logs.

## 5. Experimental Results

**This section must be filled only after experiments are run. Do not invent or estimate results.**

### 5.1 Dataset and run summary

[Insert actual dataset names, number of queries, number of accepted rewrites per category, corpus sizes, and exclusions.]

### 5.2 Retrieval effectiveness

[Insert the measured nDCG@10, Recall@100, and MRR@10 results for each method and dataset. Include uncertainty intervals.]

### 5.3 Transformation-level analysis

[Insert actual paired changes by rewrite category and method. Report categories with no reliable difference as well as those with observed changes.]

### 5.4 Ranking stability

[Insert the selected ranking-stability results and explain whether stability changes correspond to changes in relevance effectiveness.]

### 5.5 Statistical tests

[Report test names, hypotheses, correction method, effect sizes, confidence intervals, and exact sample sizes.]

## 6. Discussion

[Interpret only results supported by the experiments. Compare findings with the closest prior studies. Discuss domain-specific effects, practical implications, alternative explanations, and any unexpected or null findings.]

## 7. Limitations

Potential limitations to assess and report include:
- Synthetic rewrites may not reflect the distribution of real user queries.
- Meaning preservation is difficult to verify perfectly.
- Benchmark relevance judgments may be incomplete.
- Results may depend on model versions, tokenization, retrieval parameters, and domain selection.
- Public benchmark results may not generalize to commercial search logs.
- Computation and the selected datasets may limit statistical power.
- Query-level observations are not necessarily independent; statistical procedures should account for the experimental structure.

## 8. Ethics and Responsible Use

Use public datasets in accordance with their licenses. Do not publish personal or sensitive information. Document the use of generative models. Follow the target venue's policies on authorship, AI assistance, originality, and simultaneous submissions. Authors must review and take responsibility for the final manuscript.

## 9. Conclusion

[Write after completing the experiments. Summarize the actual answer to each research question, the contribution supported by evidence, and the most important limitation.]

## References (initial candidates; verify details and cite the versions actually read)

1. Thakur, N., Reimers, N., Rücklé, A., Srivastava, A., & Gurevych, I. (2021). BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models. NeurIPS Datasets and Benchmarks. https://arxiv.org/abs/2104.08663
2. Bailey, P., Moffat, A., Scholer, F., & Thomas, P. (2016). UQV100: A Test Collection with Query Variability. SIGIR. https://www.microsoft.com/en-us/research/publication/uqv100-a-test-collection-with-query-variability/
3. Bailey, P., Moffat, A., Scholer, F., & Thomas, P. (2017). Retrieval Consistency in the Presence of Query Variations. SIGIR. https://www.microsoft.com/en-us/research/publication/retrieval-consistency-presence-query-variations/
4. Penha, G., Câmara, A., & Hauff, C. (2022). Evaluating the Robustness of Retrieval Pipelines with Query Variation Generators. ECIR. https://arxiv.org/abs/2111.13057
5. Hagen, T., Scells, H., & Potthast, M. (2024). Revisiting Query Variation Robustness of Transformer Models. Findings of EMNLP 2024. https://aclanthology.org/2024.findings-emnlp.248/

Verify each reference against the publisher/official record and expand the related-work list before submission.
