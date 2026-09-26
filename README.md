# risk-gate-check

Which pull requests can skip senior review? This repository replays three routing policies on the real history of
[Orchard Core](https://github.com/OrchardCMS/OrchardCore) (a multi-tenant .NET CMS) and counts, for each one, how many
known regression-introducing changes it let through, and how many PRs it routed to review.

It is an exploratory, retrospective comparison on a public project, not a blinded holdout and not an estimate of how
safe auto-merging is. It is an independent study, not endorsed by the Orchard Core project.

## Result (evaluation cohort: 479 PRs merged into `main` in 2025)

On 479 historical PRs, both rule-based policies let 7 of 10 confirmed regressions pass. The hybrid let 2 pass in each
of three runs, routing 34 to 35% of PRs to review rather than 32%. This measures routing, not prevented failures.

| Policy | Known regressions let through | Routed to review | Expected by random routing at that share |
|---|---|---|---|
| Sensitive areas (a path list) | 7 of 10 (95% CI 35% to 93%) | 155 of 479 (32.4%) | 6.8 |
| Deterministic (structural diff signals) | 7 of 10 (35% to 93%) | 155 of 479 (32.4%) | 6.8 |
| Hybrid (same structural triggers, a model reads the rest), three runs | 2, 2 and 2 of 10 (3% to 56%) | 166, 165, 165 of 479 (34.4% to 34.7%) | 6.5 to 6.6 |

- 2 of 10 is the share of known regression-introducing PRs that were let through. It is not an error rate among
  allowed PRs, and it says nothing about the PRs nobody later tied to a failure.
- The two rule-based policies are near the random-routing expectation on this cohort. The dashed line on the page is
  an expected value, not a confidence boundary.
- Stability: each run routed to review five confirmed regressions that the deterministic policy allowed. Four were the
  same across all runs (#17481, #17515, #18121, #18541); the fifth alternated between two cases (#17369 in two runs,
  #17421 in one). #18508 passed every time. A correct routing is not a correct diagnosis: the model's reason for
  #17369 names broken analytics scripts, the documented failure was an exception.
- The hybrid is not the deterministic gate plus extra catches: it keeps the hard triggers but replaces the soft score.
  In run 1 it routed 46 PRs to review that the deterministic policy allowed, and allowed 35 that it routed to review.
- Sign test on the 5 discordant confirmed cases, each run: p = 0.06. Three runs do not make ten cases thirty.
- Wider label set (confirmed plus incomplete attributions, 22 cases): 14 and 12 let through by the rules; 5, 6 and 4
  by the hybrid.
- UNKNOWN (malformed model answers, routed to review by rule): 2, 1 and 0 per run.
- Truncated input: 38 of the 357 model inputs were cut (diff over 60,000 characters or over 400 files). The frozen
  hybrid allowed 27, 28 and 25 of them. `riskgate/strict.py` has the deployable variant, where a truncated input is never
  allowed: 2 of 10 let through at 39.7% to 40.3% routed to review (`hybrid_deployable` in the summaries).
- The loads are near, not equal: `nearest_load_threshold_secondary` in the summaries puts each scored policy at the
  threshold whose load is nearest the path list's; the loads still differ.

Files: `results/summary_evaluation*.json`, `results/decisions_evaluation*.jsonl` (every PR, every policy, with
reasons), `results/hybrid_passes_evaluation.json`, `runs/model*/<pr>.json` (raw model output, input and prompt
fingerprints, tokens, retries), one directory per run. The published results come from these three runs; the model was
not re-run after the code review.

## Method

- **Cohort** (`data/cohort_manifest.json`): every PR merged into `main`, excluding dependency and bookkeeping bots.
  Development: 891 PRs merged in 2024. Evaluation: 479 PRs merged in 2025. Outcomes observed until 2026-09-26.
- **What the gate sees**: the merged change (squash commit against its first parent), a title and the file list.
  No description, comments or later history. The title is the PR's title as read from GitHub on 2026-09-26, not
  proven to be the title at merge time; it differs from the squash-commit subject for 92 of the 479 PRs (editorial
  wording), including 2 of the 10 confirmed cases, neither of which mentions the later failure.
  `scripts/make_snapshots.py` writes the snapshots; `scripts/evaluate.py` refuses a snapshot whose diff hash differs
  from `data/snapshot_diff_sha256.json`, and a stored model answer whose recorded input or prompt fingerprint differs
  from the one recomputed from the snapshot, or whose answer fails strict parsing (all 1,071 stored answers pass).
- **Labels** (`oracle/`): cross-references and post-merge comments of every cohort PR were mined
  (`scripts/fetch_prs.py`, `scripts/fetch_xrefs.py`, `scripts/mine_candidates.py`, output in `oracle/mined_candidates.json`),
  then read by hand (`oracle/adjudication.py`, built into `oracle/labels.json` by `scripts/build_labels.py`).
  Class A, confirmed: a failure users of the software can hit, tied to the PR by a merged revert with a stated defect,
  an attribution restated in the merged fix, or made by a core maintainer, or a stated reproducible witness; and the
  fix touches a file the PR touched. Class B: attribution by a non-maintainer, hedged, a revert without a stated
  defect, or a CI-only failure (the flaky test caused by #17951 is B). Class C: SZZ only (`oracle/szz_candidates.json`).
- **Policies** (`riskgate/policies.py`, `policies/frozen.json`). Thresholds were selected on 2024. The rule author had
  already seen the labelled 2025 cases, so this is an exploratory retrospective comparison, not a blinded holdout.
  Freeze commit 8c69d2d (2026-09-26 10:55:20 -03:00): the 2025 labels existed (10:35); no 2025 policy decision and no
  2025 model answer did (first 2025 answer 10:55:33, scoring 11:02).
- **Model**: `claude-sonnet-5` through `claude -p` on a subscription. Evaluation, three runs over the same 357 PRs:
  1,107 calls (1,071 evaluations and 36 retries), 9.06 M input and 279 k output tokens. Calibration: 169 calls on a
  seeded 2024 sample and the 2024 positives. PR counts are a workload proxy, not measured review time.

## Reproduce

```
git clone https://github.com/fred1433/risk-gate-check && cd risk-gate-check
git clone --mirror https://github.com/OrchardCMS/OrchardCore.git work/oc-full.git
python3 scripts/make_snapshots.py                 # 1,370 snapshots from the manifest, about a minute
python3 scripts/evaluate.py evaluation            # run 1; add runs/model_pass2 or runs/model_pass3 for the others
python3 -m unittest discover tests                # check contract, strict parsing, fingerprints, lessons
```

No model call is needed to replay the stored results. Rebuilding the labels from scratch needs the GitHub CLI:
`scripts/fetch_prs.py 2023-01-01 2026-09-27`, then `scripts/fetch_xrefs.py`, `scripts/mine_candidates.py` and
`scripts/build_labels.py`. Re-running the model: `OUT=runs/model_new python3 scripts/run_model.py data/eval_model_prs.txt`.

## Run your policy on the same cases

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
and the policy come from the base branch; the PR's code is read as data through the API, never checked out or
executed; the token is read-only and no secret is used. Contract (`riskgate/check.py`, tested in `tests/test_check.py`):

- ALLOW passes. UNKNOWN never passes, whatever approvals exist.
- REVIEW_REQUIRED passes only with an approving GitHub review whose `commit_id` is the full head SHA that was evaluated,
  from a named senior who is not the PR's author, and not superseded by a later review from that person.
- The head SHA is read before and after the PR data; if it moved, or the file list is incomplete, the result is UNKNOWN.
- The `senior-approved` label only asks for a re-run (a review event cannot start a `pull_request_target` workflow);
  it is never the evidence.
- Changes to the gate itself (`riskgate/`, `policies/`, `.github/`) always need a senior. On this one-person
  repository they can only be merged by an administrator lifting protection.

Demo: #1 (documentation, passes), #2 (authorization change, routed to review; its author cannot release it).

## Lessons kept out of the frozen policies

`riskgate/lessons.py`: the missed #18508 added `services.RemoveAll<...>()`, which silently removed a registration
another feature needed. The frozen rule only watched deleted registration lines, worth one point against a threshold of
three, so widening that detector alone would not have escalated it; the lesson is a separate escalation rule for added
calls that remove or replace registrations. It is not used to rescore history.

## Limits

- 10 confirmed cases: the intervals are wide and assume independent cases.
- The labels only know the failures someone linked to their cause. An unlabelled PR is not a safe PR.
- The model's training data may include these 2025 issues (stated cutoff January 2026, no day given). Four labelled
  2025 failures were first reported from February 2026 on. #17378, #18413 and #18503 (class B) were routed to review by
  the deterministic rules as well; #17409 (class B) is the only one that rests on the model, routed to review in two
  runs of three. #18508 was reported on 21 January 2026, which cannot be placed before or after the cutoff. Memory is
  not ruled out; a shadow run on new PRs is the real test.
- No historical test coverage was available: missing coverage is unknown, not zero.
- Orchard Core migrations are YesSql, not EF; tenants are isolated by table prefix or separate database. A detected
  migration is not a safe migration.
- Passing this gate is not merging; with a merge queue, the merge-group revision must be evaluated too.

## License

Code: MIT. Orchard Core is BSD-3-Clause, (c) .NET Foundation and contributors; its code is not redistributed here,
only PR numbers, titles, file paths and short quotations from public issues.
