import pytest

from qvr.run import RunConfig, run_experiment
from synthetic import HashingEncoder, build_collection, make_rewrites


@pytest.fixture(scope="session")
def synthetic_run(tmp_path_factory):
    coll = build_collection()
    recs = make_rewrites(coll)
    out = tmp_path_factory.mktemp("synthetic_run")
    cfg = RunConfig(systems=("bm25", "lsa", "dense", "rrf_bm25_lsa", "rrf_bm25_dense"), lsa_dim=20,
                    discard_identical_rewrites=False)
    run_experiment(coll, recs, cfg, out, encoders={"dense": HashingEncoder()})
    return out, coll, recs
