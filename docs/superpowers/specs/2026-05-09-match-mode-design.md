# 比赛模式 / 调试模式双轨设计

日期：2026-05-09
关联任务：阶段 3 代码审查 Critical 3 修复（B1 + B2）
关联代码审查：见对话上下文

## 背景

当前 GUI 是双人手动操作模式：红蓝两方都在同一界面通过同一套交互（输入骰子 → 点棋子 → 点目标格）操作。这适合调试和两人面对面下棋，但不符合 PROJECT_PHASES.md 阶段 3"比赛模式提示"7 项要求暗示的实际比赛流程：

- 程序代表你方一方
- 你方回合：你录入骰子，给程序操作
- 对方回合：你看对方的实际走子，把骰子和走法录入到程序，让程序更新对盘面的认知

本次改造在保留调试模式（向后兼容）的前提下，新增比赛模式。

## 目标

1. 现有所有测试和 GUI 行为在调试模式下保持不变
2. 新增比赛模式入口、选边流程、对方回合提示
3. 棋谱字段扩展以记录每步的来源（self / opponent / unknown）
4. 把分散在 ControlPanel 的"比赛模式提示"7 项集中到独立的 MatchModePanel

## 非目标

- 不实现 AI 推荐走法（属阶段 4，本期 phase 显示 "未启用 AI" 占位）
- 不改 core 规则
- 不变更棋谱 JSON 现有字段（仅新增 source 字段，旧棋谱兼容）

## 核心状态

`MainWindow` 新增：

```python
self._mode: Literal["debug", "match"] = "debug"
self._our_side: Player | None = None  # 仅 match 模式有值
```

调试模式：现有逻辑不变。
比赛模式：根据 `state.current_player == _our_side` 区分"你方/对方"回合。

## 状态机（仅 match 模式）

```
state.current_player == _our_side（你方回合）
  ├─ _awaiting_dice → phase = "请录入骰子"
  └─ else → phase = "请选择走法"

state.current_player != _our_side（对方回合）
  ├─ _awaiting_dice → phase = "等待对方录入：请输入对方骰子"
  └─ else → phase = "等待对方录入：请点选对方走法"

winner != None → phase = "对局已结束"
```

棋盘点击交互在两种回合下完全相同（点棋子→点目标格）。差异仅在 phase 文字和棋谱 source 字段。

## GUI 元素

### 菜单栏

`MainWindow.__init__` 给 master 加 menubar：

```
文件 | 模式 ▾ | 帮助
       ├ 调试模式
       └ 比赛模式
```

切换菜单项触发 `_set_mode("debug" | "match")`。

### 选边弹窗

切到 match 模式时，弹一个 Tkinter `Toplevel`：

```
┌─────────────────────┐
│  你方使用：          │
│                     │
│  [ 红方 ]  [ 蓝方 ] │
└─────────────────────┘
```

用户点击后设置 `_our_side` 并切换到 match。中途取消则不切换。

### MatchModePanel（B2）

新模块 `gui/match_mode.py`，集中显示 7 项比赛提示：

1. 当前该谁操作（"红方（你方）" / "蓝方（对方）"）
2. 是否需要录入骰子（仅"对方阶段还没录骰子"时高亮）
3. 是否需要录入对方走法（对方阶段已录骰子但没录走法时高亮）
4. 当前可走棋子
5. 当前推荐走法（"未启用 AI"占位）
6. 是否可以悔棋
7. 当前棋谱是否已保存

调试模式下 MatchModePanel 显示简版（隐藏 #2 #3 的"对方"语义）。

ControlPanel 中已实现的 `phase_var`、`current_player_var`、`record_status_var` 在 B2 阶段迁出到 MatchModePanel。

## 棋谱字段扩展

`MoveRecord` 加字段：

```python
source: Literal["self", "opponent", "unknown"] = "unknown"
```

序列化时写入 `"source"` key。反序列化用 `data.get("source", "unknown")`，旧棋谱（无此字段）自动归类 unknown。

调试模式所有走法 `source = "unknown"`。
比赛模式根据 `current_player == _our_side` 决定 `"self"` / `"opponent"`。

## 实现拆分（每步独立 TDD）

### B1.1 — 模式状态 + 菜单 + 选边弹窗
- `MainWindow._mode`、`_our_side` 状态
- 菜单栏 wire-up
- 选边弹窗（用 `tk.Toplevel` 而非 simpledialog，便于测试）
- 调试模式行为完全不变

测试：
- 默认 `_mode == "debug"` 且 `_our_side is None`
- 切到 match 后 `_mode == "match"`，`_our_side` 是用户选的颜色
- 选边弹窗取消 → mode 保持 debug

### B1.2 — 比赛模式 phase 文字
- 扩展 `_compute_phase_label` 区分你方/对方
- 调试模式 phase 文字保持不变

测试：
- match + 你方 + 等骰子 → "请录入骰子"
- match + 对方 + 等骰子 → "等待对方录入：请输入对方骰子"
- debug 模式无论谁的回合 → "请录入骰子"（行为不变）

### B1.3 — MoveRecord 加 source 字段
- `MoveRecord` 加 `source` 字段
- `GameRecord.append` 接受 `source` 参数
- `MainWindow._apply_selected_move` 根据 mode/our_side 决定 source
- 旧棋谱反序列化兼容

测试：
- 调试模式 append 的 step source = "unknown"
- 比赛模式我方 append source = "self"
- 比赛模式对方 append source = "opponent"
- JSON 保存/加载保留 source
- 旧 JSON（无 source 字段）加载后默认 unknown

### B2 — 抽 MatchModePanel
- 新建 `gui/match_mode.py` 含 `MatchModePanel(tk.Frame)`
- 把 ControlPanel 的 `phase_var`、`current_player_var`、`record_status_var` 迁出
- ControlPanel 仅保留：骰子输入、合法走法列表、走法控制按钮（执行/悔棋/重置/保存/加载）、状态消息

测试：
- MatchModePanel 实例化不抛异常
- `set_phase` / `set_current_player` / `set_record_dirty` 等方法存在并更新对应 StringVar
- main_window._refresh 同时更新两个 panel

## 测试策略

- 所有现有测试保持过（调试模式行为不变）
- 每个 B1.x 都加对应单元测试
- 不引入 mock，直接用 Tk fixture
- 选边弹窗的取消路径用 monkeypatch 模拟用户选择，不依赖人工点击

## 风险与决策

- **MoveRecord frozen=True 含可变 dict 的问题**（审查报告 Minor 1）：本期不动，留 Minor 处理
- **菜单切换中途的状态保留**：从 match 切回 debug 时，棋盘和棋谱保留，仅 mode 和 our_side 重置。从 debug 切到 match 时，重置棋局（避免对方/你方归属混乱）
- **选边弹窗的模态性**：用 `transient` + `grab_set`，未选边时无法操作主窗口

## 验收

- 现有 60+ 测试全过
- 新增至少 10 个测试覆盖 B1.1-B1.3 + B2
- 手动验证：菜单切换、选边、对方回合录入、棋谱保存查看 source 字段
