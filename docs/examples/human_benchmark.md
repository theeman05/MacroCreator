# Human Benchmarking Macro

This example demonstrates how to build a reactive bot by splitting logic into two specialized tasks: a **Scanner** and a **Bot**. This "Producer-Consumer" pattern is the most efficient way to handle high-speed pixel monitoring without blocking the UI or engine.


## Key Concepts

### 1. Decoupled State Management

Instead of having one massive function that scans *and* clicks, we separate the concerns into two classes:

* **`BenchmarkScanner`**: Responsible only for visual input. It updates a boolean flag, `is_target_color`, as fast as the engine allows.
* **`ReactionBot`**: Watches that flag and executes the click the millisecond it turns true.

### 2. Using Global Variables with `addVar`

To make the macro flexible, we use the engine's built-in variable system. This allows the user to pick the target point and color through the UI rather than hardcoding coordinates:

* **`CaptureMode.POINT`**: Opens a crosshair for the user to select the click location.
* **`CaptureMode.COLOR`**: Opens a color picker to define exactly what shade of "Green" the bot is looking for.

### 3. High-Frequency Polling (`repeat=True`)

By setting `repeat=True` when calling `addBasicTask`, these functions act as high-speed loops. The engine automatically handles the re-execution, allowing the scanner to poll the screen colors continuously.

### 4. Edge Triggering and Debouncing

To prevent the bot from clicking a thousand times while the screen is green, we implement a simple state check:

* **State Locking**: We use `clicked_already` to ensure only one click occurs per color change.
* **The Reset**: The flag is only reset when the `is_target_color` returns to false (when the screen turns red or blue again), preparing the bot for the next round.

---

## The Implementation

This setup uses `pydirectinput` to click once the color is detected.

```python title="examples/human_benchmark_macro.py"
--8<-- "examples/human_benchmark_macro.py:humanized_reaction_logic"
```

??? tip "View the complete runnable script"
    ```python title="examples/human_benchmark_macro.py"
    --8<-- "examples/human_benchmark_macro.py"
    ```
