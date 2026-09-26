"""Replay YOUR policy on the same frozen cohort and labels.
    python3 scripts/replay_custom.py mypolicy:decide evaluation
A policy is any function decide(snapshot: dict, diff: str) -> {"decision": "ALLOW"|"REVIEW_REQUIRED"|"UNKNOWN", "reasons": [str]}.
snapshot = {"pr", "title", "base_sha", "merge_sha", "files": [{"path","add","dele"}]}; diff = the merged change as unified diff.
Anything other than ALLOW counts as sent to a senior (UNKNOWN is never permissive). Needs snapshots/ (scripts/make_snapshots.py)."""
import importlib, json, sys, os
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate.stats import clopper_pearson
mod, fn = sys.argv[1].split(":"); decide = getattr(importlib.import_module(mod), fn)
period = sys.argv[2] if len(sys.argv) > 2 else "evaluation"
man = json.load(open("data/cohort_manifest.json"))[period]
labels = {l["pr"]: l for l in json.load(open("oracle/labels.json"))["labels"]}
N = R = 0; m = k = 0; missed = []
for e in man["prs"]:
    n = e["pr"]; s = json.load(open(f"snapshots/{n}/snapshot.json")); d = open(f"snapshots/{n}/diff.patch", errors="replace").read()
    try: dec = decide(s, d)["decision"]
    except Exception: dec = "UNKNOWN"
    N += 1; rev = dec != "ALLOW"; R += rev
    if labels.get(n, {}).get("cls") == "A":
        m += 1
        if not rev: k += 1; missed.append(n)
lo, hi = clopper_pearson(k, m)
print(f"{period}: {k}/{m} confirmed failure-introducing changes passed (95% CI {lo:.0%} to {hi:.0%}); {R}/{N} = {R/N:.1%} sent to a senior")
print("passed:", missed)
