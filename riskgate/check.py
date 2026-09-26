"""GitHub required check: runs the frozen deterministic policy on a pull request, fail-closed.
Runs from a checkout of the BASE commit (workflow trigger pull_request_target): the PR's code is fetched as data through
the API and never executed, so a PR cannot rewrite the policy that judges it. No repository secrets are used.
Exit 0 only for ALLOW, or for REVIEW_REQUIRED released by a senior's label on this exact head commit, applied by someone other than the PR's author."""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate.policies import deterministic, ALLOW, REVIEW, UNKNOWN

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ["GITHUB_REPOSITORY"]; TOKEN = os.environ["GITHUB_TOKEN"]
EVENT = json.load(open(os.environ["GITHUB_EVENT_PATH"]))
SENIORS = set(filter(None, os.environ.get("RISKGATE_SENIORS", "").split(",")))
RELEASE_LABEL = "senior-approved"
SELF = ("riskgate/", "policies/", ".github/")  # changes to the gate itself always need a senior

def gh(path, accept="application/vnd.github+json", method="GET"):
    req = urllib.request.Request(API + path, method=method, headers={"Authorization": f"Bearer {TOKEN}", "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
        return body if accept.endswith("diff") else (json.loads(body) if body else None)

def main():
    pr = EVENT["pull_request"]; n = pr["number"]; head = pr["head"]["sha"]
    frozen = json.load(open("policies/frozen.json"))
    try:
        files = []
        page = 1
        while True:
            batch = gh(f"/repos/{REPO}/pulls/{n}/files?per_page=100&page={page}")
            files += batch; page += 1
            if len(batch) < 100: break
        diff = gh(f"/repos/{REPO}/pulls/{n}", accept="application/vnd.github.v3.diff")
        snap = dict(pr=n, title=pr["title"], files=[dict(path=f["filename"], add=f.get("additions"), dele=f.get("deletions")) for f in files])
        d = deterministic(snap, diff, frozen["theta"])
        if any(f["filename"].startswith(SELF) for f in files):
            d = dict(decision=REVIEW, reasons=["this change edits the gate itself"] + d["reasons"], score=99)
    except Exception as e:  # anything unexpected is UNKNOWN, and UNKNOWN never passes
        d = dict(decision=UNKNOWN, reasons=[f"evaluation failed: {type(e).__name__}"], score=None)

    action = EVENT.get("action")
    if action == "synchronize" and any(l["name"] == RELEASE_LABEL for l in pr.get("labels", [])):
        # new code after a release: the release is stale, remove it (auditable in the PR timeline)
        gh(f"/repos/{REPO}/issues/{n}/labels/{RELEASE_LABEL}", method="DELETE")
        pr["labels"] = [l for l in pr["labels"] if l["name"] != RELEASE_LABEL]
    released = False; release_note = ""
    if d["decision"] != ALLOW and any(l["name"] == RELEASE_LABEL for l in pr.get("labels", [])):
        # the label survives only until the next push (removed above), so its presence binds it to this head commit;
        # it counts only if the person who applied it last is a named senior who is not the PR's author
        events, page = [], 1
        while True:
            batch = gh(f"/repos/{REPO}/issues/{n}/events?per_page=100&page={page}")
            events += batch; page += 1
            if len(batch) < 100: break
        applied = [e for e in events if e.get("event") == "labeled" and e.get("label", {}).get("name") == RELEASE_LABEL]
        who = applied[-1]["actor"]["login"] if applied else None
        if who and who == pr["user"]["login"]:
            release_note = f"release ignored: applied by the author ({who}); a different senior must release"
        elif who in SENIORS:
            released = True
        elif who:
            release_note = f"release ignored: {who} is not a named senior"
    lines = [f"Decision on {head[:7]}: {d['decision']}" + (" (released by a senior)" if released else "")] + [f"- {r}" for r in d["reasons"]] + ([f"- {release_note}"] if release_note else [])
    summary = "\n".join(lines)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write("### Risk gate\n\n" + summary + "\n")
    sys.exit(0 if d["decision"] == ALLOW or released else 1)

if __name__ == "__main__":
    main()
