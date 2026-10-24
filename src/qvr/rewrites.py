"""Query-variation generators, rewrite-file I/O and review merging.

Rewrite record schema (one JSON object per line; the first six fields are the original kit's schema)::

    qid, rewrite_id, category, query, meaning_preserved, review_status          (required)
    generator, original_query, review_label, reviewer, review_note, notes       (optional)

``review_status`` values used here:
    automatic_by_construction  character-level typo that leaves the intended query unchanged (as in Penha et al. 2022)
    unreviewed                 candidate that still needs a validity judgment
    llm_reviewed               judged by an LLM reviewer (``review_label`` holds the label)
    human_verified             judged by a human annotator - NEVER set by this code

The analysis only uses records whose status is in the caller's allow-list and whose ``meaning_preserved`` is True.
"""
from __future__ import annotations

import csv
import json
import random
import string
from collections import Counter
from pathlib import Path

from .data import natural_key

_RES = Path(__file__).parent / "resources"
NLTK_ENGLISH_STOPWORDS = frozenset(
    w for w in (_RES / "nltk_english_stopwords.txt").read_text(encoding="utf-8").split() if w
)

AUTOMATIC = "automatic_by_construction"
UNREVIEWED = "unreviewed"
LLM_REVIEWED = "llm_reviewed"
HUMAN_VERIFIED = "human_verified"

REVIEW_LABELS = ("equivalent", "broader", "narrower", "different")
REQUIRED_FIELDS = {"qid", "rewrite_id", "category", "query", "meaning_preserved", "review_status"}

QWERTY_NEIGHBORS = {
    "q": "wa", "w": "qase", "e": "wsdr", "r": "edft", "t": "rfgy", "y": "tghu", "u": "yhji", "i": "ujko",
    "o": "iklp", "p": "ol", "a": "qwsz", "s": "awedxz", "d": "serfcx", "f": "drtgvc", "g": "ftyhbv",
    "h": "gyujnb", "j": "huikmn", "k": "jiolm", "l": "kop", "z": "asx", "x": "zsdc", "c": "xdfv",
    "v": "cfgb", "b": "vghn", "n": "bhjm", "m": "njk",
}


def normalise_query(q: str) -> str:
    return " ".join(q.lower().split())


def _eligible(tokens: list[str], min_len: int = 4) -> list[int]:
    return [i for i, t in enumerate(tokens) if len(t) >= min_len and t.isalpha() and t.isascii()]


def neighb_char_swap(query: str, rng: random.Random):
    """Swap two adjacent, different characters inside one word of at least four letters."""
    toks = query.split()
    cand = _eligible(toks)
    rng.shuffle(cand)
    for i in cand:
        w = toks[i]
        pairs = [p for p in range(len(w) - 1) if w[p] != w[p + 1]]
        if pairs:
            p = rng.choice(pairs)
            toks[i] = w[:p] + w[p + 1] + w[p] + w[p + 2:]
            return " ".join(toks)
    return None


def random_char_sub(query: str, rng: random.Random):
    """Replace one random character of one word (four or more letters) with a different random letter."""
    toks = query.split()
    cand = _eligible(toks)
    if not cand:
        return None
    i = rng.choice(cand)
    w = toks[i]
    p = rng.randrange(len(w))
    toks[i] = w[:p] + rng.choice([c for c in string.ascii_lowercase if c != w[p]]) + w[p + 1:]
    return " ".join(toks)


def qwerty_char_sub(query: str, rng: random.Random):
    """Replace one character with a physically adjacent key on a QWERTY keyboard."""
    toks = query.split()
    cand = _eligible(toks)
    if not cand:
        return None
    i = rng.choice(cand)
    w = toks[i]
    positions = [p for p, c in enumerate(w) if c in QWERTY_NEIGHBORS]
    if not positions:
        return None
    p = rng.choice(positions)
    toks[i] = w[:p] + rng.choice(QWERTY_NEIGHBORS[w[p]]) + w[p + 1:]
    return " ".join(toks)


def random_order_swap(query: str, rng: random.Random):
    """Swap two words that have different surface forms."""
    toks = query.split()
    pairs = [(i, j) for i in range(len(toks)) for j in range(i + 1, len(toks)) if toks[i] != toks[j]]
    if not pairs:
        return None
    i, j = rng.choice(pairs)
    toks[i], toks[j] = toks[j], toks[i]
    return " ".join(toks)


def remove_stopwords(query: str, rng: random.Random | None = None):
    kept = [t for t in query.split() if t not in NLTK_ENGLISH_STOPWORDS]
    return " ".join(kept) if kept else None


# (generator id, function, category, initial review status)
AUTOMATIC_GENERATORS = [
    ("NeighbCharSwap", neighb_char_swap, "misspelling", AUTOMATIC),
    ("RandomCharSub", random_char_sub, "misspelling", AUTOMATIC),
    ("QWERTYCharSub", qwerty_char_sub, "misspelling", AUTOMATIC),
    ("RandomOrderSwap", random_order_swap, "ordering", UNREVIEWED),
    ("RemoveStopWords", remove_stopwords, "naturality", UNREVIEWED),
]

CATEGORY_OF_GENERATOR = {g: c for g, _, c, _ in AUTOMATIC_GENERATORS}
CATEGORY_OF_GENERATOR.update({
    "LLM_NaturalQuestion": "naturality",
    "LLM_Paraphrase": "paraphrasing",
    "LLM_SynonymSwap": "paraphrasing",
})


def generate_automatic(queries: dict[str, str], seed: int = 13):
    """Deterministic rewrites for every query. Returns (records, Counter of skipped (generator, reason))."""
    records, skipped = [], Counter()
    for qid in sorted(queries, key=natural_key):
        original = queries[qid]
        for gen, fn, category, status in AUTOMATIC_GENERATORS:
            rng = random.Random(f"{seed}|{qid}|{gen}")  # str seeds hash with sha512: stable across processes
            new = fn(original, rng)
            if new is None:
                skipped[(gen, "not_applicable")] += 1
                continue
            if normalise_query(new) == normalise_query(original):
                skipped[(gen, "identical_to_original")] += 1
                continue
            records.append({
                "qid": qid,
                "rewrite_id": f"{qid}__{gen}",
                "category": category,
                "generator": gen,
                "query": new,
                "original_query": original,
                "meaning_preserved": True if status == AUTOMATIC else None,
                "review_status": status,
            })
    return records, skipped


def swap_touches_only_function_words(original: str, rewrite: str) -> bool:
    """True when two reordered queries differ only in positions holding NLTK stop words.

    This is the conservative, mechanical validity rule for word-order rewrites: displacing articles, prepositions or
    conjunctions cannot change which content words belong together, whereas moving any content word can.
    """
    a, b = original.split(), rewrite.split()
    if len(a) != len(b) or sorted(a) != sorted(b):
        raise ValueError("not a pure reordering of the same words")
    moved = [(x, y) for x, y in zip(a, b) if x != y]
    return bool(moved) and all(x in NLTK_ENGLISH_STOPWORDS and y in NLTK_ENGLISH_STOPWORDS for x, y in moved)


def read_jsonl(path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def write_jsonl(path, records) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_rewrites(path, allowed_statuses=(HUMAN_VERIFIED,)):
    """Load a rewrite file, keeping only allowed statuses with ``meaning_preserved`` True.

    The default admits human-verified rewrites only (the original kit's rule). Returns (kept, Counter of drops).
    """
    kept, dropped = [], Counter()
    allowed = set(allowed_statuses)
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            missing = REQUIRED_FIELDS - set(item)
            if missing:
                raise ValueError(f"rewrite line {line_no} is missing fields: {sorted(missing)}")
            if item["review_status"] not in allowed:
                dropped["status_not_allowed"] += 1
                continue
            if item["meaning_preserved"] is not True:
                dropped["not_meaning_preserved"] += 1
                continue
            item["qid"] = str(item["qid"])
            kept.append(item)
    return kept, dropped


def merge_reviews(candidates: list[dict], reviews: list[dict]):
    """Attach reviewer labels to candidates. A label other than ``equivalent`` sets meaning_preserved False."""
    by_id = {r["rewrite_id"]: r for r in reviews}
    merged, stats = [], Counter()
    for c in candidates:
        c = dict(c)
        rev = by_id.get(c["rewrite_id"])
        if rev is not None:
            label = rev["label"]
            if label not in REVIEW_LABELS:
                raise ValueError(f"unknown review label {label!r} for {c['rewrite_id']}")
            c["review_label"] = label
            c["reviewer"] = rev.get("reviewer", "")
            c["review_note"] = rev.get("note", "")
            c["meaning_preserved"] = label == "equivalent"
            c["review_status"] = LLM_REVIEWED
            stats[f"reviewed:{label}"] += 1
        else:
            stats["unreviewed"] += 1
        merged.append(c)
    return merged, stats


def audit_sample(records: list[dict], per_category: int = 20, seed: int = 13, by: str = "category") -> list[dict]:
    """Stratified random sample for a human validity audit; the human columns are left blank.

    ``by`` is the stratum: ``"category"`` or ``"generator"`` (records without a generator fall back to their category).
    ``per_category`` is the number of rewrites drawn from each stratum.
    """
    if by not in ("category", "generator"):
        raise ValueError("by must be 'category' or 'generator'")
    rng = random.Random(seed)
    strata: dict[str, list[dict]] = {}
    for r in records:
        strata.setdefault(r.get(by) or r["category"], []).append(r)
    rows = []
    for name in sorted(strata):
        pool = sorted(strata[name], key=lambda r: r["rewrite_id"])
        for r in rng.sample(pool, min(per_category, len(pool))):
            rows.append({
                "rewrite_id": r["rewrite_id"],
                "category": r["category"],
                "generator": r.get("generator", ""),
                "original_query": r.get("original_query", ""),
                "rewrite_query": r["query"],
                "llm_label": r.get("review_label", ""),
                "human_label_equivalent_broader_narrower_different": "",
                "human_notes": "",
            })
    return rows


def write_audit_sheet(path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
