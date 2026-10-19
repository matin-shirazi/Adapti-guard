#!/usr/bin/env python3
"""Hard set v1 deterministic integrity checks (Path 2 / T2). Needs ONLY committed files
(MANIFEST.json, FREEZE_RECORD.json, frozen packs); never reads local_private/. No LLM / API calls.

Checks: manifest hash == freeze record; unique ids, source_rowkeys and text_sha256; ids == llm-+sha1(rowkey)[:10];
split counts 170/68 and split hash; frozen pack file hashes; no exact-text overlap between the Hard set
(text_sha256) and any string of the two frozen confirmatory packs (raw and normalized), and no shared ids.

  python scripts/hardset_checks.py      # prints JSON, exit 0 iff all checks pass
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HS = ROOT / "datasets/attackset_hard_v1"
MANIFEST_SHA256 = "786505ecaa77c6c8619495a23661eb364dd0c857c368a7c1cb9c383b8b7ba1d4"
SPLIT_SHA256 = "93629be41f26f0ecf6779bd4cdfa6f97d09984b7ba6fd4ecd0ab7628646fdfa3"
SPLIT_COUNTS = {"test": 170, "calibration": 68}
FROZEN_PACKS = {
    "vnext_confirm_v1": ("datasets/frozen/vnext_confirm_v1/dataset.jsonl",
                         "523c881820710783b5290c76ea5fe5fc01a6341fb427defcba1119fc3e721518"),
    "phase1_confirm_v1": ("datasets/frozen/phase1_confirm_v1/dataset.jsonl",
                          "c789811a07d3ed06e1c77d8a45eda6172f480226e006d84fa28386a982536d01"),
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def load_items():
    return json.loads((HS / "MANIFEST.json").read_text(encoding="utf-8"))["items"]


def split_hash(items) -> str:
    return sha256_text("\n".join(sorted(f"{i['id']}\t{i['split']}" for i in items)))


def duplicates(values):
    return sorted(v for v, n in Counter(values).items() if n > 1)


def strings(rec):
    """Every string leaf of a JSON record (keys excluded)."""
    if isinstance(rec, str):
        yield rec
    elif isinstance(rec, dict):
        for v in rec.values():
            yield from strings(v)
    elif isinstance(rec, list):
        for v in rec:
            yield from strings(v)


def pack_overlap(items, rel: str):
    raw = (ROOT / rel).read_bytes()
    hs = {i["text_sha256"] for i in items}
    ids = {i["id"] for i in items}
    recs = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    exact, shared_ids, n_strings = [], [], 0
    for r in recs:
        if r.get("id") in ids:
            shared_ids.append(r.get("id"))
        for s in strings(r):
            n_strings += 1
            for variant in (s, s.strip(), " ".join(s.split())):
                if sha256_text(variant) in hs:
                    exact.append(r.get("id"))
                    break
    return {"sha256": sha256_bytes(raw), "records": len(recs), "strings_checked": n_strings,
            "exact_text_overlap": sorted(set(exact)), "shared_ids": sorted(set(shared_ids))}


def run():
    items = load_items()
    freeze = json.loads((HS / "FREEZE_RECORD.json").read_text(encoding="utf-8"))
    man_sha = sha256_bytes((HS / "MANIFEST.json").read_bytes())
    res = {
        "manifest_sha256": man_sha,
        "manifest_eq_freeze_record": man_sha == freeze["human_written"]["manifest_sha256"] == MANIFEST_SHA256,
        "n_items": len(items),
        "duplicate_ids": duplicates(i["id"] for i in items),
        "duplicate_rowkeys": duplicates((i["source_phase"], i["source_rowkey"]) for i in items),
        "duplicate_text_sha256": duplicates(i["text_sha256"] for i in items),
        "ids_eq_sha1_rowkey": sum(i["id"] == "llm-" + hashlib.sha1(i["source_rowkey"].encode()).hexdigest()[:10] for i in items),
        "split_counts": dict(Counter(i["split"] for i in items)),
        "split_sha256": split_hash(items),
        "packs": {n: pack_overlap(items, rel) for n, (rel, _) in FROZEN_PACKS.items()},
    }
    ok = (res["manifest_eq_freeze_record"] and res["n_items"] == 238 and not res["duplicate_ids"]
          and not res["duplicate_rowkeys"] and not res["duplicate_text_sha256"] and res["ids_eq_sha1_rowkey"] == 238
          and res["split_counts"] == SPLIT_COUNTS and res["split_sha256"] == SPLIT_SHA256
          and all(res["packs"][n]["sha256"] == FROZEN_PACKS[n][1] and not res["packs"][n]["exact_text_overlap"]
                  and not res["packs"][n]["shared_ids"] for n in FROZEN_PACKS))
    res["all_pass"] = bool(ok)
    return res


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=1, sort_keys=True))
    sys.exit(0 if r["all_pass"] else 1)
