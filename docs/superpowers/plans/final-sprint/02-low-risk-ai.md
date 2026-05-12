# Task Group 02 - Low-Risk AI Work

目标：在不破坏默认稳定路径的前提下，做可验证、可回滚的 AI 增强。任何候选未过晋升门禁，都不能替换 `greedy_risk`。

---

## Task 5: self-capture 评估实验入口

**Files:**

- Create: `ai/self_capture.py`
- Create: `tests/test_self_capture.py`
- Modify: `ai/evaluator.py`
- Modify: `ai/greedy_ai.py`
- Modify: `ai/match.py`

**Goal:** 为“吃本方子换取机动性”建立可测、默认关闭的 evaluator 特征。

### Design

```text
self_capture_mobility_gain(state, perspective)
  For each dice 1..6:
    find legal moves for perspective
    filter moves where captured_piece.player == perspective
    estimate best mobility delta after that self-capture
  Return average positive delta across dice values

Default evaluator self_capture_weight = 0.0
Candidate experiments may set self_capture_weight > 0
```

API note:

```text
GameState.apply_move() requires move.player == state.current_player.
evaluate() may be called when state.current_player is opponent.
Therefore ai/self_capture.py must simulate on a copied state whose current_player is set to perspective.
Use GameState.deserialize(state.serialize()) to copy. Do not mutate the original.
```

### Steps

- [ ] Create `tests/test_self_capture.py`:

```python
from ai.self_capture import self_capture_mobility_gain
from core.game_state import GameState
from core.types import Player, Position


def test_self_capture_gain_is_zero_when_no_self_capture_exists():
    state = GameState.from_layout(
        red={1: Position(0, 0)},
        blue={1: Position(4, 4)},
        current_player=Player.RED,
    )

    assert self_capture_mobility_gain(state, Player.RED) == 0.0


def test_self_capture_gain_does_not_mutate_state():
    state = GameState.from_layout(
        red={1: Position(0, 0), 2: Position(1, 1), 3: Position(0, 2)},
        blue={1: Position(4, 4)},
        current_player=Player.BLUE,
    )
    before = state.serialize()

    self_capture_mobility_gain(state, Player.RED)

    assert state.serialize() == before
```

- [ ] Run failing test:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_self_capture.py -v
```

Expected:

```text
FAIL: No module named ai.self_capture
```

- [ ] Create `ai/self_capture.py`:

```python
from __future__ import annotations

from core.game_state import GameState
from core.types import Player


def self_capture_mobility_gain(state: GameState, perspective: Player) -> float:
    """Estimate mobility gained by legal self-capture options without mutating state."""
    perspective = Player.from_value(perspective)
    baseline = _average_legal_moves(state, perspective)
    total = 0.0

    for dice in range(1, 7):
        best_delta = 0.0
        for move in state.legal_moves(perspective, dice):
            if move.captured_piece is None or move.captured_piece.player is not perspective:
                continue
            sim = GameState.deserialize(state.serialize())
            sim.current_player = perspective
            sim.apply_move(move, dice=dice)
            delta = _average_legal_moves(sim, perspective) - baseline
            best_delta = max(best_delta, delta)
        total += best_delta

    return total / 6.0


def _average_legal_moves(state: GameState, player: Player) -> float:
    return sum(len(state.legal_moves(player, dice)) for dice in range(1, 7)) / 6.0
```

- [ ] Wire evaluator with default off:

```text
Add SELF_CAPTURE_WEIGHT = 0.0
Add evaluate(..., self_capture_weight: float = SELF_CAPTURE_WEIGHT)
Add + self_capture_weight * self_capture_mobility_gain(state, perspective)
```

- [ ] Wire `GreedyAI` and `ai_version_signature()`:

```text
GreedyAI constructor accepts self_capture_weight
GreedyAI passes it into evaluate()
ai_version_signature includes self_capture_weight
```

- [ ] Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_self_capture.py tests/test_evaluator.py tests/test_evaluator_injection.py tests/test_ai_basic.py -v
```

Expected:

```text
All selected tests pass
```

---

## Task 6: 参数搜索基础设施

**Files:**

- Create: `scripts/param_sweep.py`
- Create: `tests/test_param_sweep.py`
- Create/Modify: `reports/param_sweep.md`

**Goal:** 用固定搜索空间和独立验证 seed 找到可复现的 `greedy_risk` 参数候选。

### Steps

- [ ] Create `tests/test_param_sweep.py`:

```python
from scripts.param_sweep import iter_param_grid, summarize_candidate


def test_iter_param_grid_contains_expected_keys():
    params = next(iter_param_grid(limit=1, seed=1))

    assert set(params) >= {
        "distance_weight",
        "material_weight",
        "expected_risk_weight",
        "expected_win_risk_weight",
    }


def test_summarize_candidate_formats_win_rate():
    row = summarize_candidate(
        params={"distance_weight": 1.0},
        wins=12,
        games=20,
        illegal_moves=0,
        crashes=0,
        max_step_time_ms=3.0,
    )

    assert "60.0%" in row
    assert "distance_weight=1.0" in row
```

- [ ] Implement `scripts/param_sweep.py`.

Required CLI:

```text
--sample-size 20
--games 100
--seed 2026
--validation-games 200
--output reports/param_sweep.md
```

Parameter grid:

```python
DISTANCE_WEIGHTS = [0.5, 1.0, 2.0, 3.0]
MATERIAL_WEIGHTS = [5.0, 10.0, 20.0]
EXPECTED_RISK_WEIGHTS = [1.0, 3.0, 5.0]
EXPECTED_WIN_RISK_WEIGHTS = [100.0, 500.0, 1000.0]
SELF_CAPTURE_WEIGHTS = [0.0, 0.5, 1.0]
```

Implementation rules:

```text
Use direct play_one_game() calls, not shelling out to quick_bench.
Candidate AI = build_ai("greedy_risk", seed=..., **params)
Baseline AI = build_ai("greedy_risk", seed=...) or build_ai("greedy")
First pass: sample-size candidates, games per candidate.
Validation pass: top 5 candidates on different seed range.
Write markdown report with train and validation results.
```

- [ ] Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_param_sweep.py -v
& ".venv/Scripts/python.exe" "scripts/param_sweep.py" --sample-size 3 --games 10 --validation-games 10 --seed 2026 --output reports/param_sweep_smoke.md
```

Expected:

```text
tests pass
smoke report exists
each row has params, win rate, illegal, crashes, max step ms
```

- [ ] Real sweep if time allows:

```powershell
& ".venv/Scripts/python.exe" "scripts/param_sweep.py" --sample-size 20 --games 100 --validation-games 200 --seed 2026 --output reports/param_sweep.md
```

Do not update defaults here. Task 8 handles promotion.

---

## Task 7: 开局搜索基础设施

**Files:**

- Create: `scripts/search_openings.py`
- Create: `tests/test_search_openings.py`
- Modify: `ai/opening_layouts.py` only if a candidate passes gate
- Create/Modify: `reports/opening_report.md`

**Goal:** 搜索 720 种出发区排列中的候选布局，但不直接改 GUI 默认。

### Steps

- [ ] Create `tests/test_search_openings.py`:

```python
from scripts.search_openings import generate_side_layouts, mirror_layout_for_blue


def test_generate_side_layouts_can_limit_count():
    layouts = list(generate_side_layouts(limit=3))

    assert len(layouts) == 3
    assert all(set(layout) == {1, 2, 3, 4, 5, 6} for layout in layouts)


def test_mirror_layout_for_blue_keeps_piece_ids():
    red = next(generate_side_layouts(limit=1))
    blue = mirror_layout_for_blue(red)

    assert set(blue) == set(red)
    assert all(position.row + position.col >= 6 for position in blue.values())
```

- [ ] Implement generator in `scripts/search_openings.py`:

```python
RED_HOME = [
    Position(0, 0),
    Position(0, 1),
    Position(0, 2),
    Position(1, 0),
    Position(1, 1),
    Position(2, 0),
]
```

Rules:

```text
generate_side_layouts(limit=None, seed=None) maps piece ids 1..6 to RED_HOME permutations.
mirror_layout_for_blue(red_layout) maps Position(row, col) -> Position(4 - row, 4 - col).
Keep piece ids unchanged.
```

- [ ] Implement runner.

CLI:

```text
--sample-size 100
--games 50
--validation-games 200
--seed 2026
--output reports/opening_report.md
```

Search flow:

```text
sample N red layouts
opponent layouts: mirror layout, balanced_v1, aggressive_v1, defensive_v1
run greedy_risk vs greedy using custom starting_state
rank by candidate win rate
validate top 10 with independent seed
```

- [ ] Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_search_openings.py tests/test_opening_layouts.py -v
& ".venv/Scripts/python.exe" "scripts/search_openings.py" --sample-size 5 --games 10 --validation-games 10 --seed 2026 --output reports/opening_report_smoke.md
```

Expected:

```text
tests pass
smoke report exists
top candidate rows include red layout metadata and validation result
```

- [ ] Add preset only after gate.

If a layout passes opening gate, add to `ai/opening_layouts.py`:

```python
"balanced_tuned_v1": OpeningLayout(
    id="balanced_tuned_v1",
    name="数据候选均衡 V1",
    red={...},
    blue={...},
),
```

Then run:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_opening_layouts.py tests/test_opening_panel.py -v
```

Do not change `gui/opening_panel.py` default until Task 8 confirms promotion.

---

## Task 8: 候选参数/布局晋升判定

**Files:**

- Modify: `ai/match.py` if adding candidate AI kind
- Modify: `gui/main_window.py` only if AI passes gate
- Modify: `gui/opening_panel.py` only if layout passes gate
- Create/Modify: `reports/ai_promotion_decision.md`

**Goal:** 用固定门禁决定是否替换默认 AI 或默认布局。默认选择是保守：未过 gate 就不替换。

### Steps

- [ ] If no AI candidate exists:

```text
Create reports/ai_promotion_decision.md
Decision: Keep greedy_risk
Reason: no candidate passed preliminary sweep
```

- [ ] If candidate exists, run candidate vs `greedy_risk` both sides:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk_tuned --blue greedy_risk --games 200 --seed 2026 --report-name candidate_vs_greedy_risk_red
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy_risk_tuned --games 200 --seed 2026 --report-name candidate_vs_greedy_risk_blue
```

- [ ] Run candidate vs `greedy` both sides:

```powershell
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk_tuned --blue greedy --games 200 --seed 2026 --report-name candidate_vs_greedy_red
& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy --blue greedy_risk_tuned --games 200 --seed 2026 --report-name candidate_vs_greedy_blue
```

- [ ] Write `reports/ai_promotion_decision.md`:

```markdown
# AI Promotion Decision

date:
candidate:
baseline:

| comparison | games | candidate wins | win rate | CI95 | illegal | crashes | timeouts | avg ms | max ms |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|

Decision:
- [ ] Promote candidate
- [ ] Keep greedy_risk

Reason:
```

- [ ] Promote AI only if all gates pass.

If promoted:

```text
Update gui/main_window.py recommender from build_ai("greedy_risk", seed=0) to promoted kind or promoted params.
Update ai/match.py build_ai() if new kind is needed.
Update tests expecting GUI recommendation text if name changes.
```

If not promoted:

```text
Do not modify GUI default.
Keep candidate accessible only through harness if useful.
```

- [ ] Promote layout only if opening gate passes.

If promoted:

```text
Add tuned layout to ai/opening_layouts.py PRESETS.
Change gui/opening_panel.py default layout_var and reset/select_layout default only after report supports it.
Update tests/test_opening_panel.py expected default if needed.
```

If not promoted:

```text
Keep GUI default balanced_v1.
Document best experimental layouts in reports/opening_report.md only.
```

- [ ] Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

Expected:

```text
All exit 0
```
