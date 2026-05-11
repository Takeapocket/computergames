# S2 R-1 Opening Layout Entry GUI — Design Spec

Date: 2026-05-11
Status: Approved
Scope: Complete opening layout entry for competition use

---

## Context

The Einstein Chess competition program needs a GUI for entering opening layouts before each game. Currently only a fixed default layout exists. Competition rules allow arbitrary placement of 6 pieces per side in their home zones. The operator must be able to: (1) select or customize their own layout, (2) enter the opponent's layout by looking at the opponent's screen, and (3) start the game with both layouts.

This is Sprint Step S2 in the pre-competition plan, following S1 (R-3 crash recovery, already complete).

---

## Data Model

### Layout Type

```python
Layout = dict[int, Position]  # piece_id (1-6) -> Position(row, col)
```

### File: `ai/opening_layouts.py`

**Presets** — at least 3 built-in layouts:
- `balanced_v1` — even piece distribution
- `aggressive_v1` — key pieces on the diagonal toward target corner
- `defensive_v1` — protects piece 1 from being trapped

**Validation** — `validate_layout(red: Layout, blue: Layout) -> list[str]`:
- Red pieces all within the 6-cell top-left zone where `row + col <= 2`: `{(0,0), (0,1), (0,2), (1,0), (1,1), (2,0)}`
- Blue pieces all within the 6-cell bottom-right zone where `row + col >= 6`: `{(2,4), (3,3), (3,4), (4,2), (4,3), (4,4)}`
- Each side has exactly pieces 1-6 (no missing, no duplicates)
- No coordinate overlap between any two pieces

**Persistence** — custom layout save/load:
- `save_layout(id, red, blue, name)` → `layouts/{id}.json`
- `list_saved_layouts() -> list[LayoutMeta]`
- `load_layout(id) -> tuple[Layout, Layout]`
- JSON schema: `{"id": str, "name": str, "created": ISO8601, "red": {"1": [r,c], ...}, "blue": {"1": [r,c], ...}}`

### GameState Integration

`GameState.from_layout(red, blue)` already exists and is the single entry point for creating game state from a layout. GUI never duplicates rule logic.

---

## GUI Design

### Approach: Embedded State Switch in MainWindow

MainWindow gains a `_phase` field: `"setup"` | `"playing"`.

### Setup Phase Layout

```
┌──────────────────────────────────────────────┐
│  Einstein Chess — Opening Setup               │
├──────────────────┬───────────────────────────┤
│                  │  My Layout                  │
│                  │  [▼ balanced_v1      ]      │
│   5×5 Board      │                             │
│   (click to      │  Opponent Layout            │
│    place)        │  Side: [▼ Red]              │
│                  │  Click opponent zone to      │
│                  │  enter their pieces          │
│                  │                             │
│                  │  [Edit Custom] [Save Layout] │
│                  │  [Confirm → Start Game]      │
├──────────────────┴───────────────────────────┤
│  Status: Select your layout, then enter       │
│  opponent's layout                             │
└──────────────────────────────────────────────┘
```

### Piece Selector

Sidebar shows buttons 1-6 for the current editing side. Selected number is highlighted. Clicking a board cell places the selected piece number.

### Interaction Flow

1. **Select my layout**: Dropdown with presets + saved custom layouts. Board immediately shows my pieces.
2. **Custom edit mode**: Click "Edit Custom" → board enters edit mode. Click cells in my zone to place/remove pieces. Piece selector (1-6) on sidebar.
3. **Enter opponent layout**: Look at opponent screen, click cells in opponent zone to place their pieces. Same piece selector.
4. **Confirm**: Validates both layouts. On success, calls `GameState.from_layout()` and switches to `playing` phase.

### Cell Click Behavior

- Click empty cell → place selected piece number
- Click cell with a piece → remove that piece
- Click cell outside the current editing zone → status bar warning

### Side Assignment

The user must indicate whether they play Red or Blue this game. This determines which zone is "my zone" vs "opponent zone". This information is needed for S3 (best-of-7) integration but must be captured here.

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `ai/opening_layouts.py` | Preset layouts, validation, save/load/list for custom layouts |
| `gui/opening_panel.py` | Tkinter Frame: piece selector, layout dropdown, confirm button |
| `layouts/*.json` | User-saved custom layouts |
| `tests/test_opening_layouts.py` | Layout model, validation, persistence tests |
| `tests/test_opening_panel.py` | Opening panel interaction logic tests |

### Modified Files

| File | Changes |
|------|---------|
| `gui/main_window.py` | Add `_phase` state, integrate OpeningPanel, setup→playing switch |
| `ai/match.py` | Import presets from `opening_layouts` instead of hardcoded layout |
| `gui/board_widget.py` | Support "edit mode" with click callbacks and zone highlighting |

---

## GameRecord Metadata

On confirm, both layouts are written to the game record metadata:

```json
{
  "red_layout": {"1": [0,0], "2": [0,1], ...},
  "blue_layout": {"1": [4,4], "2": [4,3], ...},
  "red_layout_source": "preset:balanced_v1",
  "blue_layout_source": "manual_entry"
}
```

Both layouts are saved for post-game analysis.

---

## Error Handling

- **Validation failure on confirm**: Show specific error (e.g., "Red side missing piece 3"), stay in setup phase.
- **Custom layout save failure**: Show error toast, don't block the flow.
- **Corrupt layout file**: `list_saved_layouts()` silently skips unparseable files.
- **Both layouts incomplete**: Status bar message indicating which side is incomplete.

---

## Testing Strategy

### Unit Tests (`test_opening_layouts.py`)
- All preset layouts pass validation
- Validation rejects: out-of-zone, missing piece IDs, duplicate coordinates, overlap
- Save/load round-trip consistency
- Empty and partially-filled layout handling
- `list_saved_layouts()` skips corrupt files

### GUI Logic Tests (`test_opening_panel.py`)
- Preset selection updates piece data correctly
- Place/remove piece operations update data
- Confirm triggers validation
- Invalid operations rejected (zone violation, duplicate piece number)

### Integration Tests (`test_main_window.py` additions)
- setup→playing state switch creates correct GameState
- Opening layout written to record metadata
- Cancel returns to setup state

---

## Implementation Order

1. `ai/opening_layouts.py` + tests (data model, validation, persistence)
2. `gui/board_widget.py` edit mode support
3. `gui/opening_panel.py` + tests (panel logic)
4. `gui/main_window.py` integration + tests
5. Manual GUI smoke test
