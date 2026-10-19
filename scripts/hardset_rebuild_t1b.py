#!/usr/bin/env python3
"""Hard set v1 rebuild (Path 2, T1b): re-materialize the 238 frozen items from the public
microsoft/llmail-inject-challenge raw submissions by ``source_rowkey`` and verify ``text_sha256``.

Deterministic, offline (reads files already downloaded), no LLM / API calls, USD 0.
It never re-selects or re-draws items. A missing row or a hash mismatch is a BLOCKING GAP:
the script exits non-zero before any split or overlap check (owner hard stop, 2026-10-19).

Text convention (verified, 238/238): text = f"Subject of the email: {subject}.   Body: {body}"
(the challenge's own prompt format, as used for the keys of labelled_unique_submissions_*.json).

Usage:
  python scripts/hardset_rebuild_t1b.py --raw-dir local_private/llmail_raw \
      --out local_private/hardset_v1/hardset_items.jsonl \
      --report datasets/attackset_hard_v1/REBUILD_REPORT_T1B_20261019.json
Raw texts go only to --out (under local_private/, never committed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets/attackset_hard_v1/MANIFEST.json"
FREEZE = ROOT / "datasets/attackset_hard_v1/FREEZE_RECORD.json"
HF_REPO = "microsoft/llmail-inject-challenge"
HF_REVISION = "1063bdf01ec8762b812d5e06ee768a06faa5a6f7"
RAW_FILES = {"phase1": "raw_submissions_phase1.jsonl", "phase2": "raw_submissions_phase2.jsonl"}
FROZEN_PACKS = {
    "vnext_confirm_v1": ("datasets/frozen/vnext_confirm_v1/dataset.jsonl",
                         "523c881820710783b5290c76ea5fe5fc01a6341fb427defcba1119fc3e721518"),
    "phase1_confirm_v1": ("datasets/frozen/phase1_confirm_v1/dataset.jsonl",
                          "c789811a07d3ed06e1c77d8a45eda6172f480226e006d84fa28386a982536d01"),
}
# metadata keys of frozen-pack records that are not text shown to a model
PACK_META_KEYS = {"id", "category", "attack_type", "label", "split", "success_condition", "family",
                  "difficulty", "is_attack", "expected", "source", "seed", "tool_name", "pair_id"}
JACCARD = 0.6


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def item_text(subject: str | None, body: str | None) -> str:
    return f"Subject of the email: {subject}.   Body: {body}"


def item_id(rowkey: str) -> str:
    """Manifest ids are 'llm-' + first 10 hex of sha1(RowKey) (checked for all 238)."""
    return "llm-" + hashlib.sha1(rowkey.encode("utf-8")).hexdigest()[:10]


def split_hash(items) -> str:
    """sha256 of '\\n'.join(sorted('<id>\\t<split>')), UTF-8, no trailing newline."""
    return sha256_text("\n".join(sorted(f"{i['id']}\t{i['split']}" for i in items)))


def canonical_jsonl(rows) -> bytes:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")


def norm(s: str) -> str:
    return " ".join(s.lower().split())


def tokens(s: str) -> frozenset:
    return frozenset(re.findall(r"[a-z0-9]+", s.lower()))


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def pack_texts(rec) -> list[str]:
    out = []

    def walk(v, key=None):
        if isinstance(v, str):
            if key not in PACK_META_KEYS:
                out.append(v)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
    walk(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    a = ap.parse_args()

    freeze = json.loads(FREEZE.read_text())
    man_sha = sha256_file(MANIFEST)
    assert man_sha == freeze["human_written"]["manifest_sha256"], "MANIFEST.json does not match FREEZE_RECORD"
    items = json.loads(MANIFEST.read_text())["items"]
    want = {(i["source_phase"], i["source_rowkey"]): i for i in items}

    raw_sha, found, dup = {}, {}, Counter()
    for ph, fn in RAW_FILES.items():
        p = a.raw_dir / fn
        raw_sha[fn] = sha256_file(p)
        with open(p, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                k = (ph, r.get("RowKey"))
                if k in want:
                    dup[k] += 1
                    found.setdefault(k, []).append(r)

    per, status = [], Counter()
    for it in items:
        k = (it["source_phase"], it["source_rowkey"])
        rows = found.get(k, [])
        ok = [r for r in rows if sha256_text(item_text(r["subject"], r["body"])) == it["text_sha256"]]
        st = "match" if ok else ("missing_rowkey" if not rows else "hash_mismatch")
        status[st] += 1
        per.append((it, ok[0] if ok else None, st, len(rows)))

    report = {
        "task": "Path 2 / T1b Hard set v1 rebuild (re-materialization, not re-selection)",
        "date": "2026-10-19",
        "api_calls": 0, "usd": 0.0,
        "manifest": {"path": "datasets/attackset_hard_v1/MANIFEST.json", "sha256": man_sha,
                     "matches_freeze_record": True, "items": len(items)},
        "source": {"hf_repo": HF_REPO, "hf_revision": HF_REVISION, "files_sha256": raw_sha},
        "text_convention": 'f"Subject of the email: {subject}.   Body: {body}"',
        "hash_check": {"matched": status["match"], "of": len(items),
                       "hash_mismatch": status["hash_mismatch"], "missing_rowkey": status["missing_rowkey"],
                       "rowkeys_with_multiple_rows": sum(1 for v in dup.values() if v > 1)},
    }
    if status["match"] != len(items):
        report["status"] = "BLOCKING GAP: fewer than 238 items verified; hard stop before split/overlap checks"
        report["unverified_ids"] = sorted(it["id"] for it, r, st, n in per if st != "match")
        a.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
        print(json.dumps(report["hash_check"]))
        return 2

    # secondary consistency checks (manifest metadata vs source row)
    meta = Counter()
    for it, r, st, n in per:
        meta["id_eq_sha1_rowkey"] += item_id(it["source_rowkey"]) == it["id"]
        meta["scenario_eq"] += r.get("scenario") == it["source_scenario"]
        meta["team_prefix_eq"] += str(r.get("team_id", "")).startswith(it["team"]) or it["team"] in str(r.get("team_id", ""))
    report["metadata_checks"] = dict(meta)

    rows = [{**{k: it[k] for k in sorted(it)}, "subject": r["subject"], "body": r["body"],
             "text": item_text(r["subject"], r["body"])} for it, r, st, n in per]
    rows.sort(key=lambda x: x["id"])
    blob = canonical_jsonl(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(blob)
    report["items_jsonl"] = {"path_local_private": str(a.out), "committed": False,
                             "canonical_form": "one json.dumps(sort_keys=True, ensure_ascii=False) per line, UTF-8, LF, sorted by id",
                             "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob), "rows": len(rows)}

    sp = Counter(i["split"] for i in items)
    report["split"] = {"counts": dict(sp), "split_sha256": split_hash(items),
                       "rule": "sha256('\\n'.join(sorted(f'{id}\\t{split}'))); split taken unchanged from MANIFEST.json, never redrawn",
                       "v1_1_needed": False}

    # 3.6 no-overlap with frozen confirmatory packs (text only; no labels used)
    hs_norm = {sha256_text(norm(r["text"])): r["id"] for r in rows}
    hs_norm.update({sha256_text(norm(r["body"] or "")): r["id"] for r in rows})
    hs_tok = [(r["id"], tokens(r["body"] or "")) for r in rows]
    ov = {}
    for name, (rel, expect) in FROZEN_PACKS.items():
        p = ROOT / rel
        got = sha256_file(p)
        assert got == expect, f"frozen pack hash changed: {name}"
        exact, near, best = [], [], 0.0
        recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        for rec in recs:
            for t in pack_texts(rec):
                if sha256_text(norm(t)) in hs_norm:
                    exact.append([rec.get("id"), hs_norm[sha256_text(norm(t))]])
                tt = tokens(t)
                if len(tt) < 5:
                    continue
                for iid, bt in hs_tok:
                    j = jaccard(tt, bt)
                    best = max(best, j)
                    if j >= JACCARD:
                        near.append([rec.get("id"), iid, round(j, 4)])
        ov[name] = {"sha256": got, "records": len(recs), "exact_normalized_matches": exact,
                    "near_duplicates_jaccard_ge_0.6": near, "max_jaccard": round(best, 4)}
    report["overlap_with_frozen_packs"] = {
        "method": "exact: sha256 of lowercased whitespace-collapsed text (item text and item body) vs every string field of each pack record except metadata keys; near: word-token set Jaccard >= 0.6 vs item body (pack strings with >= 5 tokens)",
        "packs": ov}
    report["status"] = "VERIFIED 238/238; split unchanged; overlap reported above"
    a.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"hash_check": report["hash_check"], "metadata_checks": meta,
                      "split": report["split"], "overlap": {k: (len(v["exact_normalized_matches"]), len(v["near_duplicates_jaccard_ge_0.6"]), v["max_jaccard"]) for k, v in ov.items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
