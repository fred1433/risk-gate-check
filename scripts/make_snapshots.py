"""Clean decision-time snapshots. For each cohort PR: the merged change (squash commit vs its first parent), its title and
its file list. Nothing else: no body, no comments, no later history. The gate and the model only ever read these files."""
import json,subprocess,os,hashlib,sys
G=["git","--git-dir","work/oc-full.git"]
man=json.load(open("data/cohort_manifest.json"))
for part in ("development","evaluation"):
    for e in man[part]["prs"]:
        n=e["pr"]; d=f"snapshots/{n}"; 
        if os.path.exists(d+"/snapshot.json"): continue
        os.makedirs(d,exist_ok=True)
        m=e["merge_commit"]; base=m+"^1"
        diff=subprocess.check_output(G+["diff","-M","--no-color",base,m],errors="replace",text=True)
        ns=subprocess.check_output(G+["diff","-M","--numstat",base,m],text=True)
        files=[]
        for l in ns.splitlines():
            a,dl,path=l.split("\t",2)
            files.append(dict(path=path,add=None if a=="-" else int(a),dele=None if dl=="-" else int(dl)))
        open(d+"/diff.patch","w").write(diff)
        snap=dict(pr=n,title=e["title"],base_sha=subprocess.check_output(G+["rev-parse",base],text=True).strip(),merge_sha=m,
                  files=files,diff_sha256=hashlib.sha256(diff.encode()).hexdigest())
        json.dump(snap,open(d+"/snapshot.json","w"),indent=1)
print("done")
