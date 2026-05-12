from record.auto_save import (
    AUTO_SAVE_MATCH_PATH,
    AUTO_SAVE_PATH,
    auto_save_match,
    clear_auto_save,
    clear_auto_save_match,
    has_auto_save,
    has_auto_save_match,
    load_auto_save,
    load_auto_save_match,
)

# 注意：不要在这里 from record.auto_save import auto_save —— 函数名与子模块 `auto_save`
# 同名会覆盖 `record.auto_save` 子模块属性，导致 `import record.auto_save as m` 实际拿到的是函数。
from record.game_record import GameRecord, MoveRecord, MoveSource
from record.match_record import MatchRecord
from record.serializer import deserialize_game_state, from_json, serialize_game_state, to_json

__all__ = [
    "AUTO_SAVE_MATCH_PATH",
    "AUTO_SAVE_PATH",
    "GameRecord",
    "MatchRecord",
    "MoveRecord",
    "MoveSource",
    "auto_save_match",
    "clear_auto_save",
    "clear_auto_save_match",
    "deserialize_game_state",
    "from_json",
    "has_auto_save",
    "has_auto_save_match",
    "load_auto_save",
    "load_auto_save_match",
    "serialize_game_state",
    "to_json",
]
