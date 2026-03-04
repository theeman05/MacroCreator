# Threaded Task Creation

This example demonstrates how to create a threaded task runs in its own thread. It demonstrates how to handle 'Interrupted Pauses' (Safety Stops) and Aborts correctly without crashing.

## Key Concepts

Managing background threads in a desktop automation environment requires careful handling to ensure that a "Pause" or "Stop" command actually halts execution immediately without leaving orphan processes or corrupted resources.

### 1. The Thread Controller vs. Basic Controller

While standard tasks use `yield` to give control back to the engine, threaded tasks run on a separate OS thread. Because of this, they use a specialized `ThreadController` which provides blocking methods like `controller.sleep()` and `controller.waitForResume()` to keep the thread synchronized with the main engine state.

### 2. Handling "Hard" Pauses (Interrupted Pauses)

When a user triggers a pause, the engine can perform an "Interrupted Pause" (Hard Pause).

* **The Mechanism**: The engine uses `.throw()` to inject a `TaskInterruptedException` directly into the thread.
* **The Benefit**: This immediately breaks the thread out of a long `controller.sleep()` call.
* **Safety**: By wrapping your logic in a `try/except/finally` block, you can catch this interruption to safely release resources (like file handles or network sockets) before the thread is fully suspended.

### 3. Graceful Aborts

If a macro is stopped entirely, the engine throws a `TaskAbortException`.

* **Immediate Exit**: Unlike a pause, an abort signifies the end of the task's lifecycle.
* **Best Practice**: You should always catch this at the top level of your `ThreadFunc` and return immediately to ensure the thread terminates and doesn't "hang" in the background.

### 4. Deterministic Resumption

After a hard pause, a thread may be in an inconsistent state. The `controller.waitForResume()` method acts as a synchronization barrier. It ensures that the thread remains stationary until the user explicitly hits "Play" again, preventing the macro from "jumping ahead" while the engine is still paused.

### 5. Managing Real-Time Drift

Because threaded tasks can be interrupted, calculating durations based on wall-clock time (`time.time()`) can be misleading. In the provided example, we calculate the `target_duration` to demonstrate how the total elapsed real time might exceed the actual "active" time if the task was paused mid-sleep.

## The Implementation

```python title="examples/threaded_macro.py"
--8<-- "examples/threaded_macro.py:thread_logic"
```

??? tip "View the complete script"
    ```python title="examples/threaded_macro.py"
    --8<-- "examples/threaded_macro.py"
    ```
