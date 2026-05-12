# R-1 Review Followup 处置决策

日期：2026-05-11
对应 R-1 commit：`8d03fc9 Add opening layout setup GUI`

R-1 提交后做的代码 review 提了 4 个非阻塞性 issue。在 R-2 plan 批准后逐一复审，最终处置如下。

---

## Issue 1：`_load_record` 不还原 `_our_side` / `_mode`

**位置**：`gui/main_window.py:325-356`（review 时怀疑没还原 metadata 里的 `our_side`）

**结论**：✅ codex 在 R-1 commit 里已修复
- `_restore_mode_from_record_metadata()` 已实现（`main_window.py:483-493`）
- `_load_record` 与 `_restore_auto_save_if_available` 都调用此方法（line 284 / 351）
- 测试 `test_load_record_restores_match_side_from_metadata`（`tests/test_main_window.py:675-698`）覆盖

无需追加任何代码改动。

---

## Issue 2：`set_our_side` 切换颜色会清空对方布局

**位置**：`gui/opening_panel.py:104-110`

**review 当时担心**：赛场紧张时点错 radio 会丢失对方录入。

**处置**：⏸️ 延后到 R-2 自然消除

依据：
1. R-2 plan §4 明确"比赛模式必须真正禁用红/蓝 radio，不能只靠'不调用 set_our_side'"
2. R-2 实现会通过 `set_side_controls_enabled(False)` 在 match 模式下禁用颜色 radio
3. debug 模式下用户切换颜色重置布局，属可接受 UX（debug 是开发用，不是赛场）

因此该 issue 在 R-2 完成后**自然不会触发**。在 R-1 followup 阶段不单独修。

---

## Issue 3：`save_current_layout` 要求双方都有效才能存

**位置**：`gui/opening_panel.py:191`

**review 当时担心**：用户想存"我方速攻布局"作为模板，但被双方都必须有效的限制卡住。

**处置**：✅ 保留 spec 现状

依据：
1. 原 spec `save_layout(id, red, blue, name)` 就是这样设计
2. 实际比赛中操作员保存的是"本盘双方布局快照"，不是"我方单边模板"——用于复盘
3. 单边模板可以通过手动改 JSON 实现，需求频率极低
4. 改动会带来"保存的布局是单边还是双边"歧义，UX 复杂度高

赛后如有真实使用反馈再评估。

---

## Issue 4：`defensive_v1` / `aggressive_v1` 没 harness 数据

**位置**：`ai/opening_layouts.py:184-245`

**review 当时担心**：3 套预设是凭直觉摆的，没用 `quick_bench` 验过实际胜率。

**处置**：⏸️ 延后到 S3（AI 低风险清理与 harness 工程化）

依据：
1. 预设布局只是 GUI 默认值，不影响代码正确性
2. 比赛中操作员可以自定义布局，预设不一定被采用
3. PROJECT_PHASES.md §A3 已规划"开局布局搜索"，包括对 3 套候选布局做 tournament 验证
4. S3 阶段的 `scripts/search_openings.py` 是更合适的工具

R-1 不阻塞、不预先验证。

---

## 总结

| Issue | 处置 | 行动 |
|---|---|---|
| 1. _load_record 还原 mode | 已修 | 0 |
| 2. set_our_side 清空 | 延后 → R-2 | 0 |
| 3. save_layout 双方校验 | 保留 spec | 0 |
| 4. 布局 harness 验证 | 延后 → S3 | 0 |

**R-1 review followup 阶段无新代码改动**，直接进入 R-2 实现。
