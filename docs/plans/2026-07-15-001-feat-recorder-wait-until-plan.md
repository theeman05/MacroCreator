---
title: Recorder Wait-Until Step - Plan
type: feat
date: 2026-07-15
topic: recorder-wait-until
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

# Recorder Wait-Until Step - Plan

## Goal Capsule

- **Objective:** Add a "Wait Until" step to the visual recorder so users can record reactive and timed macros — pause the recording until a screen condition is met, then play on — without writing a Python task or introducing branching.
- **Product authority:** Repo owner (Ethan).
- **Open blockers:** None block planning. Several sub-decisions are intentionally deferred to planning (see Outstanding Questions).

## Product Contract

### Summary

A new blocking **Wait Until** step type for the visual recorder. It polls a user-drawn screen area until a condition holds — a number read via OCR crossing a threshold, a color match, or a text match — then the rest of the linear recording continues. Both sides of a condition can talk to user variables: the comparison target can be a literal or a bound variable, and the value read off-screen can optionally be written back into a variable.

### Problem Frame

The recorder today replays a fixed, linear sequence (`DELAY`, `KEYBOARD`, `MOUSE`, `TEXT`) with no ability to react to what's on screen. That blocks a whole class of real macros. The motivating one: a game with a set of early "waves" that are the most valuable to farm. The user wants a recording that reads the current wave from a region they draw, and once it reaches a threshold, clicks a stop button and restarts the game to re-enter the valuable loop. That behavior isn't recordable at all right now — the only route is writing a Python task, which defeats the point of the visual recorder for users who don't code. The gap is purely in the recorder surface: the engine already has screen-reading (`vision.py`), on-screen capture (`CaptureMode`), and typed variables.

### Key Decisions

- **Wait-until, not branching** (session-settled: user-directed — chosen over if/else branching: keeps the timeline strictly linear so the recorder stays a recorder, not a weaker rival to the Python task API sitting next to it). A wait-until adds a *pause condition*, not logic. The wave loop needs timing, not branches — the "restart" is just the task's existing repeat.
- **No timeout in v1** (session-settled: user-directed — chosen over a required or optional max-wait: simplest to ship). The step waits indefinitely; the escape is the user stopping the task. Because it polls cooperatively, waiting forever does not trip the deadlock watchdog.
- **Every input is literal-or-variable, in both directions** (session-settled: user-directed — chosen over throwaway reads or input-only). The watch area, the comparison target, and the read output each accept either a value defined in place or a bound user variable. This makes the step a clean superset that also serves "read a value into a variable," and lets a recording be re-tuned from the Variables tab without editing steps.
- **Image / template-appears condition deferred** (session-settled: user-directed — chosen over including it in v1: it's the only condition needing new template-capture UI). v1 ships Number, Color, and Text.

### Requirements

**Step and timeline**

R1. A new "Wait Until" step type is selectable in the recorder alongside the existing `DELAY`, `KEYBOARD`, `MOUSE`, and `TEXT` steps, and appears as a normal step in the timeline.

R2. The step is blocking: on run, the recording pauses on it until its condition is satisfied, then continues to the next step. The timeline stays strictly linear — no branch paths or jump targets.

R3. The step polls cooperatively (yields between checks) so pause (F6) and stop/interrupt (F8/F10) stay responsive and the deadlock watchdog is not tripped while waiting.

**Conditions**

R4. Each step tests exactly one condition, of type Number (OCR), Color, or Text.

R5. Number: OCR a user-drawn region, parse a number, satisfied when it meets the target under a comparison operator (at least `>=`, `<=`, `==`).

R6. Color: sample a user-chosen point or region, satisfied when it matches the target color within a tolerance.

R7. Text: OCR a user-drawn region, satisfied when it contains (or equals) the target text.

R8. The watch area can be **defined by drawing** on screen through the existing capture overlay **or bound to a user variable** of the matching type (a `Region`/`QRect`, or a point), chosen through the same literal-or-variable input as the target.

**Variables**

R9. Every configurable input in the step — the watch area (R8), the comparison target (threshold number, target color, or target text), and the read output — offers a literal-or-variable choice: a value defined in place, or a bound user variable. The comparison target may likewise be a typed literal or a bound variable.

R10. The value read off-screen can optionally be written into a user variable (typed to the condition kind) for use by later steps or display in the Variables tab. Storing is opt-in per step.

**Persistence**

R11. A Wait Until step serializes and deserializes with the rest of the timeline like other step types, so recordings that use it persist per profile.

### Key Flows

F1. **Wave-farming loop.**
- **Trigger:** User records a task and inserts a Wait Until step at the front.
- **Steps:** Draw a rect over the wave counter; set condition Number `>=` target, where target is a literal (e.g. `15`) or a bound variable (e.g. `targetWave`); optionally store the read into a variable (e.g. `currentWave`); record the stop-button click and the restart clicks after it; enable the task's repeat.
- **Result:** On run, the task waits until the wave reading meets the target, clicks stop, runs the restart clicks, and the repeat loops back to waiting — re-entering the valuable early loop each cycle.

### Acceptance Examples

AE1. **Covers R5.** OCR reads `17`, target is `15`, operator `>=` → satisfied; the next step runs.

AE2. **Covers R6.** The sampled pixel is within tolerance of the target color → satisfied.

AE3. **Covers R7.** OCR reads `GAME OVER`, target text `GAME OVER`, mode "contains" → satisfied.

AE4. **Covers R9.** Target is bound to variable `targetWave` = 20. The user edits `targetWave` to 10 in the Variables tab → the step now triggers at a reading of ≥ 10 without editing the recording.

AE5. **Covers R3, R2.** The condition never becomes true → the step keeps polling and yielding, stays responsive to F6/F10, and shows no deadlock-watchdog kill dialog.

AE6. **Covers R5.** OCR returns an unparseable reading (e.g. garbled text where a number is expected) → the step treats it as not-yet-satisfied and keeps waiting rather than erroring. (Exact behavior confirmed in Outstanding Questions.)

### Scope Boundaries

**Deferred for later:**
- Image / template-appears condition (`findImageCenter`) — needs new "capture this image as a template" UI the other conditions don't.
- Timeout / max-wait and any timeout action (continue vs abort).

**Outside this product's identity:**
- Branching, if/else, and jump targets — general control flow belongs to the Python task API. The recorder stays linear.

### Dependencies / Assumptions

- Number and Text conditions depend on **Tesseract OCR**, a separate install (hardcoded path `C:\Program Files\Tesseract-OCR\tesseract.exe`), and OCR reads are inherently fuzzy. Color has no such dependency and is the most reliable condition.
- Reuses existing engine primitives: `vision.py` (`captureScreenColor`, `captureScreenText`), the `CaptureMode` capture overlay (POINT / REGION / COLOR), user variables (`addVar` / `VariableStore`), and `GlobalTypeHandler` for typed round-trip of stored/compared values.
- Recorded (manual) tasks run on the cooperative scheduler via `ManualTaskWrapper` — this is what makes cooperative polling feasible without a new execution model.

### Outstanding Questions

Poll cadence and failed-read behavior are resolved in Open Implementation Decisions;
variable read/write typing rides on `updateValue` + `GlobalTypeHandler`. One item remains:

- The full set of Number comparison operators to expose beyond `>=`, `<=`, `==`.

### Sources / Research

- `macro_studio/core/recording/timeline_handler.py` — `ActionType`, `MouseFunction`, `TimelineStep` (add the new step type and its serialization).
- `macro_studio/ui/widgets/recorder/action_bindings.py` — `SneakyWidget` editor family and the enum-dropdown pattern to mirror for condition type and the literal-or-variable picker.
- `macro_studio/vision.py` — `captureScreenColor`, `captureScreenText`, `findImageCenter`.
- `CaptureMode` in `macro_studio/core/types_and_enums.py` — on-screen POINT/REGION/COLOR capture overlay.
- Variables: `addVar` / `VariableStore`; `GlobalTypeHandler` in `macro_studio/core/registries/type_handler.py`.
- `ManualTaskWrapper` / `ManualTaskController` — how recorded tasks execute on the cooperative scheduler.

## Implementation Map

The feature adds **no new execution model**. The runtime is already a cooperative
generator, and the literal-or-variable resolver and the vision calls already exist.
The work is one new poll-and-yield branch plus five supporting changes.

### Runtime spine

`ManualTaskWrapper.runTask()` (`manual_task_wrapper.py:119`) is the generator the
scheduler drives. A `WAIT_UNTIL` branch slots in next to the `DELAY` branch:

```python
elif step.action_type == ActionType.WAIT_UNTIL:
    yield from self._runWaitUntil(step)
```

```python
DEFAULT_POLL = 0.25  # seconds; see IU-DEC-1

def _runWaitUntil(self, step):
    cond = step.value                                   # WaitCondition struct
    while True:
        reading = self._readArea(cond)                  # vision call per type
        if cond.store_var:
            self.var_store.updateValue(cond.store_var, reading)
        if self._evaluate(cond, reading):               # parse failure => False
            return
        yield from taskSleep(cond.poll_interval or DEFAULT_POLL)
```

Every miss passes through `taskSleep`, so the task keeps yielding — pause (F6) and
stop (F10) stay responsive and the deadlock watchdog never fires (R3). A hard
interrupt thrown into the `taskSleep` propagates to the existing
`except TaskInterruptedException` handler with no new handling.

### Implementation Units

Ordered by dependency; each names the file and the change.

IU1. **Data model** — `timeline_handler.py`. Add `ActionType.WAIT_UNTIL`. Model
`TimelineStep.value` for this type as a `WaitCondition` struct (condition type;
watch area; operator/mode; target; color tolerance; optional store-var) with its
own `_toDict` / `fromJson`, using `GlobalTypeHandler` to (de)serialize the embedded
`QRect` / `QColor`. (R1, R11)

IU2. **Variable resolution (read side)** — `manual_task_wrapper.py`. Mirror the
existing `_getMousePos` (`manual_task_wrapper.py:48`): a value is either a literal
(`QRect` / `QColor` / number / str) or a variable name (`str`) resolved via
`self.var_store.get(name).value`. One resolver for the watch area, one for the
target. (R8, R9)

IU3. **Vision mapping + evaluation** — `manual_task_wrapper.py`. `_readArea` and
`_evaluate` dispatch on condition type:
- Number → `captureScreenText(QRect)` → parse number → operator compare. Tesseract.
- Text → `captureScreenText(QRect)` → contains / equals. Tesseract.
- Color → `captureScreenColor(QPoint)` → RGB distance ≤ tolerance. No dependency.
  Note: color reads a **point**, so its watch area is a `QPoint`; Number/Text read a
  **`QRect`**. The editor picks capture mode by condition type. (R4–R7)

IU4. **Editor UI** — `action_bindings.py` + `timeline.py`. New `WAIT_UNTIL` binding
that renders the summary sentence and opens a popup editor (the `TextFunctionDialog`
pattern). Like `DualMouseEditor`, it needs `overlay` + `var_store` injected, so
`TimelineItemWidget`'s special-case construction (`timeline.py:54`) grows a second
branch. Draw/pick actions reuse the `CaptureMode` overlay flow; the `Value | Variable`
toggles reuse the variable-picker pattern. (R1, R8, R9, R10)

IU5. **Palette entry** — `recorder_main.py`. One `ACTION_TYPES` entry (purple, eye
icon, non-pairable). Drag/drop and click-to-add already handle non-pairable steps. (R1)

IU6. **Code export** — `generatePythonCode` (`manual_task_wrapper.py:136`). A
`WAIT_UNTIL` branch emitting an equivalent `while` loop with the vision call and
`taskSleep`, so exported scripts stay faithful.

### Open Implementation Decisions

- **IU-DEC-1 — poll cadence.** Propose a `DEFAULT_POLL` of ~0.25s, not user-tunable
  in v1. Revisit if any condition needs faster reaction.
- **IU-DEC-2 — failed OCR read.** On an unparseable Number read, `_evaluate` returns
  `False` and the loop keeps waiting (satisfies AE6). Confirm this over erroring.

## Verification

No automated suite exists; verify by running the GUI and exercising the flow.

- **Happy path (Color, no OCR):** record a Wait Until (Color) step over a swatch that
  changes, then a follow-up click; run and confirm it blocks until the color matches,
  then continues. Proves the runtime spine without a Tesseract dependency.
- **Number / wave loop (F1):** with Tesseract installed, build the wave-farm loop and
  confirm it waits until the reading crosses the threshold, then runs the stop/restart
  clicks and repeats.
- **Variables both ways:** bind the target to a variable, edit it in the Variables tab
  mid-idle, confirm the trigger threshold changes (AE4); enable store-reading and watch
  the value appear in the Variables tab.
- **Responsiveness (R3, AE5):** while a step is waiting on a condition that never
  becomes true, confirm F6 pause and F10 stop both work and no watchdog kill dialog
  appears.
- **Interrupt parity:** hard-pause during a wait, resume, and confirm behavior matches
  interrupting a `DELAY` (resume proceeds past the step). Flag if undesirable.
- **Persistence:** save a task using the step, reload the profile, confirm the
  condition round-trips intact.
