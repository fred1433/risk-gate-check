"""Contract tests for the GitHub check (python3 -m unittest discover tests)."""
import unittest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate.check import evaluate

H1 = "a" * 40; H2 = "b" * 40
AUTH_DIFF = """diff --git a/app/C.cs b/app/C.cs
--- a/app/C.cs
+++ b/app/C.cs
@@ -1,1 +1,1 @@
-if (!(await _authorizationService.AuthorizeAsync(User, t, "X")).Succeeded)
+if (t != "demo" && !(await _authorizationService.AuthorizeAsync(User, t, "X")).Succeeded)
"""
DOC_DIFF = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,1 +1,1 @@
-a
+b
"""
FROZEN = {"theta": 3}
SENIORS = {"senior1", "senior2"}

def event(head=H1, author="dev"):
    return {"pull_request": {"number": 7, "head": {"sha": head}, "user": {"login": author}}}

class FakeGH:
    def __init__(self, heads, files, diff, reviews=(), fail=None, changed_files=None):
        self.heads = list(heads); self.files = files; self.diff = diff; self.reviews = list(reviews); self.fail = fail
        self.changed = len(files) if changed_files is None else changed_files
    def __call__(self, path, accept="application/vnd.github+json"):
        if self.fail and self.fail in path: raise TimeoutError("simulated")
        if path == "/pulls/7":
            if accept.endswith("diff"): return self.diff
            h = self.heads.pop(0) if len(self.heads) > 1 else self.heads[0]
            return {"head": {"sha": h}, "changed_files": self.changed, "title": "t"}
        if path.startswith("/pulls/7/files"): return self.files if "page=1" in path else []
        if path.startswith("/pulls/7/reviews"): return self.reviews if "page=1" in path else []
        raise AssertionError(path)

AUTH_FILES = [{"filename": "app/C.cs", "additions": 1, "deletions": 1}]
DOC_FILES = [{"filename": "README.md", "additions": 1, "deletions": 1}]
def approve(who, sha, state="APPROVED"): return {"user": {"login": who}, "state": state, "commit_id": sha}

class CheckContract(unittest.TestCase):
    def run_check(self, gh, ev=None): return evaluate(ev or event(), gh, FROZEN, SENIORS)

    def test_allow_passes(self):
        self.assertEqual(self.run_check(FakeGH([H1], DOC_FILES, DOC_DIFF))[0], 0)

    def test_review_without_approval_fails(self):
        code, lines = self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF))
        self.assertEqual(code, 1); self.assertIn("REVIEW_REQUIRED", lines[0])

    def test_review_with_senior_approval_on_head_passes(self):
        self.assertEqual(self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF, [approve("senior1", H1)]))[0], 0)

    def test_unknown_never_released_even_with_valid_approval(self):
        code, lines = self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF, [approve("senior1", H1)], fail="/files"))
        self.assertEqual(code, 1); self.assertIn("UNKNOWN", lines[0]); self.assertNotIn("released", lines[0])

    def test_approval_on_previous_commit_does_not_count_after_push(self):
        self.assertEqual(self.run_check(FakeGH([H2], AUTH_FILES, AUTH_DIFF, [approve("senior1", H1)]), event(H2))[0], 1)

    def test_head_moved_during_read_is_unknown(self):
        code, lines = self.run_check(FakeGH([H1, H2], AUTH_FILES, AUTH_DIFF, [approve("senior1", H1)]))
        self.assertEqual(code, 1); self.assertIn("UNKNOWN", lines[0])

    def test_stale_event_after_push_is_unknown(self):
        # a run for an older event (e.g. a relabel queued before a push) sees the new head and refuses to decide
        code, lines = self.run_check(FakeGH([H2], AUTH_FILES, AUTH_DIFF, [approve("senior1", H1)]), event(H1))
        self.assertEqual(code, 1); self.assertIn("UNKNOWN", lines[0])

    def test_author_cannot_release(self):
        self.assertEqual(self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF, [approve("senior1", H1)]), event(author="senior1"))[0], 1)

    def test_non_senior_cannot_release(self):
        self.assertEqual(self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF, [approve("someone", H1)]))[0], 1)

    def test_later_changes_requested_revokes(self):
        rv = [approve("senior1", H1), approve("senior1", H1, "CHANGES_REQUESTED")]
        self.assertEqual(self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF, rv))[0], 1)

    def test_dismissed_approval_revokes(self):
        rv = [approve("senior1", H1), approve("senior1", H1, "DISMISSED")]
        self.assertEqual(self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF, rv))[0], 1)

    def test_incomplete_file_list_is_unknown(self):
        code, lines = self.run_check(FakeGH([H1], DOC_FILES, DOC_DIFF, changed_files=5000))
        self.assertEqual(code, 1); self.assertIn("UNKNOWN", lines[0])

    def test_reviews_api_failure_keeps_it_blocked(self):
        self.assertEqual(self.run_check(FakeGH([H1], AUTH_FILES, AUTH_DIFF, [approve("senior1", H1)], fail="/reviews"))[0], 1)

    def test_editing_the_gate_needs_review(self):
        files = [{"filename": "policies/frozen.json", "additions": 1, "deletions": 1}]
        self.assertEqual(self.run_check(FakeGH([H1], files, DOC_DIFF.replace("README.md", "policies/frozen.json")))[0], 1)

if __name__ == "__main__":
    unittest.main()
