"""Checks added after the evaluation (independent review, 26/09/2026). The frozen policies are untouched.

validate_record: a stored model answer is used at replay only if it was produced for exactly this input (input and
prompt fingerprints recomputed from the snapshot) and its answer passes strict parsing. Otherwise the replay treats
the model result as missing, which the hybrid turns into UNKNOWN.

hybrid_deployable: the frozen hybrid, except that a change whose model input was truncated (diff over the character
budget or over 400 files) can never be ALLOWed: it becomes UNKNOWN. Reported next to the frozen result, never instead."""
import hashlib
from . import model
from .policies import hybrid, needs_model, ALLOW, UNKNOWN

def validate_record(rec, snapshot, diff):
    if rec is None: return None, "no stored answer"
    if rec.get("prompt_version") != model.PROMPT_VERSION: return None, "prompt fingerprint differs"
    if rec.get("input_sha256") != hashlib.sha256(model.build_input(snapshot, diff).encode()).hexdigest():
        return None, "input fingerprint differs"
    if rec.get("status") != "ok": return rec, "model failed"          # kept: the hybrid turns it into UNKNOWN
    last = [a for a in rec["attempts"] if "raw" in a]
    if not last or last[-1].get("is_error"): return None, "last attempt errored"
    v = model.parse_answer(last[-1]["raw"])
    if not v or v[0] != rec.get("risk"): return None, "answer fails strict parsing"
    return rec, "ok"

def hybrid_deployable(snapshot, diff, model_result, tau):
    d = hybrid(snapshot, diff, model_result, tau)
    if d["decision"] == ALLOW and needs_model(snapshot, diff) and not model.input_complete(snapshot, diff):
        return dict(decision=UNKNOWN, reasons=["model input was truncated: not allowed without a complete read"] + d["reasons"], score=None)
    return d
