"""Provides the ThreadContext class for thread-specific task operations."""
from typing import TYPE_CHECKING
from .task_context import TaskContext, require_active_task

if TYPE_CHECKING:
    from macro_studio.core.controllers.threaded_controller import ThreadedController

class ThreadContext(TaskContext):
    """Extends `TaskContext` for tasks running in a separate thread.

    This context provides additional functionalities specific to threaded tasks,
    such as blocking sleep operations that do not affect the main application
    or other tasks.
    """
    _controller: "ThreadedController"

    @require_active_task
    def sleep(self, duration: float = 0.01):
        """Blocks the current thread with high precision for a specified duration.

        This method is suitable for threaded tasks that need to pause their
        execution without yielding control back to the main engine.

        Args:
            duration: The duration in seconds to sleep the thread.
                Defaults to 0.01 seconds.

        Raises:
            TaskAbortException: If the task is stopped while sleeping.
            TaskInterruptedException: If the task is interrupted while sleeping.
        """
        self._controller.sleep(duration)

    @require_active_task
    def waitForResume(self):
        """Blocks the thread if the system or this task is in an interrupted pause.

        This method will only block the thread if the task or the entire system
        is in a "hard" (interrupted) pause state. If the task is merely
        "soft-paused" (e.g., waiting for a logical condition), this method
        returns immediately.

        Raises:
            TaskAbortException: If the task is stopped while waiting for resume.
        """
        self._controller.waitForResume()