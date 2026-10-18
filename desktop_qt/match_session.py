"""桌面比赛会话：复用规则、棋谱和计时，独立于 Qt 控件。"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from ai.match import starting_state_for
from ai.opening_layouts import layout_to_metadata, validate_layout
from core.game_state import GameState
from core.move import Move
from core.rules import target_corner
from core.types import Player, Position
from core.validation import require_bool, require_int
from desktop_qt.session import GameSession
from gui.time_limit import validate_total_seconds
from gui.timing import DEFAULT_TOTAL_SECONDS, MatchTimer
from record.auto_save import (
    AUTO_SAVE_METADATA_KEY,
    auto_save,
    auto_save_match,
    load_auto_save,
    load_auto_save_match,
)
from record.game_record import GameRecord
from record.match_record import MatchRecord


SESSION_METADATA_KEY = "desktop_session"


class MatchSession(GameSession):
    """所有改变局面、计时和比分的动作都在此执行。

    自动保存失败保留内存状态及旧文件。终盘结算必须两份都落盘后才能
    进入下一盘；重试只保存，不再次计分。创建新局由调用方先确认覆盖。
    """

    def __init__(self, data_dir: str | Path, *, now: Callable[[], float] | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.auto_save_path = self.data_dir / "recovery" / "auto_save.json"
        self.auto_save_match_path = self.data_dir / "recovery" / "auto_save_match.json"
        self._now = now
        self.revision = 0
        self.dirty = False
        self.dice = None
        self.match: MatchRecord | None = None
        self.our_side: Player | None = None
        self.auto_timeout_enabled = False
        self.total_seconds = DEFAULT_TOTAL_SECONDS
        self.mode = "single"
        self.phase = "setup"
        self.pending_finalize = False
        self.save_error: str | None = None
        self._setup()
        self.has_started = False

    @property
    def has_recovery(self) -> bool:
        return self.auto_save_path.exists() or self.auto_save_match_path.exists()

    @property
    def can_play(self) -> bool:
        return (
            self.phase == "playing" and not self.pending_finalize
            and self.continuation_error is None and self.state.get_winner() is None
        )

    @property
    def can_undo(self) -> bool:
        return self.can_play and bool(self.record.steps)

    @property
    def can_next_game(self) -> bool:
        return (
            self.match is not None and not self.match.is_finished()
            and self.phase == "finished" and not self.pending_finalize
            and self.save_error is None
        )

    def _setup(self, layout_id: str = "balanced_v1") -> None:
        self.has_started = True
        state = starting_state_for(layout_id)
        if self.match is not None:
            state.current_player = self.match.first_mover_color(self.match.current_game_index)
        self.state = state
        self.record = self._new_record(state, layout_id)
        self.timer = MatchTimer(total_seconds=self.total_seconds, current_player=state.current_player, now=self._now)
        self.timer.pause()
        self.phase = "setup"
        self.dice = None
        self.dirty = False
        self.pending_finalize = False
        self.revision += 1

    def _new_record(self, state: GameState, layout_id: str) -> GameRecord:
        record = GameRecord.from_state(state)
        record.metadata.update({
            "interface": "desktop_qt", "layout_id": layout_id,
            "time_limit_seconds": self.total_seconds,
            "auto_timeout_enabled": self.auto_timeout_enabled,
            "red_layout": layout_to_metadata({i: p.position for i, p in state.pieces[Player.RED].items()}),
            "blue_layout": layout_to_metadata({i: p.position for i, p in state.pieces[Player.BLUE].items()}),
        })
        if self.our_side is not None:
            record.metadata["our_side"] = self.our_side.value
        if self.match is not None:
            record.metadata.update({
                "match_id": self.match.match_id, "game_index": self.match.current_game_index,
                "our_role": self.match.our_role, "first_mover_color": state.current_player.value,
            })
        return record

    def start_single(
        self, *, total_seconds: float = DEFAULT_TOTAL_SECONDS,
        auto_timeout_enabled: bool = False, our_side: Player | None = None,
    ) -> None:
        total = validate_total_seconds(total_seconds)
        automatic = require_bool(auto_timeout_enabled, "auto_timeout_enabled")
        side = None if our_side is None else Player.from_value(our_side)
        self.total_seconds, self.auto_timeout_enabled, self.our_side = total, automatic, side
        self.mode, self.match = "single", None
        self._setup()
        self.retry_save()

    def new_game(self, layout_id: str = "balanced_v1") -> None:
        """保留 GameSession 入口；新版新局需要确认开局后才计时。"""
        # 先验证布局，不能因无效 preset 清空当前会话。
        starting_state_for(layout_id)
        self.mode, self.match, self.our_side = "single", None, None
        self._setup(layout_id)
        self.retry_save()

    def start_match(
        self, *, our_side: Player = Player.RED, our_role: str = "甲",
        total_seconds: float = DEFAULT_TOTAL_SECONDS, auto_timeout_enabled: bool = False,
    ) -> None:
        match = MatchRecord(
            our_side=our_side, our_role=our_role, time_limit_seconds=total_seconds,
            auto_timeout_enabled=auto_timeout_enabled,
        )
        self.match, self.mode, self.our_side = match, "match", match.our_side
        self.total_seconds, self.auto_timeout_enabled = match.time_limit_seconds, match.auto_timeout_enabled
        self._setup()
        self.retry_save()

    def confirm_opening(
        self, red: Mapping[int, Position], blue: Mapping[int, Position], *,
        current_player: Player = Player.RED, layout_id: str = "custom",
    ) -> None:
        if self.phase != "setup" or self.pending_finalize:
            raise ValueError("当前不在开局设置阶段。")
        errors = validate_layout(red, blue)
        if errors:
            raise ValueError(errors[0])
        first = (self.match.first_mover_color(self.match.current_game_index)
                 if self.match is not None else Player.from_value(current_player))
        state = GameState.from_layout(red=red, blue=blue, current_player=first)
        record = self._new_record(state, layout_id)
        timer = MatchTimer(total_seconds=self.total_seconds, current_player=first, now=self._now)
        if self.match is not None:
            self.match.start_playing()
        self.has_started = True
        self.state, self.record, self.timer = state, record, timer
        self.phase, self.dice, self.dirty = "playing", None, True
        self.revision += 1
        self.retry_save()

    def next_game(self) -> None:
        if not self.can_next_game:
            raise ValueError("本盘尚未成功保存，或整轮已结束，不能进入下一盘。")
        self._setup()
        self.retry_save()

    def _require_playing(self) -> None:
        if not self.can_play:
            raise ValueError(self.continuation_error or "当前不能操作对局。")

    def set_dice(self, value: int) -> None:
        self._require_playing()
        super().set_dice(value)
        self.retry_save()

    def legal_moves(self) -> list[Move]:
        return super().legal_moves() if self.can_play else []

    def apply_move(self, move: Move) -> None:
        self._require_playing()
        if self.dice is None:
            raise ValueError("请先录入本步骰子。")
        if not isinstance(move, Move):
            raise ValueError("move must be a Move")
        # 在计时器扣时之前验证整步，非法输入/记录异常不能改变计时或棋局。
        state, record = self.state.clone(), deepcopy(self.record)
        canonical = state.apply_move(move.copy(), dice=self.dice)
        snapshot = self.timer.snapshot()
        if self.auto_timeout_enabled and snapshot.timeout_players:
            timed_out = (self.state.current_player if self.state.current_player in snapshot.timeout_players
                         else snapshot.timeout_players[0])
            self.forfeit_timeout(timed_out)
            return
        source = "unknown" if self.our_side is None else ("self" if canonical.player is self.our_side else "opponent")
        step = record.append(dice=self.dice, move=canonical, state_after=state,
                             step_seconds=snapshot.current_step_seconds,
                             remaining_seconds=snapshot.remaining_seconds, source=source)
        elapsed, remaining = self.timer.finish_turn(state.current_player)
        record.steps[-1] = replace(step, step_seconds=elapsed, remaining_seconds=remaining)
        self.state, self.record, self.dice, self.dirty = state, record, None, True
        self.revision += 1
        winner = state.get_winner()
        if winner is not None:
            self._finalize(winner, self._winner_reason(state, winner))
        else:
            self.retry_save()

    def undo(self) -> None:
        if not self.can_undo:
            raise ValueError("当前不能悔棋；已结算盘不可撤回。")
        super().undo()
        # 与旧界面一致：撤回棋步，不返还已经使用的时间。
        self.timer.set_active_player(self.state.current_player)
        self.dice = None
        self.retry_save()

    def toggle_pause(self) -> None:
        self._require_playing()
        if self.timer.is_paused:
            self.timer.resume()
        else:
            self.timer.pause()
        self.revision += 1
        self.retry_save()

    def check_timeout(self) -> Player | None:
        if not self.can_play:
            return None
        players = self.timer.snapshot().timeout_players
        if not players:
            return None
        timed_out = self.state.current_player if self.state.current_player in players else players[0]
        if self.auto_timeout_enabled:
            self.forfeit_timeout(timed_out)
        return timed_out

    def forfeit_timeout(self, player: Player) -> None:
        self._require_playing()
        player = Player.from_value(player)
        if player not in self.timer.snapshot().timeout_players:
            raise ValueError("该方尚未超时，不能判超时负。")
        self._finalize(player.opponent, "timeout")

    def _finalize(self, winner: Player, reason: str) -> None:
        self.timer.pause()
        self.dice, self.phase, self.dirty = None, "finished", True
        result = {"winner": winner.value, "reason": reason}
        if reason == "timeout":
            result["timed_out_player"] = winner.opponent.value
        if self.match is not None:
            outcome = "us" if winner is self.match.our_side else "them"
            result.update({"winner_side": outcome, "game_index": self.match.current_game_index})
            self.record.result = result
            self.match.append_finished_game(deepcopy(self._recovery_record()), outcome)
        else:
            self.record.result = result
        self.pending_finalize = True
        self.revision += 1
        self.retry_save()

    def _recovery_record(self) -> GameRecord:
        record = deepcopy(self.record)
        from record.auto_save import _timer_metadata
        record.metadata[AUTO_SAVE_METADATA_KEY] = _timer_metadata(self.timer.snapshot())
        record.metadata[SESSION_METADATA_KEY] = {
            "mode": self.mode, "phase": self.phase, "dice": self.dice,
        }
        return record

    def retry_save(self) -> bool:
        """自动保存不清除手动导出的 dirty 提示，也不删除任何恢复文件。"""
        try:
            record, snapshot = self._recovery_record(), self.timer.snapshot()
            # Windows 防病毒/索引进程可能暂占原子替换目标。只重试写入，
            # 总等待至多 70ms；不重新执行终盘结算或追加比分。
            for delay in (0.02, 0.05, None):
                try:
                    auto_save(record, snapshot, path=self.auto_save_path)
                    if self.match is not None:
                        auto_save_match(self.match, path=self.auto_save_match_path)
                    break
                except OSError as exc:
                    if delay is None or getattr(exc, "winerror", None) not in {5, 32, 33}:
                        raise
                    time.sleep(delay)
        except (OSError, ValueError, TypeError) as exc:
            self.save_error = f"自动保存失败：{exc}。请重试保存后再继续。"
            return False
        self.save_error = None
        self.pending_finalize = False
        return True

    def checkpoint(self) -> bool:
        """供低频计时快照使用；首次启动及保存故障后不隐式覆盖/重试。"""
        if (not self.has_started or self.save_error is not None or self.pending_finalize
                or self.continuation_error is not None):
            return False
        return self.retry_save()

    def save(self, path: str | Path) -> None:
        """导出当前盘及计时快照；整轮另用 save_match，避免丢失正在进行盘。"""
        auto_save(self._recovery_record(), self.timer.snapshot(), path=path)
        self.dirty = False

    def save_match(self, path: str | Path) -> None:
        if self.match is None:
            raise ValueError("当前没有七盘制比赛。")
        deepcopy(self.match).save(path)

    @staticmethod
    def _winner_reason(state: GameState, winner: Player) -> str:
        return "target_corner" if any(
            p.alive and p.position == target_corner(winner) for p in state.pieces[winner].values()
        ) else "capture_all"

    @staticmethod
    def _record_content(record: GameRecord) -> dict:
        payload = record.to_dict()
        for key in (AUTO_SAVE_METADATA_KEY, SESSION_METADATA_KEY):
            payload["metadata"].pop(key, None)
        return payload

    def _validate_match(self, match: MatchRecord) -> None:
        if match.total_games != 7 or match.target_wins != 4:
            raise ValueError("仅支持七盘先胜四盘的比赛记录。")
        wins = {"us": 0, "them": 0}
        for index, game in enumerate(match.games, 1):
            state = game.restore_state()
            winner, _ = self._outcome(game, state, match=match, game_index=index)
            if winner is None:
                raise ValueError("整轮包含尚未结束的单盘。")
            wins["us" if winner is match.our_side else "them"] += 1
            if index < len(match.games) and max(wins.values()) >= match.target_wins:
                raise ValueError("整轮在先胜四盘后仍追加了对局。")
        if (wins["us"], wins["them"]) != (match.games_won_us, match.games_won_them):
            raise ValueError("整轮比分与各盘胜方不一致。")

    def _outcome(
        self, record: GameRecord, state: GameState, *, match: MatchRecord | None = None,
        game_index: int | None = None, timer_metadata: dict | None = None,
    ) -> tuple[Player | None, str | None]:
        winner, result = state.get_winner(), record.result
        if not result:
            return (None, None) if winner is None else (winner, self._winner_reason(state, winner))
        try:
            result_winner = Player.from_value(result["winner"])
            reason = result["reason"]
            if reason not in {"target_corner", "capture_all", "timeout"}:
                raise ValueError("恢复盘结果原因无效。")
            if match is not None:
                if require_int(result["game_index"], "game_index") != game_index:
                    raise ValueError("恢复盘结果盘号不一致。")
                outcome = "us" if result_winner is match.our_side else "them"
                if result.get("winner_side", outcome) != outcome:
                    raise ValueError("恢复盘结果胜方不一致。")
            if winner is not None:
                if winner is not result_winner or reason != self._winner_reason(state, winner):
                    raise ValueError("恢复盘结果与棋盘不一致。")
            elif reason != "timeout":
                raise ValueError("恢复盘结果与棋盘不一致。")
            else:
                timed_out = Player.from_value(result.get("timed_out_player", result_winner.opponent.value))
                if timed_out is not result_winner.opponent:
                    raise ValueError("超时方与记录胜方不一致。")
                saved_timer = timer_metadata if timer_metadata is not None else record.metadata.get(AUTO_SAVE_METADATA_KEY)
                if saved_timer is not None:
                    from record.auto_save import _validate_timer_metadata
                    _validate_timer_metadata(saved_timer)
                    if saved_timer["timer_remaining"][timed_out.value] != 0.0:
                        raise ValueError("恢复超时结果与计时不一致。")
                elif record.steps and record.steps[-1].remaining_seconds.get(timed_out) == 0.0:
                    # 旧档末步记录可证明先前行动方已到零，允许裁判随后判罚。
                    pass
                elif "timed_out_player" in result:
                    raise ValueError("超时判罚记录缺少对应零余额的计时证据。")
                elif timed_out is not state.current_player:
                    # 无计时快照的旧档维持历史接受边界，不凭空推断迟到判罚。
                    raise ValueError("恢复超时结果与棋盘不一致。")
        except (KeyError, TypeError) as exc:
            raise ValueError("单盘结果缺少有效字段。") from exc
        return result_winner, reason

    def _relation(self, match: MatchRecord, record: GameRecord, state: GameState) -> str:
        meta = record.metadata
        if meta.get("match_id") != match.match_id or "game_index" not in meta:
            raise ValueError("单盘与整轮恢复文件不匹配；可以单独打开单盘查看。")
        index = require_int(meta["game_index"], "game_index", minimum=1, maximum=7)
        if index <= len(match.games):
            if self._record_content(match.games[index - 1]) != self._record_content(record):
                raise ValueError("已结算盘与单盘恢复内容不一致。")
            return "committed"
        if index != match.current_game_index or match.is_finished():
            raise ValueError("单盘与整轮盘号不一致。")
        expected_first = match.first_mover_color(index)
        expected = {"our_side": match.our_side.value, "our_role": match.our_role,
                    "first_mover_color": expected_first.value}
        for key, value in expected.items():
            if key in meta and meta[key] != value:
                raise ValueError(f"恢复记录 {key} 不一致。")
        if record.initial_state["current_player"] != expected_first.value:
            raise ValueError("恢复记录首手不一致。")
        for key in match._stored_timer_fields:
            if key in meta and meta[key] != getattr(match, key):
                raise ValueError(f"恢复记录 {key} 不一致。")
        return "active"

    def _prepare_game(self, record: GameRecord, *, match: MatchRecord | None = None) -> dict:
        state = record.restore_state()
        meta = record.metadata
        total = validate_total_seconds(meta.get("time_limit_seconds", match.time_limit_seconds if match else DEFAULT_TOTAL_SECONDS))
        automatic = require_bool(meta.get("auto_timeout_enabled", match.auto_timeout_enabled if match else False), "auto_timeout_enabled")
        saved = meta.get(AUTO_SAVE_METADATA_KEY)
        remaining = record.steps[-1].remaining_seconds if record.steps else None
        paused = False
        if saved is not None:
            # load_auto_save 完成类型校验；手动导入也经过相同校验。
            from record.auto_save import _validate_timer_metadata
            _validate_timer_metadata(saved)
            if Player.from_value(saved["timer_current_player"]) is not state.current_player:
                raise ValueError("恢复计时行动方与棋盘不一致。")
            remaining = saved["timer_remaining"]
            paused = saved["timer_paused"]
        if remaining is not None and any(seconds > total for seconds in remaining.values()):
            raise ValueError("恢复剩余时间超过单方时限。")
        timer = MatchTimer(total_seconds=total, current_player=state.current_player, remaining_seconds=remaining, now=self._now)
        desktop = meta.get(SESSION_METADATA_KEY, {})
        if not isinstance(desktop, dict):
            raise ValueError("桌面恢复元数据必须是对象。")
        phase = desktop.get("phase", "playing")
        if phase not in {"setup", "playing", "finished"}:
            raise ValueError("桌面恢复阶段无效。")
        if desktop.get("mode", "match" if match else "single") not in {"single", "match"}:
            raise ValueError("桌面恢复模式无效。")
        dice = desktop.get("dice")
        if dice is not None:
            dice = require_int(dice, "dice", minimum=1, maximum=6)
        winner, reason = self._outcome(record, state, match=match,
                                       game_index=record.metadata.get("game_index"), timer_metadata=saved)
        if winner is not None:
            phase, dice, paused = "finished", None, True
        elif phase == "finished":
            raise ValueError("恢复阶段为结束，但棋盘和结果尚未结束。")
        if phase == "setup":
            if record.steps or record.result or dice is not None:
                raise ValueError("开局设置恢复记录不能包含走法或骰子。")
            paused = True
        if paused:
            timer.pause()
        side = match.our_side if match else (Player.from_value(meta["our_side"]) if "our_side" in meta else None)
        return dict(state=state, record=record, timer=timer, total_seconds=total,
                    auto_timeout_enabled=automatic, phase=phase, dice=dice, our_side=side,
                    timer_remaining=remaining, timer_paused=paused,
                    winner=winner, reason=reason)

    def _install(self, prepared: dict, match: MatchRecord | None) -> None:
        self.has_started = True
        if match is not None:
            # 旧整轮缺少显式计时配置时，采用已验证的当前单盘配置。
            match.time_limit_seconds = prepared["total_seconds"]
            match.auto_timeout_enabled = prepared["auto_timeout_enabled"]
        for name in ("state", "record", "timer", "total_seconds", "auto_timeout_enabled", "phase", "dice", "our_side"):
            setattr(self, name, prepared[name])
        # 验证/对比期间不扣时：所有校验通过并安装后才从快照余额起跑。
        self.timer.reset(current_player=self.state.current_player,
                         remaining_seconds=prepared["timer_remaining"])
        if prepared["timer_paused"] or self.continuation_error is not None:
            self.timer.pause()
        # 运行期快照只用于安装计时器，不保留为随后结算盘中的陈旧快照。
        self.record = deepcopy(self.record)
        for key in (AUTO_SAVE_METADATA_KEY, SESSION_METADATA_KEY):
            self.record.metadata.pop(key, None)
        self.match, self.mode = match, "match" if match is not None else "single"
        self.pending_finalize, self.save_error, self.dirty = False, None, True
        self.revision += 1

    def restore_recovery(
        self, *, game_path: str | Path | None = None, match_path: str | Path | None = None,
    ) -> bool:
        game_target = Path(game_path) if game_path is not None else self.auto_save_path
        match_target = Path(match_path) if match_path is not None else self.auto_save_match_path
        if not game_target.exists() and not match_target.exists():
            return False
        record = load_auto_save(path=game_target)[0] if game_target.exists() else None
        desktop = record.metadata.get(SESSION_METADATA_KEY, {}) if record is not None else {}
        if not isinstance(desktop, dict):
            raise ValueError("桌面恢复元数据必须是对象。")
        # 用户已明确新建单盘时，旧整轮文件保留作为历史，不参与该盘恢复。
        single = desktop.get("mode") == "single"
        match = load_auto_save_match(path=match_target) if match_target.exists() and not single else None
        if match is None and desktop.get("mode") == "match":
            raise ValueError("缺少整轮恢复文件；请单独打开单盘查看。")
        if match is not None:
            self._validate_match(match)
        if record is None:
            if match is None or match.phase == "playing":
                raise ValueError("缺少正在进行的单盘恢复文件。")
            self._install_match_only(match)
            return True
        prepared = self._prepare_game(record, match=match)
        relation = self._relation(match, record, prepared["state"]) if match is not None else "single"
        if match is not None and relation == "committed":
            if match.phase == "playing":
                raise ValueError("整轮正在进行下一盘，但恢复文件仍是已结算盘；当前盘进度缺失。")
            if record.metadata["game_index"] != len(match.games):
                raise ValueError("单盘恢复文件不是整轮最后已结算盘；恢复文件不一致。")
        if match is not None and relation == "active" and prepared["phase"] == "setup" and match.phase == "playing":
            raise ValueError("整轮进行阶段与单盘开局设置不一致。")
        if match is not None and relation == "active" and prepared["phase"] == "playing":
            match.phase = "playing"
        self._install(prepared, match)
        if match is not None and relation == "active" and prepared["winner"] is not None:
            self._finalize(prepared["winner"], prepared["reason"])
        return True

    def _install_match_only(self, match: MatchRecord) -> None:
        if match.is_finished():
            prepared = self._prepare_game(deepcopy(match.games[-1]), match=match)
            prepared["phase"] = "finished"
            self._install(prepared, match)
        else:
            self.match, self.mode, self.our_side = match, "match", match.our_side
            self.total_seconds, self.auto_timeout_enabled = match.time_limit_seconds, match.auto_timeout_enabled
            self._setup()
            self.save_error = None

    def load(self, path: str | Path) -> None:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"无法读取棋谱：{exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("棋谱必须是 JSON 对象。")
        if "games" in payload and "our_role" in payload:
            match = MatchRecord.from_dict(payload)
            self._validate_match(match)
            if match.phase == "playing":
                raise ValueError("整轮文件不包含正在进行盘，请使用自动恢复或打开对应单盘。")
            self._install_match_only(match)
        else:
            record = GameRecord.from_dict(payload)
            prepared = self._prepare_game(record)
            self._install(prepared, None)
        self.dirty = False
