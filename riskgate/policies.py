"""The three routing policies. Each returns a Decision: ALLOW | REVIEW_REQUIRED | UNKNOWN, with reasons.
UNKNOWN is never permissive: the replay and the GitHub check both treat it as REVIEW_REQUIRED."""
import re, json, math
from .signals import signals, classify

ALLOW, REVIEW, UNKNOWN = "ALLOW", "REVIEW_REQUIRED", "UNKNOWN"

# ---- Policy 1: sensitive areas (a path list a lead could write in five minutes) ----
SENSITIVE = [
    (r"Migrations?\.cs$|/Migrations/", "migration file"),
    (r"OrchardCore\.(Users|OpenId|Roles|Security|Cors)/|Authentication|Authorization|/Permissions\.cs$|Login", "auth or permissions area"),
    (r"OrchardCore\.Tenants/|/Shell/|Environment\.Shell|ShellSettings", "tenant or shell area"),
    (r"OrchardCore\.Data(\.YesSql)?(\.Abstractions)?/|/Indexes?/|IndexProvider", "data or index area"),
    (r"\.Abstractions/", "public abstractions (cross-app contract)"),
]
def simple(snapshot, diff=None):
    reasons=[]
    for f in snapshot["files"]:
        if classify(f["path"]) in ("test","docs"): continue
        for rx,why in SENSITIVE:
            if re.search(rx,f["path"]): reasons.append(f"{why}: {f['path']}"); break
    return dict(decision=REVIEW if reasons else ALLOW, reasons=reasons[:5], score=len(reasons))

# ---- shared structural triggers (plain code where the signal is structural) ----
def hard_triggers(sig):
    r=[]
    for k,why in (("migration","schema migration code"),("auth","authorization or sign-in logic changed"),("tenant","tenant or shell isolation code changed")):
        if sig[k]: r.append(f"{why}: {sig[k][0]}" + (f" (+{len(sig[k])-1})" if len(sig[k])>1 else ""))
    return r

def soft_score(sig):
    s=0; r=[]
    def add(w,why): 
        nonlocal s; s+=w; r.append(f"+{w} {why}")
    if sig["persistence"]: add(2,f"persistence/query code: {sig['persistence'][0]}")
    if sig["contract"]: add(2,f"public declaration removed or rewritten: {sig['contract'][0]}")
    if sig["asset_mismatch"]: add(2,f"asset source and generated output out of step: {sig['asset_mismatch'][0]}")
    if sig["di_changed"]: add(1,f"service registration changed: {sig['di_changed'][0]}")
    if sig["build"]: add(1,f"build or packaging file: {sig['build'][0]}")
    if sig["core_framework"]: add(1,f"core framework code: {sig['core_framework'][0]}")
    if not sig["tests_touched"] and sig["n_prod_lines"]>50: add(1,"no test changed alongside production change")
    if sig["n_prod_lines"]>1500: add(2,f"{sig['n_prod_lines']} production lines changed")
    elif sig["n_prod_lines"]>300: add(1,f"{sig['n_prod_lines']} production lines changed")
    if sig["n_files"]>30: add(1,f"{sig['n_files']} files")
    return s,r

# ---- Policy 2: deterministic ----
def deterministic(snapshot, diff, theta):
    if diff is None: return dict(decision=UNKNOWN,reasons=["diff unavailable"],score=None)
    sig=signals(snapshot,diff)
    if sig["only_docs_or_tests"]: return dict(decision=ALLOW,reasons=["docs or tests only"],score=0)
    hard=hard_triggers(sig); s,r=soft_score(sig)
    if hard: return dict(decision=REVIEW,reasons=hard+r,score=99)
    return dict(decision=REVIEW if s>=theta else ALLOW, reasons=r or ["no structural risk signal"], score=s)

# ---- Policy 3: hybrid (same structural triggers; the model reads intent only where no trigger fired) ----
def hybrid(snapshot, diff, model_result, tau):
    if diff is None: return dict(decision=UNKNOWN,reasons=["diff unavailable"],score=None)
    sig=signals(snapshot,diff)
    if sig["only_docs_or_tests"]: return dict(decision=ALLOW,reasons=["docs or tests only"],score=0)
    hard=hard_triggers(sig)
    if hard: return dict(decision=REVIEW,reasons=hard,score=99,model_called=False)
    if model_result is None or model_result.get("status")!="ok":
        why = (model_result or {}).get("status","model not run")
        return dict(decision=UNKNOWN,reasons=[f"model result unavailable ({why}): escalated"],score=None,model_called=True)
    risk=model_result["risk"]
    return dict(decision=REVIEW if risk>=tau else ALLOW, reasons=[f"model risk {risk}/5: {model_result['reason']}"], score=risk, model_called=True)

def needs_model(snapshot, diff):
    if diff is None: return False
    sig=signals(snapshot,diff)
    return not sig["only_docs_or_tests"] and not hard_triggers(sig)

def is_review(d): return d["decision"]!=ALLOW
