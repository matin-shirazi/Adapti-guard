#!/usr/bin/env python3
"""Hard set v1 rater kit (REBUILT 2026-10-19, Path 2 / T1b; the original hardset_rater_tools.py was lost).

Deterministic, stdlib only, no LLM / API calls. Implements Phase 1a of
docs/paper/negative_result/PHASES_BEFORE_MAIN_20261001.md:

  make-sheets  Write blinded CSV sheets for two independent raters (A, B) and a private key file.
               Seeded shuffle (default seed 20261001). The first --n-double items (default 60) go to
               both raters; the rest are split alternately between A and B, so every item is rated
               at least once. Each rater's sheet order is shuffled independently. Sheets show only a
               blind id and the email text: no item id, split, team, cluster, phase or heuristic label.
  check-blind  Verify that the sheets leak no item metadata (ids, row keys, split, team, cluster, phase,
               scenario, heuristic label) and that blind ids differ between raters; exit 1 on any leak.
  agree        Read the two filled sheets + key, compute Cohen's kappa on q1 (mechanism) and percent
               agreement on q2 (injection requesting an unauthorized send) over double-rated items,
               check the Phase 1 exit gate, and write human-derived labels (the only allowed source
               of mechanism labels, Phase 1c).

All outputs belong under local_private/ (never committed). Guide: RATER_GUIDE_REBUILT_20261019.md.

  python scripts/hardset_rater_tools.py make-sheets --items local_private/hardset_v1/hardset_items.jsonl \
      --out local_private/rater_sheets
  python scripts/hardset_rater_tools.py agree --dir local_private/rater_sheets
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

MECHANISMS = ("plain_request", "structured_field", "fake_markup_or_role", "authority_impersonation",
              "workflow_embedded", "social_pressure", "obfuscated_encoding", "other_unclear")
Q2 = ("yes", "no")
SHEET_COLS = ("blind_id", "email_text", "q1_mechanism", "q2_injection_unauthorized_send", "notes")
GATE = {"kappa_q1_min": 0.70, "agreement_q2_min": 0.95, "n_double_min": 60, "validated_min": 200}
DEFAULT_SEED = 20261001


def _blind_id(seed: int, rater: str, item_id: str) -> str:
    return "B" + hashlib.sha256(f"{seed}|{rater}|{item_id}".encode()).hexdigest()[:8]


def assign(item_ids, seed=DEFAULT_SEED, n_double=60):
    """Return {'A': [ids], 'B': [ids]} deterministically (input order does not matter)."""
    ids = sorted(item_ids)
    if n_double > len(ids):
        raise ValueError("n_double larger than the item count")
    rng = random.Random(seed)
    rng.shuffle(ids)
    double, rest = ids[:n_double], ids[n_double:]
    out = {"A": list(double) + rest[0::2], "B": list(double) + rest[1::2]}
    for r in ("A", "B"):
        random.Random(f"{seed}|order|{r}").shuffle(out[r])
    return out


def make_sheets(items, out: Path, seed=DEFAULT_SEED, n_double=60):
    by_id = {i["id"]: i for i in items}
    plan = assign(by_id, seed, n_double)
    out.mkdir(parents=True, exist_ok=True)
    key = {"seed": seed, "n_double": n_double, "n_items": len(by_id), "raters": {}}
    for r, ids in plan.items():
        rows = []
        for iid in ids:
            b = _blind_id(seed, r, iid)
            key["raters"].setdefault(r, {})[b] = iid
            rows.append({"blind_id": b, "email_text": by_id[iid]["text"], "q1_mechanism": "",
                         "q2_injection_unauthorized_send": "", "notes": ""})
        with open(out / f"sheet_rater_{r}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=SHEET_COLS)
            w.writeheader()
            w.writerows(rows)
    (out / "KEY_DO_NOT_SHARE_WITH_RATERS.json").write_text(json.dumps(key, indent=1, sort_keys=True))
    return key


# manifest fields that must never appear on a rater sheet (only the email text is shown)
BLIND_FORBIDDEN_FIELDS = ("id", "source_rowkey", "split", "team", "cluster", "source_phase", "source_scenario",
                          "mechanism_heuristic_UNVALIDATED", "text_sha256")
_GENERIC_VALUES = {"test", "calibration", "phase1", "phase2"}


def check_blind(items, sheet_dir: Path):
    """Return a list of leak descriptions (empty list == blind)."""
    leaks = []
    texts = {i["text"] for i in items}
    forbidden = set(MECHANISMS[:-1]) | _GENERIC_VALUES
    for i in items:
        for f in BLIND_FORBIDDEN_FIELDS:
            v = i.get(f)
            if v is not None and str(v) and str(v) not in i["text"]:
                forbidden.add(str(v))
    bids = {}
    for r in ("A", "B"):
        with open(sheet_dir / f"sheet_rater_{r}.csv", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows or tuple(rows[0].keys()) != SHEET_COLS:
            leaks.append(f"{r}: columns {tuple(rows[0].keys()) if rows else ()} != {SHEET_COLS}")
            continue
        bids[r] = {row["blind_id"] for row in rows}
        for row in rows:
            b = row["blind_id"]
            if row["email_text"] not in texts:
                leaks.append(f"{r}:{b}: email_text is not an item text")
            if b in forbidden or "llm-" in b:
                leaks.append(f"{r}:{b}: blind_id leaks item metadata")
            for col in ("q1_mechanism", "q2_injection_unauthorized_send", "notes"):
                if row[col]:
                    leaks.append(f"{r}:{b}: column {col} pre-filled")
    if "A" in bids and "B" in bids and bids["A"] & bids["B"]:
        leaks.append("blind ids shared between raters")
    return leaks


def cohen_kappa(a, b):
    assert len(a) == len(b) and a, "need paired, non-empty ratings"
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def _read_sheet(path: Path, rater: str, key):
    m = key["raters"][rater]
    res = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            q1 = row["q1_mechanism"].strip()
            q2 = row["q2_injection_unauthorized_send"].strip().lower()
            if q1 not in MECHANISMS:
                raise ValueError(f"rater {rater} {row['blind_id']}: q1 '{q1}' not in {MECHANISMS}")
            if q2 not in Q2:
                raise ValueError(f"rater {rater} {row['blind_id']}: q2 '{q2}' not in {Q2}")
            res[m[row["blind_id"]]] = (q1, q2)
    if set(res) != set(m.values()):
        raise ValueError(f"rater {rater}: sheet incomplete ({len(res)}/{len(m)})")
    return res


def agree(d: Path):
    key = json.loads((d / "KEY_DO_NOT_SHARE_WITH_RATERS.json").read_text())
    A = _read_sheet(d / "sheet_rater_A.csv", "A", key)
    B = _read_sheet(d / "sheet_rater_B.csv", "B", key)
    both = sorted(set(A) & set(B))
    k1 = cohen_kappa([A[i][0] for i in both], [B[i][0] for i in both])
    a2 = sum(A[i][1] == B[i][1] for i in both) / len(both)
    labels = {}
    for i in sorted(set(A) | set(B)):
        rs = [x for x in (A.get(i), B.get(i)) if x]
        q2_yes = all(r[1] == "yes" for r in rs)
        mech = rs[0][0] if len({r[0] for r in rs}) == 1 else None
        labels[i] = {"n_raters": len(rs), "validated": q2_yes, "mechanism_human": mech if q2_yes else None,
                     "needs_adjudication": len(rs) == 2 and (mech is None or rs[0][1] != rs[1][1])}
    n_valid = sum(v["validated"] for v in labels.values())
    gate = {"kappa_q1": round(k1, 4), "agreement_q2": round(a2, 4), "n_double": len(both), "validated": n_valid}
    gate["pass"] = (k1 >= GATE["kappa_q1_min"] and a2 >= GATE["agreement_q2_min"]
                    and len(both) >= GATE["n_double_min"] and n_valid >= GATE["validated_min"])
    gate["status"] = "PASS" if gate["pass"] else "FAIL (set stays 'candidate'; no per-mechanism result)"
    (d / "AGREEMENT.json").write_text(json.dumps({"gate_thresholds": GATE, **gate}, indent=1, sort_keys=True))
    (d / "HUMAN_LABELS.json").write_text(json.dumps(labels, indent=1, sort_keys=True))
    return gate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make-sheets")
    m.add_argument("--items", required=True, type=Path)
    m.add_argument("--out", required=True, type=Path)
    m.add_argument("--seed", type=int, default=DEFAULT_SEED)
    m.add_argument("--n-double", type=int, default=60)
    c = sub.add_parser("check-blind")
    c.add_argument("--items", required=True, type=Path)
    c.add_argument("--dir", required=True, type=Path)
    g = sub.add_parser("agree")
    g.add_argument("--dir", required=True, type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "make-sheets":
        items = [json.loads(l) for l in a.items.read_text(encoding="utf-8").splitlines() if l.strip()]
        key = make_sheets(items, a.out, a.seed, a.n_double)
        print(json.dumps({r: len(v) for r, v in key["raters"].items()}))
    elif a.cmd == "check-blind":
        items = [json.loads(l) for l in a.items.read_text(encoding="utf-8").splitlines() if l.strip()]
        leaks = check_blind(items, a.dir)
        print(json.dumps({"blind": not leaks, "leaks": leaks[:20]}))
        return 0 if not leaks else 1
    else:
        print(json.dumps(agree(a.dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
