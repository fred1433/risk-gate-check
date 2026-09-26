"""Replay the three frozen policies on a cohort period and score them against the oracle labels.
Usage: python3 scripts/evaluate.py development|evaluation"""
import json, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate.policies import simple, deterministic, hybrid, is_review, needs_model, ALLOW, UNKNOWN
from riskgate.stats import clopper_pearson
period=sys.argv[1]
F=json.load(open("policies/frozen.json"))
man=json.load(open("data/cohort_manifest.json"))[period]
labels={l["pr"]:l for l in json.load(open("oracle/labels.json"))["labels"]}
rows=[]
for e in man["prs"]:
    n=e["pr"]; s=json.load(open(f"snapshots/{n}/snapshot.json")); d=open(f"snapshots/{n}/diff.patch",errors="replace").read()
    mr=json.load(open(f"runs/model/{n}.json")) if os.path.exists(f"runs/model/{n}.json") else None
    nm=needs_model(s,d)
    p1=simple(s); p2=deterministic(s,d,F["theta"]); p3=hybrid(s,d,mr if nm else None,F["tau"])
    rows.append(dict(pr=n,title=s["title"],merged_at=e["merged_at"],label=labels.get(n,{}).get("cls"),family=labels.get(n,{}).get("family"),
                     simple=p1,deterministic=p2,hybrid=p3,model=mr if nm else None,needs_model=nm))
os.makedirs("results",exist_ok=True)
with open(f"results/decisions_{period}.jsonl","w") as f:
    for r in rows: f.write(json.dumps({k:v for k,v in r.items() if k!="model"} | {"model_status":(r["model"] or {}).get("status")})+"\n")
N=len(rows)
def summ(pol, cls=("A",)):
    lab=[r for r in rows if r["label"] in cls]
    missed=[r for r in lab if not is_review(r[pol])]
    fam_all={r["family"] for r in lab}; fam_miss={r["family"] for r in missed}
    R=sum(is_review(r[pol]) for r in rows); U=sum(r[pol]["decision"]==UNKNOWN for r in rows)
    lo,hi=clopper_pearson(len(missed),len(lab))
    return dict(k=len(missed),m=len(lab),families_m=len(fam_all),families_k=len(fam_miss),R=R,N=N,unknown=U,load=R/N,
                k_over_m_ci95=[round(lo,3),round(hi,3)],missed=[r["pr"] for r in missed],
                random_same_load_expected_k=round(len(lab)*(1-R/N),2))
out=dict(period=period,N=N,frozen=F,policies={})
for pol in ("simple","deterministic","hybrid"):
    out["policies"][pol]=dict(confirmed=summ(pol),sensitivity_A_or_B=summ(pol,("A","B")))
# secondary: matched load to the simple policy's load in THIS period, using each policy's own score ordering (labels unused)
target=out["policies"]["simple"]["confirmed"]["load"]
def at_load(pol):
    best=None
    for th in sorted({r[pol]["score"] for r in rows if r[pol]["score"] is not None}):
        rev=[r for r in rows if r[pol]["decision"]==UNKNOWN or (r[pol]["score"] is not None and r[pol]["score"]>=th)]
        load=len(rev)/N
        if best is None or abs(load-target)<abs(best[1]-target): best=(th,load,rev)
    th,load,rev=best; ids={r["pr"] for r in rev}
    lab=[r for r in rows if r["label"]=="A"]
    return dict(threshold=th,load=round(load,3),k=sum(1 for r in lab if r["pr"] not in ids),m=len(lab))
out["matched_load_secondary"]=dict(target_load=round(target,3),deterministic=at_load("deterministic"),hybrid=at_load("hybrid"))
# where hybrid and deterministic disagree
dis=[r for r in rows if is_review(r["hybrid"])!=is_review(r["deterministic"])]
out["hybrid_vs_deterministic"]=dict(disagreements=len(dis),
    hybrid_only_review=sum(1 for r in dis if is_review(r["hybrid"])),deterministic_only_review=sum(1 for r in dis if is_review(r["deterministic"])),
    labelled=[dict(pr=r["pr"],label=r["label"],title=r["title"],hybrid=r["hybrid"]["decision"],deterministic=r["deterministic"]["decision"],
                   hybrid_reasons=r["hybrid"]["reasons"],deterministic_reasons=r["deterministic"]["reasons"]) for r in dis if r["label"]])
# usage of the model in this period
calls=[r["model"] for r in rows if r["model"]]
att=[a for c in calls for a in c["attempts"]]
out["model_usage"]=dict(prs_sent_to_model=len(calls),attempts=len(att),retries=len(att)-len(calls),
    failed=sum(1 for c in calls if c["status"]!="ok"),
    input_tokens=sum((a.get("usage") or {}).get("input_tokens") or 0 for a in att)+sum((a.get("usage") or {}).get("cache_creation_input_tokens") or 0 for a in att)+sum((a.get("usage") or {}).get("cache_read_input_tokens") or 0 for a in att),
    output_tokens=sum((a.get("usage") or {}).get("output_tokens") or 0 for a in att),
    seconds=round(sum(a.get("seconds",0) for a in att),1), models=sorted({m for a in att for m in a.get("model",[])}))
json.dump(out,open(f"results/summary_{period}.json","w"),indent=1)
for pol,v in out["policies"].items():
    c=v["confirmed"]; s=v["sensitivity_A_or_B"]
    print(f"{pol:14s} missed {c['k']}/{c['m']} (fam {c['families_k']}/{c['families_m']}) CI{c['k_over_m_ci95']} review {c['R']}/{N}={c['load']:.1%} unknown {c['unknown']} | A+B {s['k']}/{s['m']} | random@load {c['random_same_load_expected_k']}  missed={c['missed']}")
print(out["matched_load_secondary"]); print({k:v for k,v in out["hybrid_vs_deterministic"].items() if k!="labelled"})
for x in out["hybrid_vs_deterministic"]["labelled"]: print("  ",x["pr"],x["label"],x["title"][:60],"H:",x["hybrid"],"D:",x["deterministic"])
print(out["model_usage"])
