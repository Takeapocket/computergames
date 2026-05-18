# AI / Opening Experiment Stop List

更新时间：2026-05-18

## 结论

赛前默认配置保持不变：

- 默认 AI：`rollout` kind + P3 promotion 显式参数。
- fallback AI：`greedy_risk`，再 fallback 到第一条合法步。
- 默认布局：`balanced_v1`。

本表用于防止重复被小样本正信号诱导。除非出现新的、可验证的技术假设，并且先写清楚门禁，否则下列路线不再消耗赛前时间。

## 不晋升总表

| 路线 / 候选 | 最新有效样本 | 结果 | 稳定性 | 决策 | 证据 |
|---|---:|---:|---|---|---|
| `curated_003` opening layout | 24g | 12/24 = 50.0%，CI95 [31.4%, 68.6%] | illegal=0, crashes=0, timeouts=0 | 不晋升；24 局 seed-pool probe 不是晋升证据 | `reports/opening_duel_curated_003_24g_20260518.md` |
| `curated_008` opening layout | 8g | 4/8 = 50.0%，CI95 [21.5%, 78.5%] | illegal=0, crashes=0, timeouts=0 | 不晋升；8 局扩展样本太小且无优势 | `reports/opening_duel_curated_008_8g_20260518.md` |
| P5.5 best balanced opening route | 60g | 23/60 = 38.3%，CI95 [27.1%, 51.0%] | illegal=0, crashes=0, timeouts=0 | 停止该布局晋升路线；`balanced_v1` 不变 | `reports/p55_opening_duel_best_balanced_60g_20260516.md` |
| `rollout_root_racing` | 50g | 20/50 = 40.0%，CI95 [27.6%, 53.8%] | illegal=0, crashes=0, timeouts=0 | candidate FAIL；不晋升，不扩样 | `reports/p10_candidate_rollout_root_racing_20260518.md` |
| P7.2 `rollout_adaptive_close_sample` | 200g | 100/200 = 50.0%，CI95 [43.1%, 56.9%] | illegal=0, crashes=0, timeouts=0 | candidate FAIL；不进入默认 | `reports/p72_candidate_rollout_adaptive_close_sample_20260516.md` |
| MCTS P4 `mcts_eval_v1` | 50g + 20g | 两组均为 30.0% | illegal=0, crashes=0, timeouts=0 | P4 FAIL；不进入正式 candidate / promotion | `reports/p4_candidate_probe_summary_20260516.md` |
| MCTS P4.1 `mcts_eval_v1(leaf_evaluator="zweistein")` | 20g | 5/20 = 25.0%，CI95 [11.2%, 46.9%] | illegal=0, crashes=0, timeouts=0 | P4.1 FAIL；按停止线停止 MCTS | `reports/p41_targeted_fix_summary_20260516.md` |
| P8 `rollout_threat_rerank` | audit 361 positions | low-confidence threat-reducing ratio = 0.005 | 审计稳定，无实现候选 | gate 不支持实现；不启动 rerank candidate | `reports/p8_threat_defense_audit_20260517.md` |
| P9.1 `rollout_zweistein_dp_cutoff` | 200g | 90/200 = 45.0%，CI95 [38.3%, 51.9%] | illegal=0, crashes=0, timeouts=0 | candidate FAIL；不晋升 | `reports/p9_candidate_rollout_zweistein_dp_cutoff_20260517.md` |
| P9.2 `rollout_exact_opp1_zdp` | 200g | 103/200 = 51.5%，CI95 [44.6%, 58.3%] | illegal=0, crashes=0, timeouts=0 | candidate FAIL；低于 P9.3 启动线 52%，不启动 TT / move ordering | `reports/p9_candidate_rollout_exact_opp1_zdp_20260517.md` |
| Expectimax depth=1 | 400g | 180/400 = 45.0% | illegal=0, crashes=0 | 失败；保留为研究代码，不作为参赛默认 AI | `reports/4-4-rebench.md` |

## 小样本警戒

以下信号不能单独触发默认配置变更：

- `opening_light_screen` 中的 2/2、5/8、6/8 等轻量筛选结果。
- 单个 seed 或单方向的红/蓝优势。
- 低于 50 局的布局 duel 正信号。
- 胜率过线但存在 timeout 的候选。
- 未直接对当前 release 默认 `rollout` 显式 kwargs 对战的旧报告。

## 重新打开条件

赛前原则上不重新打开上述路线。若比赛后继续研究，至少满足：

1. 先写清楚新的技术假设，不能只是“再试一次”。
2. candidate 必须直接对当前 release 默认 `rollout` 显式 kwargs。
3. 必须红蓝双边，记录 seed、games、Wilson CI、illegal、crashes、真实 timeouts、avg/max step ms。
4. 默认变更必须先过当前阶段门禁，并同步 `PROJECT_MEMORY.md`、`PROJECT_PHASES.md`、`release/v1.0/default_params.json` 或布局 preset。
