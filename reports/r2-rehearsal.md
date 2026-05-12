# R-2 七盘制比赛模式演练记录

日期：2026-05-11
对应阶段：PROJECT_PHASES.md §S1（R-2）
实现 commit：未提交（由用户决定何时 commit）

---

## 1. 自动化测试覆盖

### 单元测试

| 测试文件 | 用例数 | 覆盖范围 |
|---|---|---|
| `tests/test_match_record.py` | 48 | MatchRecord 数据模型：构造校验、first_mover 矩阵、winner 判定、append_finished_game、4:0 / 4:3 / 3:3、序列化往返 |
| `tests/test_match_mode.py` | 6 | MatchModePanel 4 行新显示、show/hide、向后兼容 |
| `tests/test_opening_panel.py`（新增 6 条） | +6 | reset_for_match_game 三种 sticky 场景、set_side_controls_enabled 真禁用 radio |
| `tests/test_auto_save.py`（新增 4 条） | +4 | auto_save_match / load / has / clear 往返、finished phase 保留 |
| `tests/test_match_integration.py` | 16 | 进入比赛模式、第 2 盘先手切换（甲/乙 × 红/蓝）、sticky 我方布局、4:0 完成、超时判负、reset 清理、debug legacy 仍工作、auto-save 多盘恢复 |

**总计新增 80 条 R-2 相关测试，全部通过**。全量 pytest `324 passed in 6.74s`，无回归。

### 自动化 smoke（`scripts/r2_smoke.py`）

`& ".venv/Scripts/python.exe" scripts/r2_smoke.py` 全过：

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

验证关键不变量：
- 我方甲红：第 1 盘红方先手 ✓
- 我方蓝乙：第 1 盘红方先手（对方=甲方先手）✓
- 我方蓝乙：第 2 盘蓝方先手（我方=乙方先手）✓
- 我方蓝乙：第 4 盘红方先手（对方=甲方先手）✓
- 4:0 → match.phase=finished, winner=us ✓
- reset_game 真正清理 _match + 重新启用 OpeningPanel radio ✓

---

## 2. 手测清单（人工执行）

下列场景需要操作员在真实 GUI 里跑一遍。每条记录"通过 / 异常 / 备注"。

启动：`& ".venv/Scripts/python.exe" "scripts/run_gui.py"`

### 2.1 4:0 流程
| 步骤 | 预期 | 结果 |
|---|---|---|
| 菜单 → 模式 → 比赛模式 | 弹颜色+角色 dialog | _________ |
| 选红方 / 甲方 / 确认 | 进入第 1 盘 setup；MatchModePanel 显示"第 1 盘 / 共 7 盘 / 比分 我方 0 — 对方 0 / 本盘先手 我方 / 我方身份 甲方" | _________ |
| 录对方布局 → 确认开局 | 进入 playing；状态栏显示"开局已确认，请录入第一轮骰子" | _________ |
| 完成第 1 盘（连续操作至我方到达蓝方角点或吃光蓝方） | 弹"本盘 我方 胜" dialog → 点继续 → 进入第 2 盘 setup；我方布局保留、对方清空 | _________ |
| 第 2 盘 setup → 确认开局 | playing 阶段 current_player 为蓝方（对方先手），先手提示"本盘先手：对方" | _________ |
| 连胜 4 盘 | 第 4 盘结束后弹"本轮结束！我方 胜出。最终比分：我方 4 — 对方 0" | _________ |

### 2.2 4:3 流程
| 步骤 | 预期 | 结果 |
|---|---|---|
| 启动新轮，我方甲红 | 同上 | _________ |
| 前 6 盘胜负交替（3:3） | 第 7 盘 setup 时 MatchModePanel 显示"第 7 盘 / 比分 3:3 / 本盘先手 对方（乙方先手）" | _________ |
| 第 7 盘我方胜 | 弹"本轮结束！我方 胜出。最终比分：我方 4 — 对方 3" | _________ |

### 2.3 先手序列检查
| 盘数 | 我方=甲 → 谁先手 | 我方=乙 → 谁先手 |
|---|---|---|
| 1 | 我方 ✓ | 对方 ✓ |
| 2 | 对方 ✓ | 我方 ✓ |
| 3 | 对方 ✓ | 我方 ✓ |
| 4 | 我方 ✓ | 对方 ✓ |
| 5 | 我方 ✓ | 对方 ✓ |
| 6 | 对方 ✓ | 我方 ✓ |
| 7 | 对方 ✓ | 我方 ✓ |

（自动化测试 28 case 已覆盖；手测确认 GUI 显示一致。）

### 2.4 超时判负
| 步骤 | 预期 | 结果 |
|---|---|---|
| 启动比赛模式，等待对方计时归零（或手动设置 timer 剩余时间） | 本盘对方判负，弹本盘结束 dialog | _________ |
| 检查 GameRecord.result.reason | 应为 "timeout" | _________ |

### 2.5 盘间恢复
| 步骤 | 预期 | 结果 |
|---|---|---|
| 完成第 2 盘 → 第 3 盘 setup 时关闭程序 | replays/auto_save_match.json 存在；auto_save.json 已清理 | _________ |
| 重启程序 | 弹"恢复未完成对局" → 选是 → 进入第 3 盘 setup（比分保留 a:b） | _________ |

### 2.6 盘中恢复
| 步骤 | 预期 | 结果 |
|---|---|---|
| 第 3 盘 playing 中关闭程序 | replays/auto_save.json + auto_save_match.json 都存在 | _________ |
| 重启 → 选是恢复 | 进入第 3 盘 playing，比分 + 当前局面 + 计时一致 | _________ |

### 2.7 悔棋范围
| 步骤 | 预期 | 结果 |
|---|---|---|
| 第 2 盘完成 → 进入第 3 盘 | 悔棋按钮仅对当前盘内有效 | _________ |
| 第 3 盘走一步 → 悔棋 | 第 3 盘第 1 步被悔回 | _________ |
| 第 3 盘没走过棋时点悔棋 | 状态栏提示"当前没有可悔棋的走法" | _________ |

### 2.8 整轮结束后的行为
| 步骤 | 预期 | 结果 |
|---|---|---|
| 4 胜后弹整轮结束 dialog | 可关闭 dialog；GUI 留在 playing 阶段最后一手 | _________ |
| 菜单 → 模式 → 调试模式 | 切回 debug，比赛字段隐藏 | _________ |
| 菜单 → 模式 → 比赛模式 | 弹"正在比赛模式，是否结束当前轮次并重新开始" → 选是 → 新一轮 dialog | _________ |

---

## 3. 已知限制 / 后续工作

1. **手测 2.4 超时**：当前 GUI 没有"快进时间"按钮，超时判负需要等真实 240 秒或在测试代码里直接调用 `_handle_timeout`。建议加一个 debug-only 的"减时间"按钮。延后到 S2 GUI 全流程演练阶段处理。

2. **手测 2.7 悔棋跨盘**：现在悔棋只悔当前盘的 step。但 MatchRecord.games 里历史盘的 GameRecord 是不可悔的——这个不变量没有 GUI 显式提示，只是状态栏说"没有可悔棋"。够用但不够明显。

3. **第 7 盘乙方先手**：我方乙时第 7 盘是我方先手；我方甲时第 7 盘是对方先手。状态栏文案统一显示"本盘先手：我方/对方"，但操作员需要自己把"先手"和"甲乙身份"对应起来。

4. **整轮结束后不自动切回 debug**：刻意保留在比赛模式，方便操作员保存棋谱。需要手动点菜单切回 debug 或重置棋局。

5. **`reset_for_match_game` 在 keep_our_layout=True 但我方布局为空时（异常路径）**：fall back 到加载预设。这种情况理论上只在错误使用 API 时发生，但路径已经被防御性处理。

---

## 4. 验证步骤回顾

```powershell
# 单元 + 集成（包括 R-2 新增 80 条）
& ".venv/Scripts/python.exe" -m pytest -q
# 结果：324 passed in 6.74s

# Headless smoke
& ".venv/Scripts/python.exe" "scripts/r2_smoke.py"
# 结果：全 6 步通过

# 实际 GUI（手测填表）
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

R-2 实现已具备进入手测的所有条件。AI 强度 / quick_bench 基线不变（R-2 不修改 ai/）。
