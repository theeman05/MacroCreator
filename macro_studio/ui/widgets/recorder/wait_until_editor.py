"""Editor widgets for the WAIT_UNTIL timeline step.

`WaitUntilEditor` is the compact summary shown inline in a timeline row; clicking
it opens `WaitUntilDialog`, a form for configuring the underlying `WaitCondition`.
Every input (watch area, comparison target) accepts either a literal or a bound
variable, mirroring the mouse editor's value-or-variable pattern.
"""
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QLineEdit, QSpinBox, QPushButton, QCheckBox, QStackedWidget)

from macro_studio.core.types_and_enums import CaptureMode
from macro_studio.core.recording.timeline_handler import (
    WaitCondition, ConditionType, CompareOp, TextMatch)
from macro_studio.core.registries.type_handler import GlobalTypeHandler

if TYPE_CHECKING:
    from macro_studio.core.data import VariableStore

# Which variable types can bind to each field.
_NUMBER_TYPES = (int, float)
_AREA_TYPES = {
    ConditionType.NUMBER: (QRect,),
    ConditionType.TEXT: (QRect,),
    ConditionType.COLOR: (QPoint,),
}
# The type a reading produces, per condition — the store target must match it.
_STORE_TYPES = {
    ConditionType.NUMBER: (int, float),
    ConditionType.TEXT: (str,),
    ConditionType.COLOR: (QColor,),
}

_VALUE_IDX = 0
_VAR_IDX = 1


def _toNumber(text):
    try:
        num = float(text)
        return int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        return None


def summaryText(cond: WaitCondition) -> str:
    """Human-readable one-liner for a condition, shown in the timeline row."""
    if not isinstance(cond, WaitCondition):
        return "Wait Until — click to configure"

    area = cond.area_var or (GlobalTypeHandler.toString(cond.area) if cond.area is not None else "?")

    if cond.condition_type == ConditionType.NUMBER:
        target = cond.target_var or (str(cond.target) if cond.target is not None else "?")
        text = f"Wait until [{area}] {cond.operator.value} {target}"
    elif cond.condition_type == ConditionType.TEXT:
        target = cond.target_var or (f'"{cond.target}"' if cond.target else "?")
        text = f"Wait until [{area}] {cond.text_mode.value} {target}"
    else:  # COLOR
        target = cond.target_var or (GlobalTypeHandler.toString(cond.target) if cond.target is not None else "?")
        text = f"Wait until [{area}] ~ {target} (±{cond.tolerance})"

    if cond.store_var:
        text += f"  → {cond.store_var}"
    return text


class WaitUntilDialog(QDialog):
    """Modal form for configuring a WaitCondition."""

    def __init__(self, condition: WaitCondition, var_store: "VariableStore", overlay, parent=None):
        super().__init__(parent)
        self.var_store = var_store
        self.overlay = overlay
        self._area_literal = None   # QRect / QPoint captured by drawing
        self._color_literal = None  # QColor captured by picking

        self.setWindowTitle("Wait Until")
        # Non-modal: drawing the watch area hides this dialog while the capture
        # overlay runs, and a modal exec() loop would end the moment it hides.
        self.setModal(False)
        self.setMinimumWidth(340)

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        # --- Condition type ---
        self.type_combo = QComboBox()
        for ct in ConditionType:
            self.type_combo.addItem(ct.value, ct)
        form.addRow("Condition", self.type_combo)

        # --- Watch area (draw or variable) ---
        self.area_mode = QComboBox()
        self.area_mode.addItems(["Draw", "Variable"])
        self.area_stack = QStackedWidget()

        draw_page = QWidget()
        draw_row = QHBoxLayout(draw_page)
        draw_row.setContentsMargins(0, 0, 0, 0)
        self.btn_draw = QPushButton("Draw area…")
        self.lbl_area = QLabel("Not set")
        draw_row.addWidget(self.btn_draw)
        draw_row.addWidget(self.lbl_area, 1)

        self.area_var_combo = QComboBox()
        self.area_stack.addWidget(draw_page)          # _VALUE_IDX
        self.area_stack.addWidget(self.area_var_combo)  # _VAR_IDX

        area_box = QWidget()
        area_lay = QVBoxLayout(area_box)
        area_lay.setContentsMargins(0, 0, 0, 0)
        area_lay.addWidget(self.area_mode)
        area_lay.addWidget(self.area_stack)
        form.addRow("Watch area", area_box)

        # --- Comparison (stacked by condition type) ---
        self.cmp_stack = QStackedWidget()

        # Number page
        num_page = QWidget()
        num_lay = QHBoxLayout(num_page)
        num_lay.setContentsMargins(0, 0, 0, 0)
        self.op_combo = QComboBox()
        for op in CompareOp:
            self.op_combo.addItem(op.value, op)
        self.num_target_mode = QComboBox()
        self.num_target_mode.addItems(["Value", "Variable"])
        self.num_target_stack = QStackedWidget()
        self.num_edit = QLineEdit()
        self.num_edit.setPlaceholderText("e.g. 15")
        self.num_var_combo = QComboBox()
        self.num_target_stack.addWidget(self.num_edit)
        self.num_target_stack.addWidget(self.num_var_combo)
        num_lay.addWidget(self.op_combo)
        num_lay.addWidget(self.num_target_mode)
        num_lay.addWidget(self.num_target_stack, 1)

        # Text page
        text_page = QWidget()
        text_lay = QHBoxLayout(text_page)
        text_lay.setContentsMargins(0, 0, 0, 0)
        self.text_mode_combo = QComboBox()
        for tm in TextMatch:
            self.text_mode_combo.addItem(tm.value, tm)
        self.text_target_mode = QComboBox()
        self.text_target_mode.addItems(["Value", "Variable"])
        self.text_target_stack = QStackedWidget()
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("e.g. GAME OVER")
        self.text_var_combo = QComboBox()
        self.text_target_stack.addWidget(self.text_edit)
        self.text_target_stack.addWidget(self.text_var_combo)
        text_lay.addWidget(self.text_mode_combo)
        text_lay.addWidget(self.text_target_mode)
        text_lay.addWidget(self.text_target_stack, 1)

        # Color page
        color_page = QWidget()
        color_lay = QHBoxLayout(color_page)
        color_lay.setContentsMargins(0, 0, 0, 0)
        self.color_target_mode = QComboBox()
        self.color_target_mode.addItems(["Value", "Variable"])
        self.color_target_stack = QStackedWidget()
        color_pick_page = QWidget()
        color_pick_row = QHBoxLayout(color_pick_page)
        color_pick_row.setContentsMargins(0, 0, 0, 0)
        self.btn_pick_color = QPushButton("Pick color…")
        self.swatch = QLabel()
        self.swatch.setFixedSize(24, 24)
        self._setSwatch(None)
        color_pick_row.addWidget(self.btn_pick_color)
        color_pick_row.addWidget(self.swatch)
        self.color_var_combo = QComboBox()
        self.color_target_stack.addWidget(color_pick_page)
        self.color_target_stack.addWidget(self.color_var_combo)
        self.tol_spin = QSpinBox()
        self.tol_spin.setRange(0, 442)  # max RGB Euclidean distance
        color_lay.addWidget(QLabel("±"))
        color_lay.addWidget(self.tol_spin)
        color_lay.addWidget(self.color_target_mode)
        color_lay.addWidget(self.color_target_stack, 1)

        # Map condition type -> its comparison page explicitly, so the pages don't
        # depend on ConditionType enum ordering.
        self._cmp_index = {
            ConditionType.NUMBER: self.cmp_stack.addWidget(num_page),
            ConditionType.COLOR: self.cmp_stack.addWidget(color_page),
            ConditionType.TEXT: self.cmp_stack.addWidget(text_page),
        }
        form.addRow("Reading", self.cmp_stack)

        # --- Store reading ---
        store_box = QWidget()
        store_row = QHBoxLayout(store_box)
        store_row.setContentsMargins(0, 0, 0, 0)
        self.chk_store = QCheckBox("Store reading into")
        self.store_var_combo = QComboBox()
        store_row.addWidget(self.chk_store)
        store_row.addWidget(self.store_var_combo, 1)
        form.addRow("", store_box)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("btn_save")
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

        # --- Wiring ---
        self.type_combo.currentIndexChanged.connect(self._onTypeChanged)
        self.area_mode.currentIndexChanged.connect(self.area_stack.setCurrentIndex)
        self.num_target_mode.currentIndexChanged.connect(self.num_target_stack.setCurrentIndex)
        self.text_target_mode.currentIndexChanged.connect(self.text_target_stack.setCurrentIndex)
        self.color_target_mode.currentIndexChanged.connect(self.color_target_stack.setCurrentIndex)
        self.btn_draw.clicked.connect(self._drawArea)
        self.btn_pick_color.clicked.connect(self._pickColor)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.accept)

        self._fillVarCombo(self.num_var_combo, _NUMBER_TYPES)
        self._fillVarCombo(self.text_var_combo, (str,))
        self._fillVarCombo(self.color_var_combo, (QColor,))
        # store_var_combo is filled per condition type in _onTypeChanged.
        self.store_var_combo.setToolTip("Only variables matching the reading's type are shown")

        self._loadFrom(condition if isinstance(condition, WaitCondition) else WaitCondition())

    # --- helpers ---
    def _fillVarCombo(self, combo: QComboBox, types):
        combo.clear()
        combo.addItem("— none —", None)
        for name, cfg in self.var_store.items():
            if types is None or cfg.data_type in types:
                combo.addItem(name, name)

    def _selectVar(self, combo: QComboBox, name):
        idx = combo.findData(name)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _setSwatch(self, color):
        if isinstance(color, QColor):
            self.swatch.setStyleSheet(f"background:{color.name()}; border:1px solid #555; border-radius:4px;")
        else:
            self.swatch.setStyleSheet("background:transparent; border:1px dashed #555; border-radius:4px;")

    def _onTypeChanged(self):
        ct = ConditionType(self.type_combo.currentData())
        self.cmp_stack.setCurrentIndex(self._cmp_index[ct])
        self._fillVarCombo(self.area_var_combo, _AREA_TYPES[ct])
        self._fillVarCombo(self.store_var_combo, _STORE_TYPES[ct])

    def _captureWithOverlay(self, mode):
        """Hide the dialog, run the capture overlay, then restore the dialog."""
        self.hide()
        result = self.overlay.captureData(mode)
        self.show()
        self.raise_()
        self.activateWindow()
        return result

    def _drawArea(self):
        ct = ConditionType(self.type_combo.currentData())
        mode = CaptureMode.POINT if ct == ConditionType.COLOR else CaptureMode.REGION
        result = self._captureWithOverlay(mode)
        if result is not None:
            self._area_literal = result
            self.lbl_area.setText(GlobalTypeHandler.toString(result))

    def _pickColor(self):
        result = self._captureWithOverlay(CaptureMode.COLOR)
        if isinstance(result, QColor):
            self._color_literal = result
            self._setSwatch(result)

    # --- load / save ---
    def _loadFrom(self, cond: WaitCondition):
        self.type_combo.setCurrentIndex(self.type_combo.findData(cond.condition_type))
        self._onTypeChanged()

        self.tol_spin.setValue(cond.tolerance)
        self.op_combo.setCurrentIndex(self.op_combo.findData(cond.operator))
        self.text_mode_combo.setCurrentIndex(self.text_mode_combo.findData(cond.text_mode))

        # Watch area
        if cond.area_var:
            self.area_mode.setCurrentIndex(_VAR_IDX)
            self._selectVar(self.area_var_combo, cond.area_var)
        elif cond.area is not None:
            self.area_mode.setCurrentIndex(_VALUE_IDX)
            self._area_literal = cond.area
            self.lbl_area.setText(GlobalTypeHandler.toString(cond.area))
        self.area_stack.setCurrentIndex(self.area_mode.currentIndex())

        # Target
        if cond.condition_type == ConditionType.NUMBER:
            if cond.target_var:
                self.num_target_mode.setCurrentIndex(_VAR_IDX)
                self._selectVar(self.num_var_combo, cond.target_var)
            elif cond.target is not None:
                self.num_edit.setText(str(cond.target))
        elif cond.condition_type == ConditionType.TEXT:
            if cond.target_var:
                self.text_target_mode.setCurrentIndex(_VAR_IDX)
                self._selectVar(self.text_var_combo, cond.target_var)
            elif cond.target:
                self.text_edit.setText(str(cond.target))
        elif cond.condition_type == ConditionType.COLOR:
            if cond.target_var:
                self.color_target_mode.setCurrentIndex(_VAR_IDX)
                self._selectVar(self.color_var_combo, cond.target_var)
            elif isinstance(cond.target, QColor):
                self._color_literal = cond.target
                self._setSwatch(cond.target)
        self.num_target_stack.setCurrentIndex(self.num_target_mode.currentIndex())
        self.text_target_stack.setCurrentIndex(self.text_target_mode.currentIndex())
        self.color_target_stack.setCurrentIndex(self.color_target_mode.currentIndex())

        # Store
        if cond.store_var:
            self.chk_store.setChecked(True)
            self._selectVar(self.store_var_combo, cond.store_var)

    def resultCondition(self) -> WaitCondition:
        cond = WaitCondition()
        # QComboBox returns str-Enum userData as a plain str; coerce back to the enum.
        cond.condition_type = ConditionType(self.type_combo.currentData())
        cond.operator = CompareOp(self.op_combo.currentData())
        cond.text_mode = TextMatch(self.text_mode_combo.currentData())
        cond.tolerance = self.tol_spin.value()

        if self.area_mode.currentIndex() == _VAR_IDX:
            cond.area_var = self.area_var_combo.currentData()
        else:
            cond.area = self._area_literal

        if cond.condition_type == ConditionType.NUMBER:
            if self.num_target_mode.currentIndex() == _VAR_IDX:
                cond.target_var = self.num_var_combo.currentData()
            else:
                cond.target = _toNumber(self.num_edit.text())
        elif cond.condition_type == ConditionType.TEXT:
            if self.text_target_mode.currentIndex() == _VAR_IDX:
                cond.target_var = self.text_var_combo.currentData()
            else:
                cond.target = self.text_edit.text() or None
        elif cond.condition_type == ConditionType.COLOR:
            if self.color_target_mode.currentIndex() == _VAR_IDX:
                cond.target_var = self.color_var_combo.currentData()
            else:
                cond.target = self._color_literal

        if self.chk_store.isChecked():
            cond.store_var = self.store_var_combo.currentData()
        return cond


class WaitUntilEditor(QWidget):
    """Inline summary widget for a WAIT_UNTIL row; opens the dialog on click."""
    valueChanged = Signal(object)

    def __init__(self, parent, prev_value, overlay, var_store):
        super().__init__(parent)
        self.overlay = overlay
        self.var_store = var_store
        self.value = prev_value if isinstance(prev_value, WaitCondition) else WaitCondition()
        self._dialog = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.display_btn = QPushButton()
        self.display_btn.setObjectName("SneakyButton")
        self.display_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.display_btn.clicked.connect(self._openDialog)
        layout.addWidget(self.display_btn)

        self._refresh()

    def _refresh(self):
        self.display_btn.setText(summaryText(self.value))

    def setValue(self, new_value):
        self.value = new_value if isinstance(new_value, WaitCondition) else WaitCondition()
        self._refresh()

    def _openDialog(self):
        if self._dialog is not None and self._dialog.isVisible():
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        self._dialog = WaitUntilDialog(self.value, self.var_store, self.overlay, self)
        self._dialog.accepted.connect(self._onDialogAccepted)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _onDialogAccepted(self):
        new_cond = self._dialog.resultCondition()
        self.value = new_cond
        self._refresh()
        self.valueChanged.emit(new_cond)
