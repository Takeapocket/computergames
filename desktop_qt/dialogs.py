"""Qt input forms; opening validation and layout files use the shared helpers."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from ai.opening_layouts import BLUE_ZONE, PRESETS, RED_ZONE, load_layout, save_layout, validate_layout
from core.types import Player, Position
from desktop_qt.board import position_label


class NewMatchDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建对局")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("单盘对局", "single")
        self.mode_combo.addItem("七盘制 · 先胜四盘", "match")
        self.side_combo = QComboBox()
        self.side_combo.addItem("红方", Player.RED)
        self.side_combo.addItem("蓝方", Player.BLUE)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["甲", "乙"])
        self.seconds_spin = QSpinBox()
        self.seconds_spin.setRange(1, 86400)
        self.seconds_spin.setValue(240)
        self.seconds_spin.setSuffix(" 秒")
        self.auto_timeout = QCheckBox("程序自动超时判负")
        self.auto_timeout.setChecked(False)
        form.addRow("对局模式", self.mode_combo)
        form.addRow("我方颜色", self.side_combo)
        form.addRow("我方身份", self.role_combo)
        form.addRow("每盘每方时限", self.seconds_spin)
        form.addRow(self.auto_timeout)
        layout.addLayout(form)
        note = QLabel("七盘制：甲方第 1、4、5 盘先手，乙方第 2、3、6、7 盘先手。\n默认只提示超时，手动判负须经裁判确认。确认开局后开始计时。")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("创建并设置开局")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self._mode_changed()

    def _mode_changed(self) -> None:
        self.role_combo.setEnabled(self.mode_combo.currentData() == "match")

    def options(self) -> dict:
        return {"mode": self.mode_combo.currentData(), "our_side": Player.from_value(self.side_combo.currentData()),
                "our_role": self.role_combo.currentText(), "total_seconds": self.seconds_spin.value(),
                "auto_timeout_enabled": self.auto_timeout.isChecked()}


class OpeningDialog(QDialog):
    def __init__(self, layouts_dir: Path, parent=None, *, first_player: Player = Player.RED,
                 fixed_first: bool = False, our_side: Player | None = None,
                 retained_our_layout=None, preset_id: str = "balanced_v1") -> None:
        super().__init__(parent)
        self.layouts_dir = Path(layouts_dir)
        self.layout_id = preset_id
        self.selected_preset_id = preset_id
        self._applying = False
        self._match_opening = fixed_first
        self.setWindowTitle("确认双方开局")
        self.setMinimumWidth(470)
        layout = QVBoxLayout(self)
        hint = QLabel("按棋盘位置填入双方棋子编号。每方必须恰好使用 1–6，不能重复。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        preset_row = QHBoxLayout()
        self.preset_combo = QComboBox()
        for key, preset in PRESETS.items():
            self.preset_combo.addItem(preset.name, key)
        self.preset_combo.addItem("自定义布局", None)
        preset_row.addWidget(self.preset_combo, 1)
        self.load_button = QPushButton("加载布局")
        self.save_button = QPushButton("保存布局")
        self.load_button.clicked.connect(self._load_dialog)
        self.save_button.clicked.connect(self._save_layout)
        preset_row.addWidget(self.load_button)
        preset_row.addWidget(self.save_button)
        layout.addLayout(preset_row)
        grid = QGridLayout()
        self.cells: dict[Player, dict[Position, QSpinBox]] = {Player.RED: {}, Player.BLUE: {}}
        for row in range(5):
            for col in range(5):
                position = Position(row, col)
                player = Player.RED if position in RED_ZONE else Player.BLUE if position in BLUE_ZONE else None
                if player is None:
                    cell = QLabel("·")
                    cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    grid.addWidget(cell, row, col)
                    continue
                box = QVBoxLayout()
                label = QLabel(position_label(position))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spin = QSpinBox()
                spin.setRange(0, 6)
                spin.setSpecialValueText("待填")
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spin.setAccessibleName(f"{'红方' if player is Player.RED else '蓝方'} {position_label(position)} 棋子编号")
                spin.setStyleSheet(f"QSpinBox {{ color: {'#B4483F' if player is Player.RED else '#4368A0'}; font-size: 20px; padding: 6px; }}")
                spin.valueChanged.connect(self._edited)
                self.cells[player][position] = spin
                box.addWidget(label)
                box.addWidget(spin)
                grid.addLayout(box, row, col)
        layout.addLayout(grid)
        first_row = QFormLayout()
        self.first_combo = QComboBox()
        self.first_combo.addItem("红方先手", Player.RED)
        self.first_combo.addItem("蓝方先手", Player.BLUE)
        self.first_combo.setCurrentIndex(0 if first_player is Player.RED else 1)
        self.first_combo.setEnabled(not fixed_first)
        first_row.addRow("本盘先手" + ("（按七盘制顺序）" if fixed_first else ""), self.first_combo)
        layout.addLayout(first_row)
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确认开局并开始计时")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("暂不开始")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.preset_combo.currentIndexChanged.connect(self._preset_changed)
        preset = PRESETS[preset_id]
        red, blue = preset.red, preset.blue
        if fixed_first and our_side is not None:
            if our_side is Player.RED:
                red, blue = retained_our_layout or red, {}
            else:
                red, blue = {}, retained_our_layout or blue
            hint.setText("比赛开局：对方每盘需要重新录入。我方上盘获胜时沿用上一盘实际布局。切换预设会填入双方示例，请核对实际摆法。")
        self.set_layout(red, blue, "custom" if fixed_first else preset_id)

    def set_layout(self, red, blue, layout_id: str = "custom") -> None:
        self._applying = True
        for player, values in ((Player.RED, red), (Player.BLUE, blue)):
            for spin in self.cells[player].values():
                spin.setValue(0)
            for piece_id, position in values.items():
                self.cells[player][position].setValue(piece_id)
        self.layout_id = layout_id
        if layout_id in PRESETS:
            self.selected_preset_id = layout_id
        self.preset_combo.setCurrentIndex(self.preset_combo.findData(layout_id) if layout_id in PRESETS else self.preset_combo.count() - 1)
        self._applying = False
        self._validate()

    def layouts(self):
        return tuple({spin.value(): position for position, spin in self.cells[player].items() if spin.value() > 0}
                     for player in (Player.RED, Player.BLUE))

    def _edited(self) -> None:
        if not self._applying:
            self.layout_id = "custom"
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)
            self.preset_combo.blockSignals(False)
            self._validate()

    def _validate(self) -> bool:
        errors = validate_layout(*self.layouts())
        valid = not errors
        message = "布局有效 · 请核对双方实际摆法，再确认开局。" if self._match_opening else "布局有效 · 双方编号齐全，可确认开局。"
        self.validation_label.setText(message if valid else "编号重复、缺失或待填：每方请使用完整的 1–6。")
        self.validation_label.setStyleSheet(f"color: {'#0F766E' if valid else '#B4483F'};")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)
        self.save_button.setEnabled(valid)
        return valid

    def _preset_changed(self) -> None:
        key = self.preset_combo.currentData()
        if not self._applying and key is not None:
            preset = PRESETS[key]
            self.set_layout(preset.red, preset.blue, key)

    def accept(self) -> None:
        if self._validate():
            super().accept()

    def _save_layout(self) -> None:
        if not self._validate():
            return
        layout_id = "custom_" + uuid4().hex[:12]
        try:
            save_layout(layout_id, *self.layouts(), name="自定义布局", directory=self.layouts_dir)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "布局保存失败", str(exc))
            return
        self.layout_id = layout_id
        self.validation_label.setText(f"布局已保存：{layout_id}.json")
        self.validation_label.setToolTip(str(self.layouts_dir / f"{layout_id}.json"))

    def _load_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "加载自定义布局", str(self.layouts_dir), "JSON 布局 (*.json)")
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path) -> bool:
        try:
            preset = load_layout(path.stem, directory=path.parent)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "布局加载失败", str(exc))
            return False
        self.set_layout(preset.red, preset.blue, preset.id)
        return True
