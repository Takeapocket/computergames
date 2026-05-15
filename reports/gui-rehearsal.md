# S2 GUI 全流程演练记录

日期：2026-05-12（§1-§3 headless 自动演练）/ 2026-05-13（§4 真实 Tk GUI 手动表填写完成，21 项全"正常"）
对应阶段：`PROJECT_PHASES.md` §S2 GUI 全流程演练与现场打磨
配套文件：`docs/MATCH_CHECKLIST.md`、`docs/EMERGENCY_GUIDE.md`、`scripts/s2_rehearsal.py`
前置阶段：`reports/r2-rehearsal.md`（R-2 七盘制实现与单元测试）

> 测试数量说明：本报告中的 `349 passed` 是 2026-05-12 S2 历史快照。当前全量 pytest 以 `release/v1.0/test_report.md` 为准：495 passed in 11.68s。

---

## 0. 与 r2-rehearsal.md 的关系

`r2-rehearsal.md` 记录的是 R-2 七盘制实现的单元 / 集成 / smoke 验证；
本文件记录的是 S2 阶段对**headless 自动化赛场闭环**的端到端演练，覆盖崩溃恢复、超时判负、
盘间/盘中崩溃链路等 R-2 测试未直接覆盖的工程信心点，并产出可由操作员引用的
现场清单（`docs/MATCH_CHECKLIST.md`）+ 应急手册（`docs/EMERGENCY_GUIDE.md`）。
真实 Tk GUI 的人工视觉/交互演练已于 2026-05-13 由操作员按 §4 填表完成（21 项全"正常"），S2 完整闭环。

---

## 1. 自动化基线

### 1.1 完整 pytest

```powershell
& ".venv/Scripts/python.exe" -m pytest -q
```

结果（2026-05-12，review follow-up 后）：

```
........................................................................ [ 20%]
........................................................................ [ 41%]
........................................................................ [ 61%]
........................................................................ [ 82%]
.............................................................            [100%]
349 passed in 13.54s
```

349 passed = `r2-rehearsal.md` 报告的 324 基线 + 后续 24 条新增（含 R-3 / R-1 followup 等），再加 1 条 S2 review follow-up 回归测试。0 failed、0 error、0 skipped。本节为 2026-05-12 S2 历史快照；当前全量 pytest 见 `release/v1.0/test_report.md`。

### 1.2 基础冒烟

```powershell
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
```

输出（节选）：

```
dice: 3
selected pieces: [3]
legal moves:
  1. red 3: Position(row=2, col=2) -> Position(row=3, col=2)
  2. red 3: Position(row=2, col=2) -> Position(row=2, col=3)
  3. red 3: Position(row=2, col=2) -> Position(row=3, col=3) capture
applied: Move(player=Player.RED, piece_id=3, ...)
winner: None
undo restored: True
```

✅ 通过：合法走法生成、apply_move、撤销链路全过。

### 1.3 R-2 七盘制冒烟

```powershell
& ".venv/Scripts/python.exe" "scripts/r2_smoke.py"
```

输出：

```
[1/6] init OK; setup phase, debug mode
[2/6] match entry OK; role=甲, side=red
      panel score: 比分：我方 0 — 对方 0
      panel first_mover: 本盘先手：我方
[3/6] 4:0 sweep OK; winner=us
[4/6] reset OK; back to debug
[5/6] blue-yi first mover OK: color=red
      blue-yi game 4 first mover color=red
[6/6] blue-yi game 2 first mover color=blue
smoke OK
```

✅ 通过：模式切换、4:0 整轮、reset、4 种身份的先手色。

---

## 2. S2 自动化全流程演练

新增脚本 `scripts/s2_rehearsal.py`，把 `r2-rehearsal.md` §2 的 8 个手测场景转成
无人值守的 headless 测试，每个 scenario 独立隔离 auto-save 目录，全部 dialog
静音化。运行：

```powershell
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"
```

输出（2026-05-12 首次跑通）：

```
======================================================================
S2 GUI Full-Flow Headless Rehearsal
======================================================================
[1/8] 4:0 整轮: PASS
      winner=us, games_won=4:0
[2/8] 4:3 整轮: PASS
      winner=us, games_won=4:3, 第 7 盘绝杀
[3/8] 先手序列: PASS
      red/甲: 7/7 OK; blue/甲: 7/7 OK; red/乙: 7/7 OK; blue/乙: 7/7 OK
[4/8] 超时判负: PASS
      比分=0:1, reason=timeout, timer 重排, auto_save 清理正确
[5/8] 盘间恢复: PASS
      重启后比分=1:0, 当前第 2 盘, mode=match
[6/8] 盘中恢复: PASS
      steps=1, current=blue, timer 一致
[7/8] 悔棋边界: PASS
      第 1 盘 steps=0 保留；第 2 盘 1 步可悔
[8/8] 整轮结束后行为: PASS
      4:0 finished → match 保留 → reset 回 debug 并恢复 side 控件
----------------------------------------------------------------------
Total: 8/8 scenarios passed
======================================================================
```

> 注：Windows cmd 默认 cp936，stdout 中文若出现"乱码"是终端显示问题，脚本文件本体 UTF-8，PowerShell ISE / 现代终端 / 重定向到文件后中文正常。

### 2.1 场景到验收点的映射

| Scenario | 覆盖 `PROJECT_PHASES.md` §S2 验收点 | 主要断言 |
|---|---|---|
| 1. 4:0 整轮 | 自动化覆盖一轮 4 胜状态机；不替代真实 GUI 手测 | `match.is_finished() == True`, `winner() == "us"`, `games_won = 4:0` |
| 2. 4:3 整轮 | 连续模拟至少 3 盘不崩溃 + 至少一轮 4 胜 | 前 6 盘交替 3:3 + 第 7 盘我方胜，winner="us" |
| 3. 先手序列 | 七盘制规则正确性 | 4 身份 × 7 盘 = 28 个 first_mover_color 全过 |
| 4. 超时判负 | auto_save 恢复后局面、棋谱、计时状态一致 | result.reason="timeout"，比分推进，定时器重排，单盘 auto_save 清理 |
| 5. 盘间恢复 | auto_save 恢复后局面、棋谱、计时状态一致 | 重启后 match 比分保留、current_game_index 进入下一盘、mode=match |
| 6. 盘中恢复 | auto_save 恢复后局面、棋谱、计时状态一致 | 重启后 phase=playing、steps 完整、current_player 不漂移、计时器误差 < 0.5s |
| 7. 悔棋边界 | 误操作可通过悔棋恢复 | 当前盘 1 步可悔；前一盘 GameRecord.steps 不被触动 |
| 8. 整轮结束后行为 | 自动化覆盖整轮结束状态；不替代真实 GUI 手测 | finished 后不自动 reset；reset 后 mode=debug、side 控件重新启用 |

### 2.2 GUI 不依赖网络（S2 验收第 5 点）

`scripts/s2_rehearsal.py` 不发起任何 socket / urllib / requests 调用；
`gui/main_window.py` 的 import 集合（`tkinter`、`pathlib`、`ai.match`、`core.*`、
`record.*`）也是纯本地。该验收点为静态审查结论，已用 `rg` 检查
`scripts/s2_rehearsal.py` / `gui` / `record` 未发现 `socket`、`urllib`、`requests`
等网络调用。

---

## 3. 现有测试对 S2 回归项的覆盖

`PROJECT_PHASES.md` §S2 列出"tests/test_main_window.py 补齐 R-2 后 GUI 状态回归"
作为建议输出物。审计当时现有 349 条 pytest 后结论：**已实质覆盖，不需新增重复测试**。当前全量测试数量以 `release/v1.0/test_report.md` 为准。
逐条对照：

| 回归项 | 对应测试（文件:行号） |
|---|---|
| 4:0 整轮路径 | `tests/test_match_record.py:157 test_4_0_sweep`、`tests/test_match_integration.py:164 test_match_4_0_finishes` |
| 4:3 整轮路径 | `tests/test_match_record.py:167 test_4_3_thriller` |
| finalize 写比分 / 持久化 | `tests/test_match_integration.py:178 test_match_finalize_winner_writes_result`、`:196 test_match_finalize_opponent_win`、`:211 test_match_auto_save_persists_after_finalize`、`:594 test_finalize_match_game_persists_match_before_clearing_game` |
| 盘间 / 盘中恢复 | `tests/test_match_integration.py:292 test_match_restore_from_setup_phase`、`:330 test_match_restore_setup_phase_clears_stale_single_game_auto_save`、`:388 test_match_restore_from_finished_phase_clears_and_returns_to_debug`、`:463 test_match_restore_playing_phase_with_missing_game_auto_save_prompts`、`:514 test_match_restore_playing_phase_with_missing_game_user_accepts` |
| 超时推进比分 | `tests/test_match_integration.py:618 test_timeout_during_match_advances_score`、`:640 test_handle_timeout_in_match_reschedules_timer_refresh` |
| 单盘 auto_save 在 match 模式下清理 | `tests/test_match_integration.py:426 test_enter_match_mode_clears_stale_single_game_auto_save` |
| 先手序列正确性 | `tests/test_match_record.py:74 TestFirstMover` 类、`tests/test_match_integration.py:95 test_match_first_game_uses_jia_first_mover` 等 4 条 |
| 整轮结束后行为 | `tests/test_match_integration.py:261 test_match_finished_dialog_only_fires_once`、`:230 test_reset_game_clears_match_state` |
| 重置清理 match 状态 | `tests/test_match_integration.py:230 test_reset_game_clears_match_state` |

`scripts/s2_rehearsal.py` 在自动化测试之上又跑了一层端到端 GUI 链路，作为
"测试通过 ≠ 真能跑"的额外保险。

---

## 4. 手动 GUI 演练（操作员现场过一遍）

下表沿用 `r2-rehearsal.md` §2 的格式，由操作员在赛前用真实 Tk GUI 跑一遍并填表。
`scripts/s2_rehearsal.py` 已覆盖自动化路径，**手测的重点是 UI 显示**（dialog 文案、
panel 数字、按钮启用状态、键盘焦点）等不容易在 headless 测试断言的视觉项。
**2026-05-13 操作员现场跑通并填表完成，21 项全"正常"，S2 完整闭环。**

启动：`& ".venv/Scripts/python.exe" "scripts/run_gui.py"`

### 4.1 启动到一轮 4:0

| 步骤 | 预期 | 结果 |
|---|---|---|
| 启动程序 | 棋盘 + 控件正常渲染；菜单出现"模式"项 | 正常 |
| 菜单 → 模式 → 比赛模式 | 弹颜色 + 角色 dialog | 正常 |
| 选红方 / 甲方 / 确认 | 进入第 1 盘 setup；MatchModePanel 显示比分 0:0、第 1 盘、本盘先手"我方"、身份"甲方" | 正常 |
| 录入对方布局 → 确认开局 | playing 阶段；状态栏"开局已确认，请录入第一轮骰子" | 正常 |
| 录骰子 → 选合法走法 → 执行 | 棋盘动；自动保存写入 | 正常 |
| 连续操作至我方到达蓝方角点或吃光蓝方 | 弹"本盘 我方 胜" → 点继续 → 进入第 2 盘 setup | 正常 |
| 我方布局 sticky 保留 / 对方布局清空 | OpeningPanel 显示我方按钮选中、对方区域空 | 正常 |
| 重复连胜 4 盘 | 第 4 盘结束弹"本轮结束！我方 胜出，最终比分 我方 4 — 对方 0" | 正常 |

### 4.2 4:3 决胜

| 步骤 | 预期 | 结果 |
|---|---|---|
| 启动新轮，我方甲红 | 同 §4.1 | 正常 |
| 前 6 盘胜负交替 → 3:3 | 第 7 盘 setup 时 MatchModePanel 显示"第 7 盘 / 比分 3:3 / 本盘先手 对方（乙方先手）" | 正常 |
| 第 7 盘我方胜 | 弹"本轮结束！我方 胜出。最终比分 我方 4 — 对方 3" | 正常 |

### 4.3 盘内崩溃恢复

| 步骤 | 预期 | 结果 |
|---|---|---|
| 第 3 盘 playing 中关掉程序（任务管理器结束 python.exe） | `replays/auto_save.json` + `auto_save_match.json` 都存在 | 正常 |
| 重启 `scripts/run_gui.py` → 弹"恢复未完成对局" → 选是 | 进入第 3 盘 playing；比分 + 局面 + 计时一致 | 正常 |

### 4.4 盘间崩溃恢复

| 步骤 | 预期 | 结果 |
|---|---|---|
| 完成第 2 盘 → 进入第 3 盘 setup 时关程序 | `replays/auto_save_match.json` 存在；`auto_save.json` 已被 finalize 清理 | 正常 |
| 重启 → 选是 | 进入第 3 盘 setup；比分保留 a:b | 正常 |

### 4.5 误操作恢复

| 步骤 | 预期 | 结果 |
|---|---|---|
| playing 中走一步 → 点悔棋 | 走法撤回；状态栏提示已悔棋；计时不回退 | 正常 |
| 没走过棋时点悔棋 | 状态栏"当前没有可悔棋的走法" | 正常 |
| 跨盘悔棋（第 2 盘没走过时点悔棋） | 同上，不可悔到第 1 盘 | 正常 |

### 4.6 整轮结束后操作

| 步骤 | 预期 | 结果 |
|---|---|---|
| 4 胜后弹整轮结束 dialog → 关闭 | GUI 留在 playing 阶段最后一手 | 正常 |
| 菜单 → 模式 → 调试模式 | 切回 debug，match 字段隐藏 | 正常 |
| 菜单 → 模式 → 比赛模式 | 弹颜色 + 角色 → 新一轮 | 正常 |

---

## 5. 已知限制

沿用 `r2-rehearsal.md` §3，5 条均仍有效：

1. **无快进时间按钮**：GUI 不能跳计时器；超时只能等真实 240 秒到达或在 Python 控制台手动 `_handle_timeout`。S2 自动化测试用 `_handle_timeout(Player.X)` 直接触发。
2. **悔棋跨盘提示**：悔棋只悔当前盘的 step；前盘 `GameRecord` 不变。无显式 UI 提示，只是状态栏"当前没有可悔棋"；操作员需培训理解此约束。`scripts/s2_rehearsal.py:scenario_undo_scope` 自动验证此不变量。
3. **第 7 盘乙方先手提示**：我方乙时第 7 盘是我方先手；我方甲时第 7 盘是对方先手。状态栏统一显示"本盘先手：我方 / 对方"，操作员需自己映射到甲乙身份。`scripts/s2_rehearsal.py:scenario_first_mover_sequence` 已覆盖 4 × 7 = 28 个映射。
4. **整轮结束后不自动切回 debug**：保留在比赛模式方便操作员保存棋谱。需手动点菜单切回 debug 或 reset。验收点已在 `scenario_match_finished_state` 覆盖。
5. **reset_for_match_game 异常路径**：keep_our_layout=True 但我方布局为空时 fall back 到加载预设。仅在错误使用 API 时触发，已防御性处理。

### S2 新增已知项

6. **stdout 中文乱码**：`scripts/s2_rehearsal.py` 输出在 Windows cmd 默认 cp936 终端下中文显示乱码。这是终端编码问题，不影响 exit code 与 PASS/FAIL 判定；如需可读输出，用 PowerShell 或将 stdout 重定向到 UTF-8 文件后查看。

---

## 6. S2 验收逐条对照（`PROJECT_PHASES.md` §S2 L156-162）

```
连续模拟至少 3 盘不崩溃 ✅
   → scenario_4_3（7 盘连续模拟）+ scenario_4_0（4 盘连续模拟）
至少手动跑通一轮 4 胜流程 ✅
   → scenario_4_0 + scenario_4_3 自动化覆盖状态机；§4 真实 GUI 手测表 2026-05-13 操作员填表完成（21/21 正常）
误操作可通过悔棋或加载棋谱恢复 ✅
   → scenario_undo_scope + tests/test_main_window.py 悔棋按钮状态 + 加载/保存 round-trip
auto_save 恢复后局面、棋谱、计时状态一致 ✅
   → scenario_match_restore_between_games + scenario_in_game_restore
GUI 不依赖网络 ✅
   → 静态审查：import 集合纯本地，`rg` 未发现 socket/urllib/requests 调用
```

---

## 7. 复现命令

```powershell
cd C:\Users\Takeapocket\Desktop\documents\computergames

# 完整自动化基线
& ".venv/Scripts/python.exe" -m pytest -q

# 三层冒烟
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/r2_smoke.py"
& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"

# 真实 GUI（手测填表）
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

---

## 8. 进入下一阶段判定

S2 已完整闭环（headless 自动演练 + 真实 Tk GUI 手动表）：

- ✅ `docs/MATCH_CHECKLIST.md` 落地（10 章，覆盖赛前 24h → 赛后归档）
- ✅ `docs/EMERGENCY_GUIDE.md` 落地（10 章，覆盖崩溃 / 录入错误 / 超时 / 启动失败 / 网络 / 棋谱混乱）
- ✅ `scripts/s2_rehearsal.py` 8/8 PASS
- ✅ pytest 全量通过 / 0 failed（本报告为 S2 历史快照；当前全量数量见 `release/v1.0/test_report.md`）
- ✅ 现有测试已实质覆盖 R-2 后 GUI 回归，不需新增 test_main_window.py case
- ✅ `reports/gui-rehearsal.md` §4 真实 GUI 手动演练表 2026-05-13 操作员填表完成（21/21 正常）

**下一步**：S2/S3/S4 全部闭环，进入整体 sign-off 与 release/v1.0 归档。
