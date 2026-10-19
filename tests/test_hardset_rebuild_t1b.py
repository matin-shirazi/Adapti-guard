"""Path 2 / T1b: deterministic, offline checks of the Hard set v1 rebuild and the rebuilt rater kit.
No raw item text is needed (raw texts live only in local_private/); no LLM / API calls."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HS = ROOT / "datasets/attackset_hard_v1"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rb = _load("hardset_rebuild_t1b")
rt = _load("hardset_rater_tools")
ITEMS = json.loads((HS / "MANIFEST.json").read_text())["items"]
REPORT = json.loads((HS / "REBUILD_REPORT_T1B_20261019.json").read_text())


def test_manifest_matches_freeze_record():
    freeze = json.loads((HS / "FREEZE_RECORD.json").read_text())
    assert rb.sha256_file(HS / "MANIFEST.json") == freeze["human_written"]["manifest_sha256"] \
        == "786505ecaa77c6c8619495a23661eb364dd0c857c368a7c1cb9c383b8b7ba1d4"


def test_report_records_full_hash_match_and_zero_cost():
    hc = REPORT["hash_check"]
    assert (hc["matched"], hc["of"], hc["hash_mismatch"], hc["missing_rowkey"]) == (238, 238, 0, 0)
    assert REPORT["api_calls"] == 0 and REPORT["usd"] == 0.0
    assert REPORT["manifest"]["sha256"] == rb.sha256_file(HS / "MANIFEST.json")
    assert REPORT["metadata_checks"]["id_eq_sha1_rowkey"] == 238


def test_ids_are_sha1_of_rowkey():
    assert all(rb.item_id(i["source_rowkey"]) == i["id"] for i in ITEMS)


def test_split_unchanged_and_hashed():
    assert sum(i["split"] == "test" for i in ITEMS) == 170
    assert sum(i["split"] == "calibration" for i in ITEMS) == 68
    assert rb.split_hash(ITEMS) == REPORT["split"]["split_sha256"] \
        == "93629be41f26f0ecf6779bd4cdfa6f97d09984b7ba6fd4ecd0ab7628646fdfa3"
    assert REPORT["split"]["v1_1_needed"] is False


def test_no_overlap_with_frozen_packs_recorded_with_pack_hashes():
    for name, (rel, sha) in rb.FROZEN_PACKS.items():
        p = REPORT["overlap_with_frozen_packs"]["packs"][name]
        assert p["sha256"] == sha == rb.sha256_file(ROOT / rel)
        assert p["exact_normalized_matches"] == [] and p["near_duplicates_jaccard_ge_0.6"] == []


def test_text_convention():
    assert rb.item_text("S", "B") == "Subject of the email: S.   Body: B"


def _synthetic(n=238):
    return [{"id": f"llm-{i:010x}", "text": f"email {i}"} for i in range(n)]


def test_assignment_deterministic_covering_and_double_count():
    ids = [x["id"] for x in _synthetic()]
    a1, a2 = rt.assign(ids), rt.assign(list(reversed(ids)))
    assert a1 == a2
    both = set(a1["A"]) & set(a1["B"])
    assert len(both) == 60 and set(a1["A"]) | set(a1["B"]) == set(ids)
    assert rt.assign(ids, seed=1) != a1


def test_sheets_are_blind(tmp_path):
    items = [{**x, "split": "test", "team": "t", "mechanism_heuristic_UNVALIDATED": "plain_request"} for x in _synthetic()]
    rt.make_sheets(items, tmp_path)
    for r in ("A", "B"):
        with open(tmp_path / f"sheet_rater_{r}.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert tuple(rows[0].keys()) == rt.SHEET_COLS
        flat = json.dumps(rows)
        assert "llm-" not in flat and "plain_request" not in flat and "calibration" not in flat


def test_kappa_known_values():
    assert rt.cohen_kappa(list("aabb"), list("aabb")) == 1.0
    assert rt.cohen_kappa(list("ab"), list("ba")) == pytest.approx(-1.0)
    # 2x2 table [[20,5],[10,15]] -> kappa = 0.4
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert rt.cohen_kappa(a, b) == pytest.approx(0.4)


def test_agree_end_to_end_gate(tmp_path):
    rt.make_sheets(_synthetic(), tmp_path)
    for r in ("A", "B"):
        p = tmp_path / f"sheet_rater_{r}.csv"
        with open(p, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            n = int(hashlib.sha256(row["email_text"].encode()).hexdigest(), 16)
            row["q1_mechanism"] = rt.MECHANISMS[n % 7]
            row["q2_injection_unauthorized_send"] = "yes"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rt.SHEET_COLS)
            w.writeheader()
            w.writerows(rows)
    g = rt.agree(tmp_path)
    assert g["kappa_q1"] == 1.0 and g["agreement_q2"] == 1.0 and g["n_double"] == 60
    assert g["validated"] == 238 and g["pass"] is True
