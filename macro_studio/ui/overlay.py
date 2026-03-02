from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, QRect, Signal, QEventLoop, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QKeyEvent
from typing import TYPE_CHECKING

from macro_studio.core.types_and_enums import CaptureMode
from macro_studio.core.registries.capture_type_registry import GlobalCaptureRegistry
from macro_studio.core.data import VariableConfig

if TYPE_CHECKING:
    from .main_window import MainWindow

TOOLBAR_STYLE = """
QFrame#OverlayToolbar {
    background-color: #333333;
    border: 1px solid #555;
    border-radius: 5px;
    color: white;
}
QLabel {
    color: white;
    font-weight: bold;
    padding: 0 10px;
    font-size: 14px;
}
QPushButton {
    background-color: transparent;
    border: none;
    color: #bbb;
    font-weight: bold;
    font-size: 16px;
    padding: 5px 10px;
}
QPushButton:hover {
    color: #ff5555; /* Red on hover */
    background-color: #444;
    border-radius: 3px;
}
"""


def _paintCapturable(painter, to_paint):
    if isinstance(to_paint, VariableConfig):
        to_paint = to_paint.value

    if to_paint is None: return

    if isinstance(to_paint, QPoint):
        painter.drawEllipse(to_paint, 10, 10)
    elif isinstance(to_paint, QRect):
        painter.drawRect(to_paint)
    else:
        print(f'UNEXPECTED OBJECT {type(to_paint)} FOUND WHEN DRAWING')


class TransparentOverlay(QWidget):
    captureFinished = Signal()
    cancelClicked = Signal()

    def __init__(self, main_window: "MainWindow"):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Prevents showing in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._click_through = True
        self.main_window = main_window

        self._setup_toolbar()

        screen = main_window.app.primaryScreen()
        self.setGeometry(screen.geometry())

        self.show()
        self.setClickThrough(True)
        self.render_geometry = set()
        self._is_showing_geometry = True

        self.current_mode: CaptureMode | None = None
        self.start_pos = None
        self.selection_rect: QRect | None = None
        self._highlighted: VariableConfig | QPoint | QRect | None = None
        self._captured_data = None
        self.current_mouse_pos = None
        self._frozen_screen = None

        self.cancelClicked.connect(self._finishCapture)

    @property
    def is_showing_geometry(self):
        return self._is_showing_geometry

    @is_showing_geometry.setter
    def is_showing_geometry(self, value: bool):
        if value != self._is_showing_geometry:
            self._is_showing_geometry = value
            self.update()

    def _setup_toolbar(self):
        """Creates the floating bar at the top center"""
        self.toolbar = QFrame(self)
        self.toolbar.setObjectName("OverlayToolbar")
        self.toolbar.setStyleSheet(TOOLBAR_STYLE)
        self.toolbar.setMaximumWidth(800)

        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(5, 5, 5, 5)

        self.lbl_instruction = QLabel("Select Region")
        self.lbl_instruction.setWordWrap(True)
        layout.addWidget(self.lbl_instruction)

        self.btn_cancel = QPushButton("X")
        self.btn_cancel.clicked.connect(lambda: self.cancelClicked.emit())
        layout.addWidget(self.btn_cancel)

        self.toolbar.hide()

    def raiseToolbar(self, display_text):
        self.main_window.hide()
        self.lbl_instruction.setText(display_text or "")
        self.show()
        self.toolbar.show()
        self.toolbar.raise_()

    def hideToolbar(self):
        self.toolbar.hide()
        self.setClickThrough(True)
        self.main_window.show()

    def captureData(self, mode: CaptureMode, display_text=None) -> QRect | QPoint | None:
        """Shows the overlay and waits until capture is finished"""
        self.current_mode = mode
        self.current_mouse_pos = None

        self.main_window.hide()
        self.update()

        delay_loop = QEventLoop()
        QTimer.singleShot(200, delay_loop.quit)
        delay_loop.exec()

        self._frozen_screen = self.screen().grabWindow(0)

        if display_text is None:
            if mode is CaptureMode.REGION:
                display_text = "Click and drag to select a region"
            elif mode is CaptureMode.POINT:
                display_text = "Click to set the point"
            elif mode is CaptureMode.COLOR:
                display_text = "Click any pixel on the screen to capture its color"

        self.raiseToolbar(display_text)

        self.setClickThrough(False)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.setMouseTracking(True)

        loop = QEventLoop()
        self.captureFinished.connect(loop.quit)
        loop.exec()

        # Finished capture when past loop.exec
        capture_data = self._captured_data
        self._captured_data = None
        self._frozen_screen = None

        return capture_data

    def _finishCapture(self, capture_data=None):
        if self.current_mode is None: return
        self._captured_data = capture_data
        self.start_pos = self.selection_rect = self.current_mode = None
        self.current_mouse_pos = None

        self.setMouseTracking(False)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        self.hideToolbar()
        self.captureFinished.emit()

    def setClickThrough(self, enabled: bool):
        """
        Toggles whether clicks pass through to the game or stay in the overlay.
        """
        self._click_through = enabled
        if enabled:
            # Game Mode: Clicks go through to the game
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

            self.hide()
            self.showFullScreen()

            self.raise_()  # Bring to very front
            self.activateWindow()  # Tell OS "This is the active app"
            self.setFocus()  # Tell Qt "Send key/mouse events here"
        self.update()

    def resizeEvent(self, event):
        """Keep the toolbar centered at the top"""
        if hasattr(self, 'toolbar'):
            w = 300  # Width of toolbar
            h = 50  # Height
            x = (self.width() - w) // 2
            self.toolbar.setGeometry(x, 20, w, h)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if not self.current_mode:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode is CaptureMode.POINT:
                self._finishCapture(event.pos())
            elif self.current_mode is CaptureMode.REGION:
                # Start dragging
                self.start_pos = event.pos()
                self.selection_rect = QRect(self.start_pos, self.start_pos)
                self.update()
            elif self.current_mode is CaptureMode.COLOR:
                # Grab the exact pixel color using Qt!
                pos = event.pos()
                pixmap = self.screen().grabWindow(0, pos.x(), pos.y(), 1, 1)
                color = pixmap.toImage().pixelColor(0, 0)
                self._finishCapture(color)

    def mouseMoveEvent(self, event):
        if self.current_mode is CaptureMode.REGION and self.start_pos:
            # Update the drag rectangle
            self.selection_rect = QRect(self.start_pos, event.pos()).normalized()
            self.update()  # Force repaint to show the box growing
        elif self.current_mode is CaptureMode.COLOR:
            # Update our tracker and force the magnifier to redraw
            self.current_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.current_mode is CaptureMode.REGION and self.start_pos:
            # Finish dragging
            final_rect = self.selection_rect
            self._finishCapture(final_rect)

    def keyPressEvent(self, event: QKeyEvent):
        cur_mode = self.current_mode
        if cur_mode and event.key() == Qt.Key.Key_Escape:
            self._finishCapture(None)

    def trySetHighlighted(self, config_name: str | QPoint | QRect):
        prev = self._highlighted
        if isinstance(config_name, str):
            config = self.main_window.profile.vars.get(config_name)
            if not config: return
            self._highlighted = config if (config and config.data_type in (QPoint, QRect)) else None
        else:
            self._highlighted = config_name

        if prev != self._highlighted:
            self.update()

    def removeHighlightedData(self):
        if self._highlighted:
            self._highlighted = None
            self.update()

    def paintColorMagnifier(self, painter):
        m_pos = self.current_mouse_pos

        # 11x11 capture area, 10x zoom = 110x110 magnifier box
        cap_size, zoom = 11, 10
        mag_size = cap_size * zoom

        # Grab the small 11x11 screen region around the mouse
        grab_rect = QRect(m_pos.x() - cap_size // 2, m_pos.y() - cap_size // 2, cap_size, cap_size)
        pixmap = self.screen().grabWindow(0, grab_rect.x(), grab_rect.y(), grab_rect.width(), grab_rect.height())

        # Scale it up (FastTransformation keeps the sharp pixelated grid look)
        scaled = pixmap.scaled(mag_size, mag_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)

        # Edge Handling: Default to drawing bottom-right of cursor
        offset = 15
        draw_x = m_pos.x() + offset
        draw_y = m_pos.y() + offset

        # If hitting the right edge of the screen, flip the box to the left side
        if draw_x + mag_size > self.width():
            draw_x = m_pos.x() - mag_size - offset
        # If hitting the bottom edge, flip the box above the cursor (+30 is for the text area)
        if draw_y + mag_size + 30 > self.height():
            draw_y = m_pos.y() - mag_size - offset - 30

        # Draw dark background border & text area
        painter.fillRect(draw_x - 2, draw_y - 2, mag_size + 4, mag_size + 32, QColor(30, 30, 30, 220))

        # Draw the magnified grid
        painter.drawPixmap(draw_x, draw_y, scaled)

        # Draw the targeting crosshair exactly in the middle block
        center_offset = (cap_size // 2) * zoom
        painter.setPen(QPen(QColor("red"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(draw_x + center_offset, draw_y + center_offset, zoom, zoom)

        # Read the color from the exact center of our unscaled grab
        color = pixmap.toImage().pixelColor(cap_size // 2, cap_size // 2)

        # Draw the HEX code text below the grid
        painter.setPen(QColor("white"))
        painter.drawText(QRect(draw_x, draw_y + mag_size, mag_size, 30), Qt.AlignmentFlag.AlignCenter, color.name().upper())

    def paintEvent(self, event):
        painter = QPainter(self)

        highlight_pen = QPen(QColor(100, 200, 255), 2, Qt.PenStyle.SolidLine)
        highlight_brush = QColor(100, 200, 255, 30)
        if self.current_mode:
            # Draw screenshot as our solid background
            if self._frozen_screen:
                painter.drawPixmap(0, 0, self._frozen_screen)

                if self.current_mode != CaptureMode.COLOR:
                    dim_color = QColor(0, 0, 0, 100)
                    painter.fillRect(self.rect(), dim_color)

                selection_rect = self.selection_rect
                if selection_rect:
                    painter.setPen(highlight_pen)
                    painter.setBrush(highlight_brush)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.drawRect(selection_rect)

                if self.current_mode is CaptureMode.COLOR and self.current_mouse_pos:
                    self.paintColorMagnifier(painter)
        else:
            # Show geometry when we're not choosing something
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            highlighted = self._highlighted
            if self._is_showing_geometry:
                painter.setPen(QPen(QColor(255, 0, 0, 180), 2))
                for obj_conf in self.render_geometry:
                    val = obj_conf.value
                    if val and highlighted != obj_conf:
                        _paintCapturable(painter, val)

            if highlighted:
                painter.setPen(highlight_pen)
                painter.setBrush(highlight_brush)
                _paintCapturable(painter, highlighted)