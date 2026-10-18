"""A scalable board view; legality and state changes remain outside the widget."""
from __future__ import annotations

from math import atan2, cos, sin

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from core.game_state import GameState
from core.move import Move
from core.types import Player, Position
from desktop_qt.theme import BLUE, RED, TEAL


def position_label(position: Position) -> str:
    """Display coordinates only; saved records retain core's zero-based positions."""
    return f"{chr(ord('A') + position.col)}{position.row + 1}"


def move_label(move: Move) -> str:
    capture = ""
    if move.is_capture:
        own = move.captured_piece is not None and move.captured_piece.player is move.player
        capture = " · 自吃" if own else " · 吃子"
    return f"{move.piece_id}号  {position_label(move.from_pos)} → {position_label(move.to_pos)}{capture}"


class BoardWidget(QWidget):
    square_clicked = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: GameState | None = None
        self.legal_moves: list[Move] = []
        self.selected_move: Move | None = None
        self.recommendation: Move | None = None
        self.last_move: Move | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(340, 340)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("爱恩斯坦棋棋盘，横坐标 A 至 E，纵坐标 1 至 5")

    def sizeHint(self) -> QSize:
        return QSize(570, 490)

    def board_rect(self) -> QRectF:
        side = max(1.0, min(self.width() - 62.0, self.height() - 46.0))
        return QRectF((self.width() - side) / 2 + 9, (self.height() - side) / 2 + 9, side, side)

    def cell_rect(self, position: Position) -> QRectF:
        board = self.board_rect()
        cell = board.width() / 5
        return QRectF(board.x() + position.col * cell, board.y() + position.row * cell, cell, cell)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        board = self.board_rect()
        point = event.position()
        if board.contains(point):
            col = min(4, int((point.x() - board.x()) / (board.width() / 5)))
            row = min(4, int((point.y() - board.y()) / (board.height() / 5)))
            self.square_clicked.emit(row, col)

    def paintEvent(self, event: object) -> None:
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            board = self.board_rect()
            cell = board.width() / 5
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor("#8A98A1"))
            for index in range(5):
                painter.drawText(QRectF(board.x() + index * cell, board.y() - 28, cell, 22),
                                 Qt.AlignmentFlag.AlignCenter, chr(ord("A") + index))
                painter.drawText(QRectF(board.x() - 28, board.y() + index * cell, 22, cell),
                                 Qt.AlignmentFlag.AlignCenter, str(index + 1))
            selected_origin = self.selected_move.from_pos if self.selected_move else None
            targets = {move.to_pos for move in self.legal_moves
                       if selected_origin is None or move.from_pos == selected_origin}
            origins = {move.from_pos for move in self.legal_moves}
            for row in range(5):
                for col in range(5):
                    position = Position(row, col)
                    rect = self.cell_rect(position).adjusted(1.5, 1.5, -1.5, -1.5)
                    color = "#F7F8FA" if (row + col) % 2 == 0 else "#E9EEF0"
                    if self.last_move and position in (self.last_move.from_pos, self.last_move.to_pos):
                        color = "#E5EBE8"
                    if position in targets:
                        color = "#D4EAE3"
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(color))
                    painter.drawRoundedRect(rect, 7, 7)
                    if position == selected_origin:
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.setPen(QPen(QColor(TEAL), 2))
                        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)
                    if self.state is None:
                        continue
                    piece = self.state.piece_at(position)
                    if piece is None:
                        if position in targets:
                            painter.setPen(Qt.PenStyle.NoPen)
                            painter.setBrush(QColor("#5AA596"))
                            painter.drawEllipse(rect.center(), cell * .055, cell * .055)
                        continue
                    inset = cell * .18
                    tile = self.cell_rect(position).adjusted(inset, inset, -inset, -inset)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(15, 30, 40, 24))
                    painter.drawRoundedRect(tile.translated(0, 3), cell * .13, cell * .13)
                    painter.setBrush(QColor(RED if piece.player is Player.RED else BLUE))
                    painter.drawRoundedRect(tile, cell * .13, cell * .13)
                    painter.setPen(QPen(QColor(255, 255, 255, 75), 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(tile.adjusted(3, 3, -3, -3), cell * .10, cell * .10)
                    font = QFont("Segoe UI")
                    font.setPixelSize(round(cell * .31))
                    font.setWeight(QFont.Weight.DemiBold)
                    painter.setFont(font)
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(tile, Qt.AlignmentFlag.AlignCenter, str(piece.piece_id))
                    if position in origins:
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor(TEAL))
                        painter.drawEllipse(QPointF(tile.right() + 4, tile.top() - 2), 3.5, 3.5)
            if self.recommendation is not None:
                start = self.cell_rect(self.recommendation.from_pos).center()
                finish = self.cell_rect(self.recommendation.to_pos).center()
                angle = atan2(finish.y() - start.y(), finish.x() - start.x())
                start += QPointF(cos(angle) * cell * .27, sin(angle) * cell * .27)
                finish -= QPointF(cos(angle) * cell * .17, sin(angle) * cell * .17)
                painter.setPen(QPen(QColor("#FFFFFF"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(start, finish)
                painter.setPen(QPen(QColor(TEAL), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(start, finish)
                length = cell * .16
                points = QPolygonF([finish,
                    finish - QPointF(cos(angle - .55) * length, sin(angle - .55) * length),
                    finish - QPointF(cos(angle + .55) * length, sin(angle + .55) * length)])
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(TEAL))
                painter.drawPolygon(points)
