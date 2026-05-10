# 阶段 4.2 Expected Risk 初轮评测记录

更新时间：2026-05-10

## 结论

`greedy_risk` 已实现并通过单元测试，但当前参数未通过阶段 4.2 强度门槛。

当前默认参数：

```text
expected_risk_weight = 1.0
expected_win_risk_weight = 500.0
```

## 200 局固定 seed 结果

| 对局 | 局数 | candidate 胜率 | illegal | crashes | timeouts | 报告 |
|---|---:|---:|---:|---:|---:|---|
| 红 `greedy_risk` vs 蓝 `greedy` | 200 | 58.0% | 0 | 0 | 0 | `reports/bench_phase_4_2_greedy_risk_vs_greedy.json` |
| 红 `greedy` vs 蓝 `greedy_risk` | 200 | 51.5% | 0 | 0 | 0 | `reports/bench_phase_4_2_greedy_vs_greedy_risk.json` |

按双边合并计，candidate 为 219/400 = 54.75%，低于 55% 门槛；蓝方单边也低于 55%。

## 已验证能力

- 枚举对手下一轮骰子 1-6。
- 通过 `GameState.legal_moves()` 复用 core 的骰子选子和合法走法规则。
- 估算己方棋子被吃概率。
- 估算对手下一轮直接到目标角获胜概率。
- `greedy_risk` 永远只输出合法走法；当前评测 illegal/crash/timeout 均为 0。

## 初步诊断

单纯按“总被吃概率”扣分对 1-ply greedy 的帮助有限。权重过大时 AI 明显过度保守，牺牲推进节奏；权重降到 0.5-2.0 后稳定性较好，但胜率只接近门槛。下一步不应继续盲调单一权重，应引入更细的风险结构，例如边缘安全、关键子价值或对“冲线子”的动态权重。

## 下一步

不进入 4.3 之前，建议先做一个小的 4.2b：

1. 将 capture risk 按棋子到目标角距离加权，只重罚关键推进子暴露。
2. 对“对方一步冲线”保留高权重硬惩罚。
3. 重新跑同 seed 双边 200 局；只有双边合并或单边门槛达标后，再把 `greedy_risk` 作为 GUI 默认推荐候选。
