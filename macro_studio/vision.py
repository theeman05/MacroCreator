import cv2, pytesseract, mss, os
import numpy as np
from PySide6.QtCore import QRect, QPoint
from PIL import Image

from PySide6.QtGui import QColor

TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def captureScreenText(bounds: QRect) -> str:
    """Captures a region of the screen and extracts text using Tesseract OCR.

    This method performs a screen grab via MSS, converts the buffer to a grayscale binary image for better contrast,
    and then processes it through the Tesseract engine.

    Args:
        bounds: The rectangular area of the screen to read from.

    Returns:
        The extracted text string, stripped of leading/trailing whitespace.

    Raises:
        FileNotFoundError: If the Tesseract OCR binary is not installed
            at the path specified in 'pytesseract.pytesseract.tesseract_cmd'.
    """
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
    """Captures the QColor of a specific pixel on the screen.

    Args:
        point: The specific pixel location to read from.

    Returns:
        The QColor of the specified pixel.
    """
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
    """Checks if two colors are within a certain Euclidean distance in RGB space.

    Args:
        color_a: The first color to compare (usually captured from the screen).
        color_b: The second color to compare (usually the target variable).
        tolerance: The maximum Euclidean distance allowed between colors.
            0 is an exact match, 10-20 is tight, 50+ is loose.

    Returns:
        True if the distance between the two colors is <= tolerance, False otherwise.
    """
    r_diff = color_a.red() - color_b.red()
    g_diff = color_a.green() - color_b.green()
    b_diff = color_a.blue() - color_b.blue()

    distance_sq = (r_diff ** 2) + (g_diff ** 2) + (b_diff ** 2)

    return distance_sq <= (tolerance ** 2)


def isColorSimilarPerceptual(color_a: QColor, color_b: QColor, tolerance: int = 10) -> bool:
    """ Checks if two colors are within a certain weighted RGB space based on human perception.

    Best for distinguishing between subtle UI shades (e.g., 'Active' vs 'Inactive' buttons).

    Args:
        color_a: The first color to compare (usually captured from the screen).
        color_b: The second color to compare (usually the target variable).
        tolerance: The maximum Euclidean distance allowed between colors.
            0 is an exact match, 10-20 is tight, 50+ is loose.

    Returns:
        True if the distance between the two colors is <= tolerance, False otherwise.
    """
    r_diff = color_a.red() - color_b.red()
    g_diff = color_a.green() - color_b.green()
    b_diff = color_a.blue() - color_b.blue()

    # Human eyes are most sensitive to green, then red, then blue.
    weighted_dist_sq = (r_diff ** 2 * 0.299) + (g_diff ** 2 * 0.587) + (b_diff ** 2 * 0.114)
    return weighted_dist_sq <= (tolerance ** 2)


def isBrightnessSimilar(color_a: QColor, color_b: QColor, tolerance: int = 10) -> bool:
    """Checks if the lightness/luminance of two colors are similar.

    Best for detecting if a screen region flashes, dims, or highlights, regardless of the actual color hue.

    Args:
        color_a: The first color to compare (usually captured from the screen).
        color_b: The second color to compare (usually the target variable).
        tolerance: The maximum Euclidean distance allowed between colors.
            0 is an exact match, 10-20 is tight, 50+ is loose.

    Returns:
        True if the distance between the two colors is <= tolerance, False otherwise.
    """
    return abs(color_a.lightness() - color_b.lightness()) <= tolerance


def _sctWithOptionalBounds(bounds):
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
        return sct.grab(region), region


def _templateHelper(template_path: str, bounds: QRect | None = None):
    screenshot, region = _sctWithOptionalBounds(bounds)

    screen_img = np.array(screenshot)[..., :3]  # BGRA to BGR
    template_img = cv2.imread(template_path, cv2.IMREAD_COLOR)

    if template_img is None:
        raise FileNotFoundError(f"Template image not found at: {template_path}")

    # Perform OpenCV template matching
    return template_img, region, cv2.matchTemplate(screen_img, template_img, cv2.TM_CCOEFF_NORMED)


def findImageCenter(template_path: str, bounds: QRect | None = None, threshold: float=0.8) -> tuple[QPoint, float] | None:
    """Finds an image template on the screen and return its absolute center coordinates.

    Args:
        template_path (str): Path to the template image.
        bounds: The bounds to search for the template in. If no bounds are provided, it searches the entire primary monitor.
        threshold: Confidence threshold to consider the result as a potential match.

    Returns:
        The absolute center coordinates of the found template object and the confidence score, or None if not found.
    """
    template_img, region, result = _templateHelper(template_path, bounds)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        h, w = template_img.shape[:2]
        center_x = max_loc[0] + (w // 2) + region["left"]
        center_y = max_loc[1] + (h // 2) + region["top"]
        return QPoint(center_x, center_y), max_val

    return None


def findImageCenters(template_path: str, bounds: QRect | None = None, threshold: float = 0.8) -> list[
    tuple[QPoint, float]]:
    """Finds all instances of an image template on the screen and returns their absolute center coordinates.

    Args:
        template_path (str): Path to the template image.
        bounds: The bounds to search for the template in. If no bounds are provided, it searches the entire primary monitor.
        threshold: Confidence threshold to consider the result as a potential match.

    Returns:
        A list of tuples containing the absolute center coordinates (QPoint) and the confidence score (float).
        Returns an empty list if no matches are found.
    """
    template_img, region, result = _templateHelper(template_path, bounds)

    # Find all locations in the result matrix that exceed the threshold
    y_locs, x_locs = np.where(result >= threshold)

    h, w = template_img.shape[:2]
    raw_matches = []

    # Extract the coordinates and their specific confidence scores
    for x, y in zip(x_locs, y_locs):
        score = result[y, x]
        raw_matches.append((x, y, score))

    # Sort matches by confidence score descending so we always keep the strongest match in a cluster
    raw_matches.sort(key=lambda match: match[2], reverse=True)

    final_results = []

    for x, y, score in raw_matches:
        is_duplicate = False

        # Compare against already validated matches to avoid cluster duplicates
        for prev_pt, _ in final_results:
            # Revert the absolute coordinates back to relative for distance checking
            prev_x = prev_pt.x() - region["left"] - (w // 2)
            prev_y = prev_pt.y() - region["top"] - (h // 2)

            # If the current point is within half the width/height of an existing match, it's the same object
            if abs(x - prev_x) < (w // 2) and abs(y - prev_y) < (h // 2):
                is_duplicate = True
                break

        if not is_duplicate:
            center_x = int(x + (w // 2) + region["left"])
            center_y = int(y + (h // 2) + region["top"])
            final_results.append((QPoint(center_x, center_y), float(score)))

    return final_results


def getScreenState(bounds: QRect | None = None) -> np.ndarray:
    """Capture a region and return it as a BGR numpy array for custom processing.

    Args:
        bounds: The region to capture. If ``None``, processes the whole screen.

    Returns:
        A BGR numpy array for custom processing.
    """
    screenshot, _region = _sctWithOptionalBounds(bounds)

    np_img = np.array(screenshot)
    return np_img[..., :3]