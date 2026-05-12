# 爱恩斯坦棋现场应急手册（Emergency Guide）

更新时间：2026-05-12
对应阶段：`PROJECT_PHASES.md` §S2
配套文件：`docs/MATCH_CHECKLIST.md`（操作清单）、`reports/gui-rehearsal.md`（演练记录）

---

## 总原则

1. **优先用程序自身能力恢复**（自动保存、悔棋、加载棋谱）。
2. **任何会让程序崩溃的操作 = 该方判负**（规则第 13 条），所以宁可慢一步也别冒险。
3. **不修改代码、不联网**；现场任何"工程改动"必须裁判许可。
4. 处理时间 ≤30 秒能搞定的，先处理；搞不定的立即举手叫裁判，**包干计时不会因故障暂停**。

---

## 1. 程序崩溃 / 闪退

### 现象
- GUI 窗口消失。
- Python 进程退出。
- 屏幕只剩控制台或桌面。

### 立刻动作（≤30 秒）

1. 不要慌、不要 Ctrl+C 控制台。
2. 检查 `replays/` 下两个自动保存：
   ```powershell
   dir replays\auto_save*.json
   ```
   - `auto_save_match.json`：整轮（比分、已结束盘）
   - `auto_save.json`：当前盘内（局面、计时、棋谱）
3. 重新启动主程序：
   ```powershell
   & ".venv/Scripts/python.exe" "scripts/run_gui.py"
   ```
4. 启动后会弹"检测到上次未完成的自动保存对局，是否恢复？" → **点"是"**。
5. 程序自动恢复到崩溃前一步的状态：
   - 比分一致
   - 棋盘局面一致
   - 计时（剩余秒数）一致

### 恢复失败怎么办

弹出"恢复 match auto-save 失败" / "恢复 auto-save 失败"：

1. 检查 `replays/auto_save_match.json` 文件大小：
   ```powershell
   dir replays\auto_save_match.json
   ```
   - 文件存在但 ≤ 50 字节 → 大概率原子写中途被打断（罕见），恢复无效。
   - 文件不存在 → 没有可恢复的对局。
2. 让程序新建对局：选"否"或弹错误后程序会自动 `_exit_match_mode()` 清干净并保留新一局。
3. **本盘按规则判我方负**（崩溃后无法证明胜负，且现场不能凭空恢复）。举手叫裁判，宣布本盘弃权，进入下一盘。
4. 当前 GUI 没有手动补比分入口；如果程序整体仍可继续运行，按裁判确认的真实比分做纸面记录，重新进入比赛模式开始后续对局，赛后再补整理棋谱。

### 备机切换

如果重启程序 3 次都无法启动 GUI：

1. 让裁判允许切换备机（规则允许，需裁判许可）。
2. 在备机：
   ```powershell
   & ".venv/Scripts/python.exe" "scripts/smoke_test.py"
   & ".venv/Scripts/python.exe" "scripts/run_gui.py"
   ```
3. 把主机 `replays/auto_save*.json` 复制过去（U 盘 / 直接同步目录）→ 启动 → 选恢复。

---

## 2. 录入错误（自己手快了 / 录错骰子 / 录错对方走法）

### 2.1 录错骰子（点数填错）

- 程序状态：`_awaiting_dice == False`，但还没点"执行"。
- 处理：直接在骰子输入框改正确点数 → 回车。合法走法列表会刷新。
- 没有走法被执行，没有副作用。

### 2.2 选错走法（还没点"执行"）

- 处理：直接点列表中另一条走法。`selected_move_index` 会更新。
- 仍然没点"执行" → 无副作用。

### 2.3 已经点了"执行"

走法已经入栈，自动保存已写入。用悔棋恢复：

- 点"悔棋"按钮 → `_undo_move()`。
- **悔棋只能悔当前盘内的步骤**（上一盘已 finalize 并写入 `match.games[]`，不可悔）。
- 悔棋会撤销最后一步走子和吃子，回到该步之前的局面。
- **计时不回退**（规则要求计时单方包干，每步耗时算我方时间）。
- 自动保存被覆盖为悔棋后的状态。

### 2.4 连续错乱 / 多步错误

如果悔棋不够（比如连错 3 步），但本盘自动保存还在：

1. 多次点悔棋 → 一直退到最近正确状态。
2. 如果记不清"正确状态"在哪一步：
   - 点"保存棋谱" → 命名 `incident-DEBUG.json`
   - 点"加载棋谱" → 选一个手动保存过的、确认正确的快照。
3. 如果完全没有快照可信 → 本盘判我方负，进下一盘。

---

## 3. 超时判负

### 现象

- 计时器显示我方剩余 0:00。
- 状态栏显示"X 方超时判负，Y 方获胜"。

### 程序自动处理

- `_handle_timeout(我方)` 被定时器周期调用触发。
- 走 `_finalize_match_game(对方, reason="timeout")` 路径：
  - `match.games[-1].result["reason"] == "timeout"`
  - `match.games[-1].result["winner_side"] == "them"`
  - `match.games_won_them += 1`
- 自动保存 match → 清单盘 auto_save → 弹本盘结束 dialog → 自动进入下一盘 setup。
- 定时器自动重排，进入下一盘后照常工作。

操作员动作：
1. 点弹窗"确定"。
2. 检查 MatchModePanel 比分。
3. 录入下一盘开局。

### 没有"快进"按钮

GUI 没有"快进时间"调试按钮（`reports/r2-rehearsal.md` §3 第 1 点已记录）。要触发超时只能：
- 真的等到计时归零（4 分钟包干每方）。
- 或在 Python 控制台手动 `window._handle_timeout(Player.RED)`（仅赛前演练时用）。

赛中遇到我方主动让对方超时（即对方时间归零）→ 程序自动判我方胜，按 §盘间正常推进。

---

## 4. 对方告知的走法对不上我方录入

### 4.1 对方误报走法（声称走 piece 3 实际走 piece 4）

- 规则规定双方有义务告知对方本方走法。如对方告知错误，先用"骰子映射规则"自检：
  - 骰子 d → 如 d 号棋子存活则必走 d 号；
  - 如 d 号棋子已死 → 可走最近编号棋子（双向并列时两选一）。
- 如果对方实际棋盘和声明不符 → 举手叫裁判仲裁，**不要**擅自录入错误数据。

### 4.2 我方录入对方走法时点错

- 处理同 §2.3 / 2.4，用悔棋。
- 注意悔棋后 `record.append` 的 `source` 字段不变，但状态正确。

### 4.3 录入完成后才发现走法不合法

- 程序在 `_apply_selected_move` 内调用 `state.apply_move`，只接受合法走法。
- 如果接受了 → 说明走法在规则上合法，但可能不是对方真实走的那条。
- 立刻悔棋 → 录入正确走法。

---

## 5. 程序不能启动

### 5.1 双击 `scripts/run_gui.py` 没反应

用 PowerShell 跑，看错误：

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

### 5.2 `ModuleNotFoundError: tkinter`

- Python 安装时漏了 Tk 选项。重装 Python 时勾选 "tcl/tk and IDLE"。
- 现场没法重装 → 切备机。

### 5.3 `ModuleNotFoundError: pytest`（在跑 pytest 时）

```powershell
& ".venv/Scripts/python.exe" -m pip install pytest
```

但赛中尽量不装包；只在赛前一晚处理。

### 5.4 `.venv/Scripts/python.exe` 路径找不到

```powershell
python -m venv .venv
& ".venv/Scripts/python.exe" -m pip install pytest
```

### 5.5 启动但棋盘空白 / 渲染崩溃

```powershell
& ".venv/Scripts/python.exe" "scripts/smoke_test.py"
& ".venv/Scripts/python.exe" "scripts/r2_smoke.py"
```

两个 smoke 都过 → core 正常，问题在 GUI 渲染，重启电脑试试；不过 → 切备机。

---

## 6. 网络误开 / 误连

### 现象

- 系统托盘显示 WiFi 已连接 / 有线网卡灯亮。
- 任何浏览器 / IM 弹通知。

### 立即动作（≤5 秒）

1. 右键托盘 WiFi → 断开 / 关闭 WiFi。
2. 拔网线。
3. 命令行确认：
   ```powershell
   ipconfig
   ```
   所有 IPv4 应显示空 / 169.254.* / 链路本地地址。

4. 告知裁判（这是规则违例，但本程序完全本地，不会因联网影响对局；裁判可记录但通常不判负）。

### 误开浏览器 / 弹窗

- 立即关掉。
- 本程序运行不依赖任何在线资源。

---

## 7. 棋谱 / 录入混乱无法回退

最后的应急：

1. 保存当前（混乱）状态：
   - 点"保存棋谱" → 命名 `incident-CHAOS.json`
   - 拷贝 `replays/auto_save_match.json` 到一个独立文件名
2. 让程序新建对局：菜单 → 模式 → 调试模式（这会清掉单盘 auto_save 和 match）。
   - **注意**：这会丢失当前盘的恢复能力。
3. 当前 GUI 不能手动 append 已结束盘或补比分；把真实比分交给裁判纸面确认，赛后再修复棋谱文件。
4. 实在恢复不了 → 举手叫裁判，**本盘判我方负**，进入下一盘。

---

## 8. 时间统计 / 不计时器场景

### 8.1 系统时间漂移

程序计时基于 `time.monotonic()`，不受系统时间调整影响（包括 NTP）。

### 8.2 计时器没在跑

如果 `_timer_after_id is None` 且没有定时器回调：

- 通常是某个 dialog 阻塞了 mainloop。关闭 dialog 后 `_schedule_timer_refresh` 会自动恢复。
- 极端情况下，在 Python 控制台手动 `window._schedule_timer_refresh()`。

---

## 9. 快速决策表

| 现象 | 优先动作 | 备选动作 |
|---|---|---|
| 程序崩溃 | 重启 → 恢复 | 切备机 |
| 录入错误（未执行） | 改输入 | — |
| 录入错误（已执行） | 悔棋 | 加载手动快照 |
| 多步错乱 | 加载快照 | 本盘判负 |
| 计时即将归零 | 让程序自动判 | — |
| 程序不能启动 | smoke + run_gui 控制台看错 | 切备机 |
| 网络误开 | 关网卡 / 拔网线 | 告知裁判 |
| 显示卡死 | 等 5 秒 | 强杀 → 重启恢复 |
| 录入混乱无法回退 | 加载手动快照 | 本盘判负 |

---

## 10. 重要文件清单（应急时查）

| 用途 | 路径 |
|---|---|
| 单盘自动保存 | `replays/auto_save.json` |
| 整轮自动保存 | `replays/auto_save_match.json` |
| 手动保存目录 | `records/` |
| 启动脚本 | `scripts/run_gui.py` |
| 基础冒烟 | `scripts/smoke_test.py` |
| 七盘制冒烟 | `scripts/r2_smoke.py` |
| S2 全流程演练 | `scripts/s2_rehearsal.py` |
| 规则假设 | `docs/RULE_ASSUMPTIONS.md` |
| 操作清单 | `docs/MATCH_CHECKLIST.md` |
| 演练记录 | `reports/gui-rehearsal.md` |
