"""A global registry for handling type conversions and display names.

This module provides a centralized system (`GlobalTypeHandler`) for registering
custom formatters and parsers for different Python types. It allows for consistent
conversion of objects to and from human-readable strings, and provides friendly
display names for use in UIs.
"""
import ast
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Type
from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QColor

BASIC_TYPES = (int, float, str, bool, type(None))

# Basic types that we didn't register
DEFAULT_TYPE_CLASS_NAMES = {
    int: "Integer",
    str: "Text",
    float: "Decimal"
}

@dataclass
class RegistryItem:
    """A container for type handling functions and metadata."""
    formatter: Callable[[Any], str] = None
    parser: Callable[[str], Any] = None
    display_name: str = None

class GlobalTypeHandler:
    """A static class for managing type formatters, parsers, and display names.

    This registry allows for the registration of custom functions to convert
    objects to and from strings, and to provide user-friendly names for types.
    """
    _registry: Dict[Type, RegistryItem] = {}
    _type_names_map: Dict[str, Type] = {
        "int": int,
        "float": float,
    }

    @classmethod
    def register(cls, target_type: Type, formatter: Callable[[Any], str] = None, parser: Callable[[str], Any] = None,
                 display_name: str = None):
        """Registers a new type or updates an existing one with custom handlers.

        Args:
            target_type: The class to register (e.g., `QRect`).
            formatter: A function that converts an instance of `target_type`
                into a string.
            parser: A function that converts a string back into an instance
                of `target_type`.
            display_name: A user-friendly name for the type (e.g., "Region").
        """
        reg_item = cls._registry.setdefault(target_type, RegistryItem())
        cls._type_names_map[target_type.__name__] = target_type

        if formatter: reg_item.formatter = formatter
        if parser: reg_item.parser = parser
        if display_name: reg_item.display_name = display_name

    @classmethod
    def toString(cls, obj: Any) -> str:
        """Converts an object to a string using the best available registered formatter.

        The method first attempts an exact type match, then checks for base types,
        and finally falls back to checking for subclass relationships. If no
        registered formatter is found, it defaults to `str(obj)`.

        Args:
            obj: The object to convert to a string.

        Returns:
            A string representation of the object.
        """
        if obj is None:
            return ""

        # Exact Match (Fastest)
        if (reg_item := cls._registry.get(type(obj))) and reg_item.formatter:
            return reg_item.formatter(obj)

        # If it's a basic python type not in exact matches, just return it as a string
        if isinstance(obj, BASIC_TYPES):
            return str(obj)

        # Inheritance Match (Slower, but handles subclasses)
        # We check if the object is an instance of a registered key
        for registered_type, reg_item in cls._registry.items():
            if isinstance(obj, registered_type) and reg_item.formatter:
                return reg_item.formatter(obj)

        # Fallback to str if unregistered type
        return str(obj)

    @classmethod
    def fromString(cls, target_type: Type, val_str: str) -> Any:
        """Converts a string to an instance of the target type using a registered parser.

        If a custom parser is registered for the `target_type`, it will be used.
        Otherwise, it falls back to calling the `target_type`'s constructor
        with the string.

        Args:
            target_type: The desired type of the output object.
            val_str: The string to parse.

        Returns:
            An instance of `target_type`.

        Raises:
            ValueError/TypeError: If parsing fails, either in the custom parser
                or the default constructor.
        """
        # Custom Parsers
        if (reg_item := cls._registry.get(target_type)) and reg_item.parser:
            return reg_item.parser(val_str)

        # Default Casting
        return target_type(val_str)

    @classmethod
    def getDisplayName(cls, target_type: Type) -> str:
        """Gets the user-friendly display name for a given type.

        Args:
            target_type: The type to look up.

        Returns:
            The registered display name, or a capitalized version of the
            class name as a fallback.
        """
        if (reg_item := cls._registry.get(target_type)) and reg_item.display_name:
            return reg_item.display_name

        # Basic types that we don't have anything for
        if target_type in DEFAULT_TYPE_CLASS_NAMES:
            return DEFAULT_TYPE_CLASS_NAMES[target_type]

        if hasattr(target_type, '__name__'):
            return target_type.__name__.capitalize()

        return str(target_type)

    @classmethod
    def getTypeClass(cls, type_name: str) -> Type:
        """Retrieves the class object for a given type name string.

        Args:
            type_name: The name of the type (e.g., "QRect", "int").

        Returns:
            The class object if found, otherwise defaults to `str`.
        """
        if type_name in cls._type_names_map:
            return cls._type_names_map.get(type_name)

        # Fallback to str if unregistered type
        return str

    @classmethod
    def setIfEvals(cls, key: Any, value: Any, to_dict: dict, strict_eval: bool = False):
        """Conditionally sets a key-value pair in a dictionary.

        The value is added to the dictionary only if it evaluates to `True`.
        In `strict_eval` mode, it is only added if it is not `None`.

        Args:
            key: The key to use in the dictionary.
            value: The value to potentially set.
            to_dict: The dictionary to modify.
            strict_eval: If True, only adds the value if it is not `None`.
                If False, adds the value if `bool(value)` is True.
        """
        if not value or (strict_eval and value is None): return
        to_dict[key] = value

    @classmethod
    def getRegisteredTypes(cls) -> list[Type]:
        """Returns a list of all registered types.

        Returns:
            A list containing all type classes that have been registered.
        """
        registered = {t for t in list(cls._registry.keys())}
        registered.update(DEFAULT_TYPE_CLASS_NAMES.keys())
        return list(registered)


# --- Helper Decorator for easy registration ---
def _registerClass(cls: Type, target_type: Type | None = None):
    """Internal helper to register a handler class with the GlobalTypeHandler."""
    GlobalTypeHandler.register(target_type or cls,
                               getattr(cls, "toString", None),
                               getattr(cls, "fromString", None),
                               getattr(cls, "display_name", None)
                               )
    return cls

def register_handler(cls: Type | None = None):
    """A decorator to automatically register a class as a type handler.

    This decorator inspects the decorated class for a `display_name` attribute
    and static methods named `toString` and `fromString`, and registers them
    with the `GlobalTypeHandler`.

    Can be used in two ways:
    - As `@register_handler` on a class that handles its own type.
    - As `@register_handler(TargetType)` on a class that acts as a proxy
      handler for `TargetType`.

    Args:
        cls: The class to decorate or the target type to handle.

    Returns:
        The decorated class or a wrapper function.
    """
    # HEURISTIC: Use 'duck typing' to detect if 'cls' is the Handler Class.
    # If it is a class AND has the methods we expect, it's the Handler (Direct Mode).
    is_likely_handler = (
        inspect.isclass(cls) and
        hasattr(cls, "display_name") and
        (hasattr(cls, "toString") or hasattr(cls, "fromString"))
    )

    if is_likely_handler:
        # Case 1: @registerHandler (No Parens) on a class with correct methods
        return _registerClass(cls)

    # Case 2: @registerHandler(QRect) (Target Type passed as argument)
    target_type = cls
    def wrapper(handler_cls):
        return _registerClass(handler_cls, target_type)

    return wrapper

# --- Custom type registration ---
@register_handler(QRect)
class QRectHandler:
    """Handler for converting QRect objects."""
    display_name = "Region"

    @staticmethod
    def toString(obj: QRect) -> str:
        return f"{obj.x()}, {obj.y()}, {obj.width()}, {obj.height()}"

    @staticmethod
    def fromString(text: str) -> QRect:
        parts = [p.strip() for p in text.split(',') if p.strip()]

        if len(parts) != 4:
            raise ValueError(f"QRect requires 4 integers (x, y, w, h). Found {len(parts)}.")

        try:
            vals = [int(p) for p in parts]
            return QRect(vals[0], vals[1], vals[2], vals[3]).normalized()
        except ValueError:
            raise ValueError(f"Could not convert parts to integers: {text}")


@register_handler(QPoint)
class QPointHandler:
    """Handler for converting QPoint objects."""
    display_name = "Point"
    @staticmethod
    def toString(point: QPoint) -> str:
        return f"{point.x()}, {point.y()}"

    @staticmethod
    def fromString(text: str) -> QPoint:
        parts = [p.strip() for p in text.split(',') if p.strip()]

        if len(parts) != 2:
            raise ValueError(f"QPoint requires 2 integers (x,y). Found {len(parts)}.")

        try:
            vals = [int(p) for p in parts]
            return QPoint(vals[0], vals[1])
        except ValueError:
            raise ValueError(f"Could not convert parts to integers: {text}")

@register_handler(QColor)
class QColorHandler:
    """Handler for converting QColor objects."""
    display_name = "Color"

    @staticmethod
    def toString(color: QColor) -> str:
        # Returns comma-separated RGB(A) format to stay consistent with QPoint and QRect
        if color.alpha() < 255:
            return f"{color.red()}, {color.green()}, {color.blue()}, {color.alpha()}"
        return f"{color.red()}, {color.green()}, {color.blue()}"

    @staticmethod
    def fromString(text: str) -> QColor:
        text = text.strip()

        # Handle Hex format (e.g., "#FF0000") or standard color names (e.g., "red")
        if text.startswith("#") or text.isalpha():
            color = QColor(text)
            if not color.isValid():
                raise ValueError(f"Invalid color format or name: {text}")
            return color

        # Handle comma-separated RGB(A) format (e.g., "255, 0, 0" or "255, 255, 255, 128")
        parts = [p.strip() for p in text.split(',') if p.strip()]

        if len(parts) not in (3, 4):
            raise ValueError(f"QColor requires 3 or 4 integers (r, g, b, [a]). Found {len(parts)}.")

        try:
            vals = [int(p) for p in parts]
            if len(vals) == 3:
                return QColor(vals[0], vals[1], vals[2])
            return QColor(vals[0], vals[1], vals[2], vals[3])
        except ValueError:
            raise ValueError(f"Could not convert RGB(A) parts to integers: {text}")

# --- Python type registration ---
@register_handler(bool)
class BooleanHandler:
    """Handler for converting boolean values from strings."""
    display_name = "Boolean"

    @staticmethod
    def fromString(text: str) -> bool:
        clean = text.strip().lower()
        return clean in ("true", "1", "yes", "on", "t")

@register_handler(list)
class ListHandler:
    """Handler for converting list objects."""
    @staticmethod
    def toString(val: list) -> str:
        return str([GlobalTypeHandler.toString(item) for item in val])

    @staticmethod
    def fromString(text: str) -> list:
        text = text.strip()

        # Handle empty input
        if not text:
            return []

        # Add brackets if user forgot them: "1, 2, 3" -> "[1, 2, 3]"
        if not text.startswith("["):
            text = f"[{text}]"

        try:
            # NOTE: This returns basic types (int, float, str).
            # It does NOT automatically convert "1, 1" back to QPoint
            # because a generic list doesn't know what type it holds.
            val = ast.literal_eval(text)

            if not isinstance(val, list):
                raise ValueError("Parsed value is not a list")

            return val
        except (ValueError, SyntaxError):
            raise ValueError(f"Invalid list format: {text}")

@register_handler(tuple)
class TupleHandler:
    """Handler for converting tuple objects."""
    @staticmethod
    def toString(val: tuple) -> str:
        return str(tuple(GlobalTypeHandler.toString(item) for item in val))

    @staticmethod
    def fromString(text: str) -> tuple:
        text = text.strip()

        if not text:
            return ()

        # Add parens if user forgot them: "1, 2" -> "(1, 2)"
        # Note: Users must explicitly type "1," (with comma) for single-item tuples
        if not text.startswith("("):
            text = f"({text})"

        try:
            val = ast.literal_eval(text)

            # Edge case: "(1)" parses as int 1, not tuple (1,).
            # We fail here so user knows to add a comma.
            if not isinstance(val, tuple):
                raise ValueError("Parsed value is not a tuple (Did you forget a comma for a single item?)")

            return val
        except (ValueError, SyntaxError):
            raise ValueError(f"Invalid tuple format: {text}")