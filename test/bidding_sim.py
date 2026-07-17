from macro_studio import MacroStudio, CaptureMode, Controller, taskSleep
from macro_studio.actions import taskMouseClick
from macro_studio.vision import getScreenState, findImageCenter

from PySide6.QtCore import QRect

import cv2
import numpy as np


def checkTargetColorThreshold(bounds: QRect, lightness_threshold=240, saturation_threshold=20):
    # Load the image
    img = getScreenState(bounds)

    # Convert from BGR to HLS (Hue, Lightness, Saturation)
    hls_img = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)

    # Split the channels
    lightness_channel = hls_img[:, :, 1]
    saturation_channel = hls_img[:, :, 2]

    # Create a condition where Lightness is HIGH and Saturation is LOW
    is_white_pixel = (lightness_channel > lightness_threshold) & (saturation_channel < saturation_threshold)

    # Check if ANY pixel matches both conditions
    has_white_pixel = np.any(is_white_pixel)

    return has_white_pixel


def bidScanner(controller: Controller):
    if checkTargetColorThreshold(controller.getVar("bid_region"), controller.getVar("lightness_threshold"), controller.getVar("saturation_threshold")):
        yield from taskMouseClick(controller.getVar("bid_btn"))
        yield from taskSleep(.01)

def plusFinder(controller: Controller):
    match = findImageCenter("G:/My Drive/Pictures/Plus_Sign.png", controller.getVar("sell_region"), threshold=controller.getVar("plus_threshold"))
    if match:
        yield from taskMouseClick(match[0])
        yield from taskSleep(.15)  # Wait slightly for UI and stuff
        yield from taskMouseClick(controller.getVar("first_item_pt"))
        yield from taskSleep(.15) # Wait slightly for UI and stuff

if __name__ == "__main__":
    creator = MacroStudio("Bidding Sim")

    creator.addBasicTask(bidScanner, repeat=True, display_name="Monitor Bid State")
    creator.addBasicTask(plusFinder, repeat=True, display_name="Plus Finder")

    creator.addVar("bid_region", CaptureMode.REGION)
    creator.addVar("bid_btn", CaptureMode.POINT)
    creator.addVar("lightness_threshold", int, 240)
    creator.addVar("saturation_threshold", int, 20)
    creator.addVar("first_item_pt", CaptureMode.POINT)
    creator.addVar("sell_region", CaptureMode.REGION)
    creator.addVar("plus_threshold", float, .5)

    creator.launch()
