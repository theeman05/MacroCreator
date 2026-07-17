from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, TypeAlias, Callable, Generator, Tuple
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QPixmap

if TYPE_CHECKING:
    from macro_studio.ui.overlay import TransparentOverlay
    from macro_studio.core.data.variable_config import VariableConfig

class CaptureMode(Enum):
    POINT = QPoint
    REGION = QRect
    COLOR = QColor
    # IMAGE drags a region like REGION but returns the cropped pixels (a QPixmap
    # template) instead of the rect. Its value must differ from REGION's QRect,
    # or Enum would fold it into a REGION alias. It is captured on demand by the
    # wait-until dialog, not registered as a variable capture type.
    IMAGE = QPixmap

class WorkerState(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    INTERRUPTED = auto()

@dataclass
class CaptureTypeDef:
    mode: CaptureMode
    tip: str
    capture_method: Callable[["TransparentOverlay", "VariableConfig"], None]
    type_class: type | None = None

class LogLevel(Enum):
    ERROR = auto()
    INFO = auto()
    WARN = auto()

@dataclass
class LogPacket:
    parts: Tuple[object, ...]
    level: LogLevel = LogLevel.INFO
    task_name: int | str = 0

@dataclass
class LogErrorPacket:
    message: str
    traceback: str | None
    task_name: int | str

class TaskAbortException(BaseException):
    """Raised when the macro is stopped normally."""
    pass

class TaskInterruptedException(BaseException):
    """Raised when the user triggers an interrupted pause."""
    pass

class TaskDeletedError(Exception):
    """Raised when attempting to operate on a task that has been removed."""
    pass

TaskFunc: TypeAlias = Callable[..., Generator | None]
