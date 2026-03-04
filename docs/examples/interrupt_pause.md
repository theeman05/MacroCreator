# Hard Pausable Macro Example
This example demonstrates how to create a robust, long-running task class that correctly handles the Engine's "Interrupt" and "Stop" signals.

## Key Concepts:
1. **Persistence**: Using a class allows you to store state (self.counter) easily.
2. **Hard Pause Safety**: catching TaskInterruptedException to prevent loop breakage.
3. **Cleanup**: Using 'finally' to ensure resources are closed on Stop.

## Implementation:

```python title="examples/interrupt_pause_macro.py"
--8<-- "examples/interrupt_pause_macro.py:pause_interruption_logic"
```

??? tip "View the complete script"
    ```python title="examples/interrupt_pause_macro.py"
    --8<-- "examples/interrupt_pause_macro.py"
    ```
