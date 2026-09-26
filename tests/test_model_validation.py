import unittest, os, sys, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riskgate import model
from riskgate.strict import validate_record, hybrid_deployable
from riskgate.policies import UNKNOWN, ALLOW

class Parse(unittest.TestCase):
    def test_accepts_integer(self): self.assertEqual(model.parse_answer('{"risk": 3, "reason": "x"}'), (3, "x"))
    def test_rejects_float(self): self.assertIsNone(model.parse_answer('{"risk": 2.9, "reason": "x"}'))
    def test_rejects_bool(self): self.assertIsNone(model.parse_answer('{"risk": true, "reason": "x"}'))
    def test_rejects_string_number(self): self.assertIsNone(model.parse_answer('{"risk": "3", "reason": "x"}'))
    def test_rejects_out_of_range(self): self.assertIsNone(model.parse_answer('{"risk": 6, "reason": "x"}'))
    def test_rejects_empty_reason(self): self.assertIsNone(model.parse_answer('{"risk": 2, "reason": "  "}'))
    def test_rejects_malformed(self): self.assertIsNone(model.parse_answer('{"risk": 4, "reason": "unterminated'))

SNAP = {"pr": 1, "title": "t", "files": [{"path": "src/A.cs", "add": 1, "dele": 0}]}
DIFF = "diff --git a/src/A.cs b/src/A.cs\n--- a/src/A.cs\n+++ b/src/A.cs\n@@ -1,0 +1,1 @@\n+var x = 1;\n"
def rec(risk=2, raw=None, inp=None):
    return {"prompt_version": model.PROMPT_VERSION, "input_sha256": hashlib.sha256((inp or model.build_input(SNAP, DIFF)).encode()).hexdigest(),
            "status": "ok", "risk": risk, "reason": "r", "attempts": [{"raw": raw or json.dumps({"risk": risk, "reason": "r"}), "is_error": False}]}

class Replay(unittest.TestCase):
    def test_matching_record_accepted(self): self.assertEqual(validate_record(rec(), SNAP, DIFF)[1], "ok")
    def test_stale_input_rejected(self): self.assertIsNone(validate_record(rec(inp="other"), SNAP, DIFF)[0])
    def test_prompt_change_rejected(self):
        r = rec(); r["prompt_version"] = "000"; self.assertIsNone(validate_record(r, SNAP, DIFF)[0])
    def test_nonstrict_stored_answer_rejected(self): self.assertIsNone(validate_record(rec(raw='{"risk": 2.4, "reason": "r"}'), SNAP, DIFF)[0])
    def test_truncated_input_never_allowed(self):
        big = DIFF + "+" + "y" * (model.DIFF_BUDGET + 10) + "\n"
        d = hybrid_deployable(SNAP, big, {"status": "ok", "risk": 1, "reason": "fine"}, 3)
        self.assertEqual(d["decision"], UNKNOWN)
    def test_complete_input_low_risk_allowed(self):
        self.assertEqual(hybrid_deployable(SNAP, DIFF, {"status": "ok", "risk": 1, "reason": "fine"}, 3)["decision"], ALLOW)

if __name__ == "__main__":
    unittest.main()
