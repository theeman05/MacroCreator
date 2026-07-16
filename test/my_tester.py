from macro_studio import MacroStudio, ThreadController, CaptureMode
from macro_studio.vision import findImageCenter


def stoplightScanner(controller: ThreadController):
    center = findImageCenter("C:/Users/theem/OneDrive/Desktop/TrafficLight.jpg", controller.getVar("stoplight_loc"), threshold=.2)
    if center:
        controller.log(center)


if __name__ == "__main__":
    creator = MacroStudio("My Test")

    creator.addBasicTask(stoplightScanner, repeat=True, display_name="Stoplight Scanner")
    creator.addVar("test_color", CaptureMode.COLOR)

    creator.launch()
