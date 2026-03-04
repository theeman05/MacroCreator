import pydirectinput
from PySide6.QtGui import QColor
from macro_studio import MacroStudio, CaptureMode, Controller
from macro_studio.vision import captureScreenColor, isColorSimilar

CLICK_PT_ID = "click_pt"
TARGET_COLOR_ID = "target_color"

# --8<-- [start:humanized_reaction_logic]
class BenchmarkScanner:
    """Constantly polls the screen to see if the target color has appeared."""
    is_target_color = False

    def __init__(self, studio: MacroStudio):
        # Register the scanning task
        studio.addBasicTask(self.scanColor, repeat=True, display_name="Scan Target Color")

        # Register variables.
        studio.addVar(CLICK_PT_ID, CaptureMode.POINT, pick_hint="Click the center of the benchmark area")
        studio.addVar(TARGET_COLOR_ID, CaptureMode.COLOR, default_val=QColor("#4bdb6a"), pick_hint="Pick the green screen color")

    def scanColor(self, controller: Controller):
        target_pt = controller.getVar(CLICK_PT_ID)
        target_color = controller.getVar(TARGET_COLOR_ID)

        # Safety check in case the user hasn't set the point yet
        if not target_pt or not target_color:
            return

        screen_color = captureScreenColor(target_pt)

        # Using a very tight tolerance (5) because the website's green is perfectly consistent
        self.is_target_color = isColorSimilar(screen_color, target_color, tolerance=5)


class ReactionBot:
    """Fires a click the exact millisecond the scanner detects the color."""
    clicked_already = False

    def __init__(self, studio: MacroStudio, scanner: BenchmarkScanner):
        self.scanner = scanner
        # Register the clicking task
        studio.addBasicTask(self.clickWhenReady, repeat=True, display_name="Lightning Click")

    def clickWhenReady(self, controller: Controller):
        if self.scanner.is_target_color:
            if not self.clicked_already:
                click_pt = controller.getVar(CLICK_PT_ID)
                self.clicked_already = True

                # Execute the $O(1)$ click
                pydirectinput.leftClick(click_pt.x(), click_pt.y())

                # Yield briefly to prevent double-clicking while the screen transitions
                yield 0.1
        else:
            # Reset the flag when the screen turns red or blue again
            self.clicked_already = False
# --8<-- [end:humanized_reaction_logic]

if __name__ == "__main__":
    # 1. Initialize the engine
    studio = MacroStudio("Human Benchmark Macro")

    # 2. Instantiate our classes, linking the bot to the scanner's state
    scanner = BenchmarkScanner(studio)
    ReactionBot(studio, scanner)

    # 3. Launch the UI!
    studio.launch()