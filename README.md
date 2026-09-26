# risk-gate-check

Which pull requests can skip senior review? This repository replays three routing policies on the real history of
[Orchard Core](https://github.com/OrchardCMS/OrchardCore) (a multi-tenant .NET CMS) and counts, for each one, how many
changes that later proved to break something it would have let through, and how much work it sent to a senior.

It is a historical replay on a public project. It is an independent study, not endorsed by the Orchard Core project.

## Result (evaluation cohort: 479 PRs merged into `main` in 2025)

| Policy | Confirmed failure-introducing changes that passed | Sent to a senior |
|---|---|---|
| Sensitive areas (a path list) | 7 of 10 (95% CI 35% to 93%) | 155 of 479 (32.4%) |
| Deterministic (structural diff signals) | 7 of 10 (35% to 93%) | 155 of 479 (32.4%) |
| Hybrid (same structural triggers, a model reads the rest), three independent passes | 2, 2 and 2 of 10 (3% to 56%) | 166, 165 and 165 of 479 (34.4% to 34.7%) |

- Routing a random third of the PRs to a senior would let about 6.8 of the 10 through: the two rule-based policies do
  no better than chance on this cohort.
- The model is not deterministic. The hybrid passed 2 of 10 in each pass, but not the same 2: #18508 every time,
  then #17421 (passes 1 and 2) or #17369 (pass 3). Its risk ratings for each confirmed case, per pass, are in
  `results/hybrid_passes_evaluation.json`; each pass caught 5 confirmed cases the rules passed: four of them in
  all three passes, #17369 in two, #17421 in one.
- In each pass, the hybrid escalated 5 confirmed cases that the deterministic policy passed, and the reverse happened
  0 times (exact two-sided sign test on 5 discordant cases: p = 0.06).
- Wider label set (confirmed plus incomplete attributions, 22 cases): 14 and 12 passed for the rules; 5, 6 and 4 for
  the hybrid.
- UNKNOWN decisions (malformed model answers, escalated by rule): 2, 1 and 0 per pass, all counted as sent to a senior.

Files: `results/summary_evaluation*.json`, `results/decisions_evaluation*.jsonl` (every PR, every policy, with
reasons), `runs/model*/<pr>.json` (raw model output, input hash, tokens, retries), one directory per pass.

## Method

- **Cohort** (`data/cohort_manifest.json`): every PR merged into `main`, excluding dependency and bookkeeping bots.
  Development: 891 PRs merged in 2024. Evaluation: 479 PRs merged in 2025. Outcomes observed until 2026-09-26.
- **What the gate sees**: the merged change (squash commit against its first parent), its title and file list.
  No description, comments or later history. `scripts/make_snapshots.py` writes these snapshots
  (`data/snapshot_diff_sha256.json` holds their hashes); the model reads them from an empty directory with no tools
  (`riskgate/model.py`).
- **Labels** (`oracle/`): cross-references and post-merge comments of every cohort PR were mined
  (`scripts/fetch_prs.py`, `scripts/fetch_xrefs.py`, `scripts/mine_candidates.py`, output in `oracle/mined_candidates.json`),
  then read by hand (`oracle/adjudication.py`, built into `oracle/labels.json` by `scripts/build_labels.py`).
  Class A, confirmed: a failure users of the software can hit, tied to the PR by a merged revert with a stated defect,
  an attribution restated in the merged fix, or made by a core maintainer, or a stated reproducible witness; and the
  fix touches a file the PR touched. Class B: attribution by a non-maintainer, hedged, a revert without a stated
  defect, or a CI-only failure (the flaky test caused by #17951 is B). Class C: SZZ only (`oracle/szz_candidates.json`).
- **Policies** (`riskgate/policies.py`). The thresholds were chosen on the 2024 cohort only, so that each policy sends
  about as many PRs to a senior as the sensitive-area list did in 2024 (36.4%), and frozen in commit 8c69d2d
  (2026-09-26 10:55:20 -03:00). `policies/frozen.json` records what existed at that moment:
  - the 2025 labels had already been written (10:35), and the rule author had read the titles of the 2025 labelled
    PRs before writing the rules;
  - the list of 2025 PRs the model would read had been computed from the structural signals (10:50);
  - no 2025 policy decision and no 2025 model answer existed yet (first 2025 model answer 10:55:33, scoring 11:02).
  A check against tuning on 2025: in 2024 the deterministic policy passed 7 of 28 confirmed failures at 32.5% load,
  where random routing passes 18.9; the path list 8 of 28 at 36.4% (random: 17.8). In 2025 both fall to chance level.
- **Model**: `claude-sonnet-5` through `claude -p` on a subscription. Evaluation, three passes over the same 357 PRs:
  1,107 calls, 9.06 M input and 279 k output tokens. Calibration: 169 calls on a seeded 2024 sample and the 2024 positives.

## Reproduce

```
git clone https://github.com/fred1433/risk-gate-check && cd risk-gate-check
git clone --mirror https://github.com/OrchardCMS/OrchardCore.git work/oc-full.git
python3 scripts/make_snapshots.py                 # 1,370 snapshots from the manifest, about a minute
python3 scripts/evaluate.py evaluation            # pass 1; add runs/model_pass2 or runs/model_pass3 for the others
```

No network access or model call is needed to replay the stored results. Rebuilding the labels from scratch needs the
GitHub CLI: `scripts/fetch_prs.py 2023-01-01 2026-09-27`, then `scripts/fetch_xrefs.py`, `scripts/mine_candidates.py`
and `scripts/build_labels.py`. Re-running the model: `OUT=runs/model_new python3 scripts/run_model.py data/eval_model_prs.txt`.

## Plug in your own policy

```python
# mypolicy.py
def decide(snapshot, diff):
    # snapshot: {"pr", "title", "base_sha", "merge_sha", "files": [{"path", "add", "dele"}]}
    return {"decision": "ALLOW", "reasons": ["..."]}   # or REVIEW_REQUIRED / UNKNOWN
```

```
python3 scripts/replay_custom.py mypolicy:decide evaluation
```

## The required check

`.github/workflows/risk-gate.yml` runs the frozen deterministic policy as a required check on this repository
(branch protection on `master`, source pinned to GitHub Actions). It runs through `pull_request_target`, so the workflow
and the policy come from the base branch and the PR's code is read as data, never checked out or executed; no secrets.
It fails closed: only ALLOW passes, or REVIEW_REQUIRED released with the `senior-approved` label by a named senior who
is not the PR's author. The check removes the label on the next push, so a release covers one head commit.
Demo: #1 (documentation, passes), #2 (authorization change: fails, released, fails again after a new commit; once the
author rule was added, the author's own release is refused). On this one-person repository, changes to the gate
itself can therefore only be merged by an administrator lifting protection, which is recorded.

## Limits

- 10 confirmed cases: the intervals are wide and assume independent cases; the hybrid's advantage rests on 5 cases,
  one of which it caught in only two of three passes.
- The labels only know the failures someone linked to their cause. An unlabelled PR is not a safe PR.
- The model's training data may include these 2025 issues (stated cutoff January 2026). Five labelled 2025 failures
  were first reported later. #17378, #18413 and #18503 (class B) were escalated by the deterministic rules as well, so
  they say nothing about memory; #17409 (class B) is the only one that depends on the model, and the hybrid escalated
  it in two passes of three; #18508 (confirmed, reported 21 January 2026) was passed in all three passes. Memory is not
  ruled out. A shadow run on new PRs is the real test.
- No historical test coverage was available: missing coverage is unknown, not zero.
- Orchard Core migrations are YesSql, not EF; tenants are isolated by table prefix or separate database. A detected
  migration is not a safe migration.
- `riskgate/check.py` covers pull requests; with a merge queue, the merge-group revision must be evaluated too.

## License

Code: MIT. Orchard Core is BSD-3-Clause, (c) .NET Foundation and contributors; its code is not redistributed here,
only PR numbers, titles, file paths and short quotations from public issues.
