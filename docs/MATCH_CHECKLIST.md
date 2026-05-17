# 爱恩斯坦棋现场操作清单（Match Checklist）

更新时间：2026-05-17（R-4 GUI 程序掷骰后同步）
对应阶段：`PROJECT_PHASES.md` §S2 GUI 全流程演练与现场打磨
配套文件：`docs/EMERGENCY_GUIDE.md`（应急手册）、`reports/gui-rehearsal.md`（演练记录）

---

## 0. 角色与边界

- **操作员**：一人，全程负责本机操作。
  比赛规则规定每方仅允许一名队员执行裁判允许的操作；不允许超时、修改程序或介入程序运行。
- **本程序假设**：现场无统一平台、无网络；骰子来源按双方协商或裁判要求确定，可由本程序生成，也可由对方程序、裁判或实体骰子给出。
- **数据流**：骰子生成/录入 → 程序输出我方建议走法 → 操作员执行 → 录入对方走法 → 重复。

## 1. 赛前 24 小时（备机/家中）

### 1.1 工程验证

双击根目录 `启动项目.cmd`，选择 `2. 一键赛前总检查`。

命令行等价方式：

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

成功标准：最后必须看到 `READY FOR MATCH`。该命令会检查 release 配置锁、完整 pytest、smoke、S2 rehearsal 和小样本 timing gate；失败立即修复或切换到已复验备机。

### 1.2 GUI 冒烟

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

人工验证：
- 棋盘渲染完整、5×5。
- 菜单"模式 → 比赛模式" → 弹颜色 + 角色 + 计时设置 dialog → 选红方/甲方，确认"程序自动超时判负"默认未勾选 → 进入第 1 盘 setup。
- MatchModePanel 显示"第 1 盘 / 比分 我方 0 — 对方 0 / 本盘先手 我方 / 我方身份 甲方"。
- 手动录入骰子或点击"程序掷骰" → 出现合法走法列表。
- 关闭程序前清理 `replays/auto_save*.json`（见 §1.4）。

### 1.3 数据 / 棋谱归档准备

- 在 `records/` 下建立当日子目录，如 `records/2026-05-DD/`。
- 准备一个 U 盘或外置硬盘，赛后拷贝完整工作目录。
- 检查 `.venv/` 完整可用：如果重装了 Python，必须重新 `& ".venv/Scripts/python.exe" -m pip install pytest`。

### 1.4 现场环境清理

```powershell
Remove-Item -ErrorAction SilentlyContinue replays/auto_save.json
Remove-Item -ErrorAction SilentlyContinue replays/auto_save_match.json
```

清掉残留的自救文件，避免比赛开始时弹"是否恢复未完成对局？"对话框。

## 2. 赛前 30 分钟（赛场就位后）

### 2.1 硬件确认

- 笔记本电池满电，电源线接好。
- **关闭无线网卡 + 拔网线**（比赛规则禁止联网；本程序完全本地）。
- 屏幕亮度调到对方可见角度，与裁判说明双方电脑位置。
- 备机就位（同一份代码 + `.venv`），关机备用。

### 2.2 工程二次验证

优先双击根目录 `启动项目.cmd`，选择 `2. 一键赛前总检查`。

命令行等价方式：

```powershell
& ".venv/Scripts/python.exe" "scripts/preflight_check.py"
```

成功标准同样是 `READY FOR MATCH`。如果现场时间不足，优先使用赛前已完整通过 preflight 的备机，不在比赛开始前临时跳过失败项。

### 2.3 启动主程序

优先双击根目录 `启动项目.cmd`，选择 `1. 启动 GUI`。

命令行等价方式：

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py"
```

如需 10 分钟快棋决赛加赛，可在进入比赛模式的弹窗里把"单方时限（秒）"改为 `600`；命令行也可提前指定：

```powershell
& ".venv/Scripts/python.exe" "scripts/run_gui.py" --total-seconds 600
```

启动后确认：
- 主窗口呈现棋盘 + 控件。
- 不要点任何按钮，等待裁判宣布开始。

## 3. 每轮开始

裁判宣布开始后：

1. **菜单 → 模式 → 比赛模式**。
2. 弹出对话框 → 选"我方颜色"（红 / 蓝）+ "我方角色"（甲 / 乙）→ 核对"单方时限（秒）"。
   - 注意：**甲乙是先手身份**，与红蓝颜色独立；甲方一四五盘先手，乙方二三六七盘先手。
3. 默认不要勾选"程序自动超时判负"；只有裁判明确要求双方程序自行计时时才勾选。
4. 点确认后进入第 1 盘 setup 阶段，MatchModePanel 显示比分 0:0 + 当前盘数 + 本盘先手。
5. 在开局录入区设置我方棋子布局（选预设或自定义）+ 录入对方棋子布局。
6. 确认开局 → 进入第 1 盘 playing。

## 4. 每盘流程

playing 阶段每一轮（双方各走一步前后）的操作：

每次选择走法前先确定骰子来源：
- 若双方同意由本程序生成骰子，点击"程序掷骰"，双方确认显示结果。
- 若骰子由对方程序、裁判或实体骰子给出，则手动录入骰子结果。
- 掷骰/录入后再选择合法走法；不要在看到 AI 推荐后重复掷骰。

| 步骤 | 操作员动作 | 程序响应 |
|---|---|---|
| 1 | 按双方/裁判确认的来源得到骰子：可点"程序掷骰"，或在骰子输入框填入外部点数后回车 | 显示骰子数 + 合法走法列表 |
| 2 | 看 AI 推荐 + 合法走法 → 在列表选一条 | 高亮该走法的起点 / 终点 |
| 3 | 点"执行"按钮 | 棋盘应用走法，状态栏提示"已执行：…"；自动保存（每步） |
| 4 | 告知对方本方走法（规则义务） | — |
| 5 | 等对方在他们的程序操作 → 对方告知本方他们的走法 | — |
| 6 | 按同一骰子来源规则得到对方回合骰 → 程序录入/生成骰子 → 在合法走法里点对方实际走的那条 → 执行 | 棋盘应用对方走法；状态栏 source=opponent |
| 7 | 重复 1-6 直到本盘胜负 | 任一方到达对方出发区角点 / 吃光对方 / 裁判判定超时 |

若默认计时模式下出现超时提示，先报告裁判；裁判确认某方超时负后，再点击计时面板中对应的"裁判判红方超时负" / "裁判判蓝方超时负"按钮。未得到裁判确认时不要点击。

**提示**：每 5 步左右主动 Ctrl+S（"保存棋谱"按钮）一次，作为额外快照备份。

## 5. 盘间

单盘结束时程序会自动：
1. finalize 当前盘（把胜负写入 `record.result`，append 到 `match.games[]`）。
2. 持久化 `replays/auto_save_match.json`。
3. 清掉单盘 `replays/auto_save.json`。
4. 弹出"本盘 X 胜"对话框 → 操作员点击关闭 → 自动进入下一盘 setup。

操作员盘间应做：
- 检查 MatchModePanel 比分变化是否正确。
- 检查盘数已 +1。
- 我方上一盘获胜时，开局录入区会保留我方布局（"sticky"）；我方上一盘失利时，会清空我方布局让重新挑布局。
- 录入下一盘对方布局 → 确认开局 → 进入下一盘 playing。

**两盘中间不休息**（规则规定）。操作员动作要快。

## 6. 整轮结束

任一方先胜 4 盘后程序自动：
- 弹出"本轮结束！X 胜出，最终比分 …"。
- 不自动切回 debug（保留在最后一手 playing 阶段，方便保存棋谱）。

操作员动作：
1. 点"保存棋谱"按钮，命名为 `records/2026-05-DD/round-N-RvB.json`。
2. 检查 `replays/auto_save_match.json` 是否仍是本轮的完整数据，备份到 U 盘。
3. 等待裁判判罚 / 进入下一轮。

进入下一轮：
- 菜单 → 模式 → 比赛模式 → 弹"是否结束当前轮次并重新开始" → 选是 → 弹颜色 + 角色 → 新一轮。

## 7. 两场比赛之间

赛事规则允许：休息 ≤10 分钟，可调整程序与参数，不能换电脑（除非裁判许可）。

操作员可以做的事：
- 通过比赛模式弹窗调整单方时限（决赛加赛 10 分钟快棋时改 600）。
- 调 AI 参数（如有 release 配置文件）。

**禁止**：
- 改代码、装新依赖、跑 pytest（赛中机不动）。
- 联网。
- 任何会触发 GUI 崩溃风险的操作。

## 8. 赛后

1. **保存最后一轮棋谱** + 整理 `records/`。
2. **拷贝整个工作目录到 U 盘**（含 `.venv/`、`replays/auto_save_match.json`、`records/`）。
3. 拷贝 `replays/` 全部 JSON 备份用于复盘 / 申诉。
4. 关闭程序，关机。
5. 回家后跑一遍 `& ".venv/Scripts/python.exe" -m pytest`，对照赛前基线确认没有意外文件改动。

## 9. 命令速查

| 用途 | 命令 |
|---|---|
| 一键启动菜单 | 双击 `启动项目.cmd`，或 `& ".venv/Scripts/python.exe" "scripts/launcher.py"` |
| 赛前主检查 | `& ".venv/Scripts/python.exe" "scripts/preflight_check.py"` |
| 完整 pytest | `& ".venv/Scripts/python.exe" -m pytest -q` |
| 基础冒烟 | `& ".venv/Scripts/python.exe" "scripts/smoke_test.py"` |
| R-2 七盘制冒烟 | `& ".venv/Scripts/python.exe" "scripts/r2_smoke.py"` |
| S2 GUI 全流程演练 | `& ".venv/Scripts/python.exe" "scripts/s2_rehearsal.py"` |
| 启动 GUI（默认 4 分钟，仅提示超时） | `& ".venv/Scripts/python.exe" "scripts/run_gui.py"` |
| 启动 GUI（10 分钟决赛加赛） | `& ".venv/Scripts/python.exe" "scripts/run_gui.py" --total-seconds 600` |
| 启动 GUI（程序自动超时判负，裁判要求时才用） | `& ".venv/Scripts/python.exe" "scripts/run_gui.py" --auto-timeout` |
| AI 对战基线复测（仅家中） | `& ".venv/Scripts/python.exe" "scripts/quick_bench.py" --red greedy_risk --blue greedy --games 200 --seed 2026` |

## 10. 现场绝对禁止

- 联网（无线 / 有线 / 蓝牙）。
- 用其他电脑或 USB 加载未审计的文件。
- 比赛过程中修改程序源码。
- 不要在告知对方本方走法前进行下一步操作。
- 看到对方电脑屏幕的内容（规则要求双方有义务告知棋步，**不要**用偷看的）。
