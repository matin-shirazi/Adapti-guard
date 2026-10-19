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
hc = _load("hardset_checks")
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


# --- T2: committed-files-only integrity checks (no local_private/, no skips) ---

def test_t2_ids_rowkeys_and_text_hashes_unique():
    r = hc.run()
    assert r["n_items"] == 238
    assert r["duplicate_ids"] == [] and r["duplicate_rowkeys"] == [] and r["duplicate_text_sha256"] == []
    assert r["ids_eq_sha1_rowkey"] == 238


def test_t2_split_hash_asserted_from_manifest():
    r = hc.run()
    assert r["split_counts"] == {"test": 170, "calibration": 68}
    assert r["split_sha256"] == hc.SPLIT_SHA256 == rb.split_hash(ITEMS) \
        == "93629be41f26f0ecf6779bd4cdfa6f97d09984b7ba6fd4ecd0ab7628646fdfa3"


@pytest.mark.parametrize("pack,sha", [
    ("vnext_confirm_v1", "523c881820710783b5290c76ea5fe5fc01a6341fb427defcba1119fc3e721518"),
    ("phase1_confirm_v1", "c789811a07d3ed06e1c77d8a45eda6172f480226e006d84fa28386a982536d01"),
])
def test_t2_no_overlap_with_frozen_pack_from_manifest_hashes(pack, sha):
    p = hc.run()["packs"][pack]
    assert p["sha256"] == sha and p["records"] > 0 and p["strings_checked"] > 0
    assert p["exact_text_overlap"] == [] and p["shared_ids"] == []


def test_t2_overlap_check_detects_a_planted_match(tmp_path, monkeypatch):
    # sensitivity: a pack string equal to a Hard set text (hash-wise) must be flagged
    fake = [{"id": "x", "text_sha256": hc.sha256_text("planted text"), "split": "test"}]
    pack = tmp_path / "p.jsonl"
    pack.write_text(json.dumps({"id": "r1", "prompt": "  planted   text "}) + "\n")
    monkeypatch.setattr(hc, "ROOT", tmp_path)
    assert hc.pack_overlap(fake, "p.jsonl")["exact_text_overlap"] == ["r1"]


def test_t2_checks_never_read_local_private():
    src = (ROOT / "scripts/hardset_checks.py").read_text()
    assert "local_private" not in src.split('"""', 2)[2]
    assert hc.run()["all_pass"] is True


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


# --- T3: rater kit (synthetic sheets only; real manifest metadata, synthetic email texts) ---

def _manifest_like():
    return [{**i, "text": f"Subject of the email: synthetic {n}.   Body: placeholder body {n}"} for n, i in enumerate(ITEMS)]


def test_t3_default_seed_and_deterministic_sheets(tmp_path):
    assert rt.DEFAULT_SEED == 20261001
    items = _manifest_like()
    rt.make_sheets(items, tmp_path / "a")
    rt.make_sheets(list(reversed(items)), tmp_path / "b")
    for f in ("sheet_rater_A.csv", "sheet_rater_B.csv", "KEY_DO_NOT_SHARE_WITH_RATERS.json"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()


def test_t3_sheets_blind_to_split_team_and_heuristic(tmp_path):
    items = _manifest_like()
    rt.make_sheets(items, tmp_path)
    assert rt.check_blind(items, tmp_path) == []
    raw = (tmp_path / "sheet_rater_A.csv").read_text() + (tmp_path / "sheet_rater_B.csv").read_text()
    for i in items:
        for f in ("id", "source_rowkey", "team", "text_sha256"):
            assert i[f] not in raw
    for v in ("calibration", "phase1", "phase2", *rt.MECHANISMS[:-1]):
        assert v not in raw
    assert "split" not in raw.splitlines()[0] and "team" not in raw.splitlines()[0]


def test_t3_blind_ids_differ_between_raters_and_order_not_by_split(tmp_path):
    items = _manifest_like()
    key = rt.make_sheets(items, tmp_path)
    a, b = key["raters"]["A"], key["raters"]["B"]
    assert not set(a) & set(b)
    assert len(set(a.values()) & set(b.values())) == 60
    split = {i["id"]: i["split"] for i in items}
    with open(tmp_path / "sheet_rater_A.csv", encoding="utf-8") as f:
        order = [split[a[r["blind_id"]]] for r in csv.DictReader(f)]
    assert order != sorted(order) and order != sorted(order, reverse=True)


def test_t3_check_blind_detects_planted_leaks(tmp_path):
    items = _manifest_like()
    rt.make_sheets(items, tmp_path)
    p = tmp_path / "sheet_rater_B.csv"
    with open(p, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows[0]["notes"] = items[0]["split"]
    rows[1]["blind_id"] = items[1]["id"]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rt.SHEET_COLS)
        w.writeheader()
        w.writerows(rows)
    leaks = rt.check_blind(items, tmp_path)
    assert any("pre-filled" in x for x in leaks) and any("blind_id leaks" in x for x in leaks)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=(*rt.SHEET_COLS, "split"))
        w.writeheader()
    assert any("columns" in x for x in rt.check_blind(items, tmp_path))


def _fill(tmp_path, q1_for):
    for r in ("A", "B"):
        p = tmp_path / f"sheet_rater_{r}.csv"
        with open(p, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            row["q1_mechanism"] = q1_for(r, row)
            row["q2_injection_unauthorized_send"] = "yes"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rt.SHEET_COLS)
            w.writeheader()
            w.writerows(rows)


def test_t3_low_agreement_fails_gate(tmp_path):
    rt.make_sheets(_synthetic(), tmp_path)
    _fill(tmp_path, lambda r, row: rt.MECHANISMS[(int(row["blind_id"][1:], 16)) % 7])  # independent per rater
    g = rt.agree(tmp_path)
    assert g["kappa_q1"] < 0.70 and g["pass"] is False and g["status"].startswith("FAIL")


def test_t3_invalid_or_incomplete_sheets_rejected(tmp_path):
    rt.make_sheets(_synthetic(), tmp_path)
    _fill(tmp_path, lambda r, row: "not_a_mechanism")
    with pytest.raises(ValueError):
        rt.agree(tmp_path)
    rt.make_sheets(_synthetic(), tmp_path)
    _fill(tmp_path, lambda r, row: "plain_request")
    p = tmp_path / "sheet_rater_A.csv"
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    p.write_text("".join(lines[:-1]), encoding="utf-8")
    with pytest.raises(ValueError):
        rt.agree(tmp_path)


def test_t3_rater_guide_rebuilt_unapproved_short_and_consistent():
    g = (ROOT / "docs/paper/negative_result/RATER_GUIDE_REBUILT_20261019.md").read_text(encoding="utf-8")
    assert "REBUILT, not original, awaiting owner approval" in g
    assert "Owner approval: _not given_" in g
    assert len(g.split()) <= 1000  # <= 2 pages
    for m in rt.MECHANISMS:
        assert f"`{m}`" in g
