#!/usr/bin/env python
"""Fill ``paper/manuscript_template.md`` with numbers read from the result files.

    python scripts/build_paper.py                       # writes paper/manuscript_draft.md (+ .numbers.json)
    python scripts/build_paper.py --check               # only checks; writes nothing

Every number that comes from an experiment is written in the template as a placeholder, for example
``{{p:bm25/misspelling/ndcg@10_rel|pct1}}``, and this script replaces it with the value stored in the CSV / JSON result
files, so no experimental number in the manuscript is typed by hand. Placeholder grammar::

    {{SOURCE:path/to/value|FORMAT}}      value lookups
    {{TABLE:name}}                       a whole table, built from the result files

SOURCE is one of
    m   results/vaswani_pilot/run_metadata.json          (path = keys joined by "/")
    mr  results/vaswani_pilot_reviewer_only/run_metadata.json
    a   results/vaswani_pilot/analysis/analysis_parameters.json
    b   summary_baseline.csv                             (system/column)
    p   summary_primary.csv                              (system/category/column)
    pr  the same file of the reviewer-only run
    g   summary_by_generator.csv                         (system/generator/column)
    h   summary_hybrid_vs_components.csv                 (component/category/{diff,diff_lo,diff_hi})
    s   summary_stability_vs_effectiveness.csv           (system/{rho,rho_lo,rho_hi,n_pairs})
    sr  the same file of the reviewer-only run
    rw  data/rewrites/vaswani_rewrites_review_summary.json
    x   quantities computed here from data/rewrites/vaswani_rewrites.jsonl (and x:n_tests = number of collected tests)

The build also (1) checks that the rewrite counts in the rewrite file equal the counts recorded in run_metadata.json,
and (2) evaluates ``CLAIMS``: every qualitative sentence in the template that depends on the data ("all three
intervals exclude zero", "paraphrasing moves the top 10 more than misspelling", ...) is an assertion here, so the build
fails if the data stop supporting the prose. Nothing is left unresolved: a missing key or a leftover ``{{`` is an error.
``<out>.numbers.json`` lists every placeholder with the string it was replaced by.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MINUS = "−"
SYSTEM_LABEL = {"bm25": "BM25", "lsa": "LSA", "rrf_bm25_lsa": "RRF hybrid"}
SYSTEMS = list(SYSTEM_LABEL)
CATEGORIES = ["misspelling", "paraphrasing", "naturality", "ordering"]
GENERATORS = [  # (category, generator, produced by, validity basis)
    ("misspelling", "NeighbCharSwap", "seeded code", "by construction"),
    ("misspelling", "RandomCharSub", "seeded code", "by construction"),
    ("misspelling", "QWERTYCharSub", "seeded code", "by construction"),
    ("paraphrasing", "LLM_Paraphrase", "AI assistant", "LLM review"),
    ("paraphrasing", "LLM_SynonymSwap", "AI assistant", "LLM review"),
    ("naturality", "LLM_NaturalQuestion", "AI assistant", "LLM review"),
    ("naturality", "RemoveStopWords", "code", "LLM review + assistant recheck"),
    ("ordering", "RandomOrderSwap", "seeded code", "LLM review + function-word rule"),
]


# --------------------------------------------------------------------------------------------- loading
def load_run(root: Path) -> dict:
    a = root / "analysis"
    hyb = pd.read_csv(a / "summary_hybrid_vs_components.csv").rename(
        columns={"diff_in_absolute_ndcg@10_change": "diff", "lo": "diff_lo", "hi": "diff_hi"})
    stab = pd.read_csv(a / "summary_stability_vs_effectiveness.csv").rename(
        columns={"spearman_rbo_vs_abs_delta_ndcg@10": "rho", "lo": "rho_lo", "hi": "rho_hi"})
    return {
        "meta": json.loads((root / "run_metadata.json").read_text()),
        "params": json.loads((a / "analysis_parameters.json").read_text()),
        "b": pd.read_csv(a / "summary_baseline.csv").set_index("system"),
        "p": pd.read_csv(a / "summary_primary.csv").set_index(["system", "category"]),
        "g": pd.read_csv(a / "summary_by_generator.csv").set_index(["system", "generator"]),
        "h": hyb.set_index(["component", "category"]),
        "s": stab.set_index("system"),
    }


def load_all(root: Path) -> dict:
    main = load_run(root / "results" / "vaswani_pilot")
    rev = load_run(root / "results" / "vaswani_pilot_reviewer_only")
    records = [json.loads(line) for line in (root / "data/rewrites/vaswani_rewrites.jsonl").read_text().splitlines() if line.strip()]
    return {"main": main, "rev": rev, "records": records,
            "rw": json.loads((root / "data/rewrites/vaswani_rewrites_review_summary.json").read_text())}


# --------------------------------------------------------------------------------------------- formatting
def _num(x: float, nd: int, plus: bool = False) -> str:
    s = f"{x:.{nd}f}"
    if float(s) == 0:
        s = s.lstrip("-")
        return s if not plus else s  # zero carries no sign
    if s.startswith("-"):
        return MINUS + s[1:]
    return ("+" + s) if plus else s


def _p(p: float, table: bool = False) -> str:
    if p < 0.001:
        return "<0.001" if table else "p < 0.001"
    if p >= 0.9995:
        return "1.00" if table else "p = 1.00"
    return f"{p:.3f}" if table else f"p = {p:.3f}"


def fmt_scalar(v, fmt: str) -> str:
    if fmt == "str":
        return str(v)
    if fmt == "int":
        return f"{int(round(float(v))):,}"
    if fmt in {"f2", "f3", "f4"}:
        return _num(float(v), int(fmt[1]))
    if fmt == "f3s":
        return _num(float(v), 3, plus=True)
    if fmt == "pct1":
        return _num(100 * float(v), 1) + "%"
    if fmt == "pct1s":
        return _num(100 * float(v), 1, plus=True) + "%"
    if fmt == "pct1abs":
        return f"{abs(100 * float(v)):.1f}%"
    if fmt == "peq":
        return _p(float(v))
    if fmt == "p":
        return _p(float(v), table=True)
    if fmt == "sci":
        return f"{float(v):.1e}"
    if fmt == "h16":
        return str(v)[:16]
    if fmt == "pyver":
        return str(v).split()[0]
    raise KeyError(f"unknown format {fmt!r}")


def fmt_row(row, col: str, fmt: str) -> str:
    """Formats that need the interval columns ``col_lo`` / ``col_hi`` of the same row."""
    v, lo, hi = float(row[col]), float(row[col + "_lo"]), float(row[col + "_hi"])
    if fmt == "pctci":
        return f"{_num(100*v,1)}% (95% CI {_num(100*lo,1)}% to {_num(100*hi,1)}%)"
    if fmt == "pctci_t":
        return f"{_num(100*v,1)} [{_num(100*lo,1)}, {_num(100*hi,1)}]"
    if fmt == "f3ci":
        return f"{_num(v,3)} (95% CI {_num(lo,3)} to {_num(hi,3)})"
    if fmt == "f3ci_t":
        return f"{_num(v,3)} [{_num(lo,3)}, {_num(hi,3)}]"
    if fmt == "f3sci_t":
        return f"{_num(v,3,plus=True)} [{_num(lo,3,plus=True)}, {_num(hi,3,plus=True)}]"
    if fmt == "f2ci_t":
        return f"{_num(v,2)} [{_num(lo,2)}, {_num(hi,2)}]"
    if fmt == "f2sci":
        return f"{_num(v,2)} (95% CI {_num(lo,2)} to {_num(hi,2)})"
    return fmt_scalar(v, fmt)


CI_FORMATS = {"pctci", "pctci_t", "f3ci", "f3ci_t", "f3sci_t", "f2ci_t", "f2sci"}


def count_tests() -> int:
    """Number of collected tests (parametrised cases included), so the text never quotes a stale count."""
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", str(ROOT / "tests")],
                         capture_output=True, text=True, cwd=ROOT)
    m = re.search(r"(\d+) tests? collected", out.stdout)
    if m:
        return int(m.group(1))
    per_file = [int(x) for x in re.findall(r"^\S+\.py: (\d+)$", out.stdout, re.M)]
    if per_file:
        return sum(per_file)
    n = len([line for line in out.stdout.splitlines() if "::" in line])
    if n:
        return n
    raise SystemExit("cannot count the tests (is pytest installed? pip install -e '.[test]')")


# --------------------------------------------------------------------------------------------- placeholders
class Resolver:
    def __init__(self, data: dict):
        self.d = data
        self.log: list[dict] = []
        self.extras = self._extras()

    def _extras(self) -> dict:
        recs = self.d["records"]
        cand = Counter(r["generator"] for r in recs)
        kept = Counter(r["generator"] for r in recs if r["meaning_preserved"])
        out = {"n_candidates": len(recs), "n_kept": sum(kept.values()), "n_dropped": len(recs) - sum(kept.values())}
        for g in cand:
            out[f"cand/{g}"] = cand[g]
            out[f"kept/{g}"] = kept.get(g, 0)
            out[f"dropped/{g}"] = cand[g] - kept.get(g, 0)
        auto = {"NeighbCharSwap", "RandomCharSub", "QWERTYCharSub", "RandomOrderSwap", "RemoveStopWords"}
        out["n_machine_candidates"] = sum(cand[g] for g in auto)
        out["n_assistant_written"] = sum(c for g, c in cand.items() if g.startswith("LLM_"))
        share = self.d["rw"]["typo_share_with_edited_word_in_collection_vocab"]
        out["typo_vocab_hits"] = sum(v[0] for v in share.values())
        out["typo_total"] = sum(v[1] for v in share.values())
        out["rewrites_with_status/llm_reviewed"] = sum(1 for r in recs if r["review_status"] == "llm_reviewed" and r["meaning_preserved"])
        out["rewrites_with_status/automatic"] = sum(1 for r in recs if r["review_status"] == "automatic_by_construction" and r["meaning_preserved"])
        return out

    def lookup(self, src: str, path: str, fmt: str) -> str:
        keys = path.split("/")
        if src in {"m", "mr"}:
            node = self.d["main" if src == "m" else "rev"]["meta"]
            for k in keys:
                node = node[k]
            return fmt_scalar(node, fmt)
        if src == "a":
            node = self.d["main"]["params"]
            for k in keys:
                node = node[k]
            return fmt_scalar(node, fmt)
        if src == "rw":
            node = self.d["rw"]
            for k in keys:
                node = node[k]
            return fmt_scalar(node, fmt)
        if src == "x":
            if path == "n_tests":
                return fmt_scalar(count_tests(), fmt)
            return fmt_scalar(self.extras[path], fmt)
        run = self.d["rev" if src in {"pr", "sr"} else "main"]
        table = {"b": "b", "p": "p", "pr": "p", "g": "g", "h": "h", "s": "s", "sr": "s"}[src]
        df = run[table]
        if table in {"p", "g", "h"}:
            key, col = (keys[0], keys[1]), keys[2]
        else:
            key, col = keys[0], keys[1]
        row = df.loc[key]
        if fmt in CI_FORMATS:
            return fmt_row(row, col, fmt)
        return fmt_scalar(row[col], fmt)

    def sub(self, text: str) -> str:
        def repl(m: re.Match) -> str:
            body = m.group(1).strip()
            if body.startswith("TABLE:"):
                name = body.split(":", 1)[1]
                out = TABLES[name](self.d, self.extras)
                self.log.append({"placeholder": m.group(0), "value": f"<table {name}>"})
                return out
            try:
                lhs, fmt = body.rsplit("|", 1)
                src, path = lhs.split(":", 1)
                val = self.lookup(src, path, fmt)
            except Exception as exc:  # noqa: BLE001 - report the offending placeholder
                raise SystemExit(f"cannot resolve placeholder {m.group(0)!r}: {type(exc).__name__}: {exc}")
            self.log.append({"placeholder": m.group(0), "value": val})
            return val

        return re.sub(r"\{\{([^{}]+)\}\}", repl, text)


# --------------------------------------------------------------------------------------------- tables
def _pipe_table(header: list[str], rows: list[list[str]], widths: list[int], align: list[str], caption: str) -> str:
    sep = []
    for w, a in zip(widths, align):
        dashes = "-" * max(w, 3)
        sep.append(":" + dashes if a == "l" else (dashes + ":" if a == "r" else ":" + dashes + ":"))
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(sep) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines) + f"\n\nTable: {caption}\n"


def table_rewrites(d, x):
    rows = []
    for cat, gen, by, basis in GENERATORS:
        rows.append([cat, f"`{gen}`", by, str(x[f"cand/{gen}"]), str(x[f"kept/{gen}"]), basis])
    rows.append(["**all**", "", "", f"**{x['n_candidates']}**", f"**{x['n_kept']}**", ""])
    return _pipe_table(["Category", "Generator", "Produced by", "Candidates", "Kept", "Basis of validity"], rows,
                       [11, 24, 12, 10, 6, 26], ["l", "l", "l", "r", "r", "l"],
                       "Table 1. Query rewrites by generator. *Candidates* are all rewrites produced; *kept* are those used in the analysis. "
                       "No rewrite is human-verified (Section 3.3).")


def table_baseline(d, x):
    b = d["main"]["b"]
    rows = [[SYSTEM_LABEL[s], fmt_row(b.loc[s], "ndcg@10", "f3ci_t"), fmt_row(b.loc[s], "recall@100", "f3ci_t"),
             fmt_row(b.loc[s], "mrr@10", "f3ci_t")] for s in SYSTEMS]
    return _pipe_table(["System", "nDCG@10", "Recall@100", "MRR@10"], rows, [12, 24, 24, 24], ["l", "r", "r", "r"],
                       "Table 2. Effectiveness on the original queries (93 queries, Vaswani). Mean and 95% percentile bootstrap interval over "
                       "queries (10,000 resamples).")


def table_primary(d, x):
    p = d["main"]["p"]
    rows = []
    for s in SYSTEMS:
        for c in CATEGORIES:
            r = p.loc[(s, c)]
            rows.append([SYSTEM_LABEL[s], c, f"{int(r['n_queries'])} / {int(r['n_rewrites'])}", _num(r["ndcg@10_orig"], 3),
                         _num(r["ndcg@10_rewrite"], 3), fmt_row(r, "ndcg@10_rel", "pctci_t"), fmt_scalar(r["p_holm"], "p")])
    return _pipe_table(["System", "Category", "Queries / rewrites", "nDCG@10 original", "nDCG@10 rewrites",
                        "Relative change, % [95% CI]", "Holm $p$"], rows, [12, 13, 10, 9, 9, 24, 8],
                       ["l", "l", "r", "r", "r", "r", "r"],
                       "Table 3. Effect of query-variation categories on nDCG@10 (primary analysis, 12 tests). Original and rewrite columns are means over "
                       "the queries that have at least one kept rewrite in the category (each query counts once per category). Relative change is the "
                       "ratio of the two means minus one; the interval is a cluster bootstrap over original queries. Holm $p$ comes from a "
                       "two-sided sign-flip permutation test, adjusted over the 12 tests.")


def table_stability(d, x):
    p = d["main"]["p"]
    rows = []
    for s in SYSTEMS:
        for c in CATEGORIES:
            r = p.loc[(s, c)]
            rows.append([SYSTEM_LABEL[s], c, fmt_row(r, "overlap@10", "f2ci_t"), fmt_row(r, "rbo_p0.9", "f2ci_t")])
    return _pipe_table(["System", "Category", "Overlap@10 [95% CI]", "RBO, $p$ = 0.9 [95% CI]"], rows, [12, 13, 24, 24],
                       ["l", "l", "r", "r"],
                       "Table 4. Ranking stability: agreement between the ranking for the original query and the ranking for its rewrite, from the same system "
                       "(1 = identical top 10 / identical ranking; mean over queries, cluster-bootstrap interval).")


def table_generator(d, x):
    g = d["main"]["g"]
    rows = []
    for cat, gen, _, _ in GENERATORS:
        n = int(g.loc[("bm25", gen)]["n_rewrites"])
        rows.append([cat, f"`{gen}`", str(n)] + [fmt_row(g.loc[(s, gen)], "ndcg@10_rel", "pctci_t") for s in SYSTEMS])
    return _pipe_table(["Category", "Generator", "Rewrites", "BM25", "LSA", "RRF hybrid"], rows, [11, 20, 8, 22, 22, 22],
                       ["l", "l", "r", "r", "r", "r"],
                       "Table 5. Relative change in nDCG@10 (%) by generator, with 95% cluster-bootstrap intervals. Descriptive only; these 24 cells are not part of "
                       "the multiplicity-corrected family.")


def table_hybrid(d, x):
    h = d["main"]["h"]
    rows = []
    for c in CATEGORIES:
        rows.append([c, fmt_row(h.loc[("bm25", c)], "diff", "f3sci_t"), fmt_row(h.loc[("lsa", c)], "diff", "f3sci_t")])
    return _pipe_table(["Category", "RRF hybrid minus BM25", "RRF hybrid minus LSA"], rows, [13, 30, 30], ["l", "r", "r"],
                       "Table 6. Exploratory comparison of the hybrid with its components: mean per-query difference in the *absolute* nDCG@10 change "
                       "(hybrid minus component) with a 95% cluster-bootstrap interval. Positive means the hybrid lost less (or gained more) than the "
                       "component. No test, no multiplicity correction.")


TABLES = {"rewrites": table_rewrites, "baseline": table_baseline, "primary": table_primary, "stability": table_stability,
          "generator": table_generator, "hybrid": table_hybrid}


# --------------------------------------------------------------------------------------------- integrity checks
def check_counts(d) -> list[str]:
    errs = []
    meta = d["main"]["meta"]
    recs = d["records"]
    kept_by_gen = Counter(r["generator"] for r in recs if r["meaning_preserved"])
    if dict(kept_by_gen) != meta["counts"]["rewrites_kept_by_generator"]:
        errs.append(f"kept by generator differs: file {dict(kept_by_gen)} vs metadata {meta['counts']['rewrites_kept_by_generator']}")
    if sum(kept_by_gen.values()) != meta["counts"]["rewrites_kept"]:
        errs.append("total kept differs from metadata")
    if len(recs) - sum(kept_by_gen.values()) != sum(meta["counts"]["rewrites_dropped"].values()):
        errs.append("dropped count differs from metadata")
    cat_by_gen = {r["generator"]: r["category"] for r in recs}
    for cat, gen, _, _ in GENERATORS:
        if cat_by_gen.get(gen) != cat:
            errs.append(f"generator {gen} has category {cat_by_gen.get(gen)} in the data, template assumes {cat}")
    kept_by_cat = Counter(r["category"] for r in recs if r["meaning_preserved"])
    if dict(kept_by_cat) != meta["counts"]["rewrites_kept_by_category"]:
        errs.append("kept by category differs from metadata")
    for s in SYSTEMS:
        for c in CATEGORIES:
            n = int(d["main"]["p"].loc[(s, c)]["n_rewrites"])
            if n != kept_by_cat[c]:
                errs.append(f"primary table n_rewrites {s}/{c} = {n}, rewrite file says {kept_by_cat[c]}")
    if meta["analysis_plan_sha256"] if "analysis_plan_sha256" in meta else False:
        pass
    return errs


def claims(d) -> list[tuple[str, bool]]:
    m, r = d["main"], d["rev"]
    P, G, B, H, S = m["p"], m["g"], m["b"], m["h"], m["s"]
    ci = lambda row: (row["ndcg@10_rel_lo"], row["ndcg@10_rel_hi"])
    excl0 = lambda row: ci(row)[1] < 0 or ci(row)[0] > 0
    out = []
    out.append(("misspelling: every system has Holm p < 0.001", all(P.loc[(s, "misspelling")]["p_holm"] < 0.001 for s in SYSTEMS)))
    out.append(("misspelling: every system's CI excludes 0 and the change is negative",
                all(excl0(P.loc[(s, "misspelling")]) and P.loc[(s, "misspelling")]["ndcg@10_rel"] < 0 for s in SYSTEMS)))
    out.append(("misspelling: relative losses lie between 18% and 22%",
                all(-0.22 < P.loc[(s, "misspelling")]["ndcg@10_rel"] < -0.18 for s in SYSTEMS)))
    out.append(("paraphrasing/BM25: CI excludes 0 and Holm p < 0.05", excl0(P.loc[("bm25", "paraphrasing")]) and P.loc[("bm25", "paraphrasing")]["p_holm"] < 0.05))
    out.append(("paraphrasing/LSA: CI covers 0 and Holm p > 0.05", not excl0(P.loc[("lsa", "paraphrasing")]) and P.loc[("lsa", "paraphrasing")]["p_holm"] > 0.05))
    out.append(("paraphrasing/RRF: CI excludes 0, raw p < 0.05, Holm p > 0.05",
                excl0(P.loc[("rrf_bm25_lsa", "paraphrasing")]) and P.loc[("rrf_bm25_lsa", "paraphrasing")]["p_signflip"] < 0.05
                and P.loc[("rrf_bm25_lsa", "paraphrasing")]["p_holm"] > 0.05))
    out.append(("naturality: all |relative change| < 2% and all CIs cover 0",
                all(abs(P.loc[(s, "naturality")]["ndcg@10_rel"]) < 0.02 and not excl0(P.loc[(s, "naturality")]) for s in SYSTEMS)))
    out.append(("ordering: exactly zero change and overlap 1 for every system and n = 8",
                all(P.loc[(s, "ordering")]["ndcg@10_rel"] == 0 and P.loc[(s, "ordering")]["overlap@10"] == 1 and P.loc[(s, "ordering")]["n_rewrites"] == 8 for s in SYSTEMS)))
    out.append(("paraphrasing moves the top 10 more than misspelling (lower overlap@10) for every system",
                all(P.loc[(s, "paraphrasing")]["overlap@10"] < P.loc[(s, "misspelling")]["overlap@10"] for s in SYSTEMS)))
    out.append(("paraphrasing costs less nDCG@10 than misspelling (point estimates) for every system",
                all(P.loc[(s, "paraphrasing")]["ndcg@10_rel"] > P.loc[(s, "misspelling")]["ndcg@10_rel"] for s in SYSTEMS)))
    out.append(("misspelling: the three systems' intervals overlap pairwise",
                all(max(P.loc[(a, "misspelling")]["ndcg@10_rel_lo"], P.loc[(b, "misspelling")]["ndcg@10_rel_lo"])
                    <= min(P.loc[(a, "misspelling")]["ndcg@10_rel_hi"], P.loc[(b, "misspelling")]["ndcg@10_rel_hi"])
                    for a in SYSTEMS for b in SYSTEMS)))
    out.append(("after rewriting, BM25 > RRF > LSA in nDCG@10 for misspelling, paraphrasing and naturality",
                all(P.loc[("bm25", c)]["ndcg@10_rewrite"] > P.loc[("rrf_bm25_lsa", c)]["ndcg@10_rewrite"] > P.loc[("lsa", c)]["ndcg@10_rewrite"]
                    for c in ("misspelling", "paraphrasing", "naturality"))))
    out.append(("Recall@100: misspelling and paraphrasing intervals exclude 0 for every system",
                all(P.loc[(s, c)]["recall@100_rel_hi"] < 0 for s in SYSTEMS for c in ("misspelling", "paraphrasing"))))
    out.append(("MRR@10: paraphrasing intervals cover 0 for every system",
                all(P.loc[(s, "paraphrasing")]["mrr@10_rel_lo"] < 0 < P.loc[(s, "paraphrasing")]["mrr@10_rel_hi"] for s in SYSTEMS)))
    out.append(("typo generators: all relative nDCG@10 changes lie between -26% and -15%",
                all(-0.26 < G.loc[(s, g)]["ndcg@10_rel"] < -0.15 for s in SYSTEMS for g in ("NeighbCharSwap", "RandomCharSub", "QWERTYCharSub"))))
    out.append(("naturality generators: |relative nDCG@10 change| < 2% for every system",
                all(abs(G.loc[(s, g)]["ndcg@10_rel"]) < 0.02 for s in SYSTEMS for g in ("LLM_NaturalQuestion", "RemoveStopWords"))))
    out.append(("LSA interval is separated from BM25's but overlaps the hybrid's on the original queries",
                B.loc["lsa"]["ndcg@10_hi"] < B.loc["bm25"]["ndcg@10_lo"] and B.loc["lsa"]["ndcg@10_hi"] > B.loc["rrf_bm25_lsa"]["ndcg@10_lo"]))
    out.append(("hybrid's original-query nDCG@10 is below BM25's and its paraphrased level is below BM25's",
                B.loc["rrf_bm25_lsa"]["ndcg@10"] < B.loc["bm25"]["ndcg@10"]
                and P.loc[("rrf_bm25_lsa", "paraphrasing")]["ndcg@10_rewrite"] < P.loc[("bm25", "paraphrasing")]["ndcg@10_rewrite"]))
    out.append(("baseline ordering BM25 > RRF > LSA in nDCG@10", B.loc["bm25"]["ndcg@10"] > B.loc["rrf_bm25_lsa"]["ndcg@10"] > B.loc["lsa"]["ndcg@10"]))
    out.append(("BM25 baseline CI overlaps the RRF CI (difference not established)",
                B.loc["bm25"]["ndcg@10_lo"] < B.loc["rrf_bm25_lsa"]["ndcg@10_hi"]))
    out.append(("hybrid sits between its components in relative misspelling change",
                min(P.loc[("bm25", "misspelling")]["ndcg@10_rel"], P.loc[("lsa", "misspelling")]["ndcg@10_rel"]) <= P.loc[("rrf_bm25_lsa", "misspelling")]["ndcg@10_rel"]
                <= max(P.loc[("bm25", "misspelling")]["ndcg@10_rel"], P.loc[("lsa", "misspelling")]["ndcg@10_rel"])))
    out.append(("hybrid sits between its components in relative paraphrasing change",
                min(P.loc[("bm25", "paraphrasing")]["ndcg@10_rel"], P.loc[("lsa", "paraphrasing")]["ndcg@10_rel"]) <= P.loc[("rrf_bm25_lsa", "paraphrasing")]["ndcg@10_rel"]
                <= max(P.loc[("bm25", "paraphrasing")]["ndcg@10_rel"], P.loc[("lsa", "paraphrasing")]["ndcg@10_rel"])))
    out.append(("hybrid vs BM25, paraphrasing: interval above 0", H.loc[("bm25", "paraphrasing")]["diff_lo"] > 0))
    out.append(("hybrid vs BM25, misspelling: interval covers 0", H.loc[("bm25", "misspelling")]["diff_lo"] < 0 < H.loc[("bm25", "misspelling")]["diff_hi"]))
    out.append(("hybrid vs LSA, misspelling: interval below 0", H.loc[("lsa", "misspelling")]["diff_hi"] < 0))
    out.append(("hybrid vs LSA, paraphrasing: interval covers 0", H.loc[("lsa", "paraphrasing")]["diff_lo"] < 0 < H.loc[("lsa", "paraphrasing")]["diff_hi"]))
    out.append(("Spearman(RBO, |dnDCG|) negative with CI below 0 for all systems", all(S.loc[s]["rho_hi"] < 0 for s in SYSTEMS)))
    out.append(("by generator: SynonymSwap hurts BM25 more than LLM_Paraphrase",
                G.loc[("bm25", "LLM_SynonymSwap")]["ndcg@10_rel"] < G.loc[("bm25", "LLM_Paraphrase")]["ndcg@10_rel"]))
    out.append(("by generator: LLM_Paraphrase on LSA is not distinguishable from 0",
                G.loc[("lsa", "LLM_Paraphrase")]["ndcg@10_rel_lo"] < 0 < G.loc[("lsa", "LLM_Paraphrase")]["ndcg@10_rel_hi"]))
    out.append(("by generator: SynonymSwap is the most damaging non-typo generator for every system",
                all(G.loc[(s, "LLM_SynonymSwap")]["ndcg@10_rel"] < min(G.loc[(s, g)]["ndcg@10_rel"] for g in ("LLM_Paraphrase", "LLM_NaturalQuestion", "RemoveStopWords")) for s in SYSTEMS)))
    out.append(("by generator: QWERTYCharSub is the most damaging typo generator for every system",
                all(G.loc[(s, "QWERTYCharSub")]["ndcg@10_rel"] < min(G.loc[(s, g)]["ndcg@10_rel"] for g in ("NeighbCharSwap", "RandomCharSub")) for s in SYSTEMS)))
    out.append(("by generator: all three typo generators have CIs below 0 for every system",
                all(G.loc[(s, g)]["ndcg@10_rel_hi"] < 0 for s in SYSTEMS for g in ("NeighbCharSwap", "RandomCharSub", "QWERTYCharSub"))))
    out.append(("sensitivity: misspelling and paraphrasing estimates identical in the reviewer-only run",
                all(abs(r["p"].loc[(s, c)]["ndcg@10_rel"] - P.loc[(s, c)]["ndcg@10_rel"]) < 1e-12 for s in SYSTEMS for c in ("misspelling", "paraphrasing"))))
    out.append(("sensitivity: naturality relative change moves by at most 0.001 (reviewer-only vs main)",
                all(abs(r["p"].loc[(s, "naturality")]["ndcg@10_rel"] - P.loc[(s, "naturality")]["ndcg@10_rel"]) <= 0.001 for s in SYSTEMS)))
    out.append(("sensitivity: ordering is exactly zero with n = 47 in the reviewer-only run",
                all(r["p"].loc[(s, "ordering")]["ndcg@10_rel"] == 0 and r["p"].loc[(s, "ordering")]["n_rewrites"] == 47 for s in SYSTEMS)))
    out.append(("sensitivity: every Holm-significant / non-significant decision is the same in both runs",
                all((r["p"].loc[(s, c)]["p_holm"] < 0.05) == (P.loc[(s, c)]["p_holm"] < 0.05) for s in SYSTEMS for c in CATEGORIES)))
    out.append(("diagnostic: no typo rewrite turned the edited word into a word of the collection", d["rw"]["typo_share_with_edited_word_in_collection_vocab"]
                and all(v[0] == 0 for v in d["rw"]["typo_share_with_edited_word_in_collection_vocab"].values())))
    out.append(("diagnostic: all 30 typo calibration pairs were labelled equivalent by the reviewer", d["rw"]["typo_calibration_labels"] == {"equivalent": 30}))
    out.append(("collection: 11,429 documents, 93 queries, 2,083 binary judgments",
                (m["meta"]["collection"]["n_docs"], m["meta"]["collection"]["n_queries"], m["meta"]["collection"]["n_qrels_pairs"]) == (11429, 93, 2083)
                and m["meta"]["collection"]["judgment_values"] == {"1": 2083}))
    out.append(("no rewrite used in the analysis is human-verified", set(m["meta"]["counts"]["rewrites_kept_by_status"]) <= {"llm_reviewed", "automatic_by_construction"}))
    return out


# --------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", default=str(ROOT / "paper/manuscript_template.md"))
    ap.add_argument("--out", default=str(ROOT / "paper/manuscript_draft.md"))
    ap.add_argument("--check", action="store_true", help="run the integrity checks and the placeholder resolution, write nothing")
    ap.add_argument("--no-numbers-log", action="store_true", help="do not write <out>.numbers.json (used for the README)")
    args = ap.parse_args(argv)

    data = load_all(ROOT)
    problems = check_counts(data)
    failed = [name for name, ok in claims(data) if not ok]
    for name in failed:
        problems.append(f"claim not supported by the data: {name}")
    if problems:
        print("INTEGRITY CHECK FAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    n_claims = len(claims(data))
    resolver = Resolver(data)
    text = resolver.sub(Path(args.template).read_text(encoding="utf-8"))
    if "{{" in text or "}}" in text:
        print("unresolved placeholder text remains", file=sys.stderr)
        return 1
    if args.check:
        print(f"ok: {len(resolver.log)} placeholders resolved, {n_claims} data-dependent claims hold, rewrite counts agree with run_metadata.json")
        return 0
    out = Path(args.out)
    out.write_text(text, encoding="utf-8")
    if args.no_numbers_log:
        print(f"wrote {out} ({len(resolver.log)} placeholders, {n_claims} claims checked)")
    else:
        out.with_suffix(".numbers.json").write_text(json.dumps(resolver.log, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out} ({len(resolver.log)} placeholders, {n_claims} claims checked) and {out.with_suffix('.numbers.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
