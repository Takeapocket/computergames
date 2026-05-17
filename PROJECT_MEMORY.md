# 爱恩斯坦棋参赛程序项目记忆

更新时间：2026-05-17（R-4 GUI 程序掷骰与一键启动器后同步）

## 当前结论

- 目标比赛：2026 年辽宁省大学生计算机博弈大赛校内选拔赛，项目选择为"爱恩斯坦棋"。
- 目标不是做命令行工具，而是构建一个离线可运行的 GUI 程序，用于现场比赛。
- 当前最稳假设：现场不依赖统一 API，不联网；双方各自运行自己的程序，骰子来源按双方协商或裁判要求确定，操作员录入骰子/对方走法，并根据程序输出执行本方走法。若后续 QQ 群发布统一平台/API，再新增适配层，不改核心规则引擎和 AI。
- 爱恩斯坦棋有骰子随机性，但程序仍可通过开局布阵、局面评估、期望搜索、蒙特卡洛模拟等方法显著提升胜率。
- **2026-05-11 R-0 已完成**：core 现已合规允许吃本方棋子；4.1 / 4.2 / 4.4 bench 已用合规规则重跑（slim 格式入库），全部门槛通过。详见 `reports/4-1-rebench.md` / `reports/4-2-rebench.md` / `reports/4-4-rebench.md`。
- **2026-05-11 R-1 / R-2 / R-3 已完成**：开局录入 GUI（R-1）+ 七盘制比赛模式（R-2）+ 崩溃自救（R-3）均已实现并通过 324 条 pytest（含 80 条 R-2 新增）。R-2 详见 `reports/r2-rehearsal.md`；R-1 review followup 决策见 `reports/r1-review-followup.md`。
- **2026-05-13 S2 完整闭环**：操作员现场用真实 Tk GUI 跑完 `reports/gui-rehearsal.md` §4 全部 21 个手测步骤（4.1 启动到 4:0 / 4.2 4:3 决胜 / 4.3 盘内崩溃恢复 / 4.4 盘间崩溃恢复 / 4.5 误操作恢复 / 4.6 整轮结束后操作），全部"正常"。S2 自此不再是"部分完成"，整个 final-sprint 完成定义（plan §9）全部满足，进入 release/v1.0 sign-off 与归档阶段。
- **2026-05-12 S2 headless 自动演练已完成**：`scripts/s2_rehearsal.py` 8 个 scenario 全 PASS（4:0 / 4:3 / 先手序列 / 超时判负 / 盘间恢复 / 盘中恢复 / 悔棋边界 / 整轮结束后行为）；落地 `docs/MATCH_CHECKLIST.md` 现场操作清单 + `docs/EMERGENCY_GUIDE.md` 应急手册；当日全量 pytest 已通过。详见 `reports/gui-rehearsal.md`。最新全量验证见 2026-05-15 Tk fixture follow-up 记录：495 passed in 11.68s。
- **历史记录（2026-05-13，当日快照，非最新验证）**：收官冲刺 Task Group 01-02 + 04 已完成。S3（AI 低风险清理 + harness 工程化）落地 `scripts/quick_bench.py` Wilson CI、新增 `scripts/tournament.py` pairwise matrix、清理 R-0 followup `stuck_penalty` 准死代码（grep 无残留）；S4（封版）落地 `release/v1.0/` 全套文档（README + config + default_params + known_limitations + test_report）。AI / 开局候选流水线（`scripts/param_sweep.py` / `scripts/search_openings.py` / `ai/self_capture.py`）已建立。Review 后 codex 已修复 `param_sweep.py` 双边对战门禁 + `search_openings.py` 训练/验证对手对齐与 AI 对称化，并补回归测试。当日复验：371 pytest passed、smoke OK、s2_rehearsal 8/8 PASS、AI baseline 双向 200 局 `greedy_risk` 合并胜率 55.75%（CI 通过）、max_step 6.84ms。随后 `rollout` 以双边 800 局对 `greedy_risk` 合并胜率 62.62%、Wilson lower 59.22% 晋升为 GUI/release 默认 AI；`greedy_risk` 保留为应急回退。决策详见 `reports/ai_promotion_decision.md` 与 `release/v1.0/test_report.md`。**最新验证与 adaptive/timeout 结论以 2026-05-15 条目和 `release/v1.0/test_report.md` 为准。**
- **2026-05-15 code review follow-up 已完成**：修复 adaptive rollout 误写默认参数的问题。当时 GUI/release 默认 AI 仍是 `rollout`，且默认参数保持旧 flat 形态：`rollouts_per_move=16`、`max_rollout_turns=80`、`max_step_time_ms=500.0`、`epsilon=0.15`。该结论已被 2026-05-16 P3 受控默认替换 supersede；当前默认参数以 `gui/main_window.py` 与 `release/v1.0/default_params.json` 为准。adaptive rollout（32 初采样、close sample 到 128、低置信提示）仅作为显式实验候选保留；其 direct vs old rollout 800 局合并胜率 59.00%，未达 60% 默认晋升线，不进入 release/v1.0 默认参数。`RolloutAI` 诊断现区分 `score / winrate / cutoffs / avg`；`quick_bench.py` / `bench_ai.py` 已开始聚合真实 `timeouts`，历史报告中的 legacy timeout 字段不可单独作为晋升证据。最近一次全量验证见 `release/v1.0/test_report.md`。
- **2026-05-15 P1 Rollout 根节点诊断收敛已完成**：新增 canonical `RootMoveStats` 与 `RolloutAI.last_root_stats`，`last_diagnostics` 保持兼容别名；GUI 推荐区优先读取 root stats，候选明细显示 visits、score、winrate、wins、losses、draws、avg 与低置信标记。默认 `rollout` 参数、`release/v1.0/default_params.json` 和 core 规则均未变更。验证：`scripts/smoke_test.py` 正常退出；全量 `pytest` 为 `496 passed in 11.29s`。
- **2026-05-15 P2 rollout 候选小样本已完成**：新增 benchable AI kind：`rollout_32`、`rollout_risk_playout`、`rollout_cutoff_eval`；`RolloutAI` 支持 `playout_policy=greedy|greedy_risk` 与 `cutoff_eval=draw|current`，`ai_version_signature()` 和 `scripts/bench_ai.py` profile 已记录相关元数据。默认 `rollout`、GUI 默认推荐、`release/v1.0/default_params.json` 和 core 规则均未变更。三组 candidate vs 当前默认 `rollout` 双边各 100 局均未过门禁：`rollout_32` 54.5% 且 timeouts=4；`rollout_risk_playout` 57.0% 但 timeouts=10；`rollout_cutoff_eval` 57.5% 但 timeouts=11。报告见 `reports/p2_candidate_rollout_32_20260515.*`、`reports/p2_candidate_rollout_risk_playout_20260515.*`、`reports/p2_candidate_rollout_cutoff_eval_20260515.*`。实现验证：`pytest` 为 `501 passed in 10.16s`，`scripts/smoke_test.py` 正常退出。
- **2026-05-15 P2.5 rollout deadline safety 已完成**：`RolloutAI` 新增 `deadline_safety_ms`，默认 `0.0`，内部 playout deadline 使用 `max_step_time_ms - deadline_safety_ms`；`ai_version_signature()` 记录该字段；`bench_ai.py` 仅给 `rollout_risk_playout` / `rollout_cutoff_eval` 的 candidate/promotion profile 显式传 `deadline_safety_ms=30.0`，未复验 `rollout_32`。P2.5 正式复验仅跑两个正向候选，各双边 100+100、对手 `rollout`：`rollout_risk_playout` 合并胜率 58.5%，但总 `timeouts=1`，未过总门禁；`rollout_cutoff_eval` 合并胜率 57.0%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，标记为 **P2.5 survives**。报告见 `reports/p25_candidate_rollout_risk_playout_20260515.*` 与 `reports/p25_candidate_rollout_cutoff_eval_20260515.*`。默认 `rollout`、GUI 默认推荐、`release/v1.0/default_params.json` 和 core 规则均未变更。
- **2026-05-15 P3 Zweistein-lite 已完成基础实现与 candidate 小样本**：新增 `ai/zweistein.py` 的 `zweistein_lite_score()`，特征包括终局、推进、子力、期望机动性、被吃风险和直接到角风险；新增 `greedy_zweistein`、`rollout_zweistein_cutoff`、`expectimax_zweistein_d1` 三个实验 kind。`RolloutAI.cutoff_eval` 支持 `zweistein`；`ExpectimaxAI` 支持 `leaf_evaluator=current|zweistein`；`ai_version_signature()` 记录 `leaf_evaluator`；`bench_ai.py` 为 `rollout_zweistein_cutoff` candidate/promotion profile 注入 `deadline_safety_ms=30.0`。P3 小样本：`rollout_zweistein_cutoff` vs `rollout` 双边 100+100，合并胜率 58.0%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，candidate 门禁通过。报告见 `reports/p3_candidate_rollout_zweistein_cutoff_20260515.*`。该 candidate 结论已被后续 promotion 和 2026-05-16 默认替换决策 supersede。
- **2026-05-15 P3 promotion 已通过**：按用户要求未进入 P4，先用 `scripts/bench_ai.py --candidate rollout_zweistein_cutoff --stage promotion --report-name p3_promotion_rollout_zweistein_cutoff_20260515` 复验。对手保持 old flat `rollout`，双边 400+400，结果：800 局、454 胜、合并胜率 56.75%，Wilson lower 53.29%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，平均步时 175.75ms，最大步时 720.69ms，promotion 门禁通过。报告见 `reports/p3_promotion_rollout_zweistein_cutoff_20260515.json` / `.md`；该 promotion 已在 2026-05-16 转为正式默认替换 decision。
- **2026-05-16 P3 受控默认替换已完成**：用户明确批准将 P3 promotion 已通过的 `rollout_zweistein_cutoff` 提升为 GUI/release 工作默认 AI。实现上保持 `DEFAULT_RECOMMENDER_KIND = "rollout"`，并从 `reports/p3_promotion_rollout_zweistein_cutoff_20260515.json` 的 `ai_versions.candidate` 复制完整参数到 `DEFAULT_RECOMMENDER_KWARGS` 和 `release/v1.0/default_params.json`：32 rollout / move、80 half-turn cutoff、750ms step deadline、epsilon 0.10、close sample 32、playout_policy=`greedy_risk`、cutoff_eval=`zweistein`、deadline_safety_ms=30.0。`release/v1.0/test_report.md` 已追加 P3 promotion 结果和替换说明，`reports/ai_promotion_decision.md` 已改为正式 decision。`greedy_risk` 仍是应急回退；未进入 P4，未改 MCTS，未额外调参。
- **2026-05-16 P4 entry guard 已完成**：只修复 / 验证 MCTS opponent DecisionNode 语义，不跑大样本。`MCTSAI` 在 root-player 决策节点继续最大化 root 价值，在 opponent 决策节点改为最小化 root 价值；回传仍统一为 root-player 视角。`scripts/bench_ai.py` 现在从 `release/v1.0/default_params.json` 读取当前 release 默认 rollout kwargs，并给 `mcts_eval_v1` candidate/promotion profile 注入这些 opponent kwargs；P4 candidate/promotion 不允许用裸 `opponent="rollout"` 作为晋升基线。`quick_bench.py` 已用显式 `--blue-kwargs` 做 1 局入口验证。报告见 `reports/p4_entry_guard_20260516.md` / `.json`。未修改 GUI、`release/v1.0/default_params.json` 或 `release/v1.0/config.json`。
- **2026-05-16 P4 MCTS candidate probe 已完成，未晋升**：按 P4 guard 后约束，候选只对当前 release 默认 rollout kwargs 评测。`mcts_eval_v1(time_limit_ms=200)` 双边 25+25：合并胜率 30.0%，Wilson CI [19.1%, 43.8%]，0 illegal/crash/timeout，avg 214.5ms，max 720.4ms；默认 `mcts_eval_v1(time_limit_ms=500)` 双边 10+10：合并胜率 30.0%，Wilson CI [14.5%, 51.9%]，0 illegal/crash/timeout，avg 351.4ms，max 719.7ms。两组均因胜率远低于 55% candidate 门禁失败，不扩大到 200+200，不进入 promotion discussion。报告见 `reports/p4_candidate_probe_summary_20260516.md` / `.json` 及两份 bench 自动报告。
- **2026-05-16 P4.1 targeted fix 已完成，停止 MCTS 转 P5**：新增最小真实局面测试，证明 opponent DecisionNode 会选择对 `root_player` 最差的应手；`MCTSAI` 新增 `leaf_evaluator=current|zweistein`，默认仍为 `current`，显式 `zweistein` 会走 `zweistein_lite_score()` 且签名记录 `leaf_evaluator`。P4.1 小样本 probe：`mcts_eval_v1(leaf_evaluator=zweistein)` vs 当前 release 默认 rollout kwargs，双边 10+10，合并胜率 25.0%，Wilson CI [11.2%, 46.9%]，0 illegal/crash/timeout，avg 348.9ms，max 720.2ms。因胜率 <45%，按用户规则停止 MCTS，不进入扩样或 promotion，下一步转 P5。报告见 `reports/p41_targeted_fix_summary_20260516.md` / `.json`。
- **2026-05-16 P5.0 opening-search entry guard 已完成，未晋升布局**：`scripts/search_openings.py` 主评测入口已从旧 `greedy_risk` self-play 改为读取 `release/v1.0/default_params.json`，使用当前 release 默认 `kind="rollout"` + P3 promotion 显式 kwargs 作为双方 AI；stats 聚合新增真实 `timeouts`。小样本 smoke 仅跑 `sample_size=5`、train/validation 每 opponent 各 2 局，生成 `reports/p5_opening_entry_guard_20260516.md` / `.json`。结果只证明 P5 harness 入口正确：validation top 两个红方布局分别为 5/8 和 6/8，0 illegal/crash/timeout；样本远小于晋升门禁，未改 GUI 默认布局、未改 release 默认布局。
- **2026-05-16 P5.1 opening strata + seed pool 已完成，未晋升布局**：`scripts/search_openings.py` 新增 `candidate_mode=sample|stratified`、`per_style`、`seed_pool`、`json_output`；stratified 模式按 aggressive / balanced / defensive 三类各取固定数量候选，seed pool 聚合跨 seed 对战 stats，并在报告中记录 `style`、`seed_count`、`seeds`、`train_rows`、`decision` 和真实 `timeouts`。P5.1 smoke：`candidate_mode=stratified --per-style 1 --games 1 --validation-games 1 --top-k 3 --seed-pool 2026,2027`，三类各 1 个候选，validation 结果为 aggressive 1/8、defensive 4/8、balanced 2/8，0 illegal/crash/timeout。报告见 `reports/p51_opening_strata_seed_smoke_20260516.md` / `.json`。该样本只验证分层和 seed 池流程，未改 GUI/release 默认布局。
- **2026-05-16 P5.2 opening small-scale gate 已完成，未晋升布局**：复用 P5.1 分层与 seed pool 流程，执行 `--candidate-mode stratified --per-style 2 --games 1 --validation-games 1 --top-k 3 --seed-pool 2026,2027`，共 6 个候选、train top 从 5/8 到 2/8，validation top3 分别为 3/8、4/8、4/8，`illegal_moves=0`、`crashes=0`、`timeouts=0`。报告见 `reports/p52_opening_small_scale_gate_20260516.md` / `.json`。该样本只证明扩大 smoke gate 仍可稳定运行，未达到晋升样本量或胜率门槛，未改 GUI/release 默认布局。
- **2026-05-16 P5.3 opening seed3 validation2 gate 已完成，未晋升布局**：在 P5.2 基础上把 seed 池扩到 2026/2027/2028，并把 validation games 提高到每 opponent 2 局：`--candidate-mode stratified --per-style 2 --games 1 --validation-games 2 --top-k 3 --seed-pool 2026,2027,2028`。共 6 个候选，train top3 均为 6/12；validation top3 为 10/24、10/24、11/24，`illegal_moves=0`、`crashes=0`、`timeouts=0`。报告见 `reports/p53_opening_seed3_validation2_20260516.md` / `.json`。结果显示当前分层候选没有表现出默认布局晋升信号，GUI/release 默认布局不变。
- **2026-05-16 P5.4 opening layout duel precheck 已完成，未晋升布局**：新增 `scripts/compare_opening_layouts.py`，用于把搜索候选直接对当前默认布局 `balanced_v1` 做红蓝双边小样本前置验证。取 P5.3 validation 表现最好的 balanced 候选（`validation_top[2]`，red=`1:00/2:10/3:11/4:20/5:02/6:01`），执行 `--games-per-side 4 --seed-pool 22026,22027,22028`，合并 14/24 = 58.3%，Wilson CI [38.8%, 75.5%]；candidate as red 9/12，candidate as blue 5/12，`illegal_moves=0`、`crashes=0`、`timeouts=0`。报告见 `reports/p54_opening_duel_best_balanced_20260516.md` / `.json`。这是前置正信号，但样本远小于晋升门槛且 CI 下界不足，GUI/release 默认布局不变。
- **2026-05-16 P5.5 opening duel 60-game expansion 已完成，停止该候选晋升路线**：复用 P5.4 同一 balanced 候选，扩到 `--games-per-side 10 --seed-pool 23026,23027,23028`，直接对当前默认 `balanced_v1` 做 60 局双边复验。结果合并 23/60 = 38.3%，Wilson CI [27.1%, 51.0%]；candidate as red 13/30，candidate as blue 10/30，`illegal_moves=0`、`crashes=0`、`timeouts=0`。报告见 `reports/p55_opening_duel_best_balanced_60g_20260516.md` / `.json`。P5.4 小样本正信号未能复现，该候选不进入正式晋升门禁，GUI/release 默认布局不变。
- **2026-05-17 P6 robustness lock 已完成**：新增 `tests/test_release_consistency.py` 锁定 GUI/release 默认 AI、fallback 与 `balanced_v1` 默认布局；新增 `scripts/preflight_check.py`，成功时输出 `READY FOR MATCH`。GUI 推荐兜底链已固定为 current default rollout -> `greedy_risk` -> 第一条合法步 -> 无合法步，并在推荐文本区标出来源。损坏 `auto_save.json` / `auto_save_match.json` 启动时会自动清理，不再阻塞 GUI。`scripts/timing_budget_probe.py` 120 样本结果：`illegal_recommendations=0`、`exceptions=0`、`p99_ms≈641`、`max_ms≈720`，1 个 timeout/fallback 样本已列入报告。报告见 `reports/p6_timing_budget_probe_20260516.md` / `.json`。release 默认 AI、默认布局和 core 规则未变。
- **2026-05-17 P7 rollout failure analysis 已完成，候选未晋升**：新增 `scripts/analyze_rollout_failures.py`。P7.0 对当前 release 默认 rollout vs `greedy_risk` 跑 120 局：87 胜 / 33 负，`illegal_moves=0`、`crashes=0`、`timeouts=0`；失败桶为 `missed_direct_win=0`、`allowed_direct_loss=63`、`low_confidence_loss=145`、`timeout_or_fallback=4`、`bad_self_capture=33`。因此 P7.1 direct-win guard 不成立；P7.2 `rollout_adaptive_close_sample` 作为显式实验候选注册并在 `balanced_v1` 布局 bench，双边 100+100 合并胜率 50.0%，未达 55% candidate 门槛，不进入默认。报告见 `reports/p7_rollout_failure_analysis_20260516.*` 与 `reports/p72_candidate_rollout_adaptive_close_sample_20260516.*`。最新验证：576 pytest passed、smoke OK、S2 rehearsal 8/8 PASS、preflight 输出 `READY FOR MATCH`。
- **2026-05-17 P8 threat defense audit 已完成**：新增 `scripts/analyze_threat_defense.py`，对当前 release 默认 `rollout` + P3 参数在 `balanced_v1` 下审计 chosen move 与 alternatives 的 `opponent_winning_dice_set`。审计结果：`audited_positions=307`、`chosen_allowed_direct_loss_positions=59`、`threat_reducing_alternative_positions=5`、`low_confidence.threat_reducing_ratio=0.0120`、`self_capture allowed-direct-loss rate=0.0167`。报告见 `reports/p8_threat_defense_audit_20260517.md` / `.json`。默认 AI、默认布局、core 规则和 release 配置未变。`rollout_threat_rerank` 未实现，因为审计 gate 不支持：低置信 threat-reducing ratio 0.012 < 0.250，低置信 top-k 命中 ratio 0.500 < 0.600；未过门禁不得晋升。最新验证：590 pytest passed、smoke OK、S2 rehearsal 8/8 PASS、preflight 输出 `READY FOR MATCH`。
- **2026-05-17 P9 Zweistein-DP chance-aware evaluation 已完成，候选未晋升**：P9.0 已实现 `ai/zweistein_dp.py` 概率估值表并通过测试；DP 表尺寸为 `15625 x 20`，`PDF_VAL` / `CDF_VAL` 均为 15625 行。P9.1 `rollout_zweistein_dp_cutoff` 已作为显式候选评测，双边 100+100 合并胜率 45.0%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，但未过 55% candidate 门槛；P9.2 `rollout_exact_opp1_zdp` 已作为显式候选评测，双边 100+100 合并胜率 51.5%，`illegal_moves=0`、`crashes=0`、`timeouts=0`，但未过 55% candidate 门槛，且低于 P9.3 TT / move ordering 启动线 52%，因此 P9.3 不启动。全量验证通过，`scripts/preflight_check.py` 输出 `READY FOR MATCH`。GUI/release 默认 AI、默认布局、core 规则均未变。
- **2026-05-17 R-4 GUI 程序掷骰已完成**：新增 `core/dice.py::roll_die()`，使用 `secrets.randbelow(6) + 1` 作为程序掷骰来源；GUI 在骰子 Spinbox 右侧新增"程序掷骰"按钮。按钮只在 playing 且等待骰子时启用，掷完立即禁用，执行走法进入下一轮后再启用；手动输入骰子仍保留。代码审查 follow-up 已修复 Spinbox `FocusOut` 与程序掷骰按钮点击的事件顺序边界，且禁用按钮不会吞掉手动改错提交。默认 AI、默认布局、core 规则语义和 release 配置均未变。验证：688 pytest passed、smoke OK、S2 rehearsal 8/8 PASS、preflight 输出 `READY FOR MATCH`。
- **2026-05-17 现场一键启动器已完成**：新增根目录 `启动项目.cmd` 和 `scripts/launcher.py`。双击可打开菜单，支持启动 GUI、一键赛前总检查、完整 pytest、smoke、S2 rehearsal、timing probe 和 release/default 状态显示；`scripts/launcher.py` 支持 `--list`、`--dry-run`、`--run` 非交互入口并有 `tests/test_launcher.py` 覆盖；`scripts/preflight_check.py` 已把启动器文件纳入必备文件检查；`.gitattributes` 固定 `启动项目.cmd` 为 CRLF，避免 Windows `cmd.exe` 解析异常。默认 AI、默认布局、core 规则语义和 release 配置均未变。最新验证：699 pytest passed；启动器 `--list` / `--dry-run 4` / `--run status` 均正常。

## 已确认的比赛事实

### 校内选拔赛
- 校内通知文件：`C:/Users/Takeapocket/Desktop/documents/computergames/通知 _ 关于举办 2026 年辽宁省大学生计算机博弈大赛校内选拔赛的通知.html`
- 本校报名截止时间：2026 年 5 月 18 日。
- 队伍组成：1-3 名学生及 1-2 名指导教师。
- 校赛结束后，每个棋牌类项目最终推荐 2 项参加省级决赛。
- 程序要求：参赛队使用各自研发的计算机博弈程序对弈，不限制编程软件。

### 国赛规则（2026-05-10 通过 `全国计算机博弈竞赛总则.md` + `爱恩斯坦棋项目规则.md` 确认）
- **棋盘**：5×5；红方左上出发区，蓝方右下出发区。
- **棋子**：双方各 6 子，编号 1-6。
- **骰子来源**：由双方协商或裁判要求确定；本程序支持 GUI 内"程序掷骰"和手动录入外部骰子结果。
- **开局**：可任意摆放（**无组委会强制布局**）。
- **走法**：红向下/右/右下，蓝向上/左/左上，每次一格。
- **吃子**：目标格有棋子（**含本方**）则吃掉；吃本方子是合法策略。✅ R-0 已修复 core 实现。
- **骰子映射**：骰子 d 对应棋子已死时，可走最近编号棋子（双向并列时两个都可选）。
- **胜负**：到达对方出发区角点 OR 吃光对方棋子 = 胜；**只有胜负，没有和棋**。
- **单方时限**：每盘每方 4 分钟包干，超时判负。
- **轮制**：每轮 7 盘，先胜 4 盘为胜方；甲方一四五盘先手，乙方二三六七盘先手；两盘中间不休息。
- **决赛加赛**：积分相等 → 胜负关系 → 10 分钟包干快棋两盘 → 抽签/掷骰只比一局。
- **崩盘**：程序崩溃 = 该方判负。
- **联网**：比赛中禁止任何有线/无线联网（桥牌项目例外）。
- **统一平台**：可申请使用，**不强制**；项目按"无统一平台"假设开发。
- **山寨程序检查**：参赛队需提交程序设计文档与源码，可被现场专家组质询。

### 操作规则（总则）
- 比赛过程中每方仅允许一名队员执行裁判允许的操作，不允许超时、修改程序或介入程序运行。
- 两场比赛间隙可修改或调整程序与参数，但不能更换计算机设备，除非得到裁判许可。
- 双方电脑屏幕摆放须有利于对方观察；双方有义务告知对方本方电脑产生的棋步。

## GUI 程序必须支持

- 离线运行，不依赖网络。
- 可视化 5×5 爱恩斯坦棋棋盘。
- 可手动录入当前轮骰子点数；双方同意时可由 GUI 点击"程序掷骰"生成点数。
- 可录入对方走法。
- 可输出我方建议走法，并明确显示移动棋子、起点、终点、是否吃子。
- 自动判断胜负。
- 计时功能：单方总时间 + 每步耗时统计（已实现 4 分钟包干）。
- 棋谱保存：JSON 格式（已实现）；后续如有组委会规范再适配。
- 悔棋/恢复局面（已实现）。
- 比赛模式：合法步校验、当前轮状态提示、当前推荐走法（已实现）。
- 7 盘制比赛流程（R-2 已实现）。开局录入 GUI（R-1）与崩溃自救（R-3）已实现。S2 headless 自动演练 + 真实 Tk GUI 手动表（21/21 正常）均已完成，S2 完整闭环。

## 工程约束

- 每次只做一小步，先实现可验证的最小功能，再迭代优化。
- 不凭空假设比赛平台/API；所有现场规则差异都先记录为假设，等 QQ 群或老师发布附件后再适配。
- 先做规则引擎和验证 harness，再做复杂 AI。
- 每个核心规则都要有自动测试：合法步、吃子（含本方子）、到达终点、全灭胜负、骰子对应棋子选择、悔棋恢复。
- AI 优化必须用本地对战 harness 验证：旧版本 vs 新版本、随机 AI vs 当前 AI、固定局面回归测试。
- 不优先做深度学习训练。首版 AI 采用规则评估 + 搜索/模拟，保证稳定、可解释、可答辩。
- 代码结构遵循 KISS、YAGNI、DRY、SOLID：规则引擎、AI、GUI、棋谱、平台适配分层，不把逻辑写死在界面里。

## 建议初始架构

- `core/`：棋盘状态、规则、合法步、胜负判断、走子/撤销、序列化。
- `ai/`：随机 AI、贪心 AI、期望搜索或蒙特卡洛 AI。
- `gui/`：离线 GUI，负责展示棋盘、录入骰子和走法、显示建议。
- `record/`：棋谱记录、保存、加载、导出。
- `tests/`：规则测试和 AI 对战 harness。
- `adapters/`：预留统一平台/API 适配层，只有确认平台协议后再实现。

## 下一次对话建议第一步

1. 先读取本文件 + `PROJECT_PHASES.md` "赛事规则对齐补丁"章节。
2. R-0 / R-1 / R-2 / R-3 / R-4 / S2 / S3 / S4 / P6 / P7 / P8 / P9 全部闭环；当前 GUI/release 默认仍是 `rollout` kind + P3 promotion 参数，不是旧 flat rollout。
3. P7.2 adaptive close-sample candidate 未过门禁，P8 gate 不支持 `rollout_threat_rerank`，P9.1 / P9.2 也未过 candidate，P9.3 不启动；没有用户明确批准前不得进入 GUI/release 默认。
4. P5.5 opening 候选晋升路线已停止；任何默认布局变更仍必须直接对当前 release 默认 rollout kwargs 做正式门禁验证。
5. 下一步优先赛前冻结、现场启动包核对和 QQ 群/老师附件对齐；现场启动优先双击根目录 `启动项目.cmd`；只修现场风险 bug，不继续默认 AI/布局调参。

## 待确认事项

- 校赛 QQ 群是否发布了项目附件、棋谱标准或统一平台协议（赛前持续关注）。
- 现场骰子具体来源仍需按裁判要求和双方协商执行；程序已支持本机程序掷骰和手动录入外部骰子结果。
- 校赛与省赛是否使用国赛同套规则（默认假设：是；如果有校赛特殊规则，赛前需重新对齐）。
