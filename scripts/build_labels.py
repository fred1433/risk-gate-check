"""Finalise the label set: verify each attribution on the diff (fix/revert touches a file the PR touched)."""
import json,subprocess,sys,hashlib,datetime
sys.path.insert(0,"oracle"); from adjudication import ROWS,EXCLUDED
prs={p["number"]:p for p in map(json.loads,open("data/raw/prs_2023-01-01_2026-09-27.jsonl"))}
G=["git","-C","work/OrchardCore"]
def files_of(n):
    p=prs.get(n)
    if p and p.get("mergeCommit"):
        oid=p["mergeCommit"]["oid"]
        return set(subprocess.check_output(G+["diff","--name-only",oid+"^1",oid],text=True).split())
    out=subprocess.check_output(["gh","api","--paginate",f"repos/OrchardCMS/OrchardCore/pulls/{n}/files","--jq",".[].filename"],text=True)
    return set(out.split())
labels=[]
for pr,cls,kind,who,stmt,src,fix,fam in ROWS:
    f=files_of(pr); ov=[]
    if fix:
        ff=files_of(fix); ov=sorted(f&ff)
    final=cls
    note=""
    if cls=="A" and not ov:
        final="B"; note="downgraded: fix diff shares no file with the PR"
    labels.append(dict(pr=pr,merged=prs[pr]["mergedAt"],title=prs[pr]["title"],proposed=cls,cls=final,kind=kind,who=who,
        statement=stmt,evidence="https://github.com/OrchardCMS/OrchardCore/"+src,fix_or_revert=fix,family=fam,
        overlap_files=ov[:6],n_overlap=len(ov),note=note))
out=dict(generated=datetime.date.today().isoformat(),rule=open("oracle/adjudication.py").read().split('"""')[1],
         labels=labels,excluded=[dict(pr=a,reason=b) for a,b in EXCLUDED])
json.dump(out,open("oracle/labels.json","w"),indent=1)
for l in labels: print(l["pr"],l["merged"][:10],l["proposed"],"->",l["cls"],l["n_overlap"],l["family"],l["note"])
