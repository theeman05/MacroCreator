import bisect, json
from dataclasses import dataclass
from enum import Enum
from PySide6.QtCore import QObject, Signal, QPoint, QRect
from PySide6.QtGui import QUndoCommand, QColor

from macro_studio.core.registries.type_handler import GlobalTypeHandler


class ActionType(str, Enum):
    DELAY = "DELAY"
    KEYBOARD = "KEYBOARD FUNCTION"
    MOUSE = "MOUSE FUNCTION"
    TEXT = "TEXT FUNCTION"
    WAIT_UNTIL = "WAIT UNTIL"

class MouseFunction(str, Enum):
    LEFT_CLICK = "Left Click"
    RIGHT_CLICK = "Right Click"
    SCROLL_CLICK = "Scroll Click"
    SCROLL_UP = "Scroll Up"
    SCROLL_DOWN = "Scroll Down"

M_FUNCTION_TO_PYDIRECTINPUT = {
    MouseFunction.LEFT_CLICK.name: "left",
    MouseFunction.RIGHT_CLICK.name: "right",
    MouseFunction.SCROLL_CLICK.name: "middle",  # pydirectinput calls the wheel 'middle'

    MouseFunction.SCROLL_UP.name: 1,  # Positive integers scroll up
    MouseFunction.SCROLL_DOWN.name: -1,  # Negative integers scroll down
}

class ConditionType(str, Enum):
    NUMBER = "Number"
    COLOR = "Color"
    TEXT = "Text"
    IMAGE = "Image"

class CompareOp(str, Enum):
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="

class TextMatch(str, Enum):
    CONTAINS = "contains"
    EQUALS = "equals"

class ImageMatch(str, Enum):
    APPEARS = "appears"
    DISAPPEARS = "disappears"

# Geometry type the watch area captures for each condition (Region for OCR/image, Point for color).
_COND_AREA_TYPE = {
    ConditionType.NUMBER: QRect,
    ConditionType.TEXT: QRect,
    ConditionType.COLOR: QPoint,
    ConditionType.IMAGE: QRect,
}

DEFAULT_COLOR_TOLERANCE = 20
DEFAULT_IMAGE_THRESHOLD = 0.8

@dataclass
class WaitCondition:
    """The configuration of a WAIT_UNTIL step: what to watch and what satisfies it.

    Every user-facing value can be either a literal or a bound variable. A variable
    binding lives in the matching ``*_var`` field and takes precedence over the literal;
    this keeps a text literal distinguishable from a variable name (both are strings).
    """
    condition_type: ConditionType = ConditionType.NUMBER
    area: object = None            # QRect (Number/Text/Image) or QPoint (Color) literal; None for Image = whole screen
    area_var: str | None = None    # variable name for the watch area; wins over area
    operator: CompareOp = CompareOp.GTE   # Number comparison
    text_mode: TextMatch = TextMatch.CONTAINS  # Text comparison
    image_match: ImageMatch = ImageMatch.APPEARS  # Image: wait for template to appear or disappear
    tolerance: int = DEFAULT_COLOR_TOLERANCE   # Color match tolerance
    threshold: float = DEFAULT_IMAGE_THRESHOLD  # Image template match confidence (0..1)
    target: object = None          # number / QColor / str literal to compare against
    target_var: str | None = None  # variable name for the target; wins over target
    template_id: int | None = None   # Image: id into the global template library (preferred)
    template_b64: str | None = None  # Image: legacy inline base64 PNG; fallback when template_id is unset
    store_var: str | None = None   # variable to write each reading into (optional)
    poll_interval: float | None = None  # seconds between checks; None => engine default

    def areaType(self):
        return _COND_AREA_TYPE[self.condition_type]

    def _toDict(self):
        data = {
            "condition_type": self.condition_type.name,
            "operator": self.operator.name,
            "text_mode": self.text_mode.name,
            "image_match": self.image_match.name,
            "tolerance": self.tolerance,
            "threshold": self.threshold,
        }
        if self.area_var:
            data["area_var"] = self.area_var
        elif self.area is not None:
            data["area"] = GlobalTypeHandler.toString(self.area)

        if self.target_var:
            data["target_var"] = self.target_var
        elif self.target is not None:
            data["target"] = GlobalTypeHandler.toString(self.target)

        GlobalTypeHandler.setIfEvals("template_id", self.template_id, data, strict_eval=True)
        GlobalTypeHandler.setIfEvals("template_b64", self.template_b64, data)
        GlobalTypeHandler.setIfEvals("store_var", self.store_var, data)
        GlobalTypeHandler.setIfEvals("poll_interval", self.poll_interval, data)
        return data

    @staticmethod
    def fromDict(data: dict) -> "WaitCondition":
        cond = WaitCondition()
        cond.condition_type = ConditionType[data.get("condition_type", ConditionType.NUMBER.name)]
        cond.operator = CompareOp[data.get("operator", CompareOp.GTE.name)]
        cond.text_mode = TextMatch[data.get("text_mode", TextMatch.CONTAINS.name)]
        cond.image_match = ImageMatch[data.get("image_match", ImageMatch.APPEARS.name)]
        cond.tolerance = data.get("tolerance", DEFAULT_COLOR_TOLERANCE)
        cond.threshold = data.get("threshold", DEFAULT_IMAGE_THRESHOLD)
        cond.template_id = data.get("template_id")
        cond.template_b64 = data.get("template_b64")
        cond.store_var = data.get("store_var")
        cond.poll_interval = data.get("poll_interval")

        cond.area_var = data.get("area_var")
        area_str = data.get("area")
        if area_str is not None:
            try:
                cond.area = GlobalTypeHandler.fromString(cond.areaType(), area_str)
            except (ValueError, TypeError):
                cond.area = None

        cond.target_var = data.get("target_var")
        target_str = data.get("target")
        if target_str is not None:
            cond.target = WaitCondition._parseTarget(cond.condition_type, target_str)
        return cond

    @staticmethod
    def _parseTarget(condition_type: "ConditionType", target_str: str):
        if condition_type == ConditionType.COLOR:
            try:
                return GlobalTypeHandler.fromString(QColor, target_str)
            except (ValueError, TypeError):
                return None
        if condition_type == ConditionType.NUMBER:
            try:
                num = float(target_str)
                return int(num) if num.is_integer() else num
            except (ValueError, TypeError):
                return None
        return target_str  # TEXT literal is stored verbatim


@dataclass(eq=False)
class TimelineStep:
    action_type: ActionType
    value: object = None
    detail: int=None # 1 means press, 2 means release
    partner_idx: int | None=None

    def _toDict(self):
        master = {"action_type": self.action_type.name}
        GlobalTypeHandler.setIfEvals("value", self._getSerialValue(), master)
        GlobalTypeHandler.setIfEvals("detail", self.detail, master)
        GlobalTypeHandler.setIfEvals("partner_idx", self.partner_idx, master, strict_eval=True)

        return master

    def toJson(self) -> str:
        return json.dumps(self._toDict(), default=str)

    def _getSerialValue(self):
        # Yeah, this isn't a great way to do it, but oh well.
        if isinstance(self.value, WaitCondition):
            return self.value._toDict()
        if self.value and isinstance(self.value, tuple):
            return self.value[0], GlobalTypeHandler.toString(self.value[1])
        return self.value

    @staticmethod
    def fromJson(json_str):
        step_data = json.loads(json_str)
        step = TimelineStep(**step_data)
        step.action_type = ActionType[step_data['action_type']]
        if step.action_type == ActionType.WAIT_UNTIL:
            step.value = WaitCondition.fromDict(step.value) if isinstance(step.value, dict) else WaitCondition()
        if step.action_type == ActionType.MOUSE:
            m_btn = m_pos = None
            if step.value is not None:
                m_btn, m_pos = step.value

            m_btn = m_btn or MouseFunction.LEFT_CLICK.name

            if m_pos and isinstance(m_pos, str): # Try to convert second back to QPoint
                try:
                    m_pos = GlobalTypeHandler.fromString(QPoint, m_pos)
                except (ValueError, TypeError):
                    pass

            step.value = (m_btn, m_pos)

        return step


class TimelineModel(QObject):
    stepAdded = Signal(int, object) # (index, value)
    stepMoved = Signal(int, int) # (old_index, new_index)
    stepRemoved = Signal(int) # (index)
    stepValueChanged = Signal(int, object) # (index, new_value)

    def __init__(self):
        super().__init__()
        self._steps: list[TimelineStep] = []

    def insertStep(self, index: int, data):
        """Inserts value and notifies listeners."""
        self._steps.insert(index, data)
        self.stepAdded.emit(index, data)

    def removeStep(self, index: int):
        """Removes value and notifies listeners."""
        self._steps.pop(index)
        self.stepRemoved.emit(index)

    def moveStep(self, old_index: int, new_index: int):
        """Moves value and notifies listeners."""
        self._steps.insert(new_index, self._steps.pop(old_index))
        self.stepMoved.emit(old_index, new_index)

    def moveSteps(self, selected_indices: list[int], target_index: int):
        """Batch moves multiple steps and properly triggers UI updates."""
        if not selected_indices:
            return

        selected_indices = sorted(selected_indices)

        items_to_move = [self._steps[i] for i in selected_indices]

        adjusted_target = target_index
        for row in selected_indices:
            if row < target_index:
                adjusted_target -= 1


        for row in sorted(selected_indices, reverse=True):
            self.removeStep(row)

        for i, item in enumerate(items_to_move):
            self.insertStep(adjusted_target + i, item)

    def updateStep(self, index: int, new_value):
        """Notifies listeners then updates value at index."""
        self.stepValueChanged.emit(index, new_value)
        self._steps[index].value = new_value

    def importTimeline(self, steps):
        """Deserializes the steps so changes may be made."""
        new_steps = []
        self._steps = new_steps
        for i, step_data in enumerate(steps):
            step = TimelineStep.fromJson(step_data)
            new_steps.append(step)
            self.stepAdded.emit(i, step)

    def getStep(self, index: int):
        return self._steps[index]

    def count(self):
        return len(self._steps)

# -----------------------------------------------------------------------------
# THE COMMANDS (Undo/Redo Logic)
# -----------------------------------------------------------------------------
class AddStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, index, data: TimelineStep):
        super().__init__(f"Add {data.action_type.value.title()}")
        self.model = model
        self.index = index
        self.data = data

    def redo(self):
        self.model.insertStep(self.index, self.data)

    def undo(self):
        self.model.removeStep(self.index)

class _MoveData:
    def __init__(self, offset, item):
        self.item = item
        self.og_p_idx = item.partner_idx
        if self.og_p_idx:
            self.offset = offset
            self.new_p_idx = None

    def undoPartner(self):
        self.item.partner_idx = self.og_p_idx

    def redoPartner(self):
        if self.og_p_idx is not None:
            self.item.partner_idx = self.new_p_idx

class MoveStepsCommand(QUndoCommand):
    def __init__(self, model, sorted_indices: list[int], adjusted_target: int):
        len_steps = len(sorted_indices)
        description = f"Move {len_steps} Step{'s' if len_steps > 1 else ''}"
        super().__init__(description)
        self.model = model

        self.sorted_indices = sorted_indices

        self.move_dict: dict[int, _MoveData] = {}
        self.adjusted_target = adjusted_target

        for i, row in enumerate(sorted_indices):
            self.move_dict[row] = _MoveData(offset=i,item=self.model.getStep(row))

        for row in sorted_indices:
            data = self.move_dict[row]
            og_p_idx = data.og_p_idx

            if og_p_idx is not None:
                if og_p_idx in self.move_dict:
                    # Scenario A: The partner was ALSO selected and moved.
                    # Let the higher partner handle. Yes, the lower one won't have a partner_idx, but it doesn't matter.
                    new_partner_idx = (adjusted_target + self.move_dict[og_p_idx].offset) if og_p_idx < row else None
                else:
                    # Scenario B: The partner stayed behind.
                    # Use Binary Search to find how many extracted items were above it
                    extracted_above = bisect.bisect_left(sorted_indices, og_p_idx)
                    new_partner_idx = og_p_idx - extracted_above

                    # Calculate if it shifted DOWN when the items were inserted at the new target
                    if adjusted_target <= new_partner_idx:
                        new_partner_idx += len_steps

                    new_partner_idx = new_partner_idx
                data.new_p_idx = new_partner_idx

    def redo(self):
        for row in reversed(self.sorted_indices):
            self.model.removeStep(row)

        # We need to sever the link first and re-insert because the partner may not exist at the right spot yet

        for i, row in enumerate(self.sorted_indices):
            data = self.move_dict[row]

            # Temporarily sever the link
            if data.og_p_idx is not None: data.item.partner_idx = None

            insert_spot = self.adjusted_target + i
            self.model.insertStep(insert_spot, data.item)

        for i, row in enumerate(self.sorted_indices):
            data = self.move_dict[row]

            if data.og_p_idx is not None:
                insert_spot = self.adjusted_target + i
                data.redoPartner()
                self.model.updateStep(insert_spot, data.item.value)

    def undo(self):
        last_inserted_index = self.adjusted_target + len(self.sorted_indices) - 1

        for i in range(last_inserted_index, self.adjusted_target - 1, -1):
            self.model.removeStep(i)

        for row in self.sorted_indices:
            data = self.move_dict[row]

            if data.og_p_idx is not None: data.item.partner_idx = None

            self.model.insertStep(row, data.item)

        for row in self.sorted_indices:
            data = self.move_dict[row]

            if data.og_p_idx is not None:
                data.undoPartner()
                self.model.updateStep(row, data.item.value)

class ChangeStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, index, new_value):
        super().__init__("Change")
        self.model = model
        self.index = index

        step = model.getStep(index)

        self.old_value = step.value
        self.new_value = new_value

    def redo(self):
        self.model.updateStep(self.index, self.new_value)

    def undo(self):
        self.model.updateStep(self.index, self.old_value)

class RemoveStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, index):
        data = model.getStep(index)
        super().__init__(f"Remove {data.action_type.value.title()}")
        self.model = model
        self.index = index
        self.data = data
        self.prev_partner = data.partner_idx

    def redo(self):
        self.data.partner_idx = None
        self.model.removeStep(self.index)

    def undo(self):
        self.data.partner_idx = self.prev_partner
        self.model.insertStep(self.index, self.data)