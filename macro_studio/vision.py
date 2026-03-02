import cv2, pytesseract, mss
import numpy as np
from PySide6.QtCore import QRect, QPoint
from PIL import Image
from typing import Optional

from PySide6.QtGui import QColor

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'


def captureScreenText(bounds: QRect) -> str:
    region = {
        "top": bounds.top(),
        "left": bounds.left(),
        "width": bounds.width(),
        "height": bounds.height(),
    }
    with mss.mss() as sct:
        screenshot = sct.grab(region)

    raw_bytes = np.frombuffer(screenshot.bgra, dtype=np.uint8)

    bgra_img = raw_bytes.reshape((region["height"], region["width"], 4))

    gray = cv2.cvtColor(bgra_img, cv2.COLOR_BGRA2GRAY)

    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return pytesseract.image_to_string(Image.fromarray(binary)).strip()


def captureScreenColor(point: QPoint) -> QColor:
    """Capture the QColor of a specific pixel on the screen."""
    region = {
        "top": point.y(),
        "left": point.x(),
        "width": 1,
        "height": 1,
    }
    with mss.mss() as sct:
        screenshot = sct.grab(region)

    b, g, r, a = screenshot.bgra
    return QColor(r, g, b, a)


def isColorSimilar(color_a: QColor, color_b: QColor, tolerance: int = 10) -> bool:
    """
    Checks if two colors are within a certain Euclidean distance in RGB space.
    Tolerance: 0 is exact, 10-20 is tight, 50+ is loose.
    """
    r_diff = color_a.red() - color_b.red()
    g_diff = color_a.green() - color_b.green()
    b_diff = color_a.blue() - color_b.blue()

    distance_sq = (r_diff ** 2) + (g_diff ** 2) + (b_diff ** 2)

    return distance_sq <= (tolerance ** 2)


def isColorSimilarPerceptual(color_a: QColor, color_b: QColor, tolerance: int = 10) -> bool:
    """
    Checks if two colors are within a certain weighted RGB space based on human perception.
    Best for distinguishing between subtle UI shades (e.g., 'Active' vs 'Inactive' buttons).
    """
    r_diff = color_a.red() - color_b.red()
    g_diff = color_a.green() - color_b.green()
    b_diff = color_a.blue() - color_b.blue()

    # Human eyes are most sensitive to green, then red, then blue.
    weighted_dist_sq = (r_diff ** 2 * 0.299) + (g_diff ** 2 * 0.587) + (b_diff ** 2 * 0.114)
    return weighted_dist_sq <= (tolerance ** 2)


def isBrightnessSimilar(color_a: QColor, color_b: QColor, tolerance: int = 10) -> bool:
    """
    Checks if the lightness/luminance of two colors are similar.
    Best for detecting if a screen region flashes, dims, or highlights,
    regardless of the actual color hue.
    """
    return abs(color_a.lightness() - color_b.lightness()) <= tolerance


def findImageCenter(template_path: str, bounds: Optional[QRect] = None, threshold=0.8) -> Optional[tuple[QPoint, float]]:
    """
    Finds an image template on the screen and return its absolute center coordinates.
    Args:
        template_path (str): Path to the template image.
        bounds: The bounds to search for the template in. If no bounds are provided, it searches the entire primary monitor.
        threshold: Confidence threshold to consider the result as a potential match.
    Returns:
        The absolute center coordinates of the found template object and the confidence score, or None if not found.
    """
    with mss.mss() as sct:
        if bounds:
            region = {
                "top": bounds.top(),
                "left": bounds.left(),
                "width": bounds.width(),
                "height": bounds.height(),
            }
        else:
            # Default to primary monitor
            monitor = sct.monitors[1]
            region = {
                "top": monitor["top"],
                "left": monitor["left"],
                "width": monitor["width"],
                "height": monitor["height"],
            }
        screenshot = sct.grab(region)

    screen_img = np.array(screenshot)[..., :3]  # BGRA to BGR
    template_img = cv2.imread(template_path, cv2.IMREAD_COLOR)

    if template_img is None:
        raise FileNotFoundError(f"Template image not found at: {template_path}")

    # Perform OpenCV template matching
    result = cv2.matchTemplate(screen_img, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        h, w = template_img.shape[:2]
        center_x = max_loc[0] + (w // 2) + region["left"]
        center_y = max_loc[1] + (h // 2) + region["top"]
        return QPoint(center_x, center_y), max_val

    return None


def getScreenState(bounds: QRect) -> np.ndarray:
    """Capture a region and return it as a BGR numpy array for custom processing."""
    region = {
        "top": bounds.top(),
        "left": bounds.left(),
        "width": bounds.width(),
        "height": bounds.height(),
    }
    with mss.mss() as sct:
        screenshot = sct.grab(region)

    np_img = np.array(screenshot)
    return np_img[..., :3]