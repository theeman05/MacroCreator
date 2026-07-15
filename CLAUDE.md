# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Macro Studio is a Windows desktop automation framework (PySide6 GUI + Python engine).
Users write automation logic as Python **generator functions** ("tasks") that `yield`
control back to a cooperative scheduler, or record mouse/keyboard sequences via the GUI.
The public API is `macro_studio/__init__.py`; a user script instantiates `MacroStudio`,
registers tasks/variables, and calls `launch()` (see `examples/` and `test/` for patterns).

## Commands

```bash
# Run the GUI app
python -m macro_studio.main          # or: macro-studio (installed entry point)

# Run an example / ad-hoc script (these ARE the manual test harness)
python examples/threaded_macro.py
python test/my_tester.py

# Install for development
pip install -e .

# Build the standalone Windows .exe
pyinstaller MacroStudio.spec

# Build the docs site (Zensical / mkdocs-style, config in zensical.toml)
zensical build      # or: zensical serve
```

There is **no automated test suite**. `test/` holds runnable macro scripts used for
manual verification against real games/websites, not unit tests. Verifying a change
means running the GUI and exercising the affected flow.

Bump `__version__` in `macro_studio/version.py` to release (pyproject reads it dynamically).

## Architecture

### The cooperative scheduler (the heart of the engine)

Tasks are Python generators. The engine never uses one OS thread per task; instead a
single `TaskWorker` (a `QThread`) drives all tasks on a **time-ordered heap**:

- `core/execution/task_worker.py` — `TaskWorker.run()` pops the controller with the
  earliest `wake_time`, calls `next(controller)`, and reschedules it at
  `current_time + yielded_duration`. A task that `yield`s a float sleeps that long
  *without blocking other tasks*. This is why task code uses `yield from taskSleep(x)`
  instead of `time.sleep(x)`.
- `core/controllers/task_controller.py` — `TaskController` wraps one task's generator,
  its lifecycle `TaskState` (IDLE → QUEUED → RUNNING → PAUSED/INTERRUPTED → dead), and
  the `_generation` counter used to invalidate stale heap entries after restart/resume.
- `api/task_context.py` — `TaskContext` (aliased `Controller`) is the **only** object a
  task should touch. It is injected as the `controller` argument if the task function
  declares one. Never hand a raw `TaskController` to user code.

### Pause semantics — soft vs. hard (interrupt)

This distinction is pervasive; get it right when touching execution code:

- **Soft pause** (`pause(interrupt=False)`): freezes the generator on its current line.
  Held keys stay held, locals preserved. No cleanup runs.
- **Hard pause / interrupt** (`pause(interrupt=True)`): throws `TaskInterruptedException`
  into the generator so `try/finally` blocks run (releasing keys via `holdKey`/`mouseClick`
  context managers), then suspends until resume. Actions like `taskHoldKey` catch it and
  fall through to `taskWaitForResume()`.

Terminal exceptions live in `core/types_and_enums.py`: `TaskInterruptedException` (hard
pause), `TaskAbortException` (stopped), `TaskDeletedError`. They subclass `BaseException`
(not `Exception`) so a task's bare `except Exception` won't swallow lifecycle control flow.

### Threaded tasks

`addThreadTask` uses `ThreadedController` (`core/controllers/threaded_controller.py`),
which spawns a real OS thread for genuinely blocking work while a monitor generator polls
its health on the worker heap. Threaded tasks use blocking `controller.sleep()` /
`controller.waitForResume()` (via `ThreadContext`) instead of `yield from`. This is the
"bridge" that lets blocking code coexist with the cooperative scheduler.

### Solo mode & watchdog

- `TaskManager` (`core/controllers/task_manager.py`) owns all controllers and mediates
  between the engine and the worker. A **solo controller** is exclusive: setting it stops
  every other task (`enforceSoloLock`). `isSoloable()` gates whether a task may run.
- A watchdog (`_checkWorkerHealth`) detects a task that hasn't yielded for
  `PULSE_DEADLOCK_DURATION_S` and can force-terminate a deadlocked worker via a dialog
  (`_tryShowKillDialog`). Long-running blocking code in a *basic* (non-thread) task will
  trip this — that's a signal it should be an `addThreadTask` instead.

### Data & persistence

- SQLite DB at `%APPDATA%/MacroStudio/macro_studio.db` (`core/data/database_manager.py`,
  a singleton). Stores **profiles**, recorded **tasks**, and **profile_tasks**
  relationships (which recorded tasks belong to a profile, with per-relationship
  `repeat`/`is_enabled`).
- `Profile` (`core/data/profile.py`) is the live session state and emits Qt signals
  (`loaded`, `relationshipCreated`) that `TaskManager` and the UI subscribe to.
  Recorded ("manual") tasks become `ManualTaskController`s driven by `ManualTaskWrapper`.
- User-facing **variables** (`addVar`) are typed values exposed in the GUI. Values persist
  per-profile via `VariableStore`.

### Type registry (extensibility point)

`core/registries/type_handler.py` — `GlobalTypeHandler` maps Python/Qt types to
string formatters/parsers and friendly display names so custom types render and round-trip
in the Variables GUI. Register with the `@register_handler` decorator. Built-in support:
`QRect` (Region), `QPoint` (Point), `QColor` (Color), plus bool/list/tuple. `CaptureMode`
(in `types_and_enums.py`) ties POINT/REGION/COLOR to on-screen overlay capture.

### UI layer

`ui/main_window.py` (`MainWindow`, a `QMainWindow`) is the top-level window: it owns the
global hotkeys (F6 start/pause, F8 record-or-interrupt, F10 stop), the three tabs
(`ui/tabs/`: Task Manager, Variables, Recorder), the transparent screen `overlay`, the
tray icon, and the console log dock. It communicates with the engine purely through Qt
signals (`start_signal`, `stop_signal`, `pause_signal`). `MacroStudio.__init__`
(`core/execution/engine.py`) wires those signals to `startExecution`/`pauseExecution`/
`cancelExecution`.

### Vision

`macro_studio/vision.py` — screen reading via `mss` + OpenCV + Tesseract OCR
(`captureScreenColor`, `captureScreenText`, `findImageCenter`). OCR requires a separately
installed Tesseract binary (hardcoded path `C:\Program Files\Tesseract-OCR\tesseract.exe`);
color/image functions do not.

## Conventions

- **Windows-only** by design: uses `pydirectinput` (DirectInput scan codes, needed so games
  register input), `winsound`, `ctypes.windll`, `%APPDATA%`. Actions set `pydirectinput.PAUSE = 0`.
- Method/function names are **camelCase** (e.g. `addBasicTask`, `resetGeneratorAndGetSortKey`),
  not PEP 8 snake_case. Match the surrounding style.
- Concurrency: `TaskController`/`TaskWorker` guard shared state with `QMutex`/`QMutexLocker`.
  Methods prefixed `_unsafe*` assume the caller already holds the lock — never call them
  unlocked.
- Public API surface is whatever is exported in `macro_studio/__init__.py`. User docstrings
  follow Google style (rendered by mkdocstrings into `docs/`).
