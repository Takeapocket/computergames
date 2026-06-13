from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.board import get_piece_at
from core.move import Move
from core.rules import generate_legal_moves_for_piece, get_winner, legal_piece_ids_for_dice
from core.types import Piece, Player, Position


@dataclass
class GameState:
    pieces: dict[Player, dict[int, Piece]]
    current_player: Player = Player.RED
    history: list[Move] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.current_player = Player.from_value(self.current_player)
        self.pieces.setdefault(Player.RED, {})
        self.pieces.setdefault(Player.BLUE, {})
        self._validate_piece_metadata()
        self._validate_unique_living_positions()

    @classmethod
    def from_layout(
        cls,
        red: Mapping[int, Position] | None = None,
        blue: Mapping[int, Position] | None = None,
        current_player: Player = Player.RED,
    ) -> "GameState":
        return cls(
            pieces={
                Player.RED: {
                    int(piece_id): Piece(Player.RED, int(piece_id), position)
                    for piece_id, position in sorted((red or {}).items())
                },
                Player.BLUE: {
                    int(piece_id): Piece(Player.BLUE, int(piece_id), position)
                    for piece_id, position in sorted((blue or {}).items())
                },
            },
            current_player=Player.from_value(current_player),
        )

    def piece_at(self, position: Position) -> Piece | None:
        return get_piece_at(self.pieces, position)

    def legal_piece_ids(self, player: Player, dice: int) -> list[int]:
        player = Player.from_value(player)
        return legal_piece_ids_for_dice(self.pieces[player], dice)

    def legal_moves_for_piece(self, player: Player, piece_id: int) -> list[Move]:
        player = Player.from_value(player)
        piece = self.pieces[player].get(piece_id)
        if piece is None:
            return []
        return generate_legal_moves_for_piece(piece, self.piece_at)

    def legal_moves(self, player: Player, dice: int) -> list[Move]:
        player = Player.from_value(player)
        moves: list[Move] = []
        for piece_id in self.legal_piece_ids(player, dice):
            moves.extend(self.legal_moves_for_piece(player, piece_id))
        return moves

    def apply_move(self, move: Move, dice: int) -> Move:
        if self.get_winner() is not None:
            raise ValueError("game is already finished")
        if move.player is not self.current_player:
            raise ValueError("move player must match current player")

        matching_move = self._find_matching_legal_move(move, dice)
        return self._apply_known_legal_move(matching_move)

    def _apply_known_legal_move(self, move: Move) -> Move:
        """Apply a Move freshly returned by this state's legal_moves() call."""
        if self.get_winner() is not None:
            raise ValueError("game is already finished")
        if move.player is not self.current_player:
            raise ValueError("move player must match current player")

        piece = self.pieces.get(move.player, {}).get(move.piece_id)
        if piece is None or not piece.alive or piece.position != move.from_pos:
            raise ValueError("known legal move is stale")

        if move.captured_piece is not None:
            captured = self.pieces[move.captured_piece.player][move.captured_piece.piece_id]
            captured.alive = False

        piece.position = move.to_pos
        self.history.append(move.copy())
        self.current_player = self.current_player.opponent
        return move.copy()

    def undo_move(self) -> Move | None:
        if not self.history:
            return None

        move = self.history.pop()
        self.current_player = move.player
        moved_piece = self.pieces[move.player][move.piece_id]
        moved_piece.position = move.from_pos
        moved_piece.alive = True

        if move.captured_piece is not None:
            self.pieces[move.captured_piece.player][move.captured_piece.piece_id] = move.captured_piece.copy()

        return move

    def get_winner(self) -> Player | None:
        return get_winner(self.pieces)

    def serialize(self, *, include_history: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "current_player": self.current_player.value,
            "pieces": {
                player.value: {
                    str(piece_id): piece.to_dict()
                    for piece_id, piece in sorted(player_pieces.items())
                }
                for player, player_pieces in ((Player.RED, self.pieces[Player.RED]), (Player.BLUE, self.pieces[Player.BLUE]))
            },
        }
        if include_history:
            payload["history"] = [move.to_dict() for move in self.history]
        return payload

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "GameState":
        raw_pieces = data["pieces"]
        pieces: dict[Player, dict[int, Piece]] = {
            Player.RED: {},
            Player.BLUE: {},
        }
        for player in (Player.RED, Player.BLUE):
            for piece_id, piece_data in raw_pieces.get(player.value, {}).items():
                parsed_piece_id = int(piece_id)
                piece = Piece.from_dict(piece_data)
                if piece.player is not player or piece.piece_id != parsed_piece_id:
                    raise ValueError("piece metadata must match serialized location")
                pieces[player][parsed_piece_id] = piece

        return cls(
            pieces=pieces,
            current_player=Player.from_value(data["current_player"]),
            history=[Move.from_dict(move_data) for move_data in data.get("history", [])],
        )

    def _find_matching_legal_move(self, move: Move, dice: int) -> Move:
        selected_piece_ids = self.legal_piece_ids(move.player, dice)
        if move.piece_id not in selected_piece_ids:
            raise ValueError("move piece is not selected by dice")

        legal_moves = self.legal_moves(move.player, dice)
        for legal_move in legal_moves:
            if (
                legal_move.piece_id == move.piece_id
                and legal_move.from_pos == move.from_pos
                and legal_move.to_pos == move.to_pos
            ):
                return legal_move
        raise ValueError("move is not legal")

    def _validate_piece_metadata(self) -> None:
        for player, player_pieces in self.pieces.items():
            normalized_player = Player.from_value(player)
            for piece_id, piece in player_pieces.items():
                if piece.player is not normalized_player or piece.piece_id != piece_id:
                    raise ValueError("piece metadata must match owner mapping")

    def _validate_unique_living_positions(self) -> None:
        seen: set[Position] = set()
        for player_pieces in self.pieces.values():
            for piece in player_pieces.values():
                if not piece.alive:
                    continue
                if piece.position in seen:
                    raise ValueError("living pieces cannot overlap")
                seen.add(piece.position)
