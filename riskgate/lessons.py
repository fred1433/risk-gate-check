"""Lessons from the evaluation, kept OUT of the frozen policies and never used to rescore history.

Destructive service registration (from the missed #18508): an added call that removes or replaces registrations
already made by other features (RemoveAll, Remove, Replace on the service collection) can silently disable them.
The frozen deterministic policy only watched deleted registration lines, worth one point against a threshold of three,
so widening that detector alone would not have escalated #18508. The lesson needs its own escalation rule."""
import re
from .signals import changed_lines, classify

DESTRUCTIVE = re.compile(r"\bservices\.(RemoveAll|Remove|Replace)\b|\.RemoveAll<|\bTryRemove|\.Replace\(ServiceDescriptor")

def destructive_registration(diff):
    return sorted({p for p, sign, text in changed_lines(diff) if sign == "+" and classify(p) == "code" and DESTRUCTIVE.search(text)})

def with_lessons(decision, diff):
    """Wrap any policy decision: escalate an ALLOW when a destructive registration call is added."""
    hits = destructive_registration(diff)
    if decision["decision"] == "ALLOW" and hits:
        return dict(decision="REVIEW_REQUIRED", reasons=[f"adds a call that removes existing service registrations: {hits[0]}"] + decision["reasons"], score=None)
    return decision
