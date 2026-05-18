# 轻量开局布局筛选工具设计规格

日期：2026-05-18  
状态：设计规格，待实现  
范围：新增轻量脚本、测试和小样本 smoke；不修改 GUI/release 默认配置

## 1. 背景

当前比赛版本已经进入赛前冻结主线。GUI/release 默认 AI 是 `rollout` kind 加 P3 promotion 显式参数，默认布局仍是 `balanced_v1`。P5 系列开局实验已经证明：小样本正信号不能直接作为默认布局晋升证据，且 `balanced_v1` 暂不变。

本任务不是重写 AI、不是复制外部 Zweistein 实现、不是做 720 全量长跑，而是新增一个轻量、可恢复、逐候选落盘的开局布局筛选工具。它用于在电脑和 Codex 都不适合长时间挂机的前提下，对 20 到 40 个启发式候选做极小样本双边对比，快速找出值得后续人工判断或小规模复验的 top candidates。

## 2. 目标

新增 `scripts/screen_openings_light.py`，默认生成 20 到 40 个确定性启发式候选布局，并使用当前 release 默认 AI 做 candidate vs baseline 的红蓝双边小样本对比。

核心目标：

- 读取 `release/v1.0/default_params.json` 作为双方 AI 参数来源。
- 固定 AI kind 为 `rollout`，剥离 metadata keys：`ai`、`fallback_ai`、`promotion_report`。
- baseline layout 默认使用 `balanced_v1`。
- 默认模式为 `curated`，默认候选数量控制在轻量范围内。
- 支持断点续跑，已完成 candidate 默认跳过。
- 每跑完一个 candidate 立即写 JSON，不等全部结束。
- 支持 dry-run，只生成、校验、展示候选，不跑对局。
- 生成 markdown 摘要，标明这是小样本筛选，不是晋升证据，不修改默认布局。

## 3. 非目标与硬边界

本任务明确不做：

- 不修改 `gui/main_window.py::DEFAULT_RECOMMENDER_KIND`。
- 不修改 `gui/main_window.py::DEFAULT_RECOMMENDER_KWARGS`。
- 不修改 `release/v1.0/default_params.json`。
- 不修改 `release/v1.0/config.json`。
- 不修改 core 规则语义。
- 不修改 GUI 默认布局。
- 不做 720 全量长跑 benchmark。
- 不自动跑超过轻量 smoke 规模的大样本。
- 不复制外部 Zweistein 源码。
- 不引入 PyTorch、GPU、OpenSpiel 或新重依赖。
- 不执行 `git commit` 或 `git push`。

现有 release consistency 测试仍是默认配置边界的保护线。本任务新增脚本不得绕过这些约束。

## 4. 方案取舍

推荐方案：新增独立脚本 `scripts/screen_openings_light.py`。

优点：

- 断点续跑、逐候选落盘和 markdown 摘要可以独立实现，避免把 `scripts/search_openings.py` 继续扩成多职责工具。
- 不影响现有 P5 搜索报告口径，也不改变已冻结的 release/GUI 默认项。
- 测试可以直接覆盖 candidate 生成、resume、dry-run 和聚合逻辑。

备选方案 A：扩展 `scripts/search_openings.py`。

- 优点是能复用更多现有函数。
- 缺点是会把采样搜索、分层搜索、验证 gate、轻量断点筛选混在同一个脚本里，职责变重，不利于赛前冻结阶段维护。

备选方案 B：只扩展 `scripts/compare_opening_layouts.py`。

- 优点是已有双边对比逻辑。
- 缺点是它面向单个搜索结果 candidate，不负责生成 20 到 40 个候选，也没有逐 candidate resume 的输出模型。

最终选择推荐方案。实现时可复用 `ai.match.build_ai`、`ai.match.play_one_game`、`ai.opening_layouts.PRESETS`、`ai.opening_layouts.validate_layout`、`ai.opening_layouts.mirror_layout`、`core.game_state.GameState.from_layout` 和 `core.types.Player`。

## 5. 新增文件

必须新增：

- `scripts/screen_openings_light.py`
- `tests/test_screen_openings_light.py`

可选新增：

- `reports/opening_light_screen_README.md`

脚本运行时可生成：

- `reports/opening_light_screen.json`
- `reports/opening_light_screen.md`
- smoke 专用 `reports/opening_light_screen_smoke.json`
- smoke 专用 `reports/opening_light_screen_smoke.md`

## 6. CLI 规格

`scripts/screen_openings_light.py` 提供以下参数：

```text
--mode curated|full
--max-candidates N
--games-per-side N
--seed N
--baseline-layout balanced_v1
--max-turns N
--output reports/opening_light_screen.json
--summary reports/opening_light_screen.md
--dry-run
--no-resume
```

默认值：

- `--mode curated`
- `--max-candidates 32`
- `--games-per-side 2`
- `--seed 2026`
- `--baseline-layout balanced_v1`
- `--max-turns 200`
- `--output reports/opening_light_screen.json`
- `--summary reports/opening_light_screen.md`
- resume 默认开启

安全限制：

- 非 dry-run 时，`candidate_count * games_per_side * 2` 默认不得超过 160。
- 如果超过 160，脚本应直接退出并提示用户调小 `--max-candidates` 或 `--games-per-side`。
- `--mode full` 可以生成 720 的确定性枚举序列，但默认仍受 `--max-candidates 32` 和总局数安全限制约束。
- `--games-per-side` 必须为正整数。为保持 seed 空间不重叠，建议拒绝大于 500 的值。

## 7. AI 配置读取

脚本从 `release/v1.0/default_params.json` 读取默认参数。

规则：

- 文件中 `ai` 必须为 `"rollout"`，否则报错退出。
- 构造 AI 时 kind 固定为 `"rollout"`。
- kwargs 需要剥离 metadata keys：`ai`、`fallback_ai`、`promotion_report`。
- 双方 AI 每局都重新 `build_ai("rollout", seed=..., **kwargs)`。

当前 release 参数形态示例：

```json
{
  "ai": "rollout",
  "rollouts_per_move": 32,
  "max_rollout_turns": 80,
  "max_step_time_ms": 750.0,
  "epsilon": 0.1,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 32,
  "low_confidence_margin": 0.08,
  "playout_policy": "greedy_risk",
  "cutoff_eval": "zweistein",
  "deadline_safety_ms": 30.0,
  "fallback_ai": "greedy_risk",
  "promotion_report": "reports/ai_promotion_decision.md"
}
```

## 8. Candidate 数据模型

新增轻量 dataclass：

```python
@dataclass(frozen=True)
class OpeningCandidate:
    candidate_id: str
    source: str
    red_layout: dict[int, Position]
    blue_layout: dict[int, Position]
```

约束：

- `red_layout` 是红方 6 个棋子到红方出发区位置的映射。
- 红方位置来自 `ai.opening_layouts.RED_ZONE`，实现时需排序后使用，避免 frozenset 顺序不稳定。
- `blue_layout` 一律由 `mirror_layout(red_layout)` 得到。
- 每个候选必须调用 `validate_layout(red_layout, blue_layout)`，返回空错误列表才保留。
- 相同 `red_layout` 去重，只保留首次出现项。
- `candidate_id` 在最终去重、校验后的顺序上生成，格式为 `curated_000`、`curated_001` 或 `full_000`、`full_001`。

布局 JSON 表示统一为：

```json
{
  "1": [0, 0],
  "2": [0, 1],
  "3": [0, 2],
  "4": [1, 0],
  "5": [1, 1],
  "6": [2, 0]
}
```

## 9. Candidate 生成

### 9.1 curated 模式

`curated` 是默认模式。生成顺序必须 deterministic，同一 `seed` 和 `--max-candidates` 下结果顺序一致。

候选来源按顺序组合：

1. `PRESETS["balanced_v1"].red`
2. `PRESETS["aggressive_v1"].red`
3. `PRESETS["defensive_v1"].red`
4. 低编号靠前布局
5. 高编号靠前布局
6. 低编号靠中布局
7. 高编号靠中布局
8. 基于 `balanced_v1` 的 1/6 交换
9. 基于 `balanced_v1` 的 2/5 交换
10. 基于 `balanced_v1` 的 3/4 交换
11. 基于 `balanced_v1` 的反序排列
12. 若干 deterministic shuffled permutations，用 `random.Random(seed)` 从全部 720 排列中洗牌后补足到 `--max-candidates`

位置排序建议：

- `home_positions = sorted(RED_ZONE, key=lambda p: (p.row + p.col, p.row, p.col))`
- “靠前”表示 `row + col` 更大，离红方目标更近。
- “靠中”优先使用 `(1, 1)`，再按到 `(1, 1)` 的曼哈顿距离和 `(row, col)` 排序。

实现重点不是设计复杂棋理，而是覆盖几类可解释扰动，并保持生成稳定、去重稳定。

### 9.2 full 模式

`full` 模式实现 720 个红方出发区排列：

```python
for perm in itertools.permutations(sorted(RED_ZONE), 6):
    red = {piece_id: position for piece_id, position in zip(range(1, 7), perm)}
```

`full` 模式不作为默认运行模式，不进入 smoke。非 dry-run 时仍受总局数安全限制约束。

## 10. 对战流程

每个 candidate 做两组对局：

- candidate as red vs baseline as blue
- baseline as red vs candidate as blue

baseline 从 `PRESETS[baseline_layout]` 获取：

- `baseline_red = PRESETS[baseline_layout].red`
- `baseline_blue = PRESETS[baseline_layout].blue`

每局必须重新构造 starting state：

```python
state = GameState.from_layout(
    red=red_layout,
    blue=blue_layout,
    current_player=Player.RED,
)
```

然后调用：

```python
play_one_game(
    red_ai=red_ai,
    blue_ai=blue_ai,
    dice_rng=dice_rng,
    max_turns=max_turns,
    starting_state=state,
)
```

`play_one_game()` 会复制传入状态，仍建议每局显式重新构造 `GameState`，避免未来实现变化导致状态污染。

胜负统计：

- candidate as red 时，`result.winner is Player.RED` 计入 `candidate_wins_as_red`。
- candidate as blue 时，`result.winner is Player.BLUE` 计入 `candidate_wins_as_blue`。
- `winner is None` 只计入局数，不计入 candidate wins。

## 11. Seed 规则

给定 `master_seed = --seed`，candidate index 为最终候选序号。

对每个 candidate 的双边对局使用统一的 side game index：

- candidate as red：`side_game_index = local_game_index`
- candidate as blue：`side_game_index = games_per_side + local_game_index`

派生公式：

```text
base_seed = master_seed * 100000 + candidate_index * 1000 + side_game_index
dice_seed = base_seed * 3
red_seed = base_seed * 3 + 1
blue_seed = base_seed * 3 + 2
```

每局都记录 seeds used：

```json
{
  "role": "candidate_as_red",
  "game_index": 0,
  "base_seed": 202600000,
  "dice_seed": 607800000,
  "red_seed": 607800001,
  "blue_seed": 607800002
}
```

## 12. Result JSON 规格

输出 JSON 顶层结构：

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-18T00:00:00",
  "updated_at": "2026-05-18T00:00:00",
  "argv": [],
  "mode": "curated",
  "max_candidates": 32,
  "candidate_count": 32,
  "games_per_side": 2,
  "seed": 2026,
  "baseline_layout": "balanced_v1",
  "max_turns": 200,
  "ai_kind": "rollout",
  "ai_kwargs_source": "release/v1.0/default_params.json",
  "ai_kwargs": {},
  "results": []
}
```

每个 result 至少包含：

```json
{
  "candidate_id": "curated_000",
  "source": "preset:balanced_v1",
  "red_layout": {},
  "blue_layout": {},
  "games_per_side": 2,
  "candidate_wins_as_red": 0,
  "candidate_wins_as_blue": 0,
  "combined_candidate_wins": 0,
  "combined_games": 4,
  "combined_win_rate": 0.0,
  "illegal_moves": 0,
  "crashes": 0,
  "timeouts": 0,
  "average_turns": 0.0,
  "average_step_time_ms": 0.0,
  "max_step_time_ms": 0.0,
  "seeds_used": [],
  "candidate_as_red": {},
  "candidate_as_blue": {}
}
```

`candidate_as_red` 和 `candidate_as_blue` 可包含 role-level 详细字段：

- `wins`
- `games`
- `illegal_moves`
- `crashes`
- `timeouts`
- `average_turns`
- `average_step_time_ms`
- `max_step_time_ms`

写文件规则：

- 每完成一个 candidate，立即更新 output JSON。
- 写入时先写同目录临时文件，再用原子替换，降低中断时 JSON 损坏概率。
- 如果写入失败，脚本应报错退出，不继续跑后续 candidate。

## 13. Resume 规则

默认启用 resume：

- 如果 `--output` 已存在，读取其中 `results`。
- 以 `candidate_id` 为主键，跳过已完成 candidate。
- 已完成的判断：存在同 id result，`combined_games == games_per_side * 2`，且 `red_layout` 与当前生成候选一致。

兼容性检查：

- `mode`、`seed`、`baseline_layout`、`games_per_side`、`max_turns`、`ai_kind`、`ai_kwargs` 必须与当前参数一致。
- `max_candidates` 可以比旧文件更大，用于追加新候选。
- 若关键参数不一致，脚本应报错，提示使用 `--no-resume` 或换 output 文件。

`--no-resume` 行为：

- 忽略已有 output。
- 从头运行当前候选集合。
- 开始前覆盖 output，但仍按每个 candidate 完成后逐步写入。

## 14. Dry-run

`--dry-run` 行为：

- 只生成 candidates。
- 对每个 candidate 调用 `validate_layout()`。
- 打印总候选数和前几个候选，建议前 8 个。
- 不调用 `play_one_game()`。
- 不写 output JSON。
- 不写 summary markdown。

dry-run 输出应包含：

- `mode`
- `candidate_count`
- `baseline_layout`
- 每个展示 candidate 的 `candidate_id`、`source`、`red_layout`、`blue_layout`

## 15. Markdown 摘要

`--summary reports/opening_light_screen.md` 生成 markdown 摘要。

内容必须包括：

- 生成时间
- 命令参数
- AI kind 与 kwargs 来源
- baseline layout
- candidate 数量
- games per side
- seed
- top 10 candidates 表格，按 `combined_win_rate` 降序排序
- stability totals：`illegal_moves`、`crashes`、`timeouts`
- 明确声明：

```text
这是小样本筛选，不是布局晋升证据，不修改 GUI/release 默认布局。
```

表格列建议：

```text
rank | candidate_id | win_rate | wins/games | as_red | as_blue | illegal | crashes | timeouts | avg_turns | avg_step_ms | max_step_ms | red_layout
```

## 16. 测试规格

新增 `tests/test_screen_openings_light.py`。

至少覆盖：

1. candidate 生成 deterministic：相同 mode、seed、max_candidates 得到相同 id 和 red layout 顺序。
2. candidate 数量受 `max_candidates` 限制。
3. 所有 candidate 通过 `validate_layout()`。
4. 所有 candidate 的蓝方布局等于 `mirror_layout(red_layout)`。
5. candidate id 不重复。
6. dry-run 不调用 `play_one_game()`，不写长 benchmark 文件。
7. result aggregation 正确计算 `combined_win_rate`、总 illegal、crashes、timeouts、平均 turns、平均 step time、最大 step time。
8. resume 能跳过已有 candidate：用 `tmp_path` 构造小 JSON，验证 completed id 不会再次运行。

建议额外覆盖：

- release 参数加载会剥离 metadata keys。
- `ai != "rollout"` 时抛出清晰错误。
- output 关键参数不兼容时拒绝 resume。
- `planned_games > 160` 时非 dry-run 拒绝运行。

测试实现可 monkeypatch `scripts.screen_openings_light.play_one_game`，用轻量 fake result 验证 dry-run 和 resume，不跑真实对局。

## 17. 验证命令

实现完成后只运行以下命令，不跑大样本：

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/test_screen_openings_light.py -v
& ".venv/Scripts/python.exe" scripts/screen_openings_light.py --dry-run --max-candidates 8
& ".venv/Scripts/python.exe" scripts/screen_openings_light.py --max-candidates 4 --games-per-side 1 --output reports/opening_light_screen_smoke.json --summary reports/opening_light_screen_smoke.md
```

验收条件：

- pytest 目标测试通过。
- dry-run 能展示候选且不跑对局。
- smoke 能完成 4 个候选、每边 1 局的双边对比。
- smoke JSON 存在并包含 4 条 results。
- smoke markdown 存在并包含 top candidates 表格和小样本声明。
- `git diff` 不包含 GUI 默认 AI、release 默认参数、release config、core 规则语义或 GUI 默认布局变更。

## 18. 实现边界与工程原则

KISS：

- 新脚本保持单一用途：生成轻量候选、跑双边小样本、逐候选落盘、生成摘要。
- 不引入复杂调度、并发、数据库或后台任务。

YAGNI：

- 不加晋升 gate 自动决策。
- 不加 GUI 集成。
- 不加长跑管理器。
- 不加新依赖。

DRY：

- 复用现有 core、AI、layout 和 match harness。
- 不复制规则逻辑。
- 小型统计聚合可在脚本内保留，需有测试锁定字段口径。

SOLID：

- candidate generation、AI config loading、game execution、aggregation、resume IO、summary formatting 分函数隔离。
- CLI `main()` 只负责参数解析和流程编排。
- GUI 和 release 配置不依赖该脚本。

## 19. 完成后的报告口径

最终报告给用户时需要说明：

- 修改了哪些文件。
- 运行了哪些命令及结果。
- smoke 的总局数、候选数、是否有 illegal/crash/timeout。
- 明确说明未修改 release/GUI 默认 AI、默认布局和 core 规则。
- 不声称筛选结果可以晋升默认布局。

## 20. 自检

本规格已检查：

- 无占位项。
- 无与硬性禁止项冲突的实现要求。
- 默认运行规模不超过 160 局。
- full 模式只作为可选枚举能力，非 dry-run 仍受安全限制。
- resume 规则明确，逐 candidate 写入明确。
- 测试覆盖 dry-run、resume、candidate deterministic 和聚合口径。
