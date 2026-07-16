---
title: Recorder Wait-Until Step V2 (Image Condition) - Plan
type: feat
date: 2026-07-15
topic: recorder-wait-until-v2
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: brainstorm (this session)
execution: code
---

# Recorder Wait-Until Step V2 (Image Condition) - Plan

## Goal Capsule

- **Objective:** Extend the recorder's Wait-Until step with a fourth condition type — **Image** — that searches for a captured template image within a screen area (or the whole screen) at a configurable match threshold, and can wait for it to either appear or disappear.
- **Product authority:** Repo owner (Ethan).
- **Open blockers:** None. Storage / semantics / store-target were settled this session (see Key Decisions).

## Product Contract

### Summary

A new `ConditionType.IMAGE` alongside Number / Color / Text. The user captures a template by dragging a box on screen; the step polls a search area (a drawn `QRect`, a bound variable, or nothing = whole screen) and is satisfied when the template is found at/above a threshold (**Appears**) or is no longer found (**Disappears**). On an Appears match, the found **center `QPoint`** can be stored into a variable so a later step can click it. The template is stored as **base64 inside the step JSON**, keeping profiles self-contained (duplicate/export/import "just works", no sidecar files).

### Problem Frame

V1 shipped Number, Color, and Text conditions and deliberately deferred Image because it's the only condition needing new template-capture UI. Everything else needed already exists: `vision.findImageCenter(template_path, bounds, threshold)` already does `cv2.matchTemplate` within optional bounds and returns the match center `QPoint` + confidence. The overlay already freezes the screen and does region drag-select. So V2 is wiring, capture, and storage — not new vision research.

### Key Decisions

- **Template stored as base64 in the step JSON** (session-settled: user-directed — chosen over a per-profile file or a SQLite BLOB column). Steps already serialize to JSON in SQLite and `duplicateProfile` copies rows; embedding keeps the step self-contained with no orphan files or path breakage. Templates are small (a few KB). Cost: slightly larger JSON blob, accepted.
- **Appears AND Disappears** (session-settled: user-directed — chosen over appears-only). A small match-mode combo. Appears covers "wait for the button"; Disappears covers "wait for the spinner to vanish".
- **Store the found center `QPoint`** (session-settled: user-directed — chosen over also storing confidence, or gate-only). This is the chaining payoff: wait for image → store location → click it, reusing existing QPoint store-var filtering and click-at-variable support.
- **Deferred:** multi-scale / resolution-robust matching (single-scale `TM_CCOEFF_NORMED` is fine for same-machine macros); binding a template to a variable (templates are captured literals in V2).

### Requirements

**Condition**

R1. `ConditionType.IMAGE` is selectable in the Wait-Until dialog alongside Number, Color, and Text, and behaves as a normal blocking, cooperatively-polling step (inherits V1 R2/R3 behavior).

R2. The user captures a template by dragging a box on screen through the capture overlay; a thumbnail of the captured template is shown in the dialog.

R3. The search area can be **drawn** (`QRect`), **bound to a `QRect` variable**, or **left unset**, in which case the whole primary screen is searched (`findImageCenter` already accepts `bounds=None`).

R4. A **threshold** (0–100% in the UI ↔ 0.0–1.0 internally, default 80%) controls the minimum match confidence.

R5. A **match mode** selects **Appears** (satisfied when found ≥ threshold) or **Disappears** (satisfied when not found ≥ threshold).

R6. On an **Appears** match, the found **center `QPoint`** may optionally be stored into a `QPoint`-typed variable. The store option is disabled when mode is **Disappears** (nothing to store).

R7. (Recommended, non-blocking) A **Test** button runs a single match against the live screen and reports found/not-found + confidence, flashing the hit via the existing overlay highlight.

**Persistence & export**

R8. The template persists as base64 in the step JSON and survives save/load, profile duplicate, and export/import with no external files.

R9. Exporting the task to standalone Python reproduces the Image condition with the template inlined as a base64 literal decoded in-script (no sidecar file), looping on the image matcher.

## Technical Design

### Affected files (6)

1. `macro_studio/core/recording/timeline_handler.py` — model
2. `macro_studio/vision.py` — bytes/ndarray matcher entry point
3. `macro_studio/core/types_and_enums.py` — `CaptureMode.IMAGE`
4. `macro_studio/ui/overlay.py` — capture the template pixmap on region release
5. `macro_studio/ui/widgets/recorder/wait_until_editor.py` — dialog page, summary
6. `macro_studio/core/execution/manual_task_wrapper.py` — runtime + export

### 1. Model — `timeline_handler.py`

```python
class ConditionType(str, Enum):
    NUMBER = "Number"; COLOR = "Color"; TEXT = "Text"
    IMAGE = "Image"                      # new

class ImageMatch(str, Enum):            # new, mirrors TextMatch
    APPEARS = "appears"
    DISAPPEARS = "disappears"
```

`WaitCondition` gains:
- `template_b64: str | None = None` — PNG bytes, base64; the "target" for IMAGE.
- `threshold: float = 0.8`
- `image_match: ImageMatch = ImageMatch.APPEARS`

- `_COND_AREA_TYPE[ConditionType.IMAGE] = QRect`; `area` may be `None` (whole screen).
- `_toDict` / `fromDict`: carry `template_b64` (already JSON-safe), `threshold`, `image_match` (by `.name`). Use the existing `setIfEvals` helper so unset fields stay out of the dict.

### 2. Vision — `vision.py`

`findImageCenter` currently only reads from a path. Add an in-memory path so runtime never touches disk:

```python
def templateFromB64(b64: str) -> np.ndarray:
    """base64 PNG -> BGR ndarray via cv2.imdecode."""

def findImageCenterFromArray(template_bgr, bounds=None, threshold=0.8) -> tuple[QPoint, float] | None:
    """Same match core as findImageCenter, but template already decoded."""
```

Refactor the shared match core out of `findImageCenter` (screenshot grab + `matchTemplate` + `minMaxLoc` + threshold check) so both entry points call it. Guard the `template.shape > screen region` case (matchTemplate raises) by returning `None`.

### 3. Capture mode — `types_and_enums.py` + `overlay.py`

- Add `CaptureMode.IMAGE = QRect` (it geometrically behaves like REGION).
- In `overlay.py`, drive IMAGE through the identical REGION drag flow. On region release, when `current_mode is CaptureMode.IMAGE`, also grab the template pixels from the frozen screenshot: `template = self._frozen_screen.copy(final_rect)`. Return both the rect (search-area unused for template capture) and the pixmap — simplest is to have `captureData` return the `QPixmap` for IMAGE mode and let the dialog encode it. Prompt text: "Drag a box around the image to find."
- Encoding to base64 (in the dialog or a small helper): `QPixmap -> QImage -> QBuffer("PNG") -> bytes -> base64`.

### 4. Dialog — `wait_until_editor.py`

- Add `ConditionType.IMAGE` to `type_combo` and a new stacked comparison page:
  - **Capture image…** button → `_captureWithOverlay(CaptureMode.IMAGE)`; store base64, show thumbnail `QLabel`.
  - **Threshold** spinbox/slider 0–100% with live label (maps to 0.0–1.0).
  - **Match** combo: Appears / Disappears (toggling to Disappears disables the store row).
  - **Search area**: reuse the existing Draw/Variable area widget. Loosen the save guard so IMAGE tolerates "Not set" (= whole screen). Variable option filtered to `QRect`.
  - **Test** button (R7): run `findImageCenterFromArray` once, report `found @ 0.xx` / `not found`, flash via `overlay.trySetHighlighted`.
- `_STORE_TYPES[ConditionType.IMAGE] = (QPoint,)`; `_AREA_TYPES[ConditionType.IMAGE] = (QRect,)`.
- `_loadFrom` / `resultCondition`: read/write `template_b64`, `threshold`, `image_match`.
- `summaryText` IMAGE branch, e.g. `Wait until [area|screen] image appears (≥80%)  → clickPoint`.

### 5. Runtime — `manual_task_wrapper.py`

- `_readArea` for IMAGE: decode `template_b64` once and cache the ndarray (decode is not free; cache keyed on the condition instance or the b64 string). Call `findImageCenterFromArray(template, bounds=self._resolveArea(cond) or None, threshold=cond.threshold)`. Reading = the `(QPoint, confidence)` tuple or `None`.
- `_evaluate` for IMAGE: `found = reading is not None`; `APPEARS -> found`, `DISAPPEARS -> not found`. (Threshold is applied inside the matcher.)
- `_maybeStore`: for IMAGE, store `reading[0]` (the QPoint), not the tuple. Note the existing scalar types store `reading` directly — add an IMAGE-specific extraction. Only stores on APPEARS (Disappears has no reading and store is disabled in UI anyway).
- Watch the `last_stored != reading` de-dup path in `_runWaitUntil`: a `(QPoint, float)` tuple compares fine, but confidence jitters every frame so it will "change" constantly — for IMAGE compare on the point only, or skip the de-dup.

### 6. Export — `_waitConditionExport`

IMAGE branch:
```python
imports += ["import base64, numpy as np, cv2",
            "from macro_studio.vision import findImageCenterFromArray"]
# inline: _tpl = cv2.imdecode(np.frombuffer(base64.b64decode("<b64>"), np.uint8), cv2.IMREAD_COLOR)
# loop: while True: _m = findImageCenterFromArray(_tpl, <area_expr or None>, <threshold>)
#       if (_m is not None) == <appears>: (store _m[0] into var) ; break
#       yield from taskSleep(poll)
```
Consistent with the embed decision — no sidecar PNG.

## Test Plan

- **Model round-trip:** `WaitCondition` with IMAGE → `_toDict` → `fromDict` preserves `template_b64`, `threshold`, `image_match`; base64 survives JSON.
- **Vision:** `templateFromB64(encode(x)) ≈ x`; `findImageCenterFromArray` finds a known crop of a test screenshot ≥ threshold and returns the correct center; oversized template returns `None`.
- **Runtime:** Appears satisfied when template present; Disappears satisfied when absent; QPoint stored on Appears equals match center; poll stays responsive to pause/stop.
- **Export:** generated script imports decode cleanly and the inlined loop matches on a fixture.
- **UI (manual, headed):** capture shows a thumbnail; threshold + mode persist through save/reopen; Disappears greys the store row; Test button reports confidence and flashes the hit.

## Outstanding Questions / Deferred

- Multi-scale matching (resolution independence) — deferred.
- Template-from-variable binding — deferred.
- Storing confidence alongside the point — dropped for V2 (can add a second store field later without model breakage).
- Whether to cap template size on capture (very large templates slow matchTemplate + bloat JSON) — consider a soft warning; not blocking.
