# R-P2B L1 CEM Evaluator Tuning

Date: 2026-08-03
Final review: 2026-08-18
Status: harness complete; no evaluator promotion

## Hypothesis And Stop Conditions

The previous finite random grid could not adapt its sampling distribution. This
slice tests whether a bounded log-space Cross-Entropy Method (CEM) can provide a
deterministic, resumable evidence pipeline for `greedy_risk` and
`greedy_zweistein`, using bilateral Elo against the same-kind default anchor as
its objective.

The slice must stop if default evaluator behavior drifts, samples leave their
declared bounds, fixed seeds are not replayable, RED/BLUE orientations are not
both evaluated, Elo diverges from `scripts.ladder.update_ratings`, resume accepts
incompatible evidence or duplicates candidates, output falls back to the
repository/C drive, or a real smoke records illegal moves, crashes, or timeouts.

## Implementation

- `zweistein_lite_score()` and `ZweisteinGreedyAI` accept explicit weight
  overrides while preserving the existing constants as exact defaults.
- `scripts/tune_eval_weights.py` defines bounded profiles for `greedy_risk` and
  `greedy_zweistein`, deterministic log-space sampling, elite selection, and
  smoothed CEM distribution updates.
- Every candidate plays the same-kind default anchor once as RED and once as
  BLUE per seed pair. Dice and AI seeds are shared across orientations and tie
  randomization is disabled.
- Candidate JSONL rows persist the ordered per-game seed, result, telemetry, and
  Elo-before/after chain. Aggregate telemetry is derived from that manifest and
  revalidated before write and during resume.
- Elo updates and uncertainty reuse `scripts.ladder.update_ratings()` and
  `scripts.ladder.estimate_rating_uncertainty()`.
- State/config/spec/profile/signature/distribution mismatches, duplicate IDs,
  future-generation candidate rows, non-finite JSON, and nonempty new-run
  directories are rejected. Output must be explicit or derive from
  `CG_RESEARCH_DATA_DIR`.
- Candidate/state/report schema is version 2. It records the per-game result and
  Elo chain introduced by the final review and rejects earlier schema 1 runs
  with an explicit schema mismatch instead of treating them as compatible.

## Bounded E-Drive Smoke

Command profile:

```text
profile=greedy_zweistein
generations=1
population_size=2
elite_count=1
games_per_side=1
seed=80301
layout_id=balanced_v1
max_turns=40
output=E:/computergame-data/tuning/rp2b_l1_cem_smoke_20260803
```

The run produced two unique candidates and four games in total. Both candidates
recorded `1-1-0`, `objective_elo=1501.47`, and
`candidate_rating_uncertainty=202.073`; each game ended in 20 recorded turns.
Across all candidates, `illegal_moves=0`, `crashes=0`, and `timeouts=0`.

An independent verifier replayed every persisted Elo update in original game
order through `scripts.ladder.update_ratings()` and matched both final candidate
and anchor ratings. It also confirmed bilateral orientations, common pair seeds,
AI signatures, state/report counts, and the evidence-only disclaimer. A second
invocation with the same immutable configuration and `--resume` retained exactly
two candidates and one completed generation.

The deterministic tie selected `g0000-c0000` as the report's best candidate.
This selection and the tiny equal-score sample are not evidence of improved
playing strength.

After the final schema review, the same bounded configuration was run again
with schema 2 under
`E:/computergame-data/tuning/rp2b_l1_cem_schema2_smoke_20260818`.
`state.json`, `report.json`, and both candidate rows record schema 2; the run
completed one generation with two candidates and zero illegal moves, crashes,
or timeouts. A same-config `--resume` kept two candidates and one completed
generation. The original 2026-08-03 schema 1 directory remains historical
evidence and is intentionally incompatible with final schema 2 resume.

## Verification

- L1 CEM target tests: `72 passed in 1.16s`.
- CEM + Zweistein + AI signature tests: `116 passed in 1.23s`.
- Full suite: `1071 passed in 74.51s`.
- Production diagnostics for `scripts/tune_eval_weights.py`: no findings.
- Test-file diagnostics only report the editor environment's unresolved pytest
  import and deliberate invalid-type negative tests; pytest execution is green.
- Independent specification review: PASS.
- Independent code-quality review after fixes: APPROVED, no findings.

## Decision

L1 is accepted as optimizer and persistence-harness evidence only. No default
weight, default AI, GUI behavior, release/v1.0 setting, P14 anchor, or core rule
has changed. Any future promotion requires a separately planned, sufficiently
powered persistent-ladder experiment.
