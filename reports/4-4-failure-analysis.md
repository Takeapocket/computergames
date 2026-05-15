# 阶段 4.4 ExpectimaxAI 评测失败记录

> 历史报告（2026-05-10）。本文中 `greedy_risk` 作为竞赛主力的表述是当时上下文；当前默认 AI 已升级为旧 flat `rollout`，`greedy_risk` 保留为应急回退。当前事实以 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/test_report.md` 为准。

更新时间：2026-05-10

## 结论

`ExpectimaxAI(depth=1)` 沿用 `greedy_risk` 的 evaluator kwargs（`expected_risk_weight=3.0`, `expected_win_risk_weight=500.0`）时，**显著弱于** `greedy_risk`：

| 对局 | 局数 | expectimax 胜率 | 报告 |
|---|---:|---:|---|
| 红 expectimax vs 蓝 greedy_risk | 200 | 46.5% | `reports/bench_phase_4_4_expectimax_vs_greedy_risk.json` |
| 红 greedy_risk vs 蓝 expectimax | 200 | 46.5%（蓝） | `reports/bench_phase_4_4_greedy_risk_vs_expectimax.json` |

合并：186/400 = **46.5%**，两个方向各亏约 7 个百分点。差距远超 n=400 的 ~2.5% 标准误，结论稳健。

ExpectimaxAI **暂不推荐用于竞赛**；保留在 `build_ai` 工厂里仅供后续实验。

## 推测的原因

evaluator 里的 `expected_target_win_risk(state, perspective)` 计算"对手下一轮走到目标角获胜的概率"。这个量是为 1-ply lookahead 设计的——`greedy_risk` 在自己出招后立即评估，"对手下一轮"就是真实的下一回合。

但在 `_expectimin` 里，我们已经替对手 apply 了一步走法，再调 evaluate 时 `state.current_player` 已经回到我方。此时 `expected_target_win_risk` 计算的是"对手再下一回合（隔了我方一回合）到目标角的概率"——语义上**不是**应该评估的真实威胁。同样的问题影响 `distance_weighted_capture_risk`（计算的是"对手下一轮吃我方子的概率"）。

净效应：expectimax 在搜索树的非根叶子上重复使用了一个**为根节点 1-ply 设计**的风险函数，导致威胁被双重折现 / 错位估计。结果是 expectimax 倾向于做"看起来在阻挡 1/6 forfeit 路径"但实际未必有用的走法。

## 验证假设的下一步（暂未执行）

1. **裸 expectimax**：跑 `expectimax(depth=1, expected_risk_weight=0, expected_win_risk_weight=0)` vs `greedy`（不带 risk 项的纯 material+distance 评估）。如果裸 expectimax 与 greedy 平手，说明问题确实出在 risk 项与 lookahead 的耦合。
2. **风险项在 leaf 关闭**：让 ExpectimaxAI 在 leaf eval 时强制 `expected_*_weight=0`，但中间节点保留。可能需要为 evaluator 增加"是不是 leaf"的开关。
3. **改写 risk 函数**：让 `expected_*_risk` 接受"哪一方的下一回合"作为参数，而不是默认对手。
4. **depth=2 / depth=3**：增大 lookahead 深度，看是否能压过 risk 项的错位估计。注意 depth=2 已经是 6^2 * branching = 数百次 evaluate 每步，单局可能数秒。

## 工程决策

- ExpectimaxAI、`tests/test_expectimax.py`、`build_ai` 的 `expectimax` 分支**保留**——代码本身正确（13 测试全过），只是默认配置在当前 evaluator 下不强。未来如果有人想做 (1)–(4) 中任意实验，可以直接复用。
- 当时竞赛主力仍是 `greedy_risk`；当前主力已改为旧 flat `rollout`。
- 不在 `gui/main_window.py` 引用 expectimax。

## 工程文件

- `ai/expectimax_ai.py`：未改逻辑，只是把 `_eval_kwargs` 里已知键提升为公共属性（让 `ai_version_signature` 能记录到 bench metadata）。
- `ai/match.py:ai_version_signature`：tuple 里加了 `depth`，让 expectimax 的签名包含搜索深度。
- bench 生成的两份 JSON 报告（约 600KB/份）已写入 `reports/`。
