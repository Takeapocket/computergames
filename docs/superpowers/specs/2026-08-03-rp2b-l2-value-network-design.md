# R-P2B L2 Value Network Design

Date: 2026-08-03
Status: design complete; pending explicit approval

## 1. Goal

Implement the L2 value-network slice from the approved long-term research
transition: generate reproducible P14 rollout self-play data, train a compact
PyTorch value network on the local NVIDIA GPU, and use that network as an
experimental RolloutAI cutoff evaluator and MCTSAI leaf evaluator.

This slice proves the data, training, checkpoint, inference, and search-wiring
pipeline. It does not promote a model or claim stronger play from a bounded
smoke. L3 remains responsible for policy learning, PUCT, and iterative
self-improvement.

## 2. Technical Hypothesis

The existing P14 rollout baseline provides a stable teacher distribution and
terminal game outcomes without introducing the known weakness of the current
MCTS into the labels. A small convolutional network over identity-preserving
board planes should learn a finite state-value approximation that can replace
hand-written cutoff/leaf evaluation through explicit experimental AI kinds.

Using the existing `play_one_game()` and `GameRecord` as the game fact source
keeps core rules out of the data generator. Grouping train/validation splits by
game prevents adjacent positions from the same game leaking across the split.

## 3. Scope And Non-Goals

In scope:

- P14-versus-P14 deterministic self-play data generation.
- A versioned 13-plane state encoding and RED-perspective value target.
- A compact value-only CNN, deterministic CPU/CUDA training, and checkpoint
  metadata/checksums.
- Experimental neural RolloutAI cutoff and MCTSAI leaf adapters.
- E-drive smoke data, GPU training, model loading, and bounded harness evidence.

Out of scope:

- Policy targets, policy heads, PUCT, replay-buffer sampling, arena promotion,
  iterative self-play, distributed workers, mixed precision, and Rust/C
  extensions.
- Changing default AI, P14 parameters, GUI behavior, release/v1.0, core rules,
  or existing static evaluator semantics.
- Treating a tiny loss curve or smoke match as a strength result.

## 4. State And Target Schema

### 4.1 Feature Tensor

`value_features_v1` is a contiguous float32 tensor with shape `(13, 5, 5)`:

- planes 0-5: live RED pieces 1-6, one binary plane per piece ID;
- planes 6-11: live BLUE pieces 1-6, one binary plane per piece ID;
- plane 12: all `+1` when RED is to move and all `-1` when BLUE is to move.

Coordinates stay in the absolute board orientation. Dead pieces have an empty
plane. Piece IDs are not collapsed because dice-to-piece legality depends on
identity.

The encoder validates board size, player ownership, piece ID range, finite
float32 output, and at most one occupied cell per identity plane. It lives in a
research-only module and is not imported by core or GUI startup paths.

### 4.2 Targets And Samples

Targets are terminal outcomes from RED's perspective:

- RED win: `+1.0`;
- BLUE win: `-1.0`;
- `max_turns` draw: `0.0`.

Each recorded move contributes exactly one pre-dice state: the initial state for
the first move, then each preceding move's `state_after` for the next move. The
terminal or artificial post-limit tail is not added as an extra sample. Samples
carry a stable game ID so splitting happens by game, never by adjacent state.

Games ending through illegal move, crash, timeout, or no-move forfeiture remain
in the audit JSONL but are excluded from the finalized training dataset and make
the bounded L2 smoke fail.

## 5. Self-Play Data Pipeline

Add `scripts/generate_value_selfplay.py` with immutable run configuration:

- game count, root seed, layout, and `max_turns`;
- RED/BLUE kind and kwargs, defaulting exactly to P14 rollout and
  `RELEASE_DEFAULT_ROLLOUT_KWARGS`;
- output schema versions and full AI signatures.

The script builds fresh deterministic AIs and dice RNGs per game, calls
`play_one_game()`, and persists:

- `games.jsonl`: game ID, all derived seeds, winner/termination/error/timing
  telemetry, both AI signatures, and the full `GameRecord` payload;
- `state.json`: immutable config, completed game IDs, seed manifest, counts, and
  schema versions;
- `dataset.npz`: features, targets, and integer game IDs rebuilt in stable game
  order from accepted JSONL rows;
- `manifest.json`: config, W/L/D and error totals, sample count, class balance,
  file SHA-256 values, NumPy/Python versions, and evidence disclaimer;
- `report.md`: compact human-readable summary.

New nonempty output is rejected unless `--resume` is explicit. Resume requires
exact schema/config/signature/seed compatibility, rejects duplicate or future
game IDs, and rebuilds the NPZ atomically from JSONL rather than appending binary
arrays.

Output must be supplied explicitly or resolve from
`CG_RESEARCH_DATA_DIR/selfplay/<run-id>`. No default may point into the
repository or C drive.

## 6. Value Model And Training

### 6.1 Architecture

`value_cnn_v1` is deliberately small and fixed:

1. `Conv2d(13, 64, kernel_size=3, padding=1)` + ReLU;
2. `Conv2d(64, 64, kernel_size=3, padding=1)` + ReLU;
3. flatten;
4. `Linear(64 * 5 * 5, 128)` + ReLU;
5. `Linear(128, 1)` + Tanh.

There is no batch normalization, dropout, residual tower, or policy head in L2.
The output is a scalar RED-perspective value in `[-1, 1]`.

### 6.2 Training Contract

Add `scripts/train_value_network.py` with explicit dataset/output paths, seed,
device (`cpu` or `cuda`), epochs, batch size, learning rate, weight decay, and
validation fraction. There is no silent device fallback: requesting CUDA when
unavailable is an error, while unit tests explicitly request CPU.

The split is a deterministic shuffled split of unique game IDs. Both train and
validation groups must be nonempty. Training uses MSE loss and AdamW. It records
per-epoch train/validation MSE and MAE, final sign accuracy for non-draw labels,
sample/game counts, elapsed time, selected device, GPU name, torch version, and
CUDA runtime version.

Reproducibility setup includes Python, NumPy, and `torch.manual_seed()`, disabled
cuDNN benchmarking, and deterministic algorithms. The report must state that
PyTorch does not promise bitwise reproducibility across releases, platforms, or
different CPU/GPU devices.

### 6.3 Checkpoint Contract

The checkpoint is an atomic `model.pt` dictionary containing only tensors and
primitive/list/dict metadata:

- checkpoint, feature, and architecture schema versions;
- model config and `state_dict`;
- training config and final metrics;
- source dataset SHA-256 and manifest summary.

Loading uses an explicit `map_location` and `weights_only=True`, then validates
every schema/config field before `load_state_dict()`. `model_manifest.json`
stores the final model SHA-256 and environment metadata. The exact official
PyTorch wheel/version and CUDA wheel source used in the project venv are pinned
or recorded during implementation; pip and torch caches remain on E drive.

Model output defaults to
`CG_RESEARCH_DATA_DIR/models/<run-id>` unless an explicit output directory is
provided. Nonempty model output is rejected; training never writes into tracked
repository paths.

## 7. Search Integration

Add a shared checkpoint-backed value predictor with:

- `red_value(state) -> float` in `[-1, 1]`;
- `value_for(state, perspective)` that negates RED value for BLUE;
- immutable feature/model schema and SHA-256 signature fields;
- `eval()` and inference-mode execution on the configured device;
- no fallback to a hand-written evaluator when loading or inference fails.

Two explicit experimental adapters consume it:

- neural RolloutAI overrides `_cutoff_score()` and maps perspective value with
  `(value + 1) / 2` into rollout win probability;
- neural MCTSAI overrides the static leaf score and multiplies perspective value
  by the existing MCTS scale so the current normalization recovers `[-1, 1]`.

`ai.match.build_ai()` registers separate research kinds for these adapters and
imports torch-backed modules lazily only when those kinds are requested.
`ai_version_signature()` records feature schema, architecture schema, model
SHA-256, and evaluator mode. Default kinds and signatures stay byte-for-byte
unchanged.

## 8. Dependency Boundary

PyTorch and NumPy remain research-only dependencies. `core/`, GUI startup,
release scripts, and default AI construction must neither import torch nor
require it to be installed. Tests include a subprocess/import characterization
that imports default paths while blocking torch import.

The implementation resolves the current official PyTorch CUDA wheel compatible
with Python 3.11 and the local RTX 4060/driver, installs it only in `.venv` with
`PIP_CACHE_DIR=E:/pip-cache` and `TORCH_HOME=E:/torch-cache`, and records the
installed build in `requirements-research.txt` and the L2 report.

## 9. Failure Handling

- Unknown schemas, mismatched feature/model config, checksum mismatch, malformed
  JSON/NPZ, non-finite features/targets/loss/predictions, or incompatible
  checkpoint keys fail explicitly.
- Data generation never converts crashes, illegal moves, timeouts, or no-move
  forfeits into ordinary training labels.
- Interrupted JSONL/state runs are resumable only within the declared completed
  game boundary; future/duplicate rows are rejected.
- Atomic temporary files are replaced only after complete serialization.
- CUDA OOM or unavailable CUDA is surfaced; batch size is not silently reduced.
- Search inference exceptions are surfaced to the harness and counted as a
  crash; there is no hidden static-evaluator fallback.

## 10. Verification And Bounded Evidence

Unit and integration tests must cover:

- exact feature-plane placement, player-to-move plane, dead pieces, dtype/shape,
  deterministic encoding, and invalid-state rejection;
- self-play seed determinism, P14 signatures, one-sample-per-recorded-move,
  group IDs, atomic outputs, strict resume, E-safe resolution, and tamper cases;
- CNN shape/range, finite gradients, a tiny synthetic overfit, deterministic CPU
  training, checkpoint round-trip, SHA/schema rejection, and map-location load;
- RED/BLUE perspective conversion and exact neural cutoff/leaf scale mapping;
- lazy torch import and unchanged default AI scores, choices, signatures, GUI,
  release, and core behavior;
- a tiny real `play_one_game()` data-generation path and real model-backed search
  path without mocked rule or inference code.

The bounded E-drive evidence run will:

1. generate a small P14 self-play dataset under
   `E:/computergame-data/selfplay/...`;
2. train `value_cnn_v1` for a few epochs with `--device cuda` under
   `E:/computergame-data/models/...` and prove CUDA was actually selected;
3. verify finite metrics, checkpoint reload, SHA values, and deterministic
   dataset rebuild/resume;
4. run bounded harness games for both neural Rollout cutoff and neural MCTS leaf
   adapters with zero illegal moves, crashes, and timeouts;
5. run focused tests, the complete pytest suite, production diagnostics, and
   `git diff --check`.

All reports must say `pipeline/wiring evidence only; no strength claim or
default promotion`. Any strength comparison requires a separately powered
persistent-ladder experiment.

## 11. Stop Conditions

Stop and fix or revert L2 if any of the following occurs:

- default/release behavior or signatures drift;
- torch leaks into core, GUI startup, release, or default AI imports;
- data/model/cache output enters the repository or C drive;
- fixed seeds do not reproduce game/sample order and split membership;
- adjacent positions from one game cross the train/validation boundary;
- non-finite data, gradient, loss, or prediction appears;
- checkpoint reload changes predictions beyond normal same-device float
  tolerance or accepts a mismatched schema/checksum;
- the requested CUDA smoke does not use the RTX 4060;
- any bounded game records illegal move, crash, or timeout;
- a bounded smoke is presented as evidence of stronger play.
