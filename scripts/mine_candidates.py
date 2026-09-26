import json,re
prs={p["number"]:p for p in map(json.loads,open("data/raw/prs_2023-01-01_2026-09-27.jsonl"))}
KW=re.compile(r"(regress|introduc|caused|broke|broken|break(s|ing)? |revert|since #|after #|bug|fix(es|ed)? .*#|side.?effect|no longer|stopped working|doesn't work|does not work|not working)",re.I)
cands=[]
for l in open("data/raw/xrefs.jsonl"):
    x=json.loads(l); n=x["number"]; merged=prs[n]["mergedAt"]
    for e in x["timelineItems"]["nodes"]:
        s=e.get("source") or {}
        if not s or e["createdAt"]<merged: continue
        if s.get("number")==n: continue
        text=(s.get("title") or "")+"\n"+(s.get("body") or "")
        # context around the mention
        ctx=[m.start() for m in re.finditer(r"(#%d\b|/pull/%d\b)"%(n,n),text)]
        snips=[text[max(0,i-250):i+150].replace("\n"," ") for i in ctx]
        hit=any(KW.search(sn) for sn in snips) or (not ctx and KW.search(text[:400]))
        if hit:
            cands.append({"pr":n,"kind":"xref","src":s["__typename"],"src_num":s["number"],"src_title":s["title"],"when":e["createdAt"][:10],"snips":snips[:2] if ctx else ["(mention in a comment) "+text[:300].replace("\n"," ")]})
    for c in x["comments"]["nodes"]:
        if c["createdAt"]>merged and re.search(r"(regress|broke|broken|revert|caused|introduc|bug|issue|no longer|not working|this change)",c["body"] or "",re.I):
            cands.append({"pr":n,"kind":"postmerge_comment","who":(c["author"] or {}).get("login"),"when":c["createdAt"][:10],"snips":[c["body"][:400].replace("\n"," ")]})
json.dump(cands,open("data/raw/label_candidates.json","w"),indent=1)
print(len(cands), len({c["pr"] for c in cands}))
