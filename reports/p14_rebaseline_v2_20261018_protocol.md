# P14 修正规则基线评测协议

制定日期：2026-10-18。状态：正式结果生成前冻结的方法；结果另存报告，不能用本文件当作已完成证据。

## 目的与对照

用户选择：在 `einstein-nearest-sides-v2` 规则下，对比当前 P14 与历史 P14 晋升时使用的旧版 Rollout 参数。双方都调用当前 core，不运行旧错误规则，不变更 GUI/release 默认参数。

| 参数 | P14 | 历史参数对照 |
|---|---|---|
| kind | `rollout` | `rollout` |
| rollouts_per_move | 64 | 32 |
| max_rollout_turns | 80 | 80 |
| max_step_time_ms | 2000 | 750 |
| epsilon | 0.05 | 0.1 |
| close_sample_margin | 0.08 | 0.08 |
| close_sample_rollouts_per_move | 96 | 32 |
| low_confidence_margin | 0.08 | 0.08 |
| playout_policy | `greedy_risk` | `greedy_risk` |
| cutoff_eval | `zweistein` | `zweistein` |
| deadline_safety_ms | 80 | 30 |

P14 由 `ai.release_defaults.RELEASE_DEFAULT_ROLLOUT_KWARGS` 显式构造，并核对 release 参数；对照来源为 `reports/p14_candidate_rollout_strong_64_loweps_confirm_20260518.json`。本轮预算不同，结论仅针对这两套完整配置，不能归因于算法本身，也不能当作同预算比较。历史报告的胜率不与本轮合并。

## 固定样本与执行

- 正式样本：100 对、200 局。`i = 0..99`，`pair_seed = 2026101800000 + i`。
- `dice_seed = pair_seed * 3`，`p14_seed = pair_seed * 3 + 1`，`legacy_seed = pair_seed * 3 + 2`。
- 每对两局：P14 红/对照蓝、对照红/P14 蓝。每局重建 AI 与骰子 RNG，算法 RNG seed 随算法身份换色，不随颜色换。
- 偶数 pair 先跑 P14 红，奇数 pair 先跑 P14 蓝；同一 pair 的两局相邻。单进程串行，不同时跑其他本任务的搜索或 pytest。
- 固定 `balanced_v1`，红方先行，`max_turns=200`。换色同时交换算法的先后手角色，不单独改变规则起始方或声称模拟七盘制。
- 两局复用骰子按半步编号的相同随机序列前缀；局面和终局长度可以不同，不称为相同棋局。
- 先用独立的 `pair_start=1000, pairs=1` 完成两局 smoke；这两局不进入正式 200 局。若发现非法步、崩溃或证据保存失败，先排查再启动正式批次。
- 正式批次不因中途胜率扩样、删局或更改配置。异常结果保留并报告；若需要修改实现，结束当前批次并使用新目录重新冻结协议，不混用前后源码。

## 数据与溯源

原始产物写到 `E:\computergame-data\benchmarks\` 下新的独立目录。仓库仅保留协议、小型汇总、分析报告和可复现脚本。

manifest 固定规则、配置、种子、调度、签名、Python/机器环境、HEAD 与 dirty 状态，并记录实际源码 SHA-256 与源码快照。当前工作区包含上一轮已验证但未提交的规则修正，因此仅记 Git HEAD 不足以复现。

逐局保存完整 GameRecord、骰子与走法、终止原因、真实逐步耗时、非法步/崩溃/时间越限，以及逐步内部 deadline、回退、已完成采样量。结果写入后不覆盖；只有显式 resume 且 manifest 与已存结果一致才能跳过完整对局。运行结束核对源码哈希和样本完整性。

## 统计方法与判读

主指标为 P14 胜局/全部局数，分别报告执红、执蓝与合并结果。截断局单列，不能称为正式棋规和棋。出现错误终止时同时提供数量，不把错误造成的判胜当成正常棋力证据。

同 seed 两局存在配对关系，因此主 95% 区间以 **100 个完整 pair** 为重采样单位：每对取两局胜率均值，固定 bootstrap seed `20261018`，有放回重采样 50,000 次，取 2.5%/97.5% 百分位。列出每对 P14 获胜 0/1/2 局的分布。若另列 200 局 Wilson 区间，只作未处理配对相关性的描述性参考。

耗时按算法分开汇总平均值、分位数、最大步时和每局累计思考时间。`harness timeouts` 指真实 `elapsed_ms > max_step_time_ms`，现有 harness 仅记录、不自动判负；内部 `last_timed_out` 是搜索在安全截止附近停止采样；`last_used_fallback` 才用于逐步回退统计，不能把累计 `fallback_count` 混称为真实 greedy 回退。

默认限时保留，固定 seed 不保证不同负载下完成相同采样数量或产生逐步相同轨迹。实际棋谱与采样量才是本轮观测证据。累计 AI 思考时间不包含现场人工录入、操作和裁判等待，不能单独证明整盘 4 分钟验收。

本轮不自动晋升、调参或推断 Elo。报告完成后依据结果确定下一项同预算搜索比较，默认参数保持原样。
