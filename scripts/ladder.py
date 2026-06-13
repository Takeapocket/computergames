from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.match import ai_version_signature, build_ai, play_one_game, starting_state_for
from ai.release_defaults import RELEASE_DEFAULT_ROLLOUT_KWARGS
from core.types import Player


@dataclass
class LadderPlayer:
    player_id: str
    kind: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    rating: float = 1500.0
    uncertainty: float = 350.0
    games: int = 0
    signature: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def expected_score(rating: float, opponent_rating: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent_rating - rating) / 400.0))


def update_ratings(
    red_rating: float,
    blue_rating: float,
    *,
    red_score: float,
    k_factor: float = 32.0,
) -> tuple[float, float]:
    red_expected = expected_score(red_rating, blue_rating)
    blue_expected = expected_score(blue_rating, red_rating)
    blue_score = 1.0 - red_score
    new_red = red_rating + k_factor * (red_score - red_expected)
    new_blue = blue_rating + k_factor * (blue_score - blue_expected)
    return round(new_red, 3), round(new_blue, 3)


def estimate_rating_uncertainty(
    games: int,
    *,
    initial: float = 350.0,
    floor: float = 30.0,
) -> float:
    played = max(0, int(games))
    return round(max(float(floor), float(initial) / ((played + 1) ** 0.5)), 3)


def _rating_interval(player: LadderPlayer) -> dict[str, float]:
    return {
        "low": round(player.rating - player.uncertainty, 3),
        "high": round(player.rating + player.uncertainty, 3),
    }


def _player_report_dict(player: LadderPlayer) -> dict[str, Any]:
    payload = player.to_dict()
    payload["rating_interval"] = _rating_interval(player)
    return payload


def _player_game_manifest(player: LadderPlayer) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "kind": player.kind,
        "kwargs": dict(player.kwargs),
        "signature": dict(player.signature),
    }


def _ensure_games_path_unused(games_path: Path) -> None:
    if games_path.exists() and games_path.read_text(encoding="utf-8").strip():
        raise ValueError(
            f"{games_path} already contains games; choose a new output directory "
            "or implement an explicit resume workflow."
        )


def _default_ladder_output_dir() -> Path | None:
    data_root = os.environ.get("CG_RESEARCH_DATA_DIR")
    if not data_root:
        return None
    return Path(data_root) / "ladder"


def schedule_round_robin(
    players: list[LadderPlayer],
    *,
    games_per_pair: int = 2,
) -> list[dict[str, Any]]:
    if len(players) < 2:
        raise ValueError("at least two players are required")
    if games_per_pair <= 0:
        raise ValueError("games_per_pair must be positive")
    ids = [player.player_id for player in players]
    if len(ids) != len(set(ids)):
        raise ValueError("player_id values must be unique")

    schedule: list[dict[str, Any]] = []
    for pair_index, (first, second) in enumerate(combinations(ids, 2)):
        for game_index in range(games_per_pair):
            red, blue = (first, second) if game_index % 2 == 0 else (second, first)
            schedule.append(
                {
                    "pair_index": pair_index,
                    "game_index": game_index,
                    "red": red,
                    "blue": blue,
                }
            )
    return schedule


def register_player(
    player_id: str,
    kind: str,
    *,
    kwargs: dict[str, Any] | None = None,
    rating: float = 1500.0,
) -> LadderPlayer:
    ai = build_ai(kind, seed=0, **(kwargs or {}))
    return LadderPlayer(
        player_id=player_id,
        kind=kind,
        kwargs=dict(kwargs or {}),
        rating=float(rating),
        signature=ai_version_signature(ai),
    )


def default_anchor_player() -> LadderPlayer:
    return register_player(
        "p14_default",
        "rollout",
        kwargs=dict(RELEASE_DEFAULT_ROLLOUT_KWARGS),
        rating=1500.0,
    )


def append_jsonl_result(path: str | Path, row: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _red_score_for_winner(winner: Player | None) -> float:
    if winner is Player.RED:
        return 1.0
    if winner is Player.BLUE:
        return 0.0
    return 0.5


def _play_ladder_game(
    red: LadderPlayer,
    blue: LadderPlayer,
    *,
    game_id: str,
    game_seed: int,
    games_path: Path,
    layout_id: str,
    max_turns: int,
    k_factor: float,
    schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    red_ai = build_ai(red.kind, seed=game_seed * 3 + 1, **red.kwargs)
    blue_ai = build_ai(blue.kind, seed=game_seed * 3 + 2, **blue.kwargs)
    result = play_one_game(
        red_ai=red_ai,
        blue_ai=blue_ai,
        dice_rng=random.Random(game_seed * 3),
        max_turns=max_turns,
        starting_state=starting_state_for(layout_id),
    )
    red_score = _red_score_for_winner(result.winner)
    red.rating, blue.rating = update_ratings(
        red.rating,
        blue.rating,
        red_score=red_score,
        k_factor=k_factor,
    )
    red.games += 1
    blue.games += 1
    red.uncertainty = estimate_rating_uncertainty(red.games)
    blue.uncertainty = estimate_rating_uncertainty(blue.games)
    row = {
        "game_id": game_id,
        "seed": game_seed,
        "red": red.player_id,
        "blue": blue.player_id,
        "players": {
            "red": _player_game_manifest(red),
            "blue": _player_game_manifest(blue),
        },
        "winner": result.winner.value if result.winner else None,
        "turns": result.turns,
        "red_score": red_score,
        "ratings_after": {
            red.player_id: red.rating,
            blue.player_id: blue.rating,
        },
        "uncertainty_after": {
            red.player_id: red.uncertainty,
            blue.player_id: blue.uncertainty,
        },
        "illegal_moves": result.illegal_moves,
        "crashes": result.crashes,
        "timeouts": result.timeouts,
        "avg_step_time_ms": result.avg_step_time_ms,
        "max_step_time_ms": result.max_step_time_ms,
        "termination_reason": result.termination_reason,
    }
    if schedule is not None:
        row["schedule"] = dict(schedule)
    append_jsonl_result(games_path, row)
    return row


def _escape_markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def render_markdown_report(report: dict[str, Any]) -> str:
    players = sorted(
        report["players"].values(),
        key=lambda player: (-float(player["rating"]), player["player_id"]),
    )
    lines = [
        "# Ladder Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Games: {report['games']}",
        f"- Seed: {report['seed']}",
        f"- Layout: {report['layout_id']}",
        "",
        "| Player | Kind | Rating | Uncertainty Estimate | Games |",
        "|---|---|---:|---:|---:|",
    ]
    for player in players:
        lines.append(
            "| {player_id} | {kind} | {rating:.3f} | +/- {uncertainty:.3f} | {games} |".format(
                player_id=_escape_markdown_cell(player["player_id"]),
                kind=_escape_markdown_cell(player["kind"]),
                rating=float(player["rating"]),
                uncertainty=float(player["uncertainty"]),
                games=int(player["games"]),
            )
        )
    return "\n".join(lines) + "\n"


def _write_ladder_reports(output: Path, report: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(render_markdown_report(report), encoding="utf-8")


def run_ladder_games(
    red: LadderPlayer,
    blue: LadderPlayer,
    *,
    games: int,
    seed: int,
    output_dir: str | Path,
    layout_id: str = "balanced_v1",
    max_turns: int = 200,
    k_factor: float = 32.0,
) -> dict[str, Any]:
    output = Path(output_dir)
    games_path = output / "games.jsonl"
    _ensure_games_path_unused(games_path)
    for index in range(games):
        game_seed = seed * 100_000 + index
        _play_ladder_game(
            red,
            blue,
            game_id=f"{seed}-{index + 1}",
            game_seed=game_seed,
            games_path=games_path,
            layout_id=layout_id,
            max_turns=max_turns,
            k_factor=k_factor,
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "games": games,
        "seed": seed,
        "layout_id": layout_id,
        "max_turns": max_turns,
        "games_jsonl": str(games_path),
        "players": {
            red.player_id: _player_report_dict(red),
            blue.player_id: _player_report_dict(blue),
        },
    }
    _write_ladder_reports(output, report)
    return report


def run_ladder_round_robin(
    players: list[LadderPlayer],
    *,
    games_per_pair: int,
    seed: int,
    output_dir: str | Path,
    layout_id: str = "balanced_v1",
    max_turns: int = 200,
    k_factor: float = 32.0,
) -> dict[str, Any]:
    if len(players) < 2:
        raise ValueError("at least two players are required")
    players_by_id = {player.player_id: player for player in players}
    if len(players_by_id) != len(players):
        raise ValueError("player_id values must be unique")

    output = Path(output_dir)
    games_path = output / "games.jsonl"
    _ensure_games_path_unused(games_path)
    schedule = schedule_round_robin(players, games_per_pair=games_per_pair)
    for index, scheduled in enumerate(schedule):
        game_seed = seed * 100_000 + index
        _play_ladder_game(
            players_by_id[scheduled["red"]],
            players_by_id[scheduled["blue"]],
            game_id=f"{seed}-rr-{index + 1}",
            game_seed=game_seed,
            games_path=games_path,
            layout_id=layout_id,
            max_turns=max_turns,
            k_factor=k_factor,
            schedule=scheduled,
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "games": len(schedule),
        "games_per_pair": games_per_pair,
        "color_balance_note": (
            "balanced" if games_per_pair % 2 == 0 else "odd games_per_pair gives first player one extra red game per pair"
        ),
        "seed": seed,
        "layout_id": layout_id,
        "max_turns": max_turns,
        "games_jsonl": str(games_path),
        "schedule": schedule,
        "players": {
            player_id: _player_report_dict(player)
            for player_id, player in sorted(players_by_id.items())
        },
    }
    _write_ladder_reports(output, report)
    return report


def _player_from_cli_token(token: str) -> LadderPlayer:
    return default_anchor_player() if token == "p14_default" else register_player(token, token)


def _player_from_config_entry(entry: Any) -> LadderPlayer:
    if isinstance(entry, str):
        return _player_from_cli_token(entry)
    if not isinstance(entry, dict):
        raise ValueError("player config entries must be strings or objects")

    try:
        player_id = str(entry["player_id"])
        kind = str(entry["kind"])
    except KeyError as exc:
        raise ValueError("player config objects require player_id and kind") from exc

    kwargs = entry.get("kwargs", {})
    if kwargs is None:
        kwargs = {}
    if not isinstance(kwargs, dict):
        raise ValueError("player config kwargs must be a JSON object")
    rating = float(entry.get("rating", 1500.0))

    if kind == "p14_default":
        player = default_anchor_player()
        player.player_id = player_id
        player.rating = rating
        return player
    return register_player(player_id, kind, kwargs=kwargs, rating=rating)


def load_players_config(path: str | Path) -> list[LadderPlayer]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("players") if isinstance(payload, dict) else payload
    if not isinstance(entries, list) or not entries:
        raise ValueError("players config must contain a non-empty players list")
    return [_player_from_config_entry(entry) for entry in entries]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a persistent Elo ladder pair probe.")
    parser.add_argument("--red", default="rollout")
    parser.add_argument("--blue", default="random")
    parser.add_argument("--players", default="", help="Comma-separated player ids/kinds for round-robin mode.")
    parser.add_argument("--players-config", default="", help="JSON file describing round-robin players and kwargs.")
    parser.add_argument("--games-per-pair", type=int, default=2)
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Directory for report.json/report.md/games.jsonl. Required unless "
            "CG_RESEARCH_DATA_DIR is set; default then becomes <env>/ladder."
        ),
    )
    parser.add_argument("--layout-id", default="balanced_v1")
    parser.add_argument("--max-turns", type=int, default=200)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir) if args.output_dir else _default_ladder_output_dir()
    if output_dir is None:
        parser.error("--output-dir is required unless CG_RESEARCH_DATA_DIR is set")

    if args.players_config:
        if args.players:
            parser.error("--players-config cannot be combined with --players")
        players = load_players_config(args.players_config)
        report = run_ladder_round_robin(
            players,
            games_per_pair=args.games_per_pair,
            seed=args.seed,
            output_dir=output_dir,
            layout_id=args.layout_id,
            max_turns=args.max_turns,
        )
    elif args.players:
        players = [
            _player_from_cli_token(token.strip())
            for token in args.players.split(",")
            if token.strip()
        ]
        report = run_ladder_round_robin(
            players,
            games_per_pair=args.games_per_pair,
            seed=args.seed,
            output_dir=output_dir,
            layout_id=args.layout_id,
            max_turns=args.max_turns,
        )
    else:
        red = _player_from_cli_token(args.red)
        blue = _player_from_cli_token(args.blue)
        report = run_ladder_games(
            red,
            blue,
            games=args.games,
            seed=args.seed,
            output_dir=output_dir,
            layout_id=args.layout_id,
            max_turns=args.max_turns,
        )
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
