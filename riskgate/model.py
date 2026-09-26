"""The model component of the hybrid policy. Runs `claude -p` (subscription) from an empty neutral directory with no tools,
no settings sources, no MCP servers and a fixed system prompt. It sees only the clean snapshot: title, file list, diff."""
import json, subprocess, hashlib, os, re, time, tempfile

SYSTEM = ("You are the risk gate in front of an auto-merge pipeline for Orchard Core, a multi-tenant .NET CMS used as a "
          "framework by other applications. A pull request you pass merges without a senior developer reading it; one you "
          "escalate waits for a senior. Judge how likely this change is to break existing behaviour for sites, tenants, "
          "modules or applications built on it. Answer with JSON only: "
          "{\"risk\": <1-5>, \"reason\": \"<one sentence naming the specific concern, or why it is safe>\"}")
MODEL = os.environ.get("RISKGATE_MODEL", "sonnet")
DIFF_BUDGET = 60000
PROMPT_VERSION = hashlib.sha256(SYSTEM.encode()).hexdigest()[:12]

def build_input(snapshot, diff):
    files = "\n".join(f"{f['path']} (+{f['add'] if f['add'] is not None else 'bin'} -{f['dele'] if f['dele'] is not None else 'bin'})" for f in snapshot["files"][:400])
    more = f"\n... and {len(snapshot['files'])-400} more files" if len(snapshot["files"])>400 else ""
    d = diff if len(diff) <= DIFF_BUDGET else diff[:DIFF_BUDGET] + f"\n[diff truncated: {len(diff)} characters in total]"
    return f"Title: {snapshot['title']}\n\nFiles changed:\n{files}{more}\n\nDiff:\n{d}"

NEUTRAL = tempfile.mkdtemp(prefix="riskgate-neutral-")

def call(snapshot, diff, retries=2):
    inp = build_input(snapshot, diff)
    rec = dict(pr=snapshot["pr"], model_alias=MODEL, prompt_version=PROMPT_VERSION,
               input_sha256=hashlib.sha256(inp.encode()).hexdigest(), attempts=[])
    for a in range(retries+1):
        t=time.time()
        try:
            p = subprocess.run(["claude","-p","--model",MODEL,"--tools","","--setting-sources","","--strict-mcp-config",
                                "--mcp-config",'{"mcpServers":{}}',"--disable-slash-commands","--no-session-persistence",
                                "--system-prompt",SYSTEM,"--output-format","json"],
                               input=inp, capture_output=True, text=True, cwd=NEUTRAL, timeout=300)
            out = json.loads(p.stdout)
            raw = out.get("result","")
            att = dict(seconds=round(time.time()-t,1), usage={k:out.get("usage",{}).get(k) for k in ("input_tokens","output_tokens","cache_read_input_tokens","cache_creation_input_tokens")},
                       model=list((out.get("modelUsage") or {}).keys()), is_error=out.get("is_error"), raw=raw)
            rec["attempts"].append(att)
            m = re.search(r"\{.*\}", raw, re.S)
            j = json.loads(m.group(0)) if m else None
            if j and int(j.get("risk",0)) in (1,2,3,4,5) and j.get("reason"):
                rec.update(status="ok", risk=int(j["risk"]), reason=str(j["reason"])[:400]); return rec
        except Exception as e:
            rec["attempts"].append(dict(seconds=round(time.time()-t,1), error=repr(e)[:300]))
    rec["status"]="malformed_or_failed"; return rec
