"""The trivial bound: zero misses, and a senior reads every change."""
def decide(snapshot, diff):
    return {"decision": "REVIEW_REQUIRED", "reasons": ["every change is reviewed"]}
