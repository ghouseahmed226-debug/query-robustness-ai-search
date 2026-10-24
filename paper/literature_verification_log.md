# Literature verification log

Status as of 23 October 2026. This replaces the kit's first screening note (17 October 2026), which is kept unchanged in
`legacy/kit_original/paper/literature_verification_log.md`.

## 1. What this log is, and what it is not

* It records, for every reference in `references.bib`, what was checked, where, and how deeply the source was read.
* It is **not** a systematic review. The searches were made with a general web search engine; results are titles and links only.
  DBLP could not be used (it refused automated access), and Google Scholar, the ACM Digital Library and Semantic Scholar search
  were not used.
* "Read through a summariser" means the full text was passed through a page-summarising tool, whose output can be wrong. Anything
  that rests on it is flagged in section 4 and must be checked by a human against the PDF.
* Fields that no record showed were left out of the bibliography instead of being guessed.

## 2. Searches

The searches that could be recovered are listed with dates and modes in Appendix A of the manuscript (Table 7): ten searches on
17 October 2026 (recovered from the log of the sub-agent that ran them; UTC times) and five more on 22 October 2026. The record of
searches made at the very start of the project was lost when the working session's context was compacted, so this record is
incomplete; a human author should repeat and log the search. Further searches and page reads on 22 and 23 October 2026 concerned arXiv's
policies (AI use, endorsement, submission rules, computer-science review articles) and the SIGIR 2027 call, not the literature.

Bibliographic look-ups were made on arXiv listing pages, the ACL Anthology, Crossref records (via the Crossref API), the Webis
publication anthology, publisher pages (Now Publishers, Emerald), RePEc and the GESIS knowledge graph. The exact pages consulted in the
first days of the project were not all preserved; where that is so it is stated below.

## 3. What was verified for each reference

| key | verified | source | reading level |
|:--|:--|:--|:--|
| penha2022 | title, authors, ECIR 2022, LNCS series, Springer, pp. 397-412, DOI; arXiv 2111.13057v3 (2022-02-15) | arXiv page; Crossref (volume number absent); authors' repository README says ECIR'22 | full text through a summariser (taxonomy, generators, datasets, systems, average loss, validation by the authors); LNCS volume number and editors not verified |
| hagen2024 | title, authors (Tim Hagen, Harrisen Scells, Martin Potthast), Findings of EMNLP 2024, Miami, pp. 4283-4296, DOI | ACL Anthology page; Crossref | abstract; full text through a summariser (scope: re-ranking stage; no hybrid/fusion found); authors' data repository |
| li2026 | title, authors, arXiv 2604.16576v1 (2026-04-17), cs.IR/cs.CL, no venue shown | arXiv listing | abstract only |
| percin2025 | title, authors, arXiv 2507.06956v1 (2025-07-09), cs.CL, no venue shown | arXiv listing | abstract only |
| campese2025 | title, authors; submission date and venue not shown on the page (year taken from the identifier) | arXiv listing | abstract summary only |
| sidiropoulos2022 | title, authors, SIGIR 2022 (45th), pp. 2132-2136, DOI | Crossref; arXiv 2205.02303v1 (2022-05-04) | record only |
| sidiropoulos2024 | title, authors, arXiv 2403.10939v1 (2024-03-16), no venue shown | arXiv listing | abstract only |
| zhuang2021 | title, authors, EMNLP 2021, pp. 2836-2842, DOI | ACL Anthology page | record only |
| zhuang2022 | title, authors (Shengyao Zhuang, Guido Zuccon), SIGIR 2022, pp. 1444-1454, DOI | Crossref | record only |
| tasawong2023 | title, six authors, ACL 2023 short papers, Toronto, pp. 1106-1115, DOI | ACL Anthology page | record only |
| alaofi2023 | title, five authors, SIGIR 2023 (46th), pp. 1869-1873, DOI | Crossref | record only; not read |
| bailey2016 | title (the Crossref record shows only "UQV100"), authors, SIGIR 2016, pp. 725-728, DOI | Webis anthology; Crossref | record only |
| bailey2017 | title, authors, SIGIR 2017, pp. 395-404, DOI | Webis anthology; Crossref | record only |
| moffat2015 | title, authors, CIKM 2015, pp. 1759-1762, DOI | Crossref | record only; not read |
| thakur2021 | title (spelled "Heterogenous" on the arXiv listing, version 4 of 2021-10-21, and "Heterogeneous" on the NeurIPS virtual-conference page; the bibliography follows the arXiv spelling), authors, NeurIPS 2021 Datasets and Benchmarks Track | arXiv listing; venue from a proceedings link returned by a search (not opened) | record only |
| cormack2009 | title, authors (Crossref spells the third "Stefan Buettcher"), SIGIR 2009, pp. 758-759, DOI | Crossref | record only |
| webber2010 | authors, ACM TOIS 28(4), 2010, DOI (Crossref shows pages 1-38 and no article number, so pages are omitted) | Crossref | record only |
| jarvelin2002 | ACM TOIS 20(4), pp. 422-446, 2002, DOI | bibliographic record (the exact page consulted was not preserved) | record only |
| robertson2009 | Foundations and Trends in IR 3(4), pp. 333-389, 2009, DOI. Crossref returned a record for this DOI with other volume, issue and page data (and a different publisher); it was disregarded in favour of the publisher's own page | Now Publishers page | record only |
| deerwester1990 | JASIS 41(6), pp. 391-407, September 1990 (DOI omitted: the page printed it with a rendering error) | RePEc | record only |
| porter1980 | Program 14(3), pp. 130-137, 1980, DOI 10.1108/eb046814 | Emerald page | record only |
| holm1979 | title, Scandinavian Journal of Statistics 6(2), pp. 65-70, 1979. The author "Holm, S." is inferred from the record's identifier, not shown as text | GESIS knowledge-graph record | record only |
| smucker2007 | title, authors, CIKM 2007, pp. 623-632, DOI | Crossref | record only; not read |
| vangysel2018 | title, authors, SIGIR 2018, pp. 873-876, DOI | Webis anthology (the Crossref request returned an error) | record only |
| irdatasets_vaswani | 11,429 documents, 93 queries, 2,083 judgments; no licence or citation stated | page fetched 2026-10-20 | page |
| glasgow_npl | page exists and describes the collection; states no counts, citation or licence; carries a caution about the collection (read through a summariser) | page read in October 2026 | page |
| arxiv_ai_policy | policy sentences quoted in the manuscript | arXiv blog post, fetched 2026-10-22 | post |

## 4. Claims in the manuscript that rest on a summariser or on an abstract

These must be checked by a human before anything is submitted:

* Penha et al.: the roughly 20% average loss; BM25 followed by neural re-rankers on two collections; no dense or hybrid retrievers (summariser).
* Hagen et al.: scope (re-ranking stage, models listed in the abstract); no hybrid or fusion evaluation (summariser).
* Li et al.: LLM-based dense retrievers are more robust to typos than encoder-only baselines but vulnerable to synonym substitution (abstract).
* Percin et al.: retrievers in retrieval-augmented generation degrade under minor query variations (abstract).
* Campese et al.: a loss that penalises differences between the top-k lists of equivalent queries (abstract summary).
* The gap statement itself: that none of the sources read evaluates a fused lexical-semantic first stage next to its components under the Penha et al. categories.

## 5. Differences from the kit's reference list

* Hagen et al. is cited with the authors as the ACL Anthology prints them (Tim Hagen, Harrisen Scells, Martin Potthast).
* BEIR's title is spelled differently on arXiv and on the NeurIPS page (see above); the kit used the NeurIPS spelling.
* UQV100's SIGIR 2016 and the consistency paper's SIGIR 2017 pages and DOIs were added.
* Three items in the kit's log (Weller et al. 2024; Park and Lee 2024; Hong et al. 2024) were not verified and are not used.
* The kit's links to Microsoft Research pages were replaced by DOIs and venue records.

## 6. Seen only by title, not read, not relied on

arXiv 2306.12756 and 2412.18768 (generative retrieval robustness); 2604.10745 (adaptive RAG robustness to query variations);
2604.03676 (LLM-based retrievers on BRIGHT, including query perturbations); 2407.12529 and 2603.13301 (query rewriting);
2508.17644 (demographically inspired LLM query variants); 2608.25245 (LLM query simulation); 1408.3587 (rank-similarity measures);
"Out-of-Domain Semantics to the Rescue! Zero-Shot Hybrid Retrieval Models" (ECIR 2022).

## 7. Still to do

1. Read the full text of the closest papers (Penha et al.; Hagen et al.; Li et al.; Percin et al.) and the follow-up literature that cites them.
2. Search again systematically (several databases, written queries, inclusion rules) and look specifically for 2025-2026 work on hybrid
   or fused retrievers under query variation before keeping the gap statement.
3. Re-check every bibliographic field against the publisher record; add missing volume numbers and page ranges where a record shows them.
