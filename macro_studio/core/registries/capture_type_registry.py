from enum import Enum
from typing import TYPE_CHECKING, Union, Hashable

from macro_studio.core.types_and_enums import CaptureTypeDef, CaptureMode

if TYPE_CHECKING:
    from macro_studio.ui.overlay import TransparentOverlay
    from macro_studio.core.data.variable_config import VariableConfig

PotentialMode = Union[CaptureMode, Hashable]

class GlobalCaptureRegistry:
    _definitions = {} # Maps PotentialMode -> Definition
    _type_map = {}  # Maps PythonType -> PotentialMode

    @classmethod
    def register(cls, definition: CaptureTypeDef):
        """
        Registers a capture mode. If type_class is omitted and the mode is an Enum,
        it attempts to infer it from the Enum's value.
        """
        mode = definition.mode
        type_class = definition.type_class
        if type_class is None:
            if isinstance(mode, Enum) and isinstance(mode.value, type):
                type_class = mode.value
                definition.type_class = type_class
            else:
                raise ValueError(f"Cannot infer type_class from {mode}. You must provide it explicitly.")

        cls._definitions[mode] = definition
        cls._type_map[type_class] = mode

    @classmethod
    def get(cls, mode: PotentialMode) -> CaptureTypeDef | None:
        return cls._definitions.get(mode)

    @classmethod
    def getDefinitions(cls):
        return cls._definitions

    @classmethod
    def getModeFromType(cls, type_class: type) -> PotentialMode | None:
        """Lookup to find the PotentialMode associated with a specific class. """
        return cls._type_map.get(type_class)

    @classmethod
    def containsMode(cls, mode: PotentialMode) -> bool:
        """
        Checks if a mode is explicitly registered.
        Usage: if GlobalCaptureRegistry.contains(mode):
        """
        return mode in cls._definitions

    @classmethod
    def containsType(cls, type_class: type) -> bool:
        """
        Checks if a mode is explicitly registered.
        Usage: if GlobalCaptureRegistry.contains(mode):
        """
        return type_class in cls._type_map

def captureOverlayGeneric(overlay: "TransparentOverlay", config: "VariableConfig"):
    """Standard handler for modes that uses the existing Overlay system."""
    return overlay.captureData(GlobalCaptureRegistry.getModeFromType(config.data_type), config.hint)


GlobalCaptureRegistry.register(CaptureTypeDef(
    mode=CaptureMode.POINT,
    tip="Format: x, y",
    capture_method=captureOverlayGeneric,
))

GlobalCaptureRegistry.register(CaptureTypeDef(
    mode=CaptureMode.REGION,
    tip="Format: x, y, width, height",
    capture_method=captureOverlayGeneric,
))

GlobalCaptureRegistry.register(CaptureTypeDef(
    mode=CaptureMode.COLOR,
    tip="Format: r, g, b",
    capture_method=captureOverlayGeneric,
))