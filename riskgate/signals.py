"""Deterministic signals read from a decision-time snapshot (diff + file list + title). Plain code, no model."""
import re

TEST = re.compile(r"(^|/)test/|\.Tests?/|Tests?\.cs$|/cypress|\.spec\.|\.test\.")
DOCS = re.compile(r"\.md$|(^|/)docs/|^mkdocs\.yml$|\.txt$|^\.github/ISSUE|README")
ASSET_SRC = re.compile(r"/Assets/|Assets\.json$|/package\.json$|gulpfile|\.(ts|tsx|vue|scss)$")
ASSET_OUT = re.compile(r"/wwwroot/")
BUILD = re.compile(r"\.(csproj|props|targets|sln)$|Directory\.Packages\.props|global\.json|^\.github/workflows|\.editorconfig$|nuget\.config$",re.I)

def classify(path):
    if TEST.search(path): return "test"
    if DOCS.search(path): return "docs"
    if BUILD.search(path): return "build"
    if ASSET_OUT.search(path): return "asset_out"
    if ASSET_SRC.search(path): return "asset_src"
    if path.endswith((".cshtml",".liquid")): return "view"
    if path.endswith(".cs"): return "code"
    return "other"

def changed_lines(diff):
    """(path, sign, text) for every added/removed line, per file."""
    out=[]; cur=None
    for l in diff.splitlines():
        if l.startswith("+++ "):
            cur=l[6:] if l.startswith("+++ b/") else cur
        elif l.startswith("--- "):
            cur=l[6:] if l.startswith("--- a/") else cur
        elif cur and l and l[0] in "+-" and not l.startswith(("+++","---")):
            out.append((cur,l[0],l[1:]))
    return out

RX = {
 "migration": re.compile(r"\bSchemaBuilder\b|CreateMapIndexTable|AlterIndexTable|CreateReduceIndexTable|AlterTable\b|DropMapIndexTable|\bUpdateFrom\d+Async\b|\bDataMigration\b"),
 "auth": re.compile(r"AuthorizeAsync|\[Authorize|\[AllowAnonymous|\bPermissions?\.[A-Z]|\bnew Permission\(|SignInAsync|PasswordSignIn|\bIsEnabled\b|ExternalLogin|ClaimsPrincipal|IAuthorizationService|LoginForm|OpenIddict|\bAntiforgery|ValidateAntiForgery|CanAccess|HasPermission"),
 "tenant": re.compile(r"\bShellSettings\b|TablePrefix|IShellHost|\bShellScope\b|TenantName|RequestUrlPrefix|RequestUrlHost|\bShellHost\b|ShellContext\b"),
 "persistence": re.compile(r"\bIndexProvider\b|\bMapIndex\b|ReduceIndex|\bQueryIndex\b|\bISession\b|SaveAsync\(|\bDialect\b|DbConnection|SqlBuilder|\bIStore\b|IsolationLevel"),
 "di_removed": re.compile(r"\bservices\.(Add|TryAdd|Remove|Replace)|\.Add(Scoped|Transient|Singleton)\b"),
 "public_decl": re.compile(r"^\s*(public|protected)\s+(?!override\b)(static\s+|virtual\s+|abstract\s+|sealed\s+|async\s+|partial\s+)*[\w<>\[\],\s\.?]+\s+\w+\s*(\(|\{|;|=>)|^\s*public\s+(interface|class|record|struct|enum)\b"),
}

def signals(snapshot, diff):
    files=snapshot["files"]
    cats={}
    for f in files: cats.setdefault(classify(f["path"]),[]).append(f)
    lines=changed_lines(diff)
    prod=[(p,s,t) for p,s,t in lines if classify(p) in ("code","view","other")]
    code=[(p,s,t) for p,s,t in lines if classify(p)=="code"]
    hit=lambda k,src: sorted({p for p,s,t in src if RX[k].search(t)})
    sig={}
    sig["migration"]=sorted({f["path"] for f in files if re.search(r"Migrations?\.cs$|/Migrations/",f["path"]) and classify(f["path"])=="code"} | set(hit("migration",code)))
    sig["auth"]=hit("auth",prod)
    sig["tenant"]=hit("tenant",code)
    sig["persistence"]=sorted(set(hit("persistence",code)) | {f["path"] for f in files if classify(f["path"])=="code" and re.search(r"IndexProvider\.cs$|/Indexes?/|/OrchardCore\.Data[./]",f["path"])})
    sig["di_changed"]=sorted({p for p,s,t in code if s=="-" and RX["di_removed"].search(t)})
    # a public/protected declaration removed or rewritten in shipped code = a contract other apps may compile against
    sig["contract"]=sorted({p for p,s,t in code if s=="-" and RX["public_decl"].search(t)})
    sig["build"]=[f["path"] for f in cats.get("build",[])]
    # generated assets edited without their source, or source without regenerated output
    src_mods={re.sub(r"/Assets/.*","",f["path"]) for f in cats.get("asset_src",[])}
    out_mods={re.sub(r"/wwwroot/.*","",f["path"]) for f in cats.get("asset_out",[])}
    sig["asset_mismatch"]=sorted((src_mods ^ out_mods))
    n_lines=sum((f["add"] or 0)+(f["dele"] or 0) for f in files if classify(f["path"]) not in ("docs","test"))
    sig["n_files"]=len(files)
    sig["n_prod_lines"]=n_lines
    sig["tests_touched"]=bool(cats.get("test"))
    sig["only_docs_or_tests"]=all(classify(f["path"]) in ("docs","test") for f in files) if files else True
    sig["core_framework"]=sorted({f["path"] for f in files if f["path"].startswith("src/OrchardCore/") and classify(f["path"])=="code"})
    return sig
