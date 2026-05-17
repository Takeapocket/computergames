# P6 Robustness Lock + Default Rollout Failure Analysis Design

日期：2026-05-16
状态：Review-Ready
范围：P6 赛前鲁棒性锁定 + P7 当前默认 rollout 失败归因；只允许报告驱动的小型 AI 候选，不允许直接晋升默认。

---

## 1. 背景

报名已完成，设计文档不再是当前重点。当前比赛版本的工程价值排序应回到现场可用性：

```text
规则正确 > 现场稳定 > GUI 可操作 > 默认 AI 强度 > 数据化 AI 增强 > 开局与参数优化 > 界面美观
```

当前事实：

- release/v1.0 默认 AI 是 `rollout` kind + P3 promotion 显式 kwargs。
- GUI 默认推荐仍由 `gui/main_window.py::DEFAULT_RECOMMENDER_KIND = "rollout"` 和 `DEFAULT_RECOMMENDER_KWARGS` 控制。
- release 默认参数位于 `release/v1.0/default_params.json`。
- 默认布局保持 `balanced_v1`，release 配置位于 `release/v1.0/config.json`。
- `greedy_risk` 是应急回退，不是当前默认强度基线。
- P5.5 已证明当前 opening 候选 60 局扩样失败，不晋升布局。
- P4/P4.1 MCTS 已停止，赛前不继续投入。

本阶段不能继续做“看到一个怪棋就调默认参数”的工作。P6 先锁现场鲁棒性，P7 再把默认 rollout 的失败原因数据化。只有归因报告支持某个非常小的修正时，才允许设计候选；候选只能写入 `reports/`，不得接入 GUI/release 默认。

## 2. 不可变边界

本阶段禁止修改：

- `gui/main_window.py::DEFAULT_RECOMMENDER_KIND`
- `gui/main_window.py::DEFAULT_RECOMMENDER_KWARGS`
- `release/v1.0/default_params.json`
- `release/v1.0/config.json`
- `gui/opening_panel.py` 中 `balanced_v1` 默认布局行为
- `core/` 规则语义
- `ai/mcts.py` 或 MCTS bench 路线
- 默认布局、默认 AI、默认 fallback 的 release 文案

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

1. 提升赛前现场鲁棒性，尤其是启动前检查、自动保存恢复和 GUI 推荐兜底。
2. 建立当前默认 rollout 的失败归因报告，把怪棋拆成可计数的类别。
3. 只在归因报告支持后设计一个小型 AI 候选；候选不得直接晋升默认。

## 4. 非目标

- 不优化 MCTS。
- 不继续扩大 P5.5 失败的 opening 候选。
- 不新增平台 API 或联网能力。
- 不改 core 规则。
- 不以单局截图、单方向小样本或主观观感替换默认 AI。
- 不把 P7 候选接到 GUI 默认推荐或 release 默认参数。

## 5. 输出物总览

| 阶段 | 输出物 | 责任 |
|---|---|---|
| P6.0 | `tests/test_release_consistency.py` | 锁定 release、GUI 默认 AI、fallback、默认布局一致性 |
| P6.1 | `scripts/preflight_check.py` | 一条命令完成赛前检查，成功输出 `READY FOR MATCH` |
| P6.2 | `gui/main_window.py` + GUI 测试 | 推荐兜底链：default rollout -> `greedy_risk` -> first legal move |
| P6.3 | `tests/test_auto_save.py` / `tests/test_main_window.py` / `tests/test_match_integration.py` | 损坏 auto-save 与 match auto-save 启动恢复回归 |
| P6.4 | `scripts/timing_budget_probe.py` + `reports/p6_timing_budget_probe_*.{json,md}` | 默认 rollout 步时预算探针 |
| P7.0 | `scripts/analyze_rollout_failures.py` + `reports/p7_rollout_failure_analysis_*.{json,md}` | 当前默认 rollout 失败归因 |
| P7.1 | 候选设计报告，可选代码候选 | `rollout_direct_win_guard`，不得默认启用 |
| P7.2 | 候选设计报告，可选代码候选 | adaptive close-sample 候选，不得默认启用 |

## 6. P6.0 Release Consistency Test

目标：把“默认 AI 和默认布局不变”写成自动测试，而不是靠人工记忆。

建议新增文件：

```text
tests/test_release_consistency.py
```

测试覆盖：

- `gui.main_window.DEFAULT_RECOMMENDER_KIND == "rollout"`。
- `gui.main_window.DEFAULT_RECOMMENDER_KWARGS` 精确等于 P3 promotion kwargs。
- `release/v1.0/default_params.json` 精确等于 GUI 默认 kwargs + `fallback_ai="greedy_risk"` + `promotion_report`。
- `release/v1.0/config.json["default_layout"] == "balanced_v1"`。
- `gui.opening_panel.OpeningPanel` 初始 `layout_var` 为 `balanced_v1`。
- `release/v1.0/README.md` 仍说明默认 AI 为 `rollout` kind + P3 显式参数。
- `release/v1.0/README.md` 仍说明默认布局为 `balanced_v1`。

实现边界：

- 可以保留现有 `tests/test_default_ai_config.py`，也可以把它的断言迁移到新测试文件。
- 不需要写动态扫描全仓库的“禁止字符串”测试；这种测试脆弱且容易误报。
- 不允许为了让测试通过而调整默认配置。

验收：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_release_consistency.py
```

## 7. P6.1 Preflight Check

目标：赛前用一条命令确认比赛版本处于可运行状态，并给操作员一个明确结论。

新增文件：

```text
scripts/preflight_check.py
```

默认执行内容：

1. 校验当前工作目录是项目根，关键文件存在。
2. 读取 `release/v1.0/default_params.json`，校验默认 AI 精确等于 P6.0 锁定值。
3. 读取 `release/v1.0/config.json`，校验默认布局为 `balanced_v1`。
4. 导入 `gui.main_window`，校验 GUI 默认推荐配置与 release 一致。
5. 运行：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

输出格式：

```text
[OK] release defaults locked
[OK] pytest -q
[OK] scripts/smoke_test.py
[OK] scripts/s2_rehearsal.py
READY FOR MATCH
```

失败行为：

- 任一检查失败时打印 `[FAIL] <name>: <reason>`。
- 退出码非 0。
- 不打印 `READY FOR MATCH`。

实现边界：

- 不联网。
- 不写 release 配置。
- 不清理用户棋谱。
- 不要求安装额外依赖。

验收：

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

成功时最后一行必须包含：

```text
READY FOR MATCH
```

## 8. P6.2 GUI AI Recommendation Fallback

目标：现场推荐区域不能因为默认 rollout 异常而失去可执行建议。

兜底链固定为：

```text
default rollout -> greedy_risk -> first legal move -> None
```

建议实现：

- 在 `gui/main_window.py` 中收敛 `_recommended_move()` 的异常和非法走法处理。
- 默认 `_recommender` 仍只构造当前 `rollout`。
- 当默认 rollout 返回 `None`、抛异常、返回非法走法或因内部错误无法更新时：
  1. 构造或复用 `build_ai("greedy_risk", seed=0)`。
  2. 用同一 `state` 与 `current_dice` 取回退推荐。
  3. 若仍失败，取 `state.legal_moves(current_dice)[0]`。
  4. 若没有合法走法，返回 `None` 并显示“无合法走法”。

推荐文本必须能区分来源：

```text
rollout：红方 6: ...
greedy_risk 回退：红方 6: ...
规则兜底：红方 6: ...
```

测试建议：

- `tests/test_gui_logic.py`：默认 rollout 抛异常时使用 `greedy_risk` 回退。
- `tests/test_gui_logic.py`：默认 rollout 返回非法 move 时使用 `greedy_risk` 回退。
- `tests/test_gui_logic.py`：`greedy_risk` 也失败时返回第一条合法走法。
- `tests/test_gui_logic.py`：无合法走法时推荐文本为无合法走法。
- `tests/test_main_window.py`：真实窗口中推荐区展示 fallback 来源。

实现边界：

- 不改 `RolloutAI` 默认参数。
- 不改 `greedy_risk` 权重。
- 不在 GUI 复制规则逻辑，只使用 `GameState.legal_moves()` 校验。

## 9. P6.3 Corrupted Auto-Save Recovery Tests

目标：损坏的自动保存文件不能阻塞启动，不能让 GUI 卡在半恢复状态。

现状已有：

- `record.auto_save.has_auto_save()` 和 `has_auto_save_match()` 会拒绝损坏 JSON。
- `tests/test_auto_save.py` 已覆盖部分 corrupt JSON 行为。
- `gui/main_window.py` 已有单盘和整轮恢复分支。

本阶段补齐 GUI 启动层测试：

### P6.3-A 单盘 auto-save 损坏

文件：

```text
tests/test_main_window.py
```

场景：

- `auto_save.json` 存在但内容不是合法 JSON。
- `auto_save_match.json` 不存在。
- 启动 `MainWindow`。

期望：

- GUI 不崩溃。
- 不尝试加载损坏单盘。
- 新建 fresh game。
- 损坏 `auto_save.json` 被清理或被明确判定为无效且不会在下一次启动重复阻塞。

### P6.3-B match auto-save 损坏

文件：

```text
tests/test_match_integration.py
```

场景：

- `auto_save_match.json` 存在但内容不是合法 JSON。
- `auto_save.json` 不存在。
- 启动 `MainWindow`。

期望：

- GUI 不崩溃。
- 不进入 match 恢复半状态。
- 损坏 `auto_save_match.json` 被清理或不会在下一次启动重复阻塞。

### P6.3-C match 有效但单盘 auto-save 损坏

文件：

```text
tests/test_match_integration.py
```

场景：

- `auto_save_match.json` 是有效 match，`phase="playing"`。
- `auto_save.json` 损坏。

期望：

- 行为与“match playing 但单盘 auto-save 缺失”一致：必须提示用户当前盘无法安全恢复，而不是静默丢盘内数据。
- 用户确认放弃恢复后，两个 auto-save 文件都清理。

### P6.3-D finished match + 损坏单盘残留

文件：

```text
tests/test_match_integration.py
```

场景：

- `auto_save_match.json` 是有效 match，`phase="finished"`。
- `auto_save.json` 损坏。

期望：

- finished match 提示后回到 debug。
- 损坏单盘残留被清理。

验收：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q tests/test_auto_save.py tests/test_main_window.py tests/test_match_integration.py
```

## 10. P6.4 Timing Budget Probe

目标：在不改默认 AI 的前提下，确认当前默认 rollout 在固定局面集合上的推荐耗时分布。

新增脚本：

```text
scripts/timing_budget_probe.py
```

建议输入：

```powershell
& ".venv/Scripts/python.exe" "scripts/timing_budget_probe.py" `
  --samples 120 `
  --seed 26016 `
  --output "reports/p6_timing_budget_probe_20260516.md" `
  --json-output "reports/p6_timing_budget_probe_20260516.json"
```

采样策略：

- 从 `release/v1.0/default_params.json` 读取当前默认 rollout kwargs。
- 使用 `balanced_v1` 开局。
- 用固定 seed 做若干局轻量 self-play 或随机合法推进，收集不同 dice、不同中局位置。
- 对每个样本调用一次当前默认 rollout 推荐。
- 不应用推荐结果到 GUI，不写 release 配置。

JSON 字段：

```json
{
  "ai_kind": "rollout",
  "ai_kwargs_source": "release/v1.0/default_params.json",
  "default_layout": "balanced_v1",
  "sample_count": 120,
  "avg_ms": 0.0,
  "p50_ms": 0.0,
  "p95_ms": 0.0,
  "p99_ms": 0.0,
  "max_ms": 0.0,
  "rollout_timed_out_count": 0,
  "rollout_used_fallback_count": 0,
  "illegal_recommendations": 0,
  "exceptions": 0
}
```

报告判断：

- `illegal_recommendations = 0`。
- `exceptions = 0`。
- `rollout_used_fallback_count = 0` 为理想值；若大于 0，报告必须列出样本。
- `max_ms <= 5000`，否则视为现场风险。
- `p99_ms <= 1000`，否则需要在报告中标为“赛前关注”。

P6.4 是探针，不是 AI 晋升或降级依据。若探针失败，只允许修鲁棒性或 fallback；不得因此直接调默认参数。

## 11. P7.0 Default Rollout Failure Analysis

目标：把默认 rollout 的失败拆成可复现、可计数的原因类别，为后续小候选提供证据。

新增脚本：

```text
scripts/analyze_rollout_failures.py
```

建议命令：

```powershell
& ".venv/Scripts/python.exe" "scripts/analyze_rollout_failures.py" `
  --games 120 `
  --seed-pool 27016,27017,27018 `
  --opponent greedy_risk `
  --starting-layout balanced_v1 `
  --output "reports/p7_rollout_failure_analysis_20260516.md" `
  --json-output "reports/p7_rollout_failure_analysis_20260516.json"
```

分析对象：

- subject：当前 release 默认 `rollout` + P3 显式 kwargs。
- opponent：默认先用 `greedy_risk`，因为它是应急回退且稳定；后续可扩展到 self-play，但 P7.0 不要求。
- layout：默认 `balanced_v1`。

每步采集：

- state hash 或 slim board 表示。
- player、dice、legal move count。
- chosen move。
- root stats：visits、score、winrate、avg、low_confidence。
- `last_timed_out`、`last_used_fallback`、score margin。
- 该步是否存在直接胜利合法步。
- chosen move 是否直接胜利。
- chosen move 后是否允许对手下个 dice 直接胜利。
- chosen move 是否 self-capture。
- game 结局：胜负、turns、termination reason。

失败标签：

| 标签 | 定义 |
|---|---|
| `missed_direct_win` | 当前 dice 下存在一步获胜 move，但 rollout 未选择 |
| `allowed_direct_loss` | rollout 走后，对手至少一个 dice 有一步获胜 |
| `low_confidence_loss` | 低置信推荐出现在最终输局关键窗口 |
| `timeout_or_fallback` | 推荐过程中发生 rollout timeout 或内部 fallback |
| `bad_self_capture` | 非终局 self-capture 后进入输局，且 root stats 未显示明显优势 |
| `opening_side_bias` | 失败集中在固定颜色或先后手方向 |
| `material_race_loss` | 中后盘子力优势转为推进失败 |
| `unclassified` | 无法用上述规则解释 |

注意：标签是归因线索，不是因果证明。Markdown 报告必须写明这一点。

JSON 输出：

```json
{
  "subject": {
    "ai": "rollout",
    "ai_kwargs_source": "release/v1.0/default_params.json"
  },
  "opponent": "greedy_risk",
  "games": 120,
  "seed_pool": [27016, 27017, 27018],
  "summary": {
    "subject_wins": 0,
    "subject_losses": 0,
    "illegal_moves": 0,
    "crashes": 0,
    "timeouts": 0
  },
  "failure_buckets": {
    "missed_direct_win": 0,
    "allowed_direct_loss": 0,
    "low_confidence_loss": 0,
    "timeout_or_fallback": 0,
    "bad_self_capture": 0,
    "opening_side_bias": 0,
    "material_race_loss": 0,
    "unclassified": 0
  },
  "examples": []
}
```

验收：

- 脚本能在小样本测试下生成 md/json。
- 报告包含复现命令。
- 报告明确写出：默认 AI、默认布局、release 配置未变。
- `reports/` 中只落报告，不修改 GUI/release 默认。

## 12. P7.1 Optional Candidate: rollout_direct_win_guard

启用条件：

- P7.0 报告中 `missed_direct_win` 出现明确样本。
- 样本可复现，且不是测试脚本误判合法胜利。

候选意图：

在 rollout 采样前加一个极小战术 guard：

```text
若当前 dice 下有一步直接获胜 legal move，直接选择该 move；
否则完全委托当前默认 rollout。
```

建议候选名：

```text
rollout_direct_win_guard
```

实现边界：

- 可以用轻量 wrapper 包装当前 release 默认 rollout kwargs。
- 不改 `RolloutAI` 默认行为。
- 不改 `DEFAULT_RECOMMENDER_KIND`。
- 不改 `release/v1.0/default_params.json`。
- `ai_version_signature()` 必须记录 guard 名称和 base rollout kwargs。

测试：

- 有直接到角胜利时选择直接胜利 move。
- 有吃光对方胜利时选择直接胜利 move。
- 无直接胜利时委托 base rollout。
- wrapper 返回的 move 必须属于 `state.legal_moves(dice)`。

报告门禁：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_direct_win_guard `
  --opponent rollout `
  --stage candidate `
  --games-per-side 100 `
  --report-name p71_candidate_rollout_direct_win_guard_20260516
```

即使 candidate 通过，也只能生成报告，不允许默认启用。是否晋升必须另开阶段并由用户明确批准。

## 13. P7.2 Optional Candidate: Adaptive Close-Sample

启用条件：

- P7.0 报告显示失败集中在 `low_confidence_loss` 或 close root score。
- P6.4 timing probe 显示当前机器仍有步时预算余量。

候选意图：

只在根候选接近时增加采样，而不是全局提高 rollout 数。当前默认已经有 close-sample 参数，本候选只能作为显式实验 profile 调整，例如：

```json
{
  "close_sample_margin": 0.06,
  "close_sample_rollouts_per_move": 64,
  "low_confidence_margin": 0.06
}
```

候选名建议：

```text
rollout_adaptive_close_sample
```

实现边界：

- 不改当前 release 默认 close-sample 值。
- 不改 GUI/release 默认。
- 必须使用当前 release 默认 rollout kwargs 作为 base，再局部覆盖 close-sample 参数。
- 如果 P6.4 显示 `p99_ms > 1000` 或 `max_ms > 5000`，不启动该候选。

测试：

- `build_ai("rollout_adaptive_close_sample")` 可构造。
- signature 记录覆盖后的 close-sample 参数。
- 小 `max_step_time_ms` 下仍返回合法 move 或 fallback。

报告门禁：

```powershell
& ".venv/Scripts/python.exe" "scripts/bench_ai.py" `
  --candidate rollout_adaptive_close_sample `
  --opponent rollout `
  --stage candidate `
  --games-per-side 100 `
  --report-name p72_candidate_rollout_adaptive_close_sample_20260516
```

该候选只写入 `reports/`。没有用户明确批准前，不进入 GUI/release 默认。

## 14. 执行顺序

```text
P6.0 release consistency test
  -> P6.1 preflight_check.py
  -> P6.2 GUI recommendation fallback
  -> P6.3 corrupted auto-save recovery tests
  -> P6.4 timing budget probe
  -> P7.0 rollout failure analysis report
  -> P7.1/P7.2 optional candidates only if P7.0 supports them
```

P7.1 与 P7.2 互相独立，但都依赖 P7.0。没有 P7.0 报告，不进入 P7.1/P7.2。

## 15. 总体验收

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

配置验收：

- release 默认 AI 不变：`rollout` + P3 promotion 显式 kwargs。
- release 默认布局不变：`balanced_v1`。
- `greedy_risk` 仍是 fallback。
- `core/` 规则语义不变。
- P7.1/P7.2 如实现，只能写入 `reports/` 和实验候选注册，不改 GUI/release 默认。

## 16. Spec 自检

- 已覆盖用户要求的 P6.0 至 P7.2。
- 已明确禁止修改默认 AI、默认布局、core 规则和 release 配置。
- 已把 P5.5 opening 失败和 P4/P4.1 MCTS 停止写入背景与非目标。
- 每个任务都有文件边界、测试或报告产物。
- AI 候选需要 P7.0 归因支持，且不得默认启用。
