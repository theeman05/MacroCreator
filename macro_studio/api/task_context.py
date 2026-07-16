"""Provides the TaskContext class, the primary API for task interaction."""
from functools import wraps
from typing import TYPE_CHECKING, Hashable, Any

from macro_studio.core.types_and_enums import LogLevel, TaskDeletedError

if TYPE_CHECKING:
    from macro_studio.core.controllers.task_controller import TaskController


def require_active_task(func):
    """Decorator: Ensures the task is active before executing the method.

    This decorator wraps methods of `TaskContext` to check if the underlying
    task controller is still valid and active. If the task has been deleted,
    it raises a `TaskDeletedError`.

    Args:
        func: The method of `TaskContext` to be decorated.

    Returns:
        Callable: The wrapped method.

    Raises:
        TaskDeletedError: If the task associated with this context has been deleted.
    """
    @wraps(func)
    def wrapper(self: "TaskContext", *args, **kwargs):
        is_valid = self.isValid()

        if not is_valid:
            raise TaskDeletedError(
                f"Handle Error: Task '{self._controller.name}' has been deleted and cannot be accessed."
            )

        return func(self, *args, **kwargs)

    return wrapper


class TaskContext:
    """Provides an API for interacting with and controlling a single task.

    This class acts as a handle for tasks registered with the `MacroStudio` engine,
    allowing them to query variables, log messages, and control their own
    lifecycle (pause, resume, stop, restart) or that of other tasks. An instance
    of this class is typically passed as the first argument to task functions.
    """
    def __init__(self, controller: "TaskController"):
        """Initializes a TaskContext instance.

        Args:
            controller: The internal `TaskController` managing this task.
        """
        self._controller = controller

    # --- Properties ---
    @property
    def repeat(self) -> bool:
        """Represents whether the task should automatically restart upon finishing.

        Returns:
            ``True`` if the task is set to repeat, ``False`` otherwise.
        """
        return self._controller.repeat

    @repeat.setter
    def repeat(self, value: bool):
        self._controller.repeat = value

    @property
    def display_name(self) -> str:
        """Gets or sets the display name of the task.

        If `None` is provided, the function's original name will be used as the display name.

        Notes:
            This name is used purely for display in the UI, **not** for task lookup.

        Returns:
            The current display name of the task.
        """
        return self._controller.display_name

    @display_name.setter
    def display_name(self, value: str | None):
        self._controller.display_name = value or self._controller.func.__name__

    @property
    def is_paused(self) -> bool:
        """Checks if the task is currently in a paused or interrupted state.

        Returns:
            `True`` if the task is paused or interrupted, ``False`` otherwise.
        """
        return self._controller.isPaused()

    @property
    def is_interrupted(self) -> bool:
        """Checks if the task is currently in an interrupted state.

        An interrupted task has had its execution flow broken (e.g., by `TaskInterruptedException`)
        to allow for cleanup.

        Returns:
            ``True`` if the task is interrupted, ``False`` otherwise.
        """
        return self._controller.isInterrupted()

    @property
    def is_queued(self):
        """Checks if the task is queued to run on the next run cycle.

        Returns:
            ``True`` if the task is queued, ``False`` otherwise.
        """
        return self._controller.isQueued()

    @property
    def is_ready(self):
        """Checks if the task is resting and ready to be queued for execution.

        This includes tasks that have never run (Idle) and tasks that
        have completed their previous lifecycle (Dead).

        Returns:
            ``True`` if the task is ready, ``False`` otherwise.
        """
        return self._controller.isReady()

    @property
    def is_running(self) -> bool:
        """Checks if the task is actively running.

        Returns:
            ``True`` if the task is currently executing, ``False`` otherwise.
        """
        return self._controller.isRunning()

    @property
    def is_alive(self) -> bool:
        """Checks if the task is currently active or armed for execution.

        This property indicates the local state of the task. It returns ``True``
        if the task has not reached a terminal state (e.g., Stopped, Finished,
        or Crashed), and is not Idle. This local state remains ``True`` even if the master engine's
        global worker is currently paused or completely offline.

        Returns:
            ``True`` if the task is alive, ``False`` otherwise.
        """
        return self._controller.isAlive()

    # --- Methods ---
    def getName(self) -> str:
        """Retrieves the internal name of the task.

        Returns:
            The internal name of the task.
        """
        return self._controller.name

    def isEnabled(self) -> bool:
        """Checks if the task is currently enabled.

        An enabled task will be considered for execution by the engine.

        Returns:
            bool: True if the task is enabled, False otherwise.
        """
        return self._controller.isEnabled()

    def isValid(self) -> bool:
        """Safely checks if the underlying task controller is still valid.

        This method can be called without fear of raising a `TaskDeletedError`.

        Returns:
            bool: True if the task controller is valid, False otherwise.
        """
        return self._controller.isValid()

    def isSolo(self):
        """Checks if the task is currently solo selected.
        Returns:
            bool: True if the task controller is solo selected, False otherwise
        """
        return self._controller.isSolo()

    @require_active_task
    def setEnabled(self, enabled: bool):
        """Enables or disables the task.

        An enabled task will be run by the engine; a disabled task will be skipped.

        Args:
            enabled: If True, enables the task. If False, disables it.
        """
        self._controller.setEnabled(enabled)

    @require_active_task
    def restart(self):
        """Restarts the task.

        This kills the current instance of the task and schedules a fresh one
        to start at the next work cycle of the engine.
        """
        self._controller.restart()

    @require_active_task
    def pause(self, interrupt: bool = False) -> bool:
        """Pauses the task execution.

        If the task is not already paused, this halts its execution before
        running its next step.

        Args:
            interrupt: Controls how the pause is handled.

                *   `True`: **Interrupts** the task. This raises a
                    `TaskInterruptedException` within the task, allowing it
                    to **release keys** and **clean up resources** safely
                    (e.g., cutting short a `taskSleep`).
                *   `False` (Default): **Freezes** the task in place. The
                    generator execution is suspended at the exact current line.
                    No cleanup logic is triggered; held keys remain held, and
                    local variables are preserved as-is.

        Returns:
            ``True`` if the pause command was issued successfully, ``False`` if
                the engine has stopped abruptly or the task could not be paused.
        """
        return self._controller.pause(interrupt)

    @require_active_task
    def resume(self) -> float | None:
        """Resumes a previously paused task.

        If the engine is running and the task was previously paused, this
        method resumes its execution from where it left off. If the task
        has already finished, this method does nothing.

        Returns:
            The duration in seconds for which the task was paused,
                or ``None`` if the task was not paused or could not be resumed.
        """
        return self._controller.resume()

    @require_active_task
    def stop(self):
        """Stops the task.

        This attempts to stop a task on its next execution cycle. The task
        will transition to a terminal state.
        """
        self._controller.stop()

    def log(self, *args: Any, level: LogLevel = LogLevel.INFO):
        """Sends a structured log message to the UI.

        Args:
            *args: The objects to be printed in the log message. If the log
                level is not `ERROR`, these arguments will be automatically
                cast to strings.
            level: The `LogLevel` at which to display the message (e.g., INFO, WARN, ERROR).
                Defaults to `LogLevel.INFO`.
        """
        self._controller.log(*args, level=level)

    def logError(self, error_msg: str, trace: str = ""):
        """Sends a specialized error log message to the UI.

        This method is specifically for logging errors and includes an optional
        stack trace.

        Args:
            error_msg: The main error message to display.
            trace: An optional stack trace string associated with the error.
                Defaults to an empty string.
        """
        self._controller.logError(error_msg, trace)

    def getVar(self, key: Hashable) -> Any | None:
        """Retrieves the current value of a setup variable.

        Args:
            key: The hashable identifier of the variable to retrieve.

        Returns:
            The value of the setup variable if present, otherwise None.
        """
        return self._controller.getVar(key)