"""Run the model on a list of PRs (parallel), one JSON record per PR under runs/model/<pr>.json. Resumable."""
import json, sys, os, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate import model
os.makedirs("runs/model", exist_ok=True)
prs=[int(x) for x in open(sys.argv[1]).read().split()]
todo=[n for n in prs if not os.path.exists(f"runs/model/{n}.json")]
def one(n):
    s=json.load(open(f"snapshots/{n}/snapshot.json")); d=open(f"snapshots/{n}/diff.patch",errors="replace").read()
    r=model.call(s,d); json.dump(r,open(f"runs/model/{n}.json","w"),indent=1); return n,r.get("status"),r.get("risk")
with cf.ThreadPoolExecutor(int(os.environ.get("JOBS","6"))) as ex:
    for i,(n,st,rk) in enumerate(ex.map(one,todo)):
        print(i+1,len(todo),n,st,rk,flush=True)
