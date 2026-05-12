from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from core.types import Player
from record.game_record import GameRecord


MatchRole = Literal["甲", "乙"]
MatchPhase = Literal["setup", "playing", "finished"]
MatchSideOutcome = Literal["us", "them"]

JIA_FIRST_GAMES = frozenset({1, 4, 5})


@dataclass
class MatchRecord:
    our_side: Player
    our_role: MatchRole
    total_games: int = 7
    target_wins: int = 4
    games: list[GameRecord] = field(default_factory=list)
    games_won_us: int = 0
    games_won_them: int = 0
    current_game_index: int = 1
    started_at: str = ""
    last_game_winner: Optional[MatchSideOutcome] = None
    phase: MatchPhase = "setup"
    match_id: str = ""

    def __post_init__(self) -> None:
        self.our_side = Player.from_value(self.our_side)
        if self.our_role not in ("甲", "乙"):
            raise ValueError(f"invalid match role: {self.our_role!r}")
        if self.total_games < 1:
            raise ValueError("total_games must be positive")
        if not 1 <= self.target_wins <= self.total_games:
            raise ValueError("target_wins out of range")
        if self.current_game_index < 1:
            raise ValueError("current_game_index must be positive")
        if self.current_game_index > self.total_games:
            raise ValueError(
                f"current_game_index {self.current_game_index} exceeds total_games {self.total_games}"
            )
        if self.phase not in ("setup", "playing", "finished"):
            raise ValueError(f"invalid phase: {self.phase!r}")
        if self.last_game_winner is not None and self.last_game_winner not in ("us", "them"):
            raise ValueError(f"invalid last_game_winner: {self.last_game_winner!r}")
        if self.games_won_us < 0 or self.games_won_them < 0:
            raise ValueError("scores cannot be negative")
        if self.games_won_us > self.target_wins or self.games_won_them > self.target_wins:
            raise ValueError(
                f"score exceeds target_wins: us={self.games_won_us}, "
                f"them={self.games_won_them}, target_wins={self.target_wins}"
            )
        if len(self.games) > self.total_games:
            raise ValueError(
                f"games count {len(self.games)} exceeds total_games {self.total_games}"
            )
        if self.phase == "finished" and self.winner() is None:
            raise ValueError("phase=finished requires scores to reach target_wins")
        if self.winner() is not None and self.phase != "finished":
            raise ValueError(
                f"scores reached target_wins but phase != finished: "
                f"us={self.games_won_us}, them={self.games_won_them}, "
                f"target_wins={self.target_wins}, phase={self.phase!r}"
            )
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if not self.match_id:
            self.match_id = uuid.uuid4().hex[:12]

    def start_playing(self) -> None:
        """从 setup 转入 playing。R-2 review #10：公共状态机转移点，避免外部直接赋值。"""
        if self.phase != "setup":
            raise ValueError(f"cannot start_playing from phase={self.phase!r}")
        self.phase = "playing"

    def first_mover(self, game_index: int) -> MatchSideOutcome:
        if not 1 <= game_index <= self.total_games:
            raise ValueError(f"game_index out of range: {game_index}")
        jia_first = game_index in JIA_FIRST_GAMES
        we_are_jia = self.our_role == "甲"
        return "us" if jia_first == we_are_jia else "them"

    def first_mover_color(self, game_index: int) -> Player:
        if self.first_mover(game_index) == "us":
            return self.our_side
        return self.our_side.opponent

    def winner(self) -> Optional[MatchSideOutcome]:
        if self.games_won_us >= self.target_wins:
            return "us"
        if self.games_won_them >= self.target_wins:
            return "them"
        return None

    def is_finished(self) -> bool:
        return self.winner() is not None

    def append_finished_game(self, game: GameRecord, winner: MatchSideOutcome) -> None:
        if winner not in ("us", "them"):
            raise ValueError(f"invalid winner: {winner!r}")
        if self.is_finished():
            raise ValueError("match already finished")
        if len(self.games) >= self.total_games:
            raise ValueError(
                f"match exhausted: cannot append game {len(self.games) + 1} "
                f"when total_games={self.total_games}"
            )
        self.games.append(game)
        if winner == "us":
            self.games_won_us += 1
        else:
            self.games_won_them += 1
        self.last_game_winner = winner
        if self.is_finished():
            self.phase = "finished"
        elif len(self.games) >= self.total_games:
            # 走完所有盘但平局：停在最后一盘索引，不再 +1（防 current_game_index 溢出）
            self.phase = "setup"
        else:
            self.current_game_index += 1
            self.phase = "setup"

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "our_side": self.our_side.value,
            "our_role": self.our_role,
            "total_games": self.total_games,
            "target_wins": self.target_wins,
            "games": [game.to_dict() for game in self.games],
            "games_won_us": self.games_won_us,
            "games_won_them": self.games_won_them,
            "current_game_index": self.current_game_index,
            "started_at": self.started_at,
            "last_game_winner": self.last_game_winner,
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchRecord":
        try:
            games_data = data.get("games", [])
            if not isinstance(games_data, list):
                raise ValueError("games must be a list")
            instance = cls(
                our_side=Player.from_value(data["our_side"]),
                our_role=str(data["our_role"]),
                total_games=int(data.get("total_games", 7)),
                target_wins=int(data.get("target_wins", 4)),
                games=[GameRecord.from_dict(item) for item in games_data],
                games_won_us=int(data.get("games_won_us", 0)),
                games_won_them=int(data.get("games_won_them", 0)),
                current_game_index=int(data.get("current_game_index", 1)),
                started_at=str(data.get("started_at", "")),
                last_game_winner=data.get("last_game_winner"),
                phase=str(data.get("phase", "setup")),
                match_id=str(data.get("match_id", "")),
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid match record data: {exc}") from exc
        # R-2 review #2：反序列化路径额外校验 games 数量与比分一致。
        # 构造路径允许 score-only 快捷写法（既有测试与内部用例依赖），
        # 但从 JSON 来的数据必须 len(games) == games_won_us + games_won_them。
        expected_games = instance.games_won_us + instance.games_won_them
        if len(instance.games) != expected_games:
            raise ValueError(
                f"invalid match record data: games count inconsistent with scores "
                f"(games={len(instance.games)}, us={instance.games_won_us}, "
                f"them={instance.games_won_them})"
            )
        return instance

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, payload: str) -> "MatchRecord":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid match record json") from exc
        if not isinstance(data, dict):
            raise ValueError("match record json must be an object")
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        # R-2 review Critical #3：原子写，避免中途崩溃损坏现有文件。
        from record.auto_save import _atomic_write_text

        _atomic_write_text(Path(path), self.to_json(indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "MatchRecord":
        try:
            payload = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read match record: {exc}") from exc
        return cls.from_json(payload)
