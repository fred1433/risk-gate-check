# risk-gate-check

Which pull requests can skip senior review? This repository replays three routing policies on the real history of
[Orchard Core](https://github.com/OrchardCMS/OrchardCore) (a multi-tenant .NET CMS) and counts, for each one, how many
changes that later proved to break something it would have let through, and how much work it sent to a senior.

It is a historical replay on a public project. It is an independent study, not endorsed by the Orchard Core project.

## Result (evaluation cohort: 479 PRs merged into `main` in 2025)

| Policy | Confirmed failure-introducing changes that passed | Sent to a senior |
|---|---|---|
| Sensitive areas (a path list) | 7 of 11 (95% CI 31% to 89%) | 155 of 479 (32.4%) |
| Deterministic (structural diff signals) | 7 of 11 (31% to 89%) | 155 of 479 (32.4%) |
| Hybrid (same structural triggers, a model reads the rest) | 2 of 11 (2% to 52%) | 166 of 479 (34.7%), including 2 UNKNOWN |

- Routing a random third of the PRs to a senior would let about 7.4 of the 11 through: the two rule-based policies do
  no better than chance on this cohort.
- The 11 confirmed cases are 11 distinct defects. On them, the hybrid escalated 5 that the deterministic policy passed
  and the reverse happened 0 times (exact two-sided sign test on 5 discordant cases: p = 0.06).
- Wider label set (confirmed plus incomplete attributions, 22 cases): 14, 12 and 5 passed.
- The two UNKNOWN decisions are malformed model answers, escalated by rule. Both were confirmed failures; the raw
  answers rated them 4 and 5, so the decision would not have changed.

Files: `results/summary_evaluation.json`, `results/decisions_evaluation.jsonl` (every PR, every policy, with reasons),
`runs/model/<pr>.json` (raw model output, input hash, tokens, retries).

## Method

- **Cohort** (`data/cohort_manifest.json`): every PR merged into `main`, excluding dependency and bookkeeping bots.
  Development: 891 PRs merged in 2024. Evaluation: 479 PRs merged in 2025. Outcomes observed until 2026-09-26.
- **What the gate sees**: the merged change (squash commit against its first parent), its title and file list.
  No description, comments or later history. `scripts/make_snapshots.py` writes these snapshots; the model reads them
  from an empty directory with no tools (`riskgate/model.py`).
- **Labels** (`oracle/`): cross-references and post-merge comments of every cohort PR were mined, then read by hand.
  Class A, confirmed: a merged revert with a stated defect, an attribution restated in the merged fix, or made by a core
  maintainer, or a stated reproducible witness; and the fix touches a file the PR touched. Class B: attribution by a
  non-maintainer, hedged, or a revert without a stated defect. Class C: SZZ only (`oracle/szz_candidates.json`).
- **Policies** (`riskgate/policies.py`). Thresholds were fixed on the 2024 cohort so that each policy sends about as many
  PRs to a senior as the sensitive-area list did (36.4%), then frozen (`policies/frozen.json`, commit before any 2025
  decision was computed). UNKNOWN is never permissive.
- **Model**: `claude-sonnet-5` through `claude -p` on a subscription, 357 PRs, 372 calls, 3.08 M input and 86 k output
  tokens for the evaluation (plus 169 calls on a seeded 2024 calibration sample and the 2024 positives).

## Plug in your own policy

```python
# mypolicy.py
def decide(snapshot, diff):
    # snapshot: {"pr", "title", "base_sha", "merge_sha", "files": [{"path", "add", "dele"}]}
    return {"decision": "ALLOW", "reasons": ["..."]}   # or REVIEW_REQUIRED / UNKNOWN
```

```
python3 scripts/make_snapshots.py        # needs a mirror clone in work/oc-full.git
python3 scripts/replay_custom.py mypolicy:decide evaluation
```

## The required check

`.github/workflows/risk-gate.yml` runs the frozen deterministic policy as a required check on this repository
(branch protection on `master`, source pinned to GitHub Actions). It runs through `pull_request_target`, so the workflow
and the policy come from the base branch and the PR's code is read as data, never checked out or executed; no secrets.
It fails closed: only ALLOW passes, or REVIEW_REQUIRED released by a named senior with the `senior-approved` label,
which the check removes on the next push. Demo: #1 (documentation, passes), #2 (authorization change, fails until
released, fails again after a new commit, released again).

## Limits

- 11 confirmed cases: the intervals are wide and assume independent cases.
- The labels only know the failures someone linked to their cause. An unlabelled PR is not a safe PR.
- The model's training data may include these 2025 issues. Its reasons cite lines of the diff, and the four
  failures first reported after its stated cutoff (January 2026; four class B cases reported from 25 February 2026 on)
  were all escalated, but memory is not ruled out.
  A shadow run on new PRs is the real test.
- No historical test coverage was available: missing coverage is unknown, not zero.
- Orchard Core migrations are YesSql, not EF; tenants are isolated by table prefix or separate database. A detected
  migration is not a safe migration.
- `riskgate/check.py` covers pull requests; with a merge queue, the merge-group revision must be evaluated too.

## License

Code: MIT. Orchard Core is BSD-3-Clause, (c) .NET Foundation and contributors; its code is not redistributed here,
only PR numbers, titles, file paths and short quotations from public issues.
