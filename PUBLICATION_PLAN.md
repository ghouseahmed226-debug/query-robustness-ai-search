# Publication route (updated 23 October 2026)

The first version of this file (written before the experiments) is kept in `legacy/kit_original/PUBLICATION_PLAN.md`.

## Where things stand

The pilot is done and verified as far as software and numbers go (`results/verification_report.md`, 28 checks, all passing on the
last run), but as a *paper* it is a small result: one old collection, no neural retriever, no human-verified rewrites, and a literature
search that was not systematic. Its honest framing is "a reproducible pilot and a transparent pipeline". It does **not** show that a hybrid
of a lexical and a neural retriever is more robust than either, which was the question that motivated it.

A human has to decide what to do with it. Nothing has been submitted anywhere, and an AI system cannot submit or be an author.

## Options

1. **Extend, then submit to a peer-reviewed venue (the stronger route).** Run the neural and BEIR experiments (`docs/RUN_BEIR_LOCALLY.md`), have humans validate the
   rewrites (`scripts/audit_tool.py`), redo the literature search systematically, and have a mentor or experienced researcher review the design and claims first.
   SIGIR 2027 full papers, from its call page read on 23 October 2026: dates are **proposed** (abstract 14 January 2027, full paper 21 January 2027), at most 9 pages
   plus unrestricted references, double-anonymous review, compliance with the ACM policy on AI use required, and **no change to the author list after the abstract deadline**. Preprints are allowed by exception;
   read the page's own preprint rules before posting anything. The ECIR 2027 dates given in the original kit (21 September and 5 October 2026) have passed; it was not re-checked.
2. **Post the verified pilot as an arXiv preprint.** Only after a human author has read and verified everything and accepted responsibility. A preprint is not peer review. If a
   conference submission is planned, check that venue's rules on prior preprints first.
3. **Workshop or short-paper venues** were not researched; look at current calls if this is of interest.

## arXiv rules that matter here (read on arXiv's own pages, 22 and 23 October 2026; re-check when submitting)

* Generative AI tools may not be listed as authors; the human authors take full responsibility for all contents "irrespective of how the contents were generated",
  and significant use of such tools should be reported (arXiv blog, 31 January 2023, by Kat Boboris).
* "Authors are expected to self-submit." Only registered authors can submit (arXiv submission help page). So the human author must make the submission.
* Submissions should be TeX/LaTeX source (PDFs generated from TeX are not accepted) with figures included; the author grants arXiv an irrevocable licence to distribute
  (same page). `paper/arxiv_source/` is a stand-alone LaTeX source for this; compile it yourself before uploading.
* Endorsement: since 21 January 2026 an institutional email address alone no longer qualifies a new author for endorsement. Automatic endorsement now needs both an
  institutional email and previous authorship in the endorsement domain; otherwise personal endorsement from an established arXiv author in the same domain is
  required, and arXiv staff cannot waive it (arXiv blog, 21 January 2026; arXiv endorsement help page).
* The October 2025 requirement that computer-science review articles and position papers have passed peer review first does not apply to empirical research
  papers (arXiv blog, 31 October 2025).

## Checklist before any submission

1. Read the whole manuscript, code and data; re-run `pytest` and `python scripts/verify_results.py`.
2. Check every reference against the paper itself (`paper/literature_verification_log.md` lists what was and was not read).
3. Write your own contribution and AI-use statements (the manuscript's section 8 is a draft for you to replace).
4. Decide the author list yourself; only people who contributed substantially, have read the work and accept responsibility belong on it.
5. Choose and add a licence for the repository and decide whether the rewrites and results may be released.
6. Compile `paper/arxiv_source/` locally, read the PDF, and only then submit.

## Official links

* arXiv submission help: https://info.arxiv.org/help/submit/index.html
* arXiv endorsement: https://info.arxiv.org/help/endorsement.html
* SIGIR 2027 full-paper call: https://sigir2027.org/pages/submit-full.html
* ECIR 2027 full-paper call: https://www.ecir2027.co.uk/call-for-full-papers
