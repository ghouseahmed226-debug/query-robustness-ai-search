"""Human validity audit: blind annotation sheet, agreement statistics, and promotion of human labels.

The blind sheet shows an annotator only ``(original, rewrite)``. A separate key (kept apart from the annotator) maps each
opaque audit id back to the rewrite, its generator and the labels that were used in the analysis, so the annotator is
not anchored by the LLM reviewer's label or by the generator's name.

:func:`apply_human_labels` is the **only** code path in this package that writes ``review_status = "human_verified"``.
It needs an annotator name and writes the status only for rewrites that carry a non-empty human label.
"""
from __future__ import annotations

import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from .rewrites import AUTOMATIC, HUMAN_VERIFIED, LLM_REVIEWED, REVIEW_LABELS

BLIND_FIELDS = ["audit_id", "original_query", "rewrite_query", "human_label", "human_notes"]
KEY_FIELDS = ["audit_id", "rewrite_id", "category", "generator", "review_status", "reviewer_label",
              "meaning_preserved_in_analysis"]


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (95% by default); (nan, nan) when n == 0."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cohen_kappa(a: list[str], b: list[str], labels=REVIEW_LABELS) -> float:
    """Unweighted Cohen's kappa between two label sequences; nan when chance agreement is 1."""
    if len(a) != len(b) or not a:
        raise ValueError("label sequences must be non-empty and of equal length")
    n = len(a)
    p_obs = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    p_exp = sum(ca[lab] * cb[lab] for lab in labels) / (n * n)
    return float("nan") if p_exp == 1.0 else (p_obs - p_exp) / (1.0 - p_exp)


def make_blind_sheet(records: list[dict], per_generator: int | None = 15, seed: int = 13):
    """Draw a stratified (by generator) sample of every candidate rewrite, kept or dropped, and shuffle it.

    Returns ``(blind_rows, key_rows)``. ``per_generator=None`` takes all candidates.
    Unreviewed candidates are skipped because nothing says whether the analysis would use them.
    """
    pools: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r["review_status"] not in (AUTOMATIC, LLM_REVIEWED):
            continue
        if not r.get("original_query"):
            raise ValueError(f"{r['rewrite_id']}: an annotator cannot judge a rewrite without the original query")
        pools[r.get("generator") or r["category"]].append(r)
    rng = random.Random(seed)
    chosen: list[dict] = []
    for name in sorted(pools):
        pool = sorted(pools[name], key=lambda r: r["rewrite_id"])
        chosen += pool if per_generator is None else rng.sample(pool, min(per_generator, len(pool)))
    chosen.sort(key=lambda r: r["rewrite_id"])  # canonical order first, so the shuffle is reproducible
    rng.shuffle(chosen)
    blind, key = [], []
    for i, r in enumerate(chosen, start=1):
        aid = f"A{i:04d}"
        blind.append({"audit_id": aid, "original_query": r["original_query"], "rewrite_query": r["query"],
                      "human_label": "", "human_notes": ""})
        key.append({"audit_id": aid, "rewrite_id": r["rewrite_id"], "category": r["category"],
                    "generator": r.get("generator", ""), "review_status": r["review_status"],
                    "reviewer_label": r.get("review_label", ""),
                    "meaning_preserved_in_analysis": r["meaning_preserved"]})
    return blind, key


def read_csv_rows(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path, rows: list[dict], fields: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _labelled(filled_rows: list[dict], key_rows: list[dict]) -> list[tuple[dict, str]]:
    key = {k["audit_id"]: k for k in key_rows}
    out = []
    for row in filled_rows:
        aid = row["audit_id"]
        if aid not in key:
            raise ValueError(f"unknown audit_id {aid!r}")
        label = (row.get("human_label") or "").strip().lower()
        if not label:
            continue
        if label not in REVIEW_LABELS:
            raise ValueError(f"{aid}: invalid label {row.get('human_label')!r}; allowed: {', '.join(REVIEW_LABELS)}")
        out.append((key[aid], label))
    return out


def _truthy(v) -> bool:
    return str(v).strip().lower() == "true"


def score_audit(filled_rows: list[dict], key_rows: list[dict]) -> dict:
    """Agreement between a human annotator and the labels used in the analysis.

    * ``analysis_set_validity``: share of rewrites the analysis kept that the human calls ``equivalent``
      (this is the quantity the pilot's conclusions depend on), overall and per generator, with Wilson 95% intervals.
    * ``false_drop_rate``: share of rewrites the analysis dropped that the human calls ``equivalent``.
    * ``reviewer_agreement``: raw agreement and Cohen's kappa against the blind LLM reviewer's label (four labels and
      equivalent-vs-not), on rewrites the reviewer labelled.
    """
    lab = _labelled(filled_rows, key_rows)
    kept = [(k, h) for k, h in lab if _truthy(k["meaning_preserved_in_analysis"])]
    dropped = [(k, h) for k, h in lab if not _truthy(k["meaning_preserved_in_analysis"])]

    def share(pairs):
        n = len(pairs)
        k = sum(h == "equivalent" for _, h in pairs)
        lo, hi = wilson_interval(k, n)
        return {"n": n, "human_equivalent": k, "share": (k / n) if n else float("nan"), "ci_lo": lo, "ci_hi": hi}

    by_gen = {}
    for g in sorted({k["generator"] or k["category"] for k, _ in kept}):
        by_gen[g] = share([(k, h) for k, h in kept if (k["generator"] or k["category"]) == g])
    rev = [(k["reviewer_label"], h) for k, h in lab if k["reviewer_label"]]
    out = {
        "n_rows": len(filled_rows), "n_labelled": len(lab),
        "analysis_set_validity": share(kept),
        "analysis_set_validity_by_generator": by_gen,
        "false_drop_rate": share(dropped),
    }
    if rev:
        a, b = [r for r, _ in rev], [h for _, h in rev]
        out["reviewer_agreement"] = {
            "n": len(rev), "raw_agreement": sum(x == y for x, y in rev) / len(rev),
            "kappa_4_labels": cohen_kappa(a, b),
            "kappa_equivalent_vs_not": cohen_kappa(["equivalent" if x == "equivalent" else "not" for x in a],
                                                   ["equivalent" if x == "equivalent" else "not" for x in b],
                                                   labels=("equivalent", "not")),
            "confusion_reviewer_by_human": {r: dict(Counter(h for rr, h in rev if rr == r)) for r in sorted(set(a))},
        }
    return out


def apply_human_labels(records: list[dict], filled_rows: list[dict], key_rows: list[dict], annotator: str):
    """Return ``(new_records, n_promoted)``: rewrites with a human label become ``human_verified``.

    ``meaning_preserved`` is True only for ``equivalent``. The earlier label, if any, is kept as
    ``previous_review_label`` and ``previous_review_status``. Rewrites without a human label are returned unchanged.
    """
    if not annotator or not annotator.strip():
        raise ValueError("an annotator name is required to mark rewrites as human_verified")
    by_id = {r["rewrite_id"]: r for r in records}
    notes = {row["audit_id"]: (row.get("human_notes") or "").strip() for row in filled_rows}
    promoted = {}
    for k, label in _labelled(filled_rows, key_rows):
        if k["rewrite_id"] not in by_id:
            raise ValueError(f"{k['rewrite_id']} is not in the rewrite file")
        promoted[k["rewrite_id"]] = (label, notes.get(k["audit_id"], ""))
    out = []
    for r in records:
        r = dict(r)
        if r["rewrite_id"] in promoted:
            label, note = promoted[r["rewrite_id"]]
            r["previous_review_status"] = r["review_status"]
            r["previous_review_label"] = r.get("review_label", "")
            r["review_status"] = HUMAN_VERIFIED
            r["review_label"] = label
            r["meaning_preserved"] = label == "equivalent"
            r["reviewer"] = f"human: {annotator.strip()}"
            r["review_note"] = note
        out.append(r)
    return out, len(promoted)


def audit_markdown(report: dict) -> str:
    def row(name, d):
        return f"| {name} | {d['n']} | {d['human_equivalent']} | {d['share']:.3f} | [{d['ci_lo']:.3f}, {d['ci_hi']:.3f}] |"

    lines = [f"Rows labelled: {report['n_labelled']} of {report['n_rows']}.", "",
             "| set | n | human says equivalent | share | Wilson 95% CI |", "|---|---|---|---|---|",
             row("analysis set (kept rewrites)", report["analysis_set_validity"]),
             row("dropped rewrites (false-drop rate)", report["false_drop_rate"])]
    for g, d in report["analysis_set_validity_by_generator"].items():
        lines.append(row(f"kept, {g}", d))
    ra = report.get("reviewer_agreement")
    if ra:
        lines += ["", f"Agreement with the blind LLM reviewer on {ra['n']} rewrites: raw {ra['raw_agreement']:.3f}, "
                      f"Cohen's kappa {ra['kappa_4_labels']:.3f} (4 labels), {ra['kappa_equivalent_vs_not']:.3f} "
                      f"(equivalent vs not)."]
    return "\n".join(lines)
