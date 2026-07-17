from macro_studio import MacroStudio, CaptureMode, Controller, taskSleep
from macro_studio.actions import holdKey
from macro_studio.vision import captureScreenColor, isColorSimilar

COLOR_PT_ID = "Color Point"
SCAN_COLOR_ID = "Scan Color"

class ColorScanner:
    colors_similar = False

    def __init__(self, studio: MacroStudio):
        studio.addBasicTask(self.colorScanner, repeat=True, display_name="Scan Color Point")

        studio.addVar(COLOR_PT_ID, CaptureMode.POINT)
        studio.addVar(SCAN_COLOR_ID, CaptureMode.COLOR)

    def colorScanner(self, controller: Controller):
        color_pt = controller.getVar(COLOR_PT_ID)
        go_color = controller.getVar(SCAN_COLOR_ID)

        screen_color = captureScreenColor(color_pt)

        self.colors_similar = isColorSimilar(screen_color, go_color, tolerance=15)

class RLGLPlayer:
    def __init__(self, studio: MacroStudio, scanner: ColorScanner):
        self.scanner = scanner
        studio.addBasicTask(self.moveWhenSimilar, repeat=True, display_name="Move Character")

    def moveWhenSimilar(self):
        if self.scanner.colors_similar:
            # Context manager auto-releases the key if the engine stops
            with holdKey("w"):
                while self.scanner.colors_similar:
                    # Hand control back to the engine
                    yield from taskSleep(.001)


if __name__ == "__main__":
    main_studio = MacroStudio("Red Light Green Light")

    color_scanner = ColorScanner(main_studio)

    RLGLPlayer(main_studio, color_scanner)

    main_studio.launch()
