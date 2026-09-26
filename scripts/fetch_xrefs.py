"""ORACLE store: for each cohort PR, fetch later cross-references (issues/PRs mentioning it) and its own comments.
Never given to the gate."""
import json, subprocess, sys
FRAG = """pr%d: pullRequest(number:%d){number
 timelineItems(first:60,itemTypes:[CROSS_REFERENCED_EVENT]){nodes{... on CrossReferencedEvent{createdAt
   source{__typename ... on Issue{number title body url createdAt author{login} labels(first:10){nodes{name}}}
          ... on PullRequest{number title body url createdAt mergedAt baseRefName author{login}}}}}}
 comments(first:100){nodes{author{login} createdAt body}}
 reviews(first:50){nodes{author{login} state submittedAt body}}}"""
nums=[int(x) for x in open(sys.argv[1]).read().split()]
out=open(sys.argv[2],"a")
done=set()
try:
    for l in open(sys.argv[2]): done.add(json.loads(l)["number"])
except Exception: pass
nums=[n for n in nums if n not in done]
for i in range(0,len(nums),10):
    b=nums[i:i+10]
    q="query{repository(owner:\"OrchardCMS\",name:\"OrchardCore\"){"+" ".join(FRAG%(n,n) for n in b)+"}}"
    for attempt in range(4):
        try:
            r=json.loads(subprocess.check_output(["gh","api","graphql","-f",f"query={q}"],stderr=subprocess.DEVNULL))
            break
        except subprocess.CalledProcessError:
            import time; time.sleep(5)
    else:
        print("FAIL",b,file=sys.stderr); continue
    for k,v in r["data"]["repository"].items():
        if v: out.write(json.dumps(v)+"\n")
    out.flush()
    print(i,file=sys.stderr)
