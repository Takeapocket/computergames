from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.types import Piece, Player, Position


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
            piece_id=int(data["piece_id"]),
            from_pos=Position.from_dict(data["from_pos"]),
            to_pos=Position.from_dict(data["to_pos"]),
            is_capture=bool(data["is_capture"]),
            captured_piece=Piece.from_dict(captured_data) if captured_data else None,
        )
