# P8 Threat Defense Audit + Low-confidence Rerank Design

日期：2026-05-17
状态：Review-Ready
范围：P8 威胁防守审计与低置信轻量 rerank；审计先行，候选后置，所有候选不得进入 GUI/release 默认。

---

## 1. 背景

P6 robustness lock 已完成，当前比赛版本已具备 release consistency、`scripts/preflight_check.py`、GUI 推荐兜底、损坏 auto-save 清理与 timing probe。P7 rollout failure analysis 也已完成：

- 当前默认 AI：`rollout` kind + P3 promotion 显式参数。
- 当前默认布局：`balanced_v1`。
- P7.0 默认 rollout vs `greedy_risk` 120 局：87 胜 / 33 负，`illegal_moves=0`、`crashes=0`、`timeouts=0`。
- P7 失败桶：`missed_direct_win=0`、`allowed_direct_loss=63`、`low_confidence_loss=145`、`timeout_or_fallback=4`、`bad_self_capture=33`。
- P7.1 direct-win guard 因 `missed_direct_win=0` 不成立。
- P7.2 `rollout_adaptive_close_sample` 双边 100+100 合并 50.0%，未过 55% candidate 门槛，不得默认启用。

P7 已证明“直接胜利漏看”不是当前主要问题。P8 不继续盲目加采样，而是审计：当默认 rollout 选择某步后允许对手一步获胜时，是否存在同一骰子下的其他合法走法能减少对手下一手可直接胜利的骰子数。只有这个审计结果支持并获得用户明确批准，才设计更窄的 `rollout_threat_rerank` 候选。

## 2. 不可变边界

本阶段禁止修改：

- `gui/main_window.py::DEFAULT_RECOMMENDER_KIND`
- `gui/main_window.py::DEFAULT_RECOMMENDER_KWARGS`
- `release/v1.0/default_params.json`
- `release/v1.0/config.json`
- `gui/opening_panel.py` 中 `balanced_v1` 默认布局行为
- `core/` 规则语义
- GUI/release 默认 AI、默认布局、默认 fallback 文案
- P5 开局晋升路线
- MCTS 路线

当前默认 AI 参数必须保持：

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

## 3. 目标

1. 审计 `allowed_direct_loss` 与 `low_confidence_loss` 的真实成因，区分“无可防守”与“有更安全替代但 rollout 未选”。
2. 对每个失败局面统计 chosen move 与 alternative moves 的 `opponent_winning_dice_set`。
3. 统计 low-confidence 场景中是否存在 threat-reducing alternative，以及比例和样例。
4. 审计 `bad_self_capture` 与 `allowed_direct_loss` 的重叠和条件概率，不做因果过度解释。
5. 仅在审计结果支持时，设计 `rollout_threat_rerank` 实验候选。
6. 可选新增 `rollout_safe_timing_profile`，只作为报告中的应急参数，不接默认。

## 4. 非目标

- 不继续 P5 开局晋升。
- 不重启 MCTS。
- 不启用完整 `TacticalAI`。
- 不接入 direct-win guard，因为 P7 `missed_direct_win=0`。
- 不修改 GUI/release 默认 AI。
- 不修改默认布局。
- 不修改 core 规则。
- 不根据单局观感改参数。
- 不把 `rollout_adaptive_close_sample` 重新包装成默认候选；P7.2 已失败。

## 5. 关键定义

### 5.1 opponent_winning_dice_set

对某个候选走法 `move`：

```text
先在当前 state 应用 move；
令 opponent 成为下一手行动方；
枚举 opponent 的骰子 1..6；
若某个骰子下 opponent 至少存在一个一步获胜合法走法，则该骰子进入 set。
```

一步获胜必须通过 core 状态变化和 `state.get_winner()` 判定，覆盖到角胜与吃光胜。P8 脚本不得复制 GUI 规则逻辑，可复用 `ai.tactical.opponent_winning_dice_set()` 或 P7 分析脚本中的直接胜利辅助函数。

### 5.2 threat_count

```text
threat_count = len(opponent_winning_dice_set)
```

取值范围为 `0..6`。`0` 表示该走法后对手没有任何骰子可一步直接胜利。

### 5.3 threat-reducing alternative

同一局面、同一骰子下，若存在合法替代走法 `alt` 满足：

```text
len(alt.opponent_winning_dice_set) < len(chosen.opponent_winning_dice_set)
```

则该局面记为存在 `threat_reducing_alternative`。其中：

- `full_block_alternative`：替代走法 threat_count 为 `0`。
- `partial_reduction_alternative`：替代走法 threat_count 大于 `0` 但小于 chosen。
- `equal_threat_alternative`：替代走法 threat_count 等于 chosen。
- `worse_threat_alternative`：替代走法 threat_count 大于 chosen。

P8 只审计“减少对手下一手直接胜利骰子数”，不声称该走法一定更强。

## 6. 输出物总览

| 阶段 | 输出物 | 责任 |
|---|---|---|
| P8.0 | `scripts/analyze_threat_defense.py` + `tests/test_analyze_threat_defense.py` | 生成 threat defense 审计 md/json |
| P8.1 | `reports/p8_threat_defense_audit_*.{json,md}` | 统计 chosen 与 alternatives 的 opponent winning dice |
| P8.2 | 同 P8 报告 | 统计 low-confidence 中 threat-reducing alternative 比例 |
| P8.3 | 同 P8 报告 | 审计 bad self-capture 与 allowed direct loss 相关性 |
| P8.4 | 用户批准后可选 `ai/threat_rerank.py` + `ai/match.py` profile + `scripts/bench_ai.py` profile + tests + candidate report | `rollout_threat_rerank` 实验候选 |
| P8.5 | 用户批准后可选 `ai/match.py` profile + `scripts/bench_ai.py` profile + timing/bench report | `rollout_safe_timing_profile` 报告应急参数 |

## 7. P8.0 Threat Defense Audit Script

新增脚本：

```text
scripts/analyze_threat_defense.py
```

建议命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_threat_defense.py" `
  --games 120 `
  --seed-pool 28016,28017,28018 `
  --opponent greedy_risk `
  --starting-layout balanced_v1 `
  --max-turns 200 `
  --score-margin 0.08 `
  --top-k 5 `
  --max-examples 20 `
  --output "reports/p8_threat_defense_audit_20260517.md" `
  --json-output "reports/p8_threat_defense_audit_20260517.json"
```

脚本职责：

1. 从 `release/v1.0/default_params.json` 读取当前 release 默认 rollout kwargs。
2. 使用 `balanced_v1` 开局。
3. subject 为当前默认 `rollout`，opponent 默认 `greedy_risk`。
4. 复用 P7 的对局采样方式，记录 subject 最终输局中的 subject-to-move 局面。
5. 对每个被审计局面枚举当前 dice 下所有 legal moves。
6. 对 chosen move 和每个 alternative 计算 `opponent_winning_dice_set` 与 `threat_count`。
7. 聚合 low-confidence、allowed direct loss、self-capture 相关指标。
8. 输出 JSON 与 Markdown，报告必须明确写出默认 AI、默认布局、release 配置未变。

实现边界：

- 不修改 `scripts/analyze_rollout_failures.py` 的历史输出语义。
- 可复用 P7 helper，但不要为了 P8 做大规模脚本框架重构。
- 不在脚本里复制 core 规则；所有胜负与合法性通过 `GameState` / `legal_moves()` / `apply_move()` / `get_winner()` 判定。
- JSON 可包含完整 positions；Markdown 只输出汇总和有限样例，避免报告不可读。

## 8. P8.1 Chosen vs Alternatives Threat Stats

JSON 顶层结构建议：

```json
{
  "subject": {
    "ai": "rollout",
    "ai_kwargs_source": "release/v1.0/default_params.json"
  },
  "opponent": "greedy_risk",
  "games": 120,
  "seed_pool": [28016, 28017, 28018],
  "default_layout": "balanced_v1",
  "analysis_window": {
    "subject_losses_only": true,
    "subject_to_move_only": true,
    "score_margin": 0.08,
    "top_k": 5
  },
  "summary": {
    "subject_wins": 0,
    "subject_losses": 0,
    "illegal_moves": 0,
    "crashes": 0,
    "timeouts": 0,
    "draw_max_turns": 0,
    "audited_positions": 0
  },
  "threat_defense": {
    "chosen_allowed_direct_loss_positions": 0,
    "threat_reducing_alternative_positions": 0,
    "full_block_alternative_positions": 0,
    "partial_reduction_alternative_positions": 0,
    "average_chosen_threat_count": 0.0,
    "average_best_alternative_threat_count": 0.0,
    "average_reduction_when_available": 0.0
  },
  "low_confidence": {
    "positions": 0,
    "with_allowed_direct_loss": 0,
    "with_threat_reducing_alternative": 0,
    "with_full_block_alternative": 0,
    "threat_reducing_ratio": 0.0,
    "full_block_ratio": 0.0
  },
  "self_capture_correlation": {
    "self_capture_positions": 0,
    "self_capture_and_allowed_direct_loss": 0,
    "non_self_capture_positions": 0,
    "non_self_capture_and_allowed_direct_loss": 0,
    "allowed_direct_loss_rate_given_self_capture": 0.0,
    "allowed_direct_loss_rate_given_non_self_capture": 0.0
  },
  "positions": [],
  "decision": {
    "supports_threat_rerank_candidate": false,
    "reasons": []
  },
  "command": ""
}
```

单个 position 对象建议：

```json
{
  "game_index": 0,
  "turn": 0,
  "board": "",
  "subject_player": "red",
  "player": "red",
  "dice": 1,
  "low_confidence": false,
  "score_margin": null,
  "failure_tags": ["allowed_direct_loss"],
  "chosen": {
    "piece_id": 1,
    "from": [0, 0],
    "to": [1, 1],
    "root_rank": 1,
    "root_score": 0.0,
    "root_winrate": 0.0,
    "opponent_winning_dice_set": [2, 5],
    "opponent_winning_dice_count": 2,
    "self_capture": false
  },
  "alternatives": [
    {
      "piece_id": 2,
      "from": [0, 1],
      "to": [1, 1],
      "root_rank": 2,
      "root_score": -0.02,
      "score_delta_from_chosen": -0.02,
      "opponent_winning_dice_set": [],
      "opponent_winning_dice_count": 0,
      "threat_delta_from_chosen": -2,
      "self_capture": false
    }
  ],
  "best_threat_count": 0,
  "threat_reducing_alternative_exists": true,
  "full_block_alternative_exists": true,
  "best_threat_reducing_rank": 2
}
```

排序规则：

- `alternatives` 按 `opponent_winning_dice_count` 升序、`root_rank` 升序、`piece_id/from/to` 稳定排序。
- `chosen` 也必须出现在 legal moves 中；若 chosen 不合法，计入 `illegal_moves` 并终止该局，不能继续推导。
- root stats 缺失时 `root_rank/root_score/root_winrate` 为 `null`，不得伪造。

## 9. P8.2 Low-confidence Threat-reducing Ratio

重点统计对象：

```text
subject 最终输局中的 subject-to-move 局面
且 chosen step low_confidence = true
```

报告至少给出：

- low-confidence position 总数。
- low-confidence 且 chosen 允许对手直接胜利的数量。
- low-confidence 且存在 threat-reducing alternative 的数量。
- low-confidence 且存在 full-block alternative 的数量。
- `threat_reducing_ratio = with_threat_reducing_alternative / positions`。
- `full_block_ratio = with_full_block_alternative / positions`。
- 按 `score_margin` 分桶：`<=0.02`、`(0.02,0.04]`、`(0.04,0.08]`、`>0.08 or null`。
- low-confidence top-k 覆盖率：low-confidence 且有 threat-reducing alternative 的局面中，最佳 threat-reducing alternative 是否在 rollout root stats 前 `top_k` 内。

候选启动建议门槛：

```text
low_confidence positions >= 30
with_threat_reducing_alternative / low_confidence positions >= 25%
low-confidence best threat-reducing alternative in top_k ratio >= 60%
```

若未满足，P8 只输出审计报告，不实现 `rollout_threat_rerank`。

## 10. P8.3 bad_self_capture Correlation Audit

P8 不禁止 self-capture，因为吃本方棋子是合法策略且可能有价值。审计目标只是判断 P7 的 `bad_self_capture=33` 是否与 `allowed_direct_loss` 同时出现。

报告至少给出：

```text
self_capture_positions
self_capture_and_allowed_direct_loss
non_self_capture_positions
non_self_capture_and_allowed_direct_loss
allowed_direct_loss_rate_given_self_capture
allowed_direct_loss_rate_given_non_self_capture
self_capture_with_threat_reducing_alternative
self_capture_with_full_block_alternative
```

判断规则：

- 若 self-capture 的 allowed-direct-loss 条件概率显著高于 non-self-capture，报告写“相关信号”。
- 若重叠主要出现在 low-confidence 且有 threat-reducing alternative 的局面，可以作为 `rollout_threat_rerank` 的辅助证据。
- 不新增 “ban self-capture” 候选；这会违反规则策略空间，也容易误杀好棋。
- 不启用完整 `TacticalAI`；P8 只允许 top-k threat count 轻量 rerank。

## 11. P8.4 Optional Candidate: rollout_threat_rerank

启用条件：

- P8.2 启动门槛满足。
- P8.3 未显示该问题只来自无法防守的 self-capture 噪声。
- P8 报告样例能复现：chosen 的 `threat_count` 高于某个 top-k alternative。

候选意图：

```text
先运行当前 release 默认 rollout；
仅当 base 标记 low_confidence 且 score_margin 很小时；
在 root stats top-k 中计算每个候选的 opponent_winning_dice_count；
只允许选择 score 接近 base chosen 且 threat_count 更低的候选；
否则完全返回 base chosen。
```

建议新增文件：

```text
ai/threat_rerank.py
```

建议注册 kind：

```text
rollout_threat_rerank
```

建议默认候选参数：

```json
{
  "threat_rerank_top_k": 3,
  "threat_rerank_score_margin": 0.04,
  "threat_rerank_only_low_confidence": true,
  "threat_rerank_min_reduction": 1
}
```

选择规则：

1. 构造 base：当前 release 默认 rollout kwargs，不做参数漂移。
2. `base_move = base.choose_move(state, dice)`。
3. 若 `base_move is None`，返回 `None`。
4. 若 `base.last_low_confidence` 为 false，返回 `base_move`。
5. 若 `base.last_score_margin is None` 或 `base.last_score_margin > threat_rerank_score_margin`，返回 `base_move`。
6. 从 `base.last_root_stats` 取前 `top_k`，并过滤：
   - move 必须合法；
   - move 的 root score 与 base chosen score 差距不得超过 `threat_rerank_score_margin`；
   - move 的 opponent winning dice count 至少比 base chosen 少 `threat_rerank_min_reduction`。
7. 若没有候选，返回 `base_move`。
8. 在候选中按 `opponent_winning_dice_count` 升序、root score 降序、root rank 升序选择。
9. 记录 telemetry：
   - `fire_threat_rerank_considered`
   - `fire_threat_rerank_applied`
   - `fire_threat_rerank_passthrough_not_low_confidence`
   - `fire_threat_rerank_passthrough_margin`
   - `fire_threat_rerank_passthrough_no_reduction`

实现边界：

- 不改 `RolloutAI.choose_move()` 默认行为。
- 不改 `TacticalAI`。
- 不加 direct-win guard。
- 不禁止 self-capture。
- `ai_version_signature()` 必须记录 base signature 与 rerank 参数。
- `bench_ai.py` 可通过现有 telemetry 聚合 wrapper 的 `fire_counts`；若现有聚合只扫描 `fire_counts`，wrapper 应提供同名字段。

测试建议：

- base 非 low-confidence 时透传 base move。
- score margin 大于阈值时透传 base move。
- top-k 中存在 threat_count 更低且 score 接近的 move 时 rerank。
- top-k 中 threat_count 更低但 score 差距过大时不 rerank。
- rerank 后返回的 move 必须属于 `state.legal_moves(current_player, dice)`。
- signature 包含 base rollout kwargs 与 rerank 参数。

候选 bench：

前置条件：`scripts/bench_ai.py::CANDIDATE_PROFILES["rollout_threat_rerank"]["candidate"]` 必须包含 `opponent_kwargs=RELEASE_DEFAULT_ROLLOUT_KWARGS` 和 `starting_layout="balanced_v1"`。命令使用内置 profile，不手写裸 `--opponent rollout` 口径。

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_threat_rerank `
  --stage candidate `
  --games-per-side 100 `
  --report-name p84_candidate_rollout_threat_rerank_20260517
```

门禁：

```text
candidate_win_rate >= 55.0%
illegal_moves = 0
crashes = 0
timeouts = 0
average_step_time_ms <= 500.0ms
max_step_time_ms <= 5000.0ms
report opponent_kwargs == RELEASE_DEFAULT_ROLLOUT_KWARGS
```

即使通过，也只生成报告，不允许默认启用。默认晋升必须另开阶段并由用户明确批准。

## 12. P8.5 Optional Candidate: rollout_safe_timing_profile

启用条件：

- P8.4 实现后 timing 或 bench 显示步时明显变差；或
- 赛前机器现场负载变高，需要一组已报告的应急参数；或
- P6 timing probe 后续复验出现 `p99_ms > 1000` 或 `max_ms > 5000`。

候选意图：

提供一组更保守的 rollout 参数作为“现场应急报告项”，不是默认参数。

建议 kind：

```text
rollout_safe_timing_profile
```

建议参数：

```json
{
  "rollouts_per_move": 24,
  "max_rollout_turns": 80,
  "max_step_time_ms": 650.0,
  "epsilon": 0.1,
  "close_sample_margin": 0.08,
  "close_sample_rollouts_per_move": 16,
  "low_confidence_margin": 0.08,
  "playout_policy": "greedy_risk",
  "cutoff_eval": "zweistein",
  "deadline_safety_ms": 80.0
}
```

报告命令：

前置条件：`scripts/bench_ai.py::CANDIDATE_PROFILES["rollout_safe_timing_profile"]["candidate"]` 必须包含 `opponent_kwargs=RELEASE_DEFAULT_ROLLOUT_KWARGS` 和 `starting_layout="balanced_v1"`。命令使用内置 profile，不手写裸 `--opponent rollout` 口径。

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_safe_timing_profile `
  --stage candidate `
  --games-per-side 100 `
  --report-name p85_candidate_rollout_safe_timing_profile_20260517
```

边界：

- 该 profile 不得写入 `release/v1.0/default_params.json`。
- 该 profile 不得改变 GUI 默认推荐。
- 若胜率或稳定性未过 candidate 门禁，只保留为失败报告，不作为应急建议。
- 即使通过，也只能作为“已评估应急 profile”，现场是否使用必须由用户另行明确批准。

## 13. 执行顺序

```text
P8.0 新增 analyze_threat_defense.py 与小样本测试
  -> P8.1 跑 120 局 threat defense audit 报告
  -> P8.2 根据报告计算 low-confidence threat-reducing 比例
  -> P8.3 审计 bad_self_capture 与 allowed_direct_loss 相关性
  -> 若 P8.2/P8.3 支持，先提交报告并等待用户明确批准
  -> 用户批准后才实现 P8.4 rollout_threat_rerank
  -> 用户批准且 P8.4 或现场环境显示步时风险时，才实现 P8.5 safe timing profile
```

P8.4 与 P8.5 都是可选项。P8.0-P8.3 是本阶段核心。

## 14. 总体验收

必须全部满足：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

`scripts/preflight_check.py` 成功输出：

```text
READY FOR MATCH
```

报告验收：

- `reports/p8_threat_defense_audit_*.md` 生成。
- `reports/p8_threat_defense_audit_*.json` 生成。
- 报告包含复现命令。
- 报告明确写出默认 AI、默认布局、release 配置未变。
- 报告包含 chosen vs alternatives 的 `opponent_winning_dice_set` 汇总。
- 报告包含 low-confidence threat-reducing ratio。
- 报告包含 self-capture 与 allowed-direct-loss 相关性统计。

候选验收：

- 如果实现 `rollout_threat_rerank`，必须生成 candidate vs current default rollout 双边 100+100 报告。
- 如果实现 `rollout_safe_timing_profile`，必须生成 candidate vs current default rollout 双边 100+100 报告。
- candidate 报告必须显示 `opponent_kwargs` 等于当前 release 默认 rollout 显式 kwargs。
- 未过门禁不得晋升。
- 即使过门禁，也不得在 P8 内修改 GUI/release 默认。

配置验收：

- release 默认 AI 不变：`rollout` + P3 promotion 显式 kwargs。
- release 默认布局不变：`balanced_v1`。
- `greedy_risk` 仍是 fallback。
- `core/` 规则语义不变。
- 所有候选只作为 benchable kind 和 reports 产物存在，不进入默认配置。

## 15. Spec 自检

- 已覆盖 P8.0 至 P8.5。
- 已明确 `allowed_direct_loss` 和 `low_confidence_loss` 的审计口径。
- 已定义 `opponent_winning_dice_set`、`threat_count` 与 threat-reducing alternative。
- 已明确 `bad_self_capture` 只做相关性审计，不新增 self-capture 禁止规则。
- 已把 `rollout_threat_rerank` 限制在 low-confidence 且 score margin 很小时触发。
- 已明确 P8 不修改默认 AI、默认布局、core 规则或 release 配置。
- 已保留 P8.4/P8.5 为可选候选，并要求未过门禁不得晋升。
