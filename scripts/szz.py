"""SZZ-style candidate discovery for the challenge set. Deleted/modified production lines of the fix are blamed in the
fix's parent; for addition-only hunks the line just above the insertion is blamed (weak, labelled so). Tests excluded.
Output: candidates only (class C), never confirmed causes."""
import subprocess,re,json,sys,collections
G=["git","--git-dir","work/oc-full.git"]
def sh(*a): return subprocess.check_output(G+list(a),text=True,errors="replace")
def pr_of(c):
    m=re.search(r"\(#(\d+)\)\s*$",sh("log","-1","--format=%s",c).strip()); return int(m.group(1)) if m else None
res={}
for fixpr,commit in [(19923,"f71c4528f"),(19098,"6793dcde5"),(19840,"5fd502c177"),(19696,"5792fb801e")]:
    diff=sh("diff","-U0",commit+"^",commit)
    cur=None; cands=collections.Counter(); weak=collections.Counter()
    for line in diff.splitlines():
        if line.startswith("--- "):
            cur=line[6:] if line.startswith("--- a/") else None
            if cur and (re.search(r"(^|/)test/|Tests?/|\.md$|\.json$",cur)): cur=None
        m=re.match(r"@@ -(\d+)(?:,(\d+))? \+",line)
        if m and cur:
            start=int(m.group(1)); n=int(m.group(2)) if m.group(2) is not None else 1
            rng=(start,start+n-1) if n>0 else (max(start,1),max(start,1))
            try: bl=sh("blame","-w","-M","-l","-s","-L",f"{rng[0]},{rng[1]}",commit+"^","--",cur)
            except subprocess.CalledProcessError: continue
            for b in bl.splitlines():
                c=b.split()[0].lstrip("^")
                (cands if n>0 else weak)[c]+=1
    out=[]
    for c,k in (cands+weak).most_common():
        out.append(dict(commit=c[:10],pr=pr_of(c),date=sh("log","-1","--format=%cs",c).strip(),lines=k,weak=c in weak and c not in cands))
    res[fixpr]=out
json.dump(res,open("oracle/szz_candidates.json","w"),indent=1)
for k,v in res.items():
    print("fix",k); [print("  ",x) for x in v[:8]]
