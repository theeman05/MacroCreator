"""This module handles the core application lifecycle and task management."""
import sys
from typing import TYPE_CHECKING, Hashable, Union, Any
from PySide6.QtCore import QTimer

from macro_studio.core.types_and_enums import TaskFunc, LogLevel, CaptureMode
from macro_studio.core.data import Profile
from macro_studio.core.utils import global_logger
from macro_studio.ui.main_window import MainWindow
from macro_studio.core.controllers.task_manager import TaskManager

if TYPE_CHECKING:
    from macro_studio.api import (TaskContext as Controller,ThreadContext as ThreadedController)


class MacroStudio:
    """The central engine for managing and executing macros.

    This class provides the main interface for registering tasks, managing
    variables, controlling the UI overlay, and handling the overall execution
    lifecycle of macros.

    To use the engine, instantiate it and call `launch()`:

    ```python
    main_studio = MacroStudio()
    main_studio.launch()
    ```
    """
    def __init__(self, macro_name: str = "Default"):
        """Initializes the MacroStudio engine.

        Args:
            macro_name: An optional name for the initial macro profile to load.
                If not provided, "Default" will be used.
        """
        self._profile = Profile()
        self._manager = TaskManager(self, self._profile)

        # Setup UI stuff
        self.ui = MainWindow(self._manager, self._profile)
        self.app = self.ui.app
        self.overlay = self.ui.overlay

        self._init_profile_name = macro_name

        # Connect Listeners
        self.ui.start_signal.connect(self.startExecution)
        self.ui.pause_signal.connect(self.pauseExecution)
        self.ui.stop_signal.connect(self.cancelExecution)
        self._manager.finished_signal.connect(lambda: self.cancelExecution(True))

    @property
    def repeat_delay(self) -> float:
        """The delay (in seconds) applied between repetitions of tasks.

        Returns:
            The current repeat delay in seconds.
        """
        return self._manager.repeat_delay

    @repeat_delay.setter
    def repeat_delay(self, delay: float):
        if delay < 0: raise ValueError(f"repeat_delay must be 0 or greater. Received: {delay}")
        self._manager.repeat_delay = delay

    def addVar(self, key: Hashable, data_type: CaptureMode | type, default_val: object = None, pick_hint: str = None):
        """Adds a user-definable variable to the current profile.

        These variables can be configured by the user through the UI and
        their values can be retrieved during task execution.

        Args:
            key: A unique, hashable identifier for the variable (e.g., a string).
            data_type: The expected data type or capture mode for the variable.
                Can be a Python type (e.g., `int`, `str`) or a `CaptureMode` enum
                member (e.g., `CaptureMode.POINT`, `CaptureMode.REGION`).
            default_val: The initial default value for the variable.
            pick_hint: A descriptive hint displayed to the user when they are
                prompted to "pick" a value for this variable (e.g., "Click a point on screen").
        """
        self._profile.vars.add(key, data_type, default_val, pick_hint)

    def getVar(self, key: Hashable) -> Any | None:
        """Retrieves the current value of a registered setup variable from the current profile.

        Args:
            key: The hashable identifier of the variable to retrieve.

        Returns:
            The current value of the variable if found, otherwise ``None``.
        """
        var_config = self._profile.vars.get(key)
        return var_config.value if var_config else None

    def addBasicTask(self, task_func: TaskFunc, *args: Any, enabled: bool = True, repeat: bool = False, display_name: str | None = None, **kwargs: Any) -> "Controller":
        """Registers a basic task function for execution within the macro studio.

        Basic tasks run sequentially and are managed directly by the main execution thread.

        Args:
            task_func: The Python function that defines the task's logic.
                It should be a generator function that yields control to the engine.
            *args: Positional arguments to pass to `task_func` when it is executed.
            enabled: If True, the task will be included in the execution cycle
                when `startExecution()` is called. Defaults to True.
            repeat: If True, the task will automatically restart upon completion.
                Defaults to False.
            display_name: An optional name to display for this task in the UI.
                If None, the function's `__name__` will be used.
            **kwargs: Keyword arguments to pass to `task_func` when it is executed.

        Returns:
            A `TaskContext` object, which is a handle to the registered task
                allowing for programmatic control (e.g., pausing, stopping).
        """
        return self._manager.createController(
            task_func=task_func,
            is_enabled=enabled,
            repeat=repeat,
            display_name=display_name,
            task_args=args,
            task_kwargs=kwargs
        )

    def addThreadTask(self, fun_in_thread: TaskFunc, *args: Any, enabled: bool = True, repeat: bool = False, display_name: str | None = None, **kwargs: Any) -> "ThreadedController":
        """Registers an advanced task function to run in a separate thread.

        Threaded tasks execute concurrently with other tasks and the main UI thread,
        suitable for long-running or blocking operations that shouldn't halt the UI.

        Args:
            fun_in_thread: The Python function that defines the task's logic.
                It should be a generator function that yields control to the engine.
            *args: Positional arguments to pass to `fun_in_thread` when it is executed.
            enabled: If True, the task will be included in the execution cycle
                when `startExecution()` is called. Defaults to True.
            repeat: If True, the task will automatically restart upon completion.
                Defaults to False.
            display_name: An optional name to display for this task in the UI.
                If None, the function's `__name__` will be used.
            **kwargs: Keyword arguments to pass to `fun_in_thread` when it is executed.

        Returns:
            A `ThreadedController` object, which is a handle to the registered threaded task allowing for programmatic control.
        """
        return self._manager.createThreadController(
            task_func=fun_in_thread,
            is_enabled=enabled,
            repeat=repeat,
            display_name=display_name,
            task_args=args,
            task_kwargs=kwargs
        )

    def getController(self, name_or_id: str | int) -> Union["Controller", "ThreadedController", None]:
        """Retrieves a task or thread controller handle by its name or internal ID.

        Note: For coded tasks, the `display_name` provided during registration
        is used for lookup, not the function's `__name__`.

        Args:
            name_or_id: The display name (string) or internal ID (integer) of the task.

        Returns:
            The `TaskContext` or `ThreadedController` instance if found, otherwise None.
        """
        return self._manager.getController(name_or_id)

    def isRunningTasks(self) -> bool:
        """Checks if any tasks are currently running or paused.

        Returns:
            ``True`` if the execution engine is active (running or paused), ``False`` otherwise.
        """
        return self._manager.worker.isAlive()

    def startExecution(self):
        """Initiates or resumes the execution of registered tasks.

        If the engine is currently paused, this method will resume its execution.
        If no tasks are running, it will start the execution worker and
        update the UI visuals.
        """
        if self.isRunningTasks():
            if self.isPaused():
                self.resumeExecution()
            return

        self.ui.startMacroVisuals()
        self._manager.startWorker()

    def cancelExecution(self, completed: bool = False):
        """Cancels all currently executing tasks and stops the execution engine.

        This will stop any running tasks and reset the UI visuals.

        Args:
            completed: If True, indicates that the cancellation is due to all
                tasks having completed successfully, rather than an explicit
                user cancellation. Defaults to False.
        """
        if not self.isRunningTasks():
            self.ui.stopMacroVisuals()
            return
        self.ui.startMacroVisuals()
        success = self._manager.stopWorker()
        if success:
            global_logger.log("Globally Cancelled Execution" if not completed else "Macro Finished. All tasks completed.")
            self.ui.stopMacroVisuals()

    def pauseExecution(self, interrupt: bool = False) -> bool:
        """Pauses the currently running tasks.

        Args:
            interrupt: Controls the mechanism used to pause.

                *   ``True``: **Interrupt & Cleanup.** Raises a `TaskInterruptedException`
                    inside the task. This breaks the current step immediately (e.g.,
                    cuts short a `taskSleep`), runs any `try/finally` cleanup blocks
                    to **release keys** and reset state, and then suspends.
                *   ``False``: **Freeze.** Suspends the generator execution at the exact
                    current line. No cleanup logic is triggered; held keys remain held
                    and local variables are preserved exactly as-is.

        Raises:
            ValueError: If the provided delay is a negative value.

        Returns:
            ``True`` if the pause command was issued successfully; ``False`` if the engine
                could not be paused (e.g., worker was already stopped).
        """
        if not self.isRunningTasks():
            global_logger.log("Cannot pause: Worker is already stopped.", level=LogLevel.WARN)
            self.ui.stopMacroVisuals()
            return False

        self.ui.resumeMacroVisuals()
        success = self._manager.pauseWorker(interrupt)
        if success:
            if self.isRunningTasks():
                self.ui.pauseMacroVisuals(interrupt)
                if interrupt:
                    global_logger.log(
                        "Global Interrupt Active: Running tasks interrupted and cleaned up. (Current wait timers cancelled).")
                else:
                    global_logger.log("Global Pause Active")
            else:
                # Interrupt killed running tasks
                self.ui.stopMacroVisuals()

        return success

    def isPaused(self) -> bool:
        """Checks if the execution engine is currently in a paused state.

        Returns:
            ``True`` if the engine is paused, ``False`` otherwise.
        """
        return self._manager.worker.isPaused()

    def resumeExecution(self) -> Union[float, None]:
        """Resumes macro execution if it was previously paused.

        Returns:
            The duration in seconds for which the execution was paused,
                or ``None`` if the engine was not paused or could not be resumed.
        """
        elapsed = self._manager.resumeWorker()
        if elapsed is not None:
            global_logger.log(f"Resumed Execution After {elapsed:.2f} Seconds.")
            self.ui.resumeMacroVisuals()

        return elapsed

    def _loadInitProfile(self):
        """Loads the initial macro profile based on the `_init_profile_name`."""
        profile_name = self._init_profile_name
        self._init_profile_name = None
        self._profile.load(profile_name)

    def launch(self):
        """Initializes the UI, loads the default profile, and starts the main application loop.

        This method must be called after configuring your tasks and variables
        using `addBasicTask`, `addThreadTask`, and `addVar`. It blocks until
        the application exits.

        Raises:
            SystemExit: When the Qt application event loop finishes.
        """
        if not self._init_profile_name:
            return
        self.ui.show()
        self.app.exit()

        QTimer.singleShot(0, self._loadInitProfile)

        sys.exit(self.app.exec())