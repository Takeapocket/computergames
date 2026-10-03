from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.validation import require_bool, require_int

BOARD_SIZE = 5
MIN_PIECE_ID = 1
MAX_PIECE_ID = 6


class Player(str, Enum):
    RED = "red"
    BLUE = "blue"

    @property
    def opponent(self) -> "Player":
        return Player.BLUE if self is Player.RED else Player.RED

    @classmethod
    def from_value(cls, value: str | Player) -> Player:
        if isinstance(value, Player):
            return value
        return cls(value)


@dataclass(frozen=True)
class Position:
    row: int
    col: int

    def __post_init__(self) -> None:
        require_int(self.row, "position row")
        require_int(self.col, "position col")

    def to_dict(self) -> dict[str, int]:
        return {"row": self.row, "col": self.col}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Position":
        return cls(row=data["row"], col=data["col"])


def chebyshev_distance(a: Position, b: Position) -> int:
    """Chebyshev / Chess-king distance：因为本游戏走法包含对角线，单步等于 1。"""
    return max(abs(a.row - b.row), abs(a.col - b.col))


@dataclass
class Piece:
    player: Player
    piece_id: int
    position: Position
    alive: bool = True

    def __post_init__(self) -> None:
        self.player = Player.from_value(self.player)
        require_int(self.piece_id, "piece_id", minimum=MIN_PIECE_ID, maximum=MAX_PIECE_ID)
        require_bool(self.alive, "piece alive")
        if not isinstance(self.position, Position):
            raise ValueError("piece position must be a Position")
        if not 0 <= self.position.row < BOARD_SIZE or not 0 <= self.position.col < BOARD_SIZE:
            raise ValueError("piece position must be inside the 5x5 board")

    def copy(self) -> "Piece":
        return Piece(
            player=self.player,
            piece_id=self.piece_id,
            position=self.position,
            alive=self.alive,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player.value,
            "piece_id": self.piece_id,
            "position": self.position.to_dict(),
            "alive": self.alive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Piece":
        return cls(
            player=Player.from_value(data["player"]),
            piece_id=data["piece_id"],
            position=Position.from_dict(data["position"]),
            alive=data["alive"],
        )
