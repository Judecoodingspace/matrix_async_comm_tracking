import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preformal", ROOT / "scripts/qualify_mdmt_mia_c6_pre_formal.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def test_formal_package_is_disabled_and_frozen():
    p = mod.package(); mod.validate(p)
    assert p["execution_authorized"] is False
    assert [x["cell"] for x in p["cells"]] == ["pair_23__FIFO_strong", "pair_23__FIFO_mild", "pair_44__FIFO_moderate", "pair_66__FIFO_mild"]
    assert all(x["output_root"].endswith("/attempt3") for x in p["cells"])
    assert len({x["output_root"] for x in p["cells"]}) == 4
    assert p["authorities"]["wrapper_status_contract_authority_sha"] == "0054907da0af795a5ca1b8d2f90e8a3bacb20b6d"
    assert p["authorities"]["author_wrapper_sha256"] == mod.sha(ROOT / "scripts/run_mdmt_mia_author_sync.sh")
    assert sum(x["serviceable_id_state_serviced_bytes_baseline"] for x in p["cells"]) == 14297870

def test_formal_package_rejects_drift():
    p = mod.package(); p["cells"][0]["service_rate"] = 1
    try: mod.validate(p)
    except ValueError: pass
    else: raise AssertionError("rate drift accepted")

def test_sealed_run004_baseline_verifies():
    assert mod.verify_baseline()["total_serviceable_id_state_serviced_bytes"] == 14297870
