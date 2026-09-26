"""GitHub required check: runs the frozen deterministic policy on a pull request, fail-closed.

Runs from a checkout of the BASE commit (trigger pull_request_target): the PR's code is fetched as data through the API
and never executed, so a PR cannot rewrite the policy that judges it. No repository secrets are used.

Contract
- ALLOW passes.
- REVIEW_REQUIRED passes only with a senior approval bound to the full head SHA that was evaluated: a GitHub review in
  state APPROVED whose commit_id equals that SHA, submitted by a named senior who is not the PR's author, and not
  superseded by a later review from the same person. GitHub reviews carry the commit they were given on, so a new
  push leaves the approval on the old SHA, where it no longer counts. The `senior-approved` label only asks for a
  re-run (a review event cannot start a pull_request_target workflow); it is never the evidence.
- UNKNOWN never passes, whatever approvals exist. Any failure to read the PR, an incomplete file list, or a head that
  moves while the PR is being read gives UNKNOWN.
"""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate.policies import deterministic, ALLOW, REVIEW, UNKNOWN

SELF = ("riskgate/", "policies/", ".github/")  # changes to the gate itself always need a senior


def _all_pages(gh, path):
    out, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        batch = gh(f"{path}{sep}per_page=100&page={page}")
        out += batch; page += 1
        if len(batch) < 100:
            return out


def senior_approval(reviews, head_sha, author, seniors):
    """The approving senior's login if a valid approval exists for exactly head_sha, else None."""
    latest = {}
    for r in reviews:  # API order is chronological; a later review by the same person supersedes an earlier one
        who = (r.get("user") or {}).get("login")
        if who and r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[who] = r
    for who, r in latest.items():
        if r["state"] == "APPROVED" and r.get("commit_id") == head_sha and who in seniors and who != author:
            return who
    return None


def evaluate(event, gh, frozen, seniors):
    """Returns (exit_code, summary_lines). gh(path, accept=...) is the API accessor (injected for tests)."""
    repo_pr = event["pull_request"]; n = repo_pr["number"]; head = repo_pr["head"]["sha"]
    author = repo_pr["user"]["login"]
    try:
        before = gh(f"/pulls/{n}")
        if before["head"]["sha"] != head:
            raise RuntimeError("head moved since this event; the newer event's run decides")
        files = _all_pages(gh, f"/pulls/{n}/files")
        if len(files) != before["changed_files"]:
            raise RuntimeError(f"file list incomplete ({len(files)} of {before['changed_files']})")
        diff = gh(f"/pulls/{n}", accept="application/vnd.github.v3.diff")
        after = gh(f"/pulls/{n}")
        if after["head"]["sha"] != head:
            raise RuntimeError("head moved while the pull request was being read")
        snap = dict(pr=n, title=before["title"], files=[dict(path=f["filename"], add=f.get("additions"), dele=f.get("deletions")) for f in files])
        d = deterministic(snap, diff, frozen["theta"])
        if d["decision"] == ALLOW and any(f["filename"].startswith(SELF) for f in files):
            d = dict(decision=REVIEW, reasons=["this change edits the gate itself"] + d["reasons"], score=99)
    except Exception as e:  # anything unexpected is UNKNOWN, and UNKNOWN never passes
        d = dict(decision=UNKNOWN, reasons=[f"evaluation failed: {type(e).__name__}: {e}"[:200]], score=None)

    released_by = None
    if d["decision"] == REVIEW:  # only REVIEW_REQUIRED can ever be released
        try:
            released_by = senior_approval(_all_pages(gh, f"/pulls/{n}/reviews"), head, author, seniors)
        except Exception:
            released_by = None
    lines = [f"Decision on {head}: {d['decision']}" + (f" (released by {released_by}, approval on this exact commit)" if released_by else "")]
    lines += [f"- {r}" for r in d["reasons"]]
    if d["decision"] == REVIEW and not released_by:
        lines.append("- waiting for an approving review on this exact commit by a named senior other than the author")
    ok = d["decision"] == ALLOW or (d["decision"] == REVIEW and released_by is not None)
    return (0 if ok else 1), lines


def main():
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com"); repo = os.environ["GITHUB_REPOSITORY"]; token = os.environ["GITHUB_TOKEN"]
    def gh(path, accept="application/vnd.github+json"):
        req = urllib.request.Request(f"{api}/repos/{repo}{path}", headers={"Authorization": f"Bearer {token}", "Accept": accept})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            return body if accept.endswith("diff") else json.loads(body)
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"]))
    seniors = set(filter(None, os.environ.get("RISKGATE_SENIORS", "").split(",")))
    code, lines = evaluate(event, gh, json.load(open("policies/frozen.json")), seniors)
    print("\n".join(lines))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write("### Risk gate\n\n" + "\n".join(lines) + "\n")
    sys.exit(code)


if __name__ == "__main__":
    main()
