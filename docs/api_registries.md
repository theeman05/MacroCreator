---
icon: material/dna
---

# Registries

This document details the core registries used in Macro Studio for handling type conversions and data captures. These systems are designed to be extensible, allowing developers to add support for new data types and capture methods.

## Type Handler Overview

The `GlobalTypeHandler` is a static class that provides a centralized system for converting objects to and from human-readable strings. It also manages user-friendly display names for different types. This is crucial for the UI, where variables and action parameters need to be displayed and edited as text.

### Key Concepts

- **Formatter**: A function that takes an object and returns its string representation.
- **Parser**: A function that takes a string and converts it back into an object of a specific type.
- **Display Name**: A user-friendly name for a type (e.g., "Region" for `QRect`).

### Core Methods

#### `register(target_type, formatter, parser, display_name)`
Registers a new type or updates an existing one with custom handlers.

- **`target_type`**: The class you are supporting (e.g., `QRect`).
- **`formatter`**: A function that converts an instance of `target_type` into a string.
- **`parser`**: A function that converts a string back into an instance of `target_type`.
- **`display_name`**: A pretty name to display the type as (e.g., "Region").

#### `toString(obj)`
Converts any object to a string using the best registered formatter. It prioritizes exact type matches, then checks for base types, and finally falls back to `str(obj)`.

#### `fromString(target_type, val_str)`
Converts a string to an instance of the `target_type` using a registered parser. If no custom parser is found, it attempts to call the type's constructor with the string (e.g., `int("123")`).

#### `getDisplayName(target_type)`
Returns the friendly name for a type if registered; otherwise, it defaults to the class name.

### Example: Registering a Custom Type

You can easily add support for new types using the `@register_handler` decorator. This decorator automatically finds `toString`, `fromString`, and `display_name` in your handler class.

```python
from PySide6.QtCore import QSize
from macro_studio import register_handler

@register_handler(QSize)
class QSizeHandler:
    """Handler for converting QSize objects."""
    display_name = "Size"

    @staticmethod
    def toString(obj: QSize) -> str:
        return f"{obj.width()}, {obj.height()}"

    @staticmethod
    def fromString(text: str) -> QSize:
        parts = [p.strip() for p in text.split(',') if p.strip()]
        if len(parts) != 2:
            raise ValueError("QSize requires 2 integers (width, height).")
        vals = [int(p) for p in parts]
        return QSize(vals[0], vals[1])
```

---

## Type Handler API Reference
:::macro_studio.GlobalTypeHandler

---

## Capture Registry Overview

The `GlobalCaptureRegistry` is a static class that manages different "capture modes." A capture mode defines how the user interacts with the screen overlay to capture a specific piece of data, such as a point, a rectangular region, or a color.

### Key Concepts

- **Mode**: A unique identifier for the capture type, usually a `CaptureMode` enum member.
- **Capture Method**: The function that is executed to perform the capture. This function typically interacts with the screen overlay.
- **Type Class**: The Python type of the data that will be captured (e.g., `QPoint`, `QRect`).

### Core Methods

#### `register(mode, tooltip, capture_method, type_class)`
Registers a new capture mode definition.

- **`mode`**: The `CaptureMode` enum member or other hashable key for this capture type.
- **`tooltip`**: A helpful tip displayed to the user during the capture process.
- **`capture_method`**: The function that will be called to perform the capture. It receives the overlay instance and the variable configuration.
- **`type_class`**: The Python type that the captured data will be an instance of (e.g., `QPoint`).

#### `get(mode)`
Retrieves the full `CaptureTypeDef` for a given mode.

#### `getModeFromType(type_class)`
Performs a reverse lookup to find the capture mode associated with a specific Python type.

### Default Capture Modes

Macro Studio pre-registers handlers for common types:

- **`CaptureMode.POINT`**: Captures a `QPoint`.
- **`CaptureMode.REGION`**: Captures a `QRect`.
- **`CaptureMode.COLOR`**: Captures a `QColor`.

All default modes use a generic capture method (`captureOverlayGeneric`) that works with the screen overlay system.

### Examples: Adding Custom Capture Modes

#### 1. Registering via Enum (Implicit Type)

This approach is ideal when managing multiple custom types. By mapping the `Enum` value to a class, the registry automatically identifies the data type. This makes it easy to reference specific capture modes when programmatically creating variables or UI components.

```python
from enum import Enum
from macro_studio import GlobalCaptureRegistry

class MyCircle:
    """Custom data class for storing circle coordinates."""
    def __init__(self, x=0, y=0, radius=0):
        self.x = x
        self.y = y
        self.radius = radius

class CustomCaptureMode(Enum):
    # The registry will automatically infer MyCircle as the type_class
    CIRCLE = MyCircle 

def captureCircleFromOverlay(overlay, config):
    """Custom capture method triggered by the UI."""
    circle_data = MyCircle(10, 10, 50) # Example hardcoded data
    # ... logic to have the user draw a circle ...
    return circle_data

# Register the new mode using the Enum
GlobalCaptureRegistry.register(
    mode=CustomCaptureMode.CIRCLE,
    tooltip="Click and drag to define a circle",
    capture_method=captureCircleFromOverlay
)

```

#### 2. Registering via Hashable String (Explicit Type)

Since `mode` accepts a `Hashable` object, developers do not actually need to create an `Enum`. They can simply pass a string as the `mode` identifier, but they **must** explicitly provide the `type_class` argument to avoid triggering a `ValueError`.

```python
from macro_studio import GlobalCaptureRegistry

class MyPolygon:
    """Custom data class for storing polygon vertices."""
    pass

def capturePolygonFromOverlay(overlay, config):
    polygon_data = MyPolygon()
    # ... logic to click points on the screen ...
    return polygon_data

# Register the new mode using a string identifier and explicit type_class
GlobalCaptureRegistry.register(
    mode="custom_polygon_capture",
    tooltip="Click screen points to draw a polygon",
    capture_method=capturePolygonFromOverlay,
    type_class=MyPolygon
)

```

---

## Capture Registry API Reference
:::macro_studio.GlobalCaptureRegistry