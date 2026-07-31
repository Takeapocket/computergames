# R-P2B L1 CEM Evaluator Tuning Plan

**Goal:** Add a reproducible, resumable Cross-Entropy Method (CEM) harness for
automatically tuning `greedy_risk` and `greedy_zweistein` evaluator weights with
persistent ladder Elo as the objective. Run only a bounded smoke; do not promote
or change any default/release weight.

**Technical Hypothesis:** The old finite random grid cannot adapt its search
distribution. Sampling positive weights in log space, retaining the top Elo
elite fraction, and smoothing the next Gaussian distribution should concentrate
later candidates around better regions while preserving deterministic replay
under fixed seeds. This slice validates the optimizer and evidence pipeline; a
small smoke cannot establish a stronger evaluator.

**Architecture:** Parameterize `zweistein_lite_score()` and
`ZweisteinGreedyAI` without changing their default constants. Add
`scripts/tune_eval_weights.py` with named profiles for `greedy_risk` and
`greedy_zweistein`, bounded log-space specs, deterministic sampling, elite
updates, bilateral common-seed matches, and Elo updates imported from
`scripts/ladder.py`. Persist every candidate to JSONL and the completed
distribution to `state.json`; require `--output-dir` or derive it from
`CG_RESEARCH_DATA_DIR`. Existing nonempty runs require explicit `--resume` and
matching immutable config.

**Stop Conditions:** Stop or revert if default evaluator scores/signatures move,
samples leave declared bounds, fixed seeds are not deterministic, RED/BLUE
candidate orientations are not both evaluated, objective Elo diverges from the
ladder function, resume duplicates candidate rows or accepts incompatible
config, output defaults to the repository/C drive, or any smoke records
illegal/crash/timeout. No promotion follows from this item.

---

### Task 1: Parameterize Zweistein Without Default Drift

**Files:**
- Modify: `ai/zweistein.py`
- Modify: `ai/zweistein_ai.py`
- Modify: `ai/match.py`
- Modify: `tests/test_zweistein.py`
- Modify: `tests/test_ai_basic.py`

- [x] Add failing tests for custom five-weight injection, zero-sum behavior,
  `greedy_zweistein` move sensitivity, and full AI signature fields.
- [x] Add keyword-only weights using existing constants as exact defaults.
- [x] Store/pass weights in `ZweisteinGreedyAI` and signature extraction.
- [x] Prove existing default scores and choices remain unchanged.
- [x] Run focused tests and verify GREEN.

### Task 2: Implement Deterministic CEM Core

**Files:**
- Create: `scripts/tune_eval_weights.py`
- Create: `tests/test_tune_eval_weights.py`

- [x] Add RED tests for profile validation, bounded deterministic log-space
  sampling, elite selection, smoothed mean/std updates, and minimum std.
- [x] Use immutable weight specs with finite positive lower/upper/initial values.
- [x] Support both `greedy_risk` and `greedy_zweistein` profiles.
- [x] Add a synthetic objective test showing one update moves the distribution
  toward known better parameters without invoking games.

### Task 3: Connect Bilateral Elo And Persistence

**Files:**
- Modify: `scripts/tune_eval_weights.py`
- Modify: `tests/test_tune_eval_weights.py`

- [ ] Evaluate every candidate as RED and BLUE against the same-kind default
  anchor with common fixed seeds and deterministic ties.
- [ ] Update candidate/anchor ratings only through `scripts.ladder.update_ratings`
  and record Elo uncertainty, game/error/timing telemetry, params, and AI
  signatures.
- [ ] Require E-drive-safe output resolution, append candidate JSONL rows, write
  state/report files, and reject nonempty output without `--resume`.
- [ ] Resume only when schema/profile/spec/config match; never duplicate completed
  generation/candidate IDs.
- [ ] Add CLI smoke tests using `tmp_path` and monkeypatched match execution.

### Task 4: Bounded E-Drive Smoke And Documentation

**Files:**
- Create: `reports/rp2b_l1_cem_tuning_20260731.md`
- Modify: `PROJECT_MEMORY.md`
- Modify: `PROJECT_PHASES.md`

- [ ] Run one generation with a tiny population and one game per side under an
  explicit `E:/computergame-data/tuning/...` output directory.
- [ ] Verify JSONL/state/report reproducibility metadata, bilateral games, Elo
  objective, and zero illegal/crash/timeout.
- [ ] Run focused tests, full `pytest -q`, diagnostics, and `git diff --check`.
- [ ] Record that this is optimizer/harness evidence only; do not change defaults
  or claim strength.

### Task 5: Independent Code Review

- [ ] Request a read-only reviewer focused on default drift, log-space math,
  deterministic sampling, Elo fact-source reuse, bilateral seed fairness,
  persistence/resume safety, E-drive boundaries, telemetry, and test realism.
- [ ] Fix every Critical/Important finding and rerun affected tests plus full
  pytest whenever production code changes.
- [ ] Obtain review confirmation that all blockers are closed.
