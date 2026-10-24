"""Deliberate-bug check: each mutant must make the test suite fail. Works on copies; the real source is untouched.

    python tests/mutation/run_mutants.py            # all mutants (a few minutes)
    python tests/mutation/run_mutants.py M03 M22    # only those whose name starts with the given ids

M01b is an equivalent mutant (nDCG is invariant to the logarithm base because the base cancels in nDCG/IDCG), so one
survivor is expected; any other survivor means the tests are too weak for that part of the code.
"""
import os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "qvr"
TESTS = ROOT / "tests"
WORK = Path(tempfile.mkdtemp(prefix="qvr_mutants_"))
PY = sys.executable

MUTANTS = [
    ("M01 nDCG shifted discount", "metrics.py", "math.log2(i + 2)", "math.log2(i + 3)"),
    ("M01b nDCG natural-log discount (equivalent: nDCG is base-invariant)", "metrics.py", "math.log2(i + 2)", "math.log(i + 2)"),
    ("M02 MRR off-by-one", "metrics.py", "return 1.0 / i\n", "return 1.0 / (i + 1)\n"),
    ("M03 Recall counts one extra rank", "metrics.py", "for d in ranked[:k] if rels.get(d, 0) > 0) / n_rel", "for d in ranked[:k + 1] if rels.get(d, 0) > 0) / n_rel"),
    ("M04 BM25 idf without +1", "bm25.py", "np.log1p((n - df + 0.5) / (df + 0.5))", "np.log((n - df + 0.5) / (df + 0.5))"),
    ("M05 BM25 numerator constant dropped", "bm25.py", "tf * (self.k1 + 1.0) / denom", "tf * 1.0 / denom"),
    ("M06 RBO wrong prefactor", "stability.py", "return (1 - p) / p * total", "return (1 - p) * total"),
    ("M07 RBO wrong extrapolation denominator", "stability.py", "x_s * (d - s_len) / (s_len * d) * p ** d", "x_s * (d - s_len) / (l_len * d) * p ** d"),
    ("M08 RRF rank offset", "fusion.py", "1.0 / (k + rank)", "1.0 / (k + rank - 1)"),
    ("M09 top-k ties broken by descending index", "ranking.py", "np.lexsort((idx, -scores[idx]))", "np.lexsort((-idx, -scores[idx]))"),
    ("M10 Holm without monotonic running max", "stats.py", "running = max(running, (m - rank) * p[i])", "running = (m - rank) * p[i]"),
    ("M11 exact sign-flip ignores ties with observed", "stats.py", "sums >= observed - tol", "sums > observed + tol"),
    ("M12 analysis: relative change as mean of ratios", "analysis.py",
     "rel, (rlo, rhi) = bootstrap_ratio_change_ci(mb, m0, B, boot_seed)",
     "rel, (rlo, rhi) = float(np.nanmean(mb / np.where(m0 == 0, np.nan, m0)) - 1), (0.0, 0.0)"),
    ("M13 run: delta computed against the wrong sign", "run.py", 'm[name] - base_metrics[qid][name]', 'm[name] + base_metrics[qid][name]'),
    ("M14 run: RBO computed on reversed pair depth", "run.py", "rbo_ext(ranked[qid], ranked[rid], p=cfg.rbo_p, depth=cfg.top_k)", "rbo_ext(ranked[qid], ranked[rid], p=cfg.rbo_p, depth=5)"),
    ("M15 bm25 search keeps zero-score docs", "bm25.py", "idx = idx[column[idx] > 0]", "idx = idx[column[idx] >= 0]"),
    ("M16 analysis uses only the first rewrite per query", "analysis.py", 'mean_rew = rc.groupby("qid")[cols].mean()', 'mean_rew = rc.groupby("qid")[cols].first()'),
    ("M17 analysis skips Holm correction", "analysis.py", 'primary["p_holm"] = holm_adjust(primary["p_signflip"].to_numpy())', 'primary["p_holm"] = primary["p_signflip"]'),
    ("M18 sign-flip statistic is sum of |d|", "stats.py", "observed = abs(d.sum())", "observed = float(np.abs(d).sum())"),
    ("M19 overlap normalised by list length instead of k", "stability.py", "return len(set(a[:k]) & set(b[:k])) / k", "return len(set(a[:k]) & set(b[:k])) / max(1, min(len(a), len(b), k))"),
    ("M20 rewrites default admits LLM-reviewed", "rewrites.py", "def load_rewrites(path, allowed_statuses=(HUMAN_VERIFIED,)):", "def load_rewrites(path, allowed_statuses=(HUMAN_VERIFIED, LLM_REVIEWED)):"),
    ("M21 run: identical rewrites no longer discarded", "run.py", "if cfg.discard_identical_rewrites and normalise_query", "if False and normalise_query"),
    ("M22 run: original ranking cut at depth 99", "run.py", "cleaned[key] = lst[: cfg.top_k]", "cleaned[key] = lst[: cfg.top_k - 1]"),
]

def patch(path: Path, old, new):
    s = path.read_text()
    if s.count(old) != 1:
        raise SystemExit(f"pattern not unique/found in {path.name}: {old!r} (count={s.count(old)})")
    path.write_text(s.replace(old, new))

def main():
    only = sys.argv[1:] 
    results = []
    for name, fname, old, new in MUTANTS:
        if old is None:
            continue
        if only and not any(name.startswith(o) for o in only):
            continue
        d = WORK / name.split()[0]
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(SRC, d / "qvr", ignore=shutil.ignore_patterns("__pycache__"))
        patch(d / "qvr" / fname, old, new)
        env = dict(os.environ, PYTHONPATH=f"{d}:{TESTS}")
        chk = subprocess.run([PY, "-c", "import qvr; print(qvr.__file__)"], env=env, capture_output=True, text=True, cwd=str(d))
        assert str(d) in chk.stdout, f"mutant import path wrong: {chk.stdout} {chk.stderr}"
        t0 = time.time()
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", str(TESTS)], env=env, capture_output=True, text=True, cwd=str(d))
        failed = r.returncode != 0
        last = [l for l in r.stdout.splitlines() if l.startswith("FAILED") or "error" in l.lower()][:1]
        results.append((name, "KILLED" if failed else "SURVIVED", round(time.time() - t0, 1), last[0][:110] if last else ""))
        print(results[-1], flush=True)
    surv = [r for r in results if r[1] == "SURVIVED"]
    print(f"\n{len(results) - len(surv)}/{len(results)} mutants killed; survivors: {[r[0] for r in surv]}")

if __name__ == "__main__":
    main()
    shutil.rmtree(WORK, ignore_errors=True)
