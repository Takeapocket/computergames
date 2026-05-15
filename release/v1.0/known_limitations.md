# Known Limitations

来源：`reports/gui-rehearsal.md` §5、`reports/r2-rehearsal.md` §3、S2 自动演练实测。

## GUI / 操作

1. **无快进时间按钮**：GUI 不能跳计时器；现场超时只能等真实 240 秒到达。`scripts/s2_rehearsal.py:scenario_timeout_during_match` 用内部 `_handle_timeout(Player.X)` 触发以做自动化测试。
2. **悔棋跨盘提示**：悔棋只悔当前盘；前一盘 `GameRecord` 不被触动。状态栏只提示"当前没有可悔棋的走法"，操作员需培训。
3. **第 7 盘乙方先手**：我方乙身份时第 7 盘是我方先手；我方甲身份时第 7 盘是对方先手。状态栏统一显示"本盘先手：我方/对方"，操作员需自行映射到甲乙身份。
4. **整轮结束后不自动切回 debug**：保留在比赛模式以便操作员保存棋谱。需要手动 reset 或切回 debug 模式。
5. **stdout 中文乱码（仅 Windows cmd cp936）**：脚本输出在默认 cmd 下中文可能乱码；不影响 exit code 与 PASS/FAIL 判定。可用 PowerShell 或重定向到 UTF-8 文件查看。

## AI

6. **RolloutAI 是当前默认，但仍保留回退**：`rollout` 已按 `reports/ai_promotion_decision.md` 晋升为默认推荐 AI；若现场发现输出异常，可回退到 `greedy_risk`。
7. **Expectimax 仍不作为默认**：`ExpectimaxAI(depth=1)` 在 R-0 合规规则下合并胜率 45.0%，弱于 `greedy_risk`；`expectimax_v2` 需要 fresh harness 复验后才能重新评估。
8. **参数 / 布局搜索未做晋升**：`scripts/param_sweep.py` 与 `scripts/search_openings.py` 提供流水线，但本 release 未跑大样本，未替换默认布局。
9. **没有学习型 AI**：本 release 不引入 PyTorch / Gymnasium / OpenSpiel runtime 依赖；默认 AI 是规则引擎 + `greedy_risk` fallback + bounded rollout。

## 协议 / 部署

10. **不依赖统一平台 / 网络 API**：当前 release 假设比赛现场操作员录入骰子和对方走法。若赛事确认引入统一平台，需要在 `adapters/` 增加适配层，但不在 release/v1.0 范围内。
11. **不提供二进制包**：发布形态是源码 + `.venv/`；现场用 `scripts/run_gui.py` 启动。
