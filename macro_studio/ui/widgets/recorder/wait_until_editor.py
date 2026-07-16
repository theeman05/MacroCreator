"""Editor widgets for the WAIT_UNTIL timeline step.

`WaitUntilEditor` is the compact summary shown inline in a timeline row; clicking
it opens `WaitUntilDialog`, a form for configuring the underlying `WaitCondition`.
Every input (watch area, comparison target) accepts either a literal or a bound
variable, mirroring the mouse editor's value-or-variable pattern.
"""
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Qt, Signal, QRect, QPoint, QSize, QByteArray, QBuffer, QIODevice, QEventLoop, QTimer)
from PySide6.QtGui import QColor, QPixmap, QIcon, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QLineEdit, QSpinBox, QPushButton, QCheckBox, QStackedWidget, QScrollArea,
    QToolButton, QButtonGroup, QFileDialog)

from macro_studio.core.types_and_enums import CaptureMode
from macro_studio.core.recording.timeline_handler import (
    WaitCondition, ConditionType, CompareOp, TextMatch, ImageMatch)
from macro_studio.core.registries.type_handler import GlobalTypeHandler

if TYPE_CHECKING:
    from macro_studio.core.data import VariableStore, TemplateStore

# Which variable types can bind to each field.
_NUMBER_TYPES = (int, float)
_AREA_TYPES = {
    ConditionType.NUMBER: (QRect,),
    ConditionType.TEXT: (QRect,),
    ConditionType.COLOR: (QPoint,),
    ConditionType.IMAGE: (QRect,),
}
# The type a reading produces, per condition — the store target must match it.
_STORE_TYPES = {
    ConditionType.NUMBER: (int, float),
    ConditionType.TEXT: (str,),
    ConditionType.COLOR: (QColor,),
    ConditionType.IMAGE: (QPoint,),  # the matched center point
}

_VALUE_IDX = 0
_VAR_IDX = 1


def _toNumber(text):
    try:
        num = float(text)
        return int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        return None


def _pixmapToB64(pixmap: QPixmap) -> str:
    """Encode a QPixmap as base64 PNG text for storage on the condition."""
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    buf.close()
    return bytes(ba.toBase64()).decode("ascii")


def _b64ToPixmap(b64: str) -> QPixmap:
    """Decode base64 PNG text back into a QPixmap (for the thumbnail preview)."""
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray.fromBase64(b64.encode("ascii")), "PNG")
    return pixmap


class _TemplateGallery(QWidget):
    """A horizontal strip of selectable template thumbnails backed by a TemplateStore."""
    selectionChanged = Signal(object)  # selected template id, or None

    _THUMB = 64

    def __init__(self, template_store: "TemplateStore", parent=None):
        super().__init__(parent)
        self.template_store = template_store
        self._selected_id = None
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(self._THUMB + 20)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._strip = QWidget()
        self._row = QHBoxLayout(self._strip)
        self._row.setContentsMargins(4, 4, 4, 4)
        self._row.setSpacing(6)
        self._empty = QLabel("No saved images — capture, paste, or load one below.")
        self._empty.setStyleSheet("color: #888;")
        self._row.addWidget(self._empty)
        self._row.addStretch()
        self.scroll.setWidget(self._strip)
        outer.addWidget(self.scroll)
        self.refresh()

    def refresh(self):
        """Rebuild the thumbnail buttons from the store, preserving the current selection."""
        for btn in list(self._group.buttons()):
            self._group.removeButton(btn)
            btn.setParent(None)
            btn.deleteLater()

        entries = self.template_store.all() if self.template_store else []
        self._empty.setVisible(not entries)
        for entry in entries:
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setIconSize(QSize(self._THUMB, self._THUMB))
            btn.setToolTip(entry.name)
            pm = _b64ToPixmap(entry.image_b64)
            if not pm.isNull():
                btn.setIcon(QIcon(pm))
            btn.setProperty("template_id", entry.id)
            btn.toggled.connect(lambda checked, tid=entry.id: self._onToggled(checked, tid))
            self._group.addButton(btn)
            # Insert before the trailing stretch (last item).
            self._row.insertWidget(self._row.count() - 1, btn)
            if entry.id == self._selected_id:
                btn.setChecked(True)

    def _onToggled(self, checked, tid):
        if checked and tid != self._selected_id:
            self._selected_id = tid
            self.selectionChanged.emit(tid)

    def selectedId(self):
        return self._selected_id

    def selectId(self, template_id):
        for btn in self._group.buttons():
            if btn.property("template_id") == template_id:
                btn.setChecked(True)
                return
        self._selected_id = template_id  # remember even if not rendered yet

    def clearSelection(self):
        self._group.setExclusive(False)
        for btn in self._group.buttons():
            btn.setChecked(False)
        self._group.setExclusive(True)
        self._selected_id = None
        self.selectionChanged.emit(None)


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
    elif cond.condition_type == ConditionType.IMAGE:
        # An unset area searches the whole screen rather than being "unknown".
        where = cond.area_var or (GlobalTypeHandler.toString(cond.area) if cond.area is not None else "screen")
        pct = round(cond.threshold * 100)
        img = "set" if (cond.template_id is not None or cond.template_b64) else "?"
        text = f"Wait until [{where}] image ({img}) {cond.image_match.value} (≥{pct}%)"
    else:  # COLOR
        target = cond.target_var or (GlobalTypeHandler.toString(cond.target) if cond.target is not None else "?")
        text = f"Wait until [{area}] ~ {target} (±{cond.tolerance})"

    if cond.store_var:
        text += f"  → {cond.store_var}"
    return text


class WaitUntilDialog(QDialog):
    """Modal form for configuring a WaitCondition."""

    def __init__(self, condition: WaitCondition, var_store: "VariableStore", overlay,
                 template_store: "TemplateStore" = None, parent=None):
        super().__init__(parent)
        self.var_store = var_store
        self.overlay = overlay
        self.template_store = template_store
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

        # Image page
        image_page = QWidget()
        image_lay = QVBoxLayout(image_page)
        image_lay.setContentsMargins(0, 0, 0, 0)

        self.gallery = _TemplateGallery(self.template_store)

        add_row = QHBoxLayout()
        self.btn_capture_image = QPushButton("Capture screen…")
        self.btn_paste_image = QPushButton("Paste")
        self.btn_file_image = QPushButton("From file…")
        self.btn_delete_image = QPushButton("Delete")
        add_row.addWidget(self.btn_capture_image)
        add_row.addWidget(self.btn_paste_image)
        add_row.addWidget(self.btn_file_image)
        add_row.addStretch()
        add_row.addWidget(self.btn_delete_image)

        img_bottom = QHBoxLayout()
        self.image_match_combo = QComboBox()
        for im in ImageMatch:
            self.image_match_combo.addItem(im.value, im)
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 100)
        self.threshold_spin.setSuffix("%")
        self.threshold_spin.setToolTip("Minimum match confidence")
        self.btn_test_image = QPushButton("Test")
        self.lbl_test = QLabel("")
        img_bottom.addWidget(self.image_match_combo)
        img_bottom.addWidget(QLabel("≥"))
        img_bottom.addWidget(self.threshold_spin)
        img_bottom.addWidget(self.btn_test_image)
        img_bottom.addWidget(self.lbl_test, 1)

        image_lay.addWidget(self.gallery)
        image_lay.addLayout(add_row)
        image_lay.addLayout(img_bottom)

        # Map condition type -> its comparison page explicitly, so the pages don't
        # depend on ConditionType enum ordering.
        self._cmp_index = {
            ConditionType.NUMBER: self.cmp_stack.addWidget(num_page),
            ConditionType.COLOR: self.cmp_stack.addWidget(color_page),
            ConditionType.TEXT: self.cmp_stack.addWidget(text_page),
            ConditionType.IMAGE: self.cmp_stack.addWidget(image_page),
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
        self.image_match_combo.currentIndexChanged.connect(self._updateStoreEnabled)
        self.btn_draw.clicked.connect(self._drawArea)
        self.btn_pick_color.clicked.connect(self._pickColor)
        self.btn_capture_image.clicked.connect(self._captureScreen)
        self.btn_paste_image.clicked.connect(self._pasteClipboard)
        self.btn_file_image.clicked.connect(self._loadFile)
        self.btn_delete_image.clicked.connect(self._deleteSelected)
        self.gallery.selectionChanged.connect(self._onTemplateSelected)
        self.btn_test_image.clicked.connect(self._testImage)
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
        self._updateStoreEnabled()

    def _updateStoreEnabled(self):
        """Disable the store row when nothing can be stored (image + disappears)."""
        ct = ConditionType(self.type_combo.currentData())
        disappears = (ct == ConditionType.IMAGE and
                      ImageMatch(self.image_match_combo.currentData()) == ImageMatch.DISAPPEARS)
        if disappears and self.chk_store.isChecked():
            self.chk_store.setChecked(False)
        self.chk_store.setEnabled(not disappears)
        self.store_var_combo.setEnabled(not disappears)

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

    def _addFromPixmap(self, pixmap):
        """Save a captured/pasted/loaded image into the library and select it."""
        if self.template_store is None or not isinstance(pixmap, QPixmap) or pixmap.isNull():
            return
        entry = self.template_store.add(_pixmapToB64(pixmap))
        self.gallery.refresh()
        self.gallery.selectId(entry.id)
        self.lbl_test.setText("")

    def _captureScreen(self):
        self._addFromPixmap(self._captureWithOverlay(CaptureMode.IMAGE))

    def _pasteClipboard(self):
        pixmap = QGuiApplication.clipboard().pixmap()
        if pixmap.isNull():
            self.lbl_test.setText("No image in clipboard")
            return
        self._addFromPixmap(pixmap)

    def _loadFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose an image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.lbl_test.setText("Could not load image")
            return
        self._addFromPixmap(pixmap)

    def _deleteSelected(self):
        tid = self.gallery.selectedId()
        if tid is None or self.template_store is None:
            return
        self.template_store.delete(tid)
        self.gallery.refresh()
        self.gallery.clearSelection()

    def _onTemplateSelected(self, _tid):
        self.lbl_test.setText("")

    def _imageSearchArea(self) -> QRect | None:
        """The current search bounds (drawn literal or variable value), or None = whole screen."""
        if self.area_mode.currentIndex() == _VAR_IDX:
            cfg = self.var_store.get(self.area_var_combo.currentData())
            value = cfg.value if cfg else None
        else:
            value = self._area_literal
        return value if isinstance(value, QRect) else None

    def _testImage(self):
        """Run one match against the live screen so the user can tune the threshold."""
        tid = self.gallery.selectedId()
        b64 = self.template_store.getB64(tid) if (self.template_store and tid is not None) else None
        if not b64:
            self.lbl_test.setText("Select an image first")
            return
        from macro_studio.vision import templateFromB64, findImageCenterFromArray
        try:
            template = templateFromB64(b64)
        except ValueError:
            self.lbl_test.setText("Invalid template")
            return
        threshold = self.threshold_spin.value() / 100
        area = self._imageSearchArea()

        # Hide our own windows so the grab sees the target app rather than
        # MacroStudio, and let the screen settle before capturing.
        main_window = self.overlay.main_window if self.overlay else None
        self.hide()
        if main_window is not None:
            main_window.hide()
        self._settle(150)
        try:
            result = findImageCenterFromArray(template, area, threshold)
        finally:
            if main_window is not None:
                main_window.show()
            self.show()
            self.raise_()
            self.activateWindow()

        if result is not None:
            _pt, conf = result
            self.lbl_test.setText(f"✓ found (score {conf:.2f})")
        else:
            self.lbl_test.setText(f"✗ not found (≥{self.threshold_spin.value()}%)")

    @staticmethod
    def _settle(ms: int):
        """Spin the event loop briefly so hidden windows clear the screen before a grab."""
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    # --- load / save ---
    def _loadFrom(self, cond: WaitCondition):
        self.type_combo.setCurrentIndex(self.type_combo.findData(cond.condition_type))
        self._onTypeChanged()

        self.tol_spin.setValue(cond.tolerance)
        self.op_combo.setCurrentIndex(self.op_combo.findData(cond.operator))
        self.text_mode_combo.setCurrentIndex(self.text_mode_combo.findData(cond.text_mode))
        self.image_match_combo.setCurrentIndex(self.image_match_combo.findData(cond.image_match))
        self.threshold_spin.setValue(round(cond.threshold * 100))
        # Image template: select the referenced library entry, or migrate a legacy
        # inline template into the library (deduped) and select that.
        if self.template_store is not None:
            if cond.template_id is not None and self.template_store.get(cond.template_id):
                self.gallery.selectId(cond.template_id)
            elif cond.template_b64:
                entry = self.template_store.add(cond.template_b64)
                self.gallery.refresh()
                self.gallery.selectId(entry.id)

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

        self._updateStoreEnabled()

    def resultCondition(self) -> WaitCondition:
        cond = WaitCondition()
        # QComboBox returns str-Enum userData as a plain str; coerce back to the enum.
        cond.condition_type = ConditionType(self.type_combo.currentData())
        cond.operator = CompareOp(self.op_combo.currentData())
        cond.text_mode = TextMatch(self.text_mode_combo.currentData())
        cond.image_match = ImageMatch(self.image_match_combo.currentData())
        cond.tolerance = self.tol_spin.value()
        cond.threshold = self.threshold_spin.value() / 100

        if self.area_mode.currentIndex() == _VAR_IDX:
            cond.area_var = self.area_var_combo.currentData()
        else:
            cond.area = self._area_literal

        if cond.condition_type == ConditionType.IMAGE:
            cond.template_id = self.gallery.selectedId()

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

    def __init__(self, parent, prev_value, overlay, var_store, template_store=None):
        super().__init__(parent)
        self.overlay = overlay
        self.var_store = var_store
        self.template_store = template_store
        self.value = prev_value if isinstance(prev_value, WaitCondition) else WaitCondition()
        self._dialog = None

        self.setMouseTracking(True)

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

    def _watchArea(self):
        """The highlightable watch area: a variable name (str) or a literal QRect/QPoint."""
        if not isinstance(self.value, WaitCondition):
            return None
        return self.value.area_var or self.value.area

    def enterEvent(self, event):
        area = self._watchArea()
        if area is not None:
            self.overlay.trySetHighlighted(area)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.overlay.removeHighlightedData()
        super().leaveEvent(event)

    def _openDialog(self):
        if self._dialog is not None and self._dialog.isVisible():
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        self._dialog = WaitUntilDialog(self.value, self.var_store, self.overlay,
                                       self.template_store, parent=self)
        self._dialog.accepted.connect(self._onDialogAccepted)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _onDialogAccepted(self):
        new_cond = self._dialog.resultCondition()
        self.value = new_cond
        self._refresh()
        self.valueChanged.emit(new_cond)
