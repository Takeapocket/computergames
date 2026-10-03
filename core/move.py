from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.types import Piece, Player, Position
from core.validation import require_bool, require_int


@dataclass(frozen=True)
class Move:
    player: Player
    piece_id: int
    from_pos: Position
    to_pos: Position
    is_capture: bool = False
    captured_piece: Piece | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "player", Player.from_value(self.player))
        require_int(self.piece_id, "move piece_id", minimum=1, maximum=6)
        require_bool(self.is_capture, "move is_capture")
        if not isinstance(self.from_pos, Position) or not isinstance(self.to_pos, Position):
            raise ValueError("move positions must be Positions")
        if self.captured_piece is not None and not isinstance(self.captured_piece, Piece):
            raise ValueError("captured_piece must be a Piece or None")

    def copy(self) -> "Move":
        return Move(
            player=self.player,
            piece_id=self.piece_id,
            from_pos=self.from_pos,
            to_pos=self.to_pos,
            is_capture=self.is_capture,
            captured_piece=self.captured_piece.copy() if self.captured_piece is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player.value,
            "piece_id": self.piece_id,
            "from_pos": self.from_pos.to_dict(),
            "to_pos": self.to_pos.to_dict(),
            "is_capture": self.is_capture,
            "captured_piece": self.captured_piece.to_dict() if self.captured_piece else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Move":
        captured_data = data.get("captured_piece")
        return cls(
            player=Player.from_value(data["player"]),
            piece_id=data["piece_id"],
            from_pos=Position.from_dict(data["from_pos"]),
            to_pos=Position.from_dict(data["to_pos"]),
            is_capture=data["is_capture"],
            captured_piece=Piece.from_dict(captured_data) if captured_data is not None else None,
        )
