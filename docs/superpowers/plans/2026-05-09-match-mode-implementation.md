# 比赛模式 / 调试模式双轨实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留调试模式的前提下，新增比赛模式入口、选边流程、对方回合提示、棋谱来源标记，并把"比赛模式提示"集中到独立 MatchModePanel。

**Architecture:** MainWindow 引入 `_mode` 和 `_our_side` 状态。调试模式行为完全不变（向后兼容）；比赛模式根据 `state.current_player == _our_side` 区分你方/对方回合，phase 文字和棋谱 source 字段相应变化。新增 `gui/match_mode.py` 集中 7 项比赛提示。

**Tech Stack:** Python 3.11、Tkinter、pytest。

**关联设计 spec：** `docs/superpowers/specs/2026-05-09-match-mode-design.md`

**项目工程约束（来自 AGENTS.md）：**
- 未经用户明确要求不执行 `git commit` / `git push`。本 plan 的 "Commit" 步骤标注为"等用户确认时机"，executing-plans 不应自动跑 commit
- 测试用 `.venv/Scripts/python.exe -m pytest`
- 不能在没有验证输出的情况下声称"完成"

---

## 文件结构

**新建：**
- `gui/match_mode.py` — `MatchModePanel(tk.Frame)`，集中 7 项比赛模式提示

**修改：**
- `gui/main_window.py` — 加 `_mode`、`_our_side`、菜单栏、选边弹窗、对方回合处理、source 字段写入
- `gui/control_panel.py` — B2 时把 phase / current_player / record_status 迁出到 MatchModePanel
- `record/game_record.py` — `MoveRecord` 加 `source` 字段，`append` 接受 `source`
- `tests/test_main_window.py` — 加 B1.1/B1.2/B1.3/B2 测试
- `tests/test_game_record.py` — 加 source 字段相关测试

---

## Task B1.1: 模式状态 + 菜单 + 选边弹窗

**目标：** MainWindow 拥有 `_mode` 和 `_our_side` 状态；菜单栏可切换；切到 match 时弹选边窗。调试模式行为完全不变。

**Files:**
- Modify: `gui/main_window.py`
- Test: `tests/test_main_window.py`

### Step 1: 写失败测试 — 默认 mode 是 debug

- [ ] 在 `tests/test_main_window.py` 末尾追加：

```python
def test_default_mode_is_debug(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert window._mode == "debug"
    assert window._our_side is None


def test_set_mode_to_match_with_red_side(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    window._set_mode("match", our_side=Player.RED)

    assert window._mode == "match"
    assert window._our_side is Player.RED


def test_set_mode_to_match_with_blue_side(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    window._set_mode("match", our_side=Player.BLUE)

    assert window._our_side is Player.BLUE


def test_set_mode_back_to_debug_clears_our_side(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.RED)

    window._set_mode("debug")

    assert window._mode == "debug"
    assert window._our_side is None
```

文件顶部已有 `from gui.main_window import MainWindow`，需要再加 `from core.types import Player`：

```python
from core.types import Player
```

### Step 2: 跑测试看失败

- [ ] 命令：`.venv/Scripts/python.exe -m pytest tests/test_main_window.py -k "mode" -v`
- [ ] 预期：4 个 fail，AttributeError: `_mode` / `_set_mode` 不存在

### Step 3: 写实现

- [ ] 在 `gui/main_window.py` 顶部 import 区追加：

```python
from typing import Literal
```

- [ ] 在 `MainWindow.__init__` 末尾（在 `_schedule_timer_refresh()` 之前）追加：

```python
        self._mode: Literal["debug", "match"] = "debug"
        self._our_side: Player | None = None
```

- [ ] 在类末尾追加方法：

```python
    def _set_mode(self, mode: Literal["debug", "match"], *, our_side: Player | None = None) -> None:
        if mode == "match" and our_side is None:
            raise ValueError("match mode requires our_side")
        self._mode = mode
        self._our_side = our_side if mode == "match" else None
        self._refresh()
```

### Step 4: 跑测试看通过

- [ ] 命令：`.venv/Scripts/python.exe -m pytest -v`
- [ ] 预期：62 + 4 = 66 个全过

### Step 5: 写菜单栏 + 选边弹窗的失败测试

- [ ] 追加测试：

```python
def test_main_window_creates_menu_with_mode_options(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    menubar = tk_root.nametowidget(tk_root["menu"])
    mode_menu_index = menubar.index("模式")
    assert mode_menu_index is not None  # 菜单存在则不抛异常


def test_pick_side_dialog_returns_red_when_red_chosen(tk_root, monkeypatch):
    from gui.main_window import MainWindow

    window = MainWindow(tk_root)
    window.pack()

    monkeypatch.setattr(window, "_show_pick_side_dialog", lambda: Player.RED)
    window._enter_match_mode()

    assert window._mode == "match"
    assert window._our_side is Player.RED


def test_pick_side_dialog_cancel_keeps_debug_mode(tk_root, monkeypatch):
    window = MainWindow(tk_root)
    window.pack()

    monkeypatch.setattr(window, "_show_pick_side_dialog", lambda: None)
    window._enter_match_mode()

    assert window._mode == "debug"
    assert window._our_side is None
```

### Step 6: 跑测试看失败

- [ ] 命令：`.venv/Scripts/python.exe -m pytest tests/test_main_window.py -k "menu or pick_side" -v`
- [ ] 预期：3 个 fail（菜单不存在 / `_enter_match_mode` 不存在 / `_show_pick_side_dialog` 不存在）

### Step 7: 写菜单 + 弹窗实现

- [ ] 在 `MainWindow.__init__` 头部 `super().__init__(...)` 之后、其它代码之前加菜单栏。直接修改文件：

将 `__init__` 的开头部分（从 `super().__init__(master, padx=16, pady=16)` 起）改为：

```python
        super().__init__(master, padx=16, pady=16)
        self._build_menu(master)
```

- [ ] 在类末尾追加：

```python
    def _build_menu(self, master: tk.Misc) -> None:
        if not isinstance(master, (tk.Tk, tk.Toplevel)):
            return
        menubar = tk.Menu(master)
        master.config(menu=menubar)

        mode_menu = tk.Menu(menubar, tearoff=0)
        mode_menu.add_command(label="调试模式", command=lambda: self._set_mode("debug"))
        mode_menu.add_command(label="比赛模式", command=self._enter_match_mode)
        menubar.add_cascade(label="模式", menu=mode_menu)

    def _enter_match_mode(self) -> None:
        chosen = self._show_pick_side_dialog()
        if chosen is None:
            return
        self._set_mode("match", our_side=chosen)

    def _show_pick_side_dialog(self) -> Player | None:
        dialog = tk.Toplevel(self)
        dialog.title("选择我方颜色")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        result: dict[str, Player | None] = {"side": None}

        tk.Label(dialog, text="你方使用：", padx=20, pady=10).pack()
        button_row = tk.Frame(dialog)
        button_row.pack(padx=20, pady=(0, 16))

        def choose(player: Player) -> None:
            result["side"] = player
            dialog.destroy()

        tk.Button(button_row, text="红方", width=10, command=lambda: choose(Player.RED)).pack(side=tk.LEFT, padx=4)
        tk.Button(button_row, text="蓝方", width=10, command=lambda: choose(Player.BLUE)).pack(side=tk.LEFT, padx=4)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.wait_window(dialog)
        return result["side"]
```

### Step 8: 跑测试看通过

- [ ] 命令：`.venv/Scripts/python.exe -m pytest -v`
- [ ] 预期：69 全过（66 + 3 新加）

### Step 9: 标记完成

- [ ] TaskUpdate B1.1 status=completed
- [ ] Commit 由用户决定时机

---

## Task B1.2: 比赛模式 phase 文字（你方 / 对方）

**目标：** `_compute_phase_label` 在 match 模式下区分你方/对方，调试模式不变。

**Files:**
- Modify: `gui/main_window.py:_compute_phase_label`
- Test: `tests/test_main_window.py`

### Step 1: 写失败测试

- [ ] 追加：

```python
def test_phase_in_match_my_turn_awaiting_dice(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.RED)

    assert window._awaiting_dice is True
    assert "请录入骰子" in window.controls.phase_var.get()
    assert "等待对方" not in window.controls.phase_var.get()


def test_phase_in_match_opponent_turn_awaiting_dice(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.BLUE)

    assert window.state.current_player is Player.RED
    assert "等待对方" in window.controls.phase_var.get()
    assert "骰子" in window.controls.phase_var.get()


def test_phase_in_match_opponent_turn_after_dice_input(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.BLUE)
    window._handle_dice_change("3")

    assert "等待对方" in window.controls.phase_var.get()
    assert "走法" in window.controls.phase_var.get()


def test_phase_in_debug_mode_does_not_use_opponent_text(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    # debug 默认模式

    assert "等待对方" not in window.controls.phase_var.get()
```

### Step 2: 跑测试看失败

- [ ] 命令：`.venv/Scripts/python.exe -m pytest tests/test_main_window.py -k "phase_in" -v`
- [ ] 预期：3 个 fail（"等待对方" 不在 phase_var 文字里），1 个 pass（debug 不变）

### Step 3: 写实现

- [ ] 替换 `_compute_phase_label`：

```python
    def _compute_phase_label(self, winner: Player | None) -> str:
        if winner is not None:
            return "对局已结束"
        if self._mode == "match" and self._our_side is not None and self.state.current_player is not self._our_side:
            if self._awaiting_dice:
                return "等待对方录入：请输入对方骰子"
            return "等待对方录入：请点选对方走法"
        if self._awaiting_dice:
            return "请录入骰子"
        return "请选择走法"
```

### Step 4: 跑测试看通过

- [ ] 命令：`.venv/Scripts/python.exe -m pytest -v`
- [ ] 预期：73 全过（69 + 4 新加）

### Step 5: 标记完成

- [ ] TaskUpdate B1.2 status=completed

---

## Task B1.3: MoveRecord 加 source 字段

**目标：** `MoveRecord` 加 `source: Literal["self","opponent","unknown"]`；`GameRecord.append` 接受；JSON 双向兼容；MainWindow 根据 mode/our_side 决定 source。

**Files:**
- Modify: `record/game_record.py`
- Modify: `gui/main_window.py:_apply_selected_move`
- Test: `tests/test_game_record.py`
- Test: `tests/test_main_window.py`

### Step 1: 写 record 层失败测试

- [ ] 在 `tests/test_game_record.py` 末尾追加：

```python
def test_append_records_source_self():
    state = GameState.from_layout(red=DEFAULT_RED_LAYOUT, blue=DEFAULT_BLUE_LAYOUT, current_player=Player.RED)
    record = GameRecord.from_state(state)
    moves = state.legal_moves(Player.RED, 6)
    move = state.apply_move(moves[0], dice=6)

    record.append(dice=6, move=move, state_after=state, source="self")

    assert record.steps[-1].source == "self"


def test_append_records_source_opponent():
    state = GameState.from_layout(red=DEFAULT_RED_LAYOUT, blue=DEFAULT_BLUE_LAYOUT, current_player=Player.RED)
    record = GameRecord.from_state(state)
    moves = state.legal_moves(Player.RED, 6)
    move = state.apply_move(moves[0], dice=6)

    record.append(dice=6, move=move, state_after=state, source="opponent")

    assert record.steps[-1].source == "opponent"


def test_append_default_source_is_unknown():
    state = GameState.from_layout(red=DEFAULT_RED_LAYOUT, blue=DEFAULT_BLUE_LAYOUT, current_player=Player.RED)
    record = GameRecord.from_state(state)
    moves = state.legal_moves(Player.RED, 6)
    move = state.apply_move(moves[0], dice=6)

    record.append(dice=6, move=move, state_after=state)

    assert record.steps[-1].source == "unknown"


def test_json_round_trip_preserves_source():
    state = GameState.from_layout(red=DEFAULT_RED_LAYOUT, blue=DEFAULT_BLUE_LAYOUT, current_player=Player.RED)
    record = GameRecord.from_state(state)
    moves = state.legal_moves(Player.RED, 6)
    move = state.apply_move(moves[0], dice=6)
    record.append(dice=6, move=move, state_after=state, source="self")

    restored = GameRecord.from_json(record.to_json())

    assert restored.steps[-1].source == "self"


def test_from_dict_legacy_record_without_source_defaults_to_unknown():
    state = GameState.from_layout(red=DEFAULT_RED_LAYOUT, blue=DEFAULT_BLUE_LAYOUT, current_player=Player.RED)
    record = GameRecord.from_state(state)
    moves = state.legal_moves(Player.RED, 6)
    move = state.apply_move(moves[0], dice=6)
    record.append(dice=6, move=move, state_after=state)

    raw = record.to_dict()
    for step in raw["steps"]:
        step.pop("source", None)

    restored = GameRecord.from_dict(raw)

    assert restored.steps[-1].source == "unknown"
```

注意：`tests/test_game_record.py` 里应该已经有 `DEFAULT_RED_LAYOUT` / `DEFAULT_BLUE_LAYOUT` 或类似 fixtures。如果没有，从 `gui/app.py` import。先 grep 确认：

```bash
grep -n "DEFAULT_RED_LAYOUT\|from_layout" tests/test_game_record.py
```

如果没有，在测试文件顶部加：

```python
from gui.app import DEFAULT_RED_LAYOUT, DEFAULT_BLUE_LAYOUT
```

### Step 2: 跑 record 测试看失败

- [ ] 命令：`.venv/Scripts/python.exe -m pytest tests/test_game_record.py -k "source" -v`
- [ ] 预期：5 个全 fail（TypeError: append got unexpected `source` / AttributeError: MoveRecord has no `source`）

### Step 3: 写 record 实现

- [ ] 在 `record/game_record.py` 顶部 import 区加：

```python
from typing import Literal
```

- [ ] 修改 `MoveRecord` dataclass，加字段（放到 remaining_seconds 之后）：

```python
    source: Literal["self", "opponent", "unknown"] = "unknown"
```

- [ ] 修改 `GameRecord.append` 签名，加参数（默认 unknown）：

```python
    def append(
        self,
        *,
        dice: int,
        move: Move,
        state_after: GameState,
        step_seconds: float = 0.0,
        remaining_seconds: dict[Player, float] | None = None,
        source: Literal["self", "opponent", "unknown"] = "unknown",
    ) -> None:
```

并在 append 内部构造 MoveRecord 时传入：

```python
        self.steps.append(
            MoveRecord(
                turn=len(self.steps) + 1,
                player=move.player,
                dice=dice,
                move=move,
                state_after=state_after.serialize(),
                step_seconds=step_seconds,
                remaining_seconds=remaining_seconds or {},
                source=source,
            )
        )
```

（实际函数体可能略有不同，按文件现状改。读 `record/game_record.py` 里 `append` 当前实现，对应位置加 source 字段）

- [ ] `MoveRecord.to_dict`（如果有这个方法）或 `GameRecord.to_dict` 内部构造 dict 的代码，加 `"source": step.source`
- [ ] `from_dict` 里反序列化 step 时用 `source=data.get("source", "unknown")`

### Step 4: 跑 record 测试看通过

- [ ] 命令：`.venv/Scripts/python.exe -m pytest tests/test_game_record.py -v`
- [ ] 预期：原 12 + 5 = 17 全过

### Step 5: 写 main_window 失败测试

- [ ] 在 `tests/test_main_window.py` 末尾追加：

```python
def test_apply_move_records_source_self_in_match_mode_my_turn(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.RED)
    moves = window._current_moves()
    window.selected_move_index = 0

    window._apply_selected_move()

    assert window.record.steps[-1].source == "self"


def test_apply_move_records_source_opponent_in_match_mode_opponent_turn(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    window._set_mode("match", our_side=Player.BLUE)
    moves = window._current_moves()
    window.selected_move_index = 0

    window._apply_selected_move()

    assert window.record.steps[-1].source == "opponent"


def test_apply_move_records_source_unknown_in_debug_mode(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    moves = window._current_moves()
    window.selected_move_index = 0

    window._apply_selected_move()

    assert window.record.steps[-1].source == "unknown"
```

### Step 6: 跑 main_window 测试看失败

- [ ] 命令：`.venv/Scripts/python.exe -m pytest tests/test_main_window.py -k "source" -v`
- [ ] 预期：3 个 fail（source 一直是 unknown 因为 _apply_selected_move 没传 source）

### Step 7: 写 main_window 实现

- [ ] 修改 `_apply_selected_move`，把 record.append 调用改成：

```python
        self.record.append(
            dice=self.current_dice,
            move=move,
            state_after=self.state,
            step_seconds=step_seconds,
            remaining_seconds=remaining_seconds,
            source=self._move_source(move.player),
        )
```

- [ ] 在类末尾追加：

```python
    def _move_source(self, mover: Player) -> Literal["self", "opponent", "unknown"]:
        if self._mode != "match" or self._our_side is None:
            return "unknown"
        return "self" if mover is self._our_side else "opponent"
```

注意：`move` 在 `apply_move` 之后 `state.current_player` 已经切到下一家，所以判断要用 `move.player`（已走子的一方），而非 `self.state.current_player`。

### Step 8: 跑全量回归

- [ ] 命令：`.venv/Scripts/python.exe -m pytest -v`
- [ ] 预期：原 73 + 5 record + 3 main_window = 81 全过

### Step 9: 标记完成

- [ ] TaskUpdate B1.3 status=completed

---

## Task B2: 抽出 MatchModePanel

**目标：** 新建 `gui/match_mode.py` 含 `MatchModePanel(tk.Frame)`，把 ControlPanel 中的 `phase_var`、`current_player_var`、`record_status_var` 迁出。ControlPanel 仅保留骰子输入、走法列表、操作按钮。

**Files:**
- Create: `gui/match_mode.py`
- Modify: `gui/control_panel.py` — 移除迁出的 var、相关 Label、setter
- Modify: `gui/main_window.py` — 实例化 MatchModePanel，分发更新
- Test: `tests/test_main_window.py`

### Step 1: 写失败测试

- [ ] 在 `tests/test_main_window.py` 末尾追加：

```python
def test_main_window_has_match_mode_panel(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert hasattr(window, "match_mode_panel")
    from gui.match_mode import MatchModePanel
    assert isinstance(window.match_mode_panel, MatchModePanel)


def test_match_mode_panel_displays_current_player(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "红方" in window.match_mode_panel.current_player_var.get()


def test_match_mode_panel_displays_phase(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "请录入骰子" in window.match_mode_panel.phase_var.get()


def test_match_mode_panel_displays_record_status(tk_root):
    window = MainWindow(tk_root)
    window.pack()

    assert "已保存" in window.match_mode_panel.record_status_var.get()


def test_match_mode_panel_record_status_changes_on_apply(tk_root):
    window = MainWindow(tk_root)
    window.pack()
    moves = window._current_moves()
    window.selected_move_index = 0
    window._apply_selected_move()

    assert "未保存" in window.match_mode_panel.record_status_var.get()
```

### Step 2: 跑测试看失败

- [ ] 命令：`.venv/Scripts/python.exe -m pytest tests/test_main_window.py -k "match_mode_panel" -v`
- [ ] 预期：5 个 fail（AttributeError: window has no `match_mode_panel`，ImportError: gui.match_mode）

### Step 3: 创建 MatchModePanel

- [ ] 创建 `gui/match_mode.py`：

```python
from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence


class MatchModePanel(tk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padx=16, pady=8, borderwidth=1, relief="solid")

        self.current_player_var = tk.StringVar(value="当前行动方：-")
        self.phase_var = tk.StringVar(value="当前阶段：请录入骰子")
        self.selected_pieces_var = tk.StringVar(value="可走棋子：-")
        self.recommendation_var = tk.StringVar(value="推荐走法：未启用 AI")
        self.record_status_var = tk.StringVar(value="棋谱状态：✓ 已保存")
        self.can_undo_var = tk.StringVar(value="悔棋：不可用")

        tk.Label(self, textvariable=self.current_player_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.phase_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.selected_pieces_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.recommendation_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.record_status_var, anchor="w").pack(fill=tk.X)
        tk.Label(self, textvariable=self.can_undo_var, anchor="w").pack(fill=tk.X)

    def set_current_player(self, value: str) -> None:
        self.current_player_var.set(f"当前行动方：{value}")

    def set_phase(self, phase_label: str) -> None:
        self.phase_var.set(f"当前阶段：{phase_label}")

    def set_selected_pieces(self, piece_ids: Sequence[int]) -> None:
        value = "、".join(str(pid) for pid in piece_ids) if piece_ids else "-"
        self.selected_pieces_var.set(f"可走棋子：{value}")

    def set_recommendation(self, text: str) -> None:
        self.recommendation_var.set(f"推荐走法：{text}")

    def set_record_dirty(self, dirty: bool) -> None:
        self.record_status_var.set("棋谱状态：● 未保存" if dirty else "棋谱状态：✓ 已保存")

    def set_can_undo(self, enabled: bool) -> None:
        self.can_undo_var.set("悔棋：可用" if enabled else "悔棋：不可用")
```

### Step 4: 修改 ControlPanel 移除迁出的内容

- [ ] 在 `gui/control_panel.py` 删除：
  - `self.current_player_var` 及其 Label
  - `self.phase_var` 及其 Label
  - `self.selected_pieces_var` 及其 Label
  - `self.record_status_var` 及其 Label
  - `set_current_player`、`set_phase`、`set_selected_pieces`、`set_record_dirty` 方法

- [ ] 保留：dice spinbox、move listbox、apply/undo/reset/save/load 按钮、winner 标签、status 标签、`set_can_apply` / `set_can_undo`

### Step 5: 修改 MainWindow 实例化 MatchModePanel

- [ ] 在 `gui/main_window.py` 顶部加 import：

```python
from gui.match_mode import MatchModePanel
```

- [ ] 在 `__init__` 中 `self.timer_panel.pack(...)` 之后、`self.controls = ControlPanel(...)` 之前插入：

```python
        self.match_mode_panel = MatchModePanel(side_panel)
        self.match_mode_panel.pack(fill=tk.X, pady=(0, 8))
```

- [ ] 修改 `_refresh`，把对 `self.controls.set_current_player/set_selected_pieces/set_phase/set_record_dirty/set_can_undo` 的调用改成对应 `self.match_mode_panel.xxx`。`set_can_undo` 可以同时调两边（按钮在 controls，提示在 panel），但如果 ControlPanel 仍持有 `undo_button`，则 set_can_undo 留在 controls，panel 也加一个仅显示文字状态的 set_can_undo。

具体地，新的 `_refresh` 末尾应类似：

```python
        self.match_mode_panel.set_current_player(player_label(self.state.current_player))
        self.match_mode_panel.set_selected_pieces(selected_ids)
        self.match_mode_panel.set_phase(self._compute_phase_label(winner))
        self.match_mode_panel.set_record_dirty(self._record_dirty)
        self.match_mode_panel.set_can_undo(bool(self.state.history))
        self.controls.set_dice(self.current_dice)
        self.controls.set_moves(move_labels, self.selected_move_index)
        self.controls.set_winner(player_label(winner) if winner is not None else "未结束")
        self.controls.set_status(self.status_message)
        self.controls.set_can_apply(winner is None and self.selected_move_index is not None)
        self.controls.set_can_undo(bool(self.state.history))
        self.timer_panel.set_snapshot(self.timer.snapshot())
        self.board.set_state(...)
```

### Step 6: 跑测试看通过

- [ ] 命令：`.venv/Scripts/python.exe -m pytest -v`
- [ ] 预期：原 81 + 5 = 86 全过。如果之前的 record_dirty / phase / current_player 测试断言的是 `controls.xxx_var`，需要改成 `match_mode_panel.xxx_var`。

实际上 B2 会破坏 A3/A4 的测试（它们断言 `window.controls.record_status_var` / `window.controls.phase_var`）。需要更新这些测试改为断言 `window.match_mode_panel.xxx`。

具体要更新的测试：
- `test_record_dirty_false_on_fresh_window`
- `test_record_dirty_true_after_apply`
- `test_phase_starts_in_awaiting_dice`
- `test_phase_after_dice_input_is_select`
- `test_phase_returns_to_awaiting_dice_after_apply`
- `test_phase_in_match_my_turn_awaiting_dice`（B1.2 加的）
- `test_phase_in_match_opponent_turn_awaiting_dice`（B1.2 加的）
- `test_phase_in_match_opponent_turn_after_dice_input`（B1.2 加的）
- `test_phase_in_debug_mode_does_not_use_opponent_text`（B1.2 加的）

把这些测试里的 `window.controls.phase_var` / `record_status_var` 改为 `window.match_mode_panel.phase_var` / `record_status_var`。

### Step 7: 跑全量回归

- [ ] 命令：`.venv/Scripts/python.exe -m pytest -v`
- [ ] 预期：86 全过

### Step 8: 标记完成

- [ ] TaskUpdate B2 status=completed

---

## 完成后

- 启动 GUI 手动验证：
  ```bash
  .venv/Scripts/python.exe scripts/run_gui.py
  ```
  - 默认进入调试模式，行为同改造前
  - 菜单 → 比赛模式 → 弹窗选红方 → phase 显示"请录入骰子"
  - 入红方比赛模式后切到对方回合（apply 一手），phase 应显示"等待对方录入"
  - 保存棋谱到 records/，打开 JSON 检查每个 step 含 `"source"` 字段

- 询问用户是否 commit B 组改动，征得许可后 commit

---

## Self-Review 结果

- ✓ Spec 覆盖：B1.1 状态/菜单/弹窗、B1.2 phase 文字、B1.3 source 字段、B2 MatchModePanel 全部对应任务
- ✓ 无 placeholder：所有代码块都是完整可运行的代码
- ✓ 类型一致：`Player` / `Literal["self","opponent","unknown"]` / `_mode` / `_our_side` 命名贯穿
- ✓ 调试模式向后兼容：每个 task 测试都覆盖"debug 模式行为不变"的断言
