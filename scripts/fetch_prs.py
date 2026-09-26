"""Fetch all merged PRs of OrchardCMS/OrchardCore in a date range (GraphQL search, split by month).
Output: data/raw/prs_<from>_<to>.jsonl. Bodies are stored for the ORACLE only; the gate never sees them."""
import json, subprocess, sys, datetime, os
Q = """query($q:String!,$after:String){search(query:$q,type:ISSUE,first:100,after:$after){issueCount pageInfo{hasNextPage endCursor}
nodes{... on PullRequest{number title body author{login} createdAt mergedAt baseRefName headRefOid baseRefOid
mergeCommit{oid} additions deletions changedFiles labels(first:20){nodes{name}} url}}}}"""
def run(q, after=None):
    args = ["gh","api","graphql","-f",f"query={Q}","-f",f"q={q}"]
    if after: args += ["-f",f"after={after}"]
    return json.loads(subprocess.check_output(args))["data"]["search"]
start = datetime.date.fromisoformat(sys.argv[1]); end = datetime.date.fromisoformat(sys.argv[2])
os.makedirs("data/raw", exist_ok=True)
out = open(f"data/raw/prs_{start}_{end}.jsonl","w"); n=0
d = start
while d < end:
    nxt = min((d.replace(day=1)+datetime.timedelta(days=32)).replace(day=1), end)
    q = f"repo:OrchardCMS/OrchardCore is:pr is:merged merged:{d}..{nxt - datetime.timedelta(days=1)}"
    after=None
    while True:
        r = run(q, after)
        for node in r["nodes"]:
            out.write(json.dumps(node)+"\n"); n+=1
        if not r["pageInfo"]["hasNextPage"]: break
        after = r["pageInfo"]["endCursor"]
    print(d, r["issueCount"], file=sys.stderr)
    d = nxt
print(n)
