"""A global registry for managing and looking up capture mode definitions.

This module provides a centralized system for registering different types of
data captures (e.g., screen points, regions, colors) and associating them
with their corresponding data types, UI tips, and capture methods.
"""
from enum import Enum
from typing import TYPE_CHECKING, Union, Hashable, Callable

from macro_studio.core.types_and_enums import CaptureTypeDef, CaptureMode

if TYPE_CHECKING:
    from macro_studio.ui.overlay import TransparentOverlay
    from macro_studio.core.data.variable_config import VariableConfig

PotentialMode = Union[CaptureMode, Enum, Hashable]

class GlobalCaptureRegistry:
    """A static class that serves as a global registry for capture modes.

    This registry maps capture modes (which can be `CaptureMode` enums or other
    hashable types) to a `CaptureTypeDef` definition. It also provides
    reverse lookups from Python types to their associated capture modes.
    """
    _definitions = {}  # Maps PotentialMode -> CaptureTypeDef
    _type_map = {}     # Maps PythonType -> PotentialMode

    @classmethod
    def register(cls, mode: PotentialMode, tooltip: str, capture_method: Callable[["TransparentOverlay", "VariableConfig"], None], type_class: type | None = None):
        """Registers a new capture mode definition.

        If the `type_class` is not provided, this method
        will attempt to infer it from the `mode` enum's value, if applicable.

        Args:
            mode: The capture mode to register.
            tooltip: A string providing guidance to the user during capture.
            capture_method: The function called to perform the capture.
            type_class: The Python type associated with this capture mode.

        Raises:
            ValueError: If `type_class` cannot be inferred from the provided `mode`.
        """
        if type_class is None:
            if isinstance(mode, Enum) and isinstance(mode.value, type):
                type_class = mode.value
            else:
                raise ValueError(f"Cannot infer type_class from {mode}. You must provide it explicitly.")

        cls._definitions[mode] = CaptureTypeDef(mode, tooltip, capture_method, type_class)
        cls._type_map[type_class] = mode

    @classmethod
    def get(cls, mode: PotentialMode) -> CaptureTypeDef | None:
        """Retrieves the definition for a given capture mode.

        Args:
            mode: The capture mode to look up.

        Returns:
            The `CaptureTypeDef` for the specified mode, or None if not found.
        """
        return cls._definitions.get(mode)

    @classmethod
    def getDefinitions(cls) -> dict[PotentialMode, CaptureTypeDef]:
        """Returns all registered capture mode definitions.

        Returns:
            A dictionary mapping all registered modes to their definitions.
        """
        return cls._definitions

    @classmethod
    def getModeFromType(cls, type_class: type) -> PotentialMode | None:
        """Finds the capture mode associated with a specific Python type.

        Args:
            type_class: The Python type to look up (e.g., `QPoint`, `QRect`).

        Returns:
            The associated capture mode, or None if no mode is registered for the type.
        """
        return cls._type_map.get(type_class)

    @classmethod
    def containsMode(cls, mode: PotentialMode) -> bool:
        """Checks if a specific capture mode is registered.

        Args:
            mode: The capture mode to check.

        Returns:
            True if the mode is registered, False otherwise.
        """
        return mode in cls._definitions

    @classmethod
    def containsType(cls, type_class: type) -> bool:
        """Checks if a capture mode is registered for a specific Python type.

        Args:
            type_class: The Python type to check.

        Returns:
            True if a mode is associated with the type, False otherwise.
        """
        return type_class in cls._type_map

def captureOverlayGeneric(overlay: "TransparentOverlay", config: "VariableConfig"):
    """A generic handler for capture modes that use the screen overlay.

    This function is designed to be used as the `capture_method` in a
    `CaptureTypeDef`. It invokes the overlay's capture functionality based on
    the variable's data type.

    Args:
        overlay: The `TransparentOverlay` instance to use for capturing.
        config: The `VariableConfig` object for the variable being captured.

    Returns:
        The data captured by the overlay, or None if the capture is canceled.
    """
    mode = GlobalCaptureRegistry.getModeFromType(config.data_type)
    return overlay.captureData(mode, config.hint)


# --- Default Registrations ---

GlobalCaptureRegistry.register(
    mode=CaptureMode.POINT,
    tooltip="Format: x, y",
    capture_method=captureOverlayGeneric,
)

GlobalCaptureRegistry.register(
    mode=CaptureMode.REGION,
    tooltip="Format: x, y, width, height",
    capture_method=captureOverlayGeneric,
)

GlobalCaptureRegistry.register(
    mode=CaptureMode.COLOR,
    tooltip="Format: r, g, b",
    capture_method=captureOverlayGeneric,
)