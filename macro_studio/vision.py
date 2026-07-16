import cv2, pytesseract, mss, os, base64
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


def trimTransparentB64(b64: str) -> str:
    """Return a base64 PNG with fully-transparent border rows/columns removed.

    Images with no alpha channel (screen grabs, JPGs) or that are entirely
    transparent are returned unchanged. Template matching ignores alpha, so
    trimming the transparent margins tightens the search to the real content
    (like Photoshop's "Trim").

    Args:
        b64: base64 text of a PNG image.

    Returns:
        base64 text of the trimmed PNG, or the original string when there is
        nothing to trim.
    """
    raw = base64.b64decode(b64)
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim != 3 or img.shape[2] < 4:
        return b64  # no alpha channel to trim against

    mask = img[:, :, 3] > 0  # opaque (even partially) pixels
    if not mask.any():
        return b64  # fully transparent; nothing meaningful to keep

    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    y0, y1 = int(rows[0]), int(rows[-1])
    x0, x1 = int(cols[0]), int(cols[-1])
    if x0 == 0 and y0 == 0 and x1 == img.shape[1] - 1 and y1 == img.shape[0] - 1:
        return b64  # already tight

    ok, png = cv2.imencode(".png", img[y0:y1 + 1, x0:x1 + 1])
    if not ok:
        return b64
    return base64.b64encode(png.tobytes()).decode("ascii")


def templateFromB64(b64: str) -> np.ndarray:
    """Decode a base64-encoded PNG template into a BGR numpy array.

    Args:
        b64: base64 text of a PNG image (as stored on a WAIT_UNTIL image condition).

    Returns:
        The template as a BGR numpy array, ready for ``findImageCenterFromArray``.

    Raises:
        ValueError: If the string cannot be base64-decoded or is not a decodable image.
    """
    raw = base64.b64decode(b64)  # binascii.Error is a subclass of ValueError
    template = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError("Could not decode template image bytes")
    return template


def _findTemplate(template_bgr: np.ndarray, bounds: QRect | None, threshold: float) -> tuple[QPoint, float] | None:
    """Shared match core: locate ``template_bgr`` within ``bounds`` (or the whole screen)."""
    screenshot, region = _sctWithOptionalBounds(bounds)
    screen_img = np.array(screenshot)[..., :3]  # BGRA to BGR

    h, w = template_bgr.shape[:2]
    # matchTemplate raises when the template is larger than the search image.
    if h > screen_img.shape[0] or w > screen_img.shape[1]:
        return None

    result = cv2.matchTemplate(screen_img, template_bgr, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        center_x = max_loc[0] + (w // 2) + region["left"]
        center_y = max_loc[1] + (h // 2) + region["top"]
        return QPoint(center_x, center_y), max_val

    return None


def findImageCenter(template_path: str, bounds: QRect | None = None, threshold: float=0.8) -> tuple[QPoint, float] | None:
    """Finds an image template on the screen and return its absolute center coordinates.

    Args:
        template_path (str): Path to the template image.
        bounds: The bounds to search for the template in. If no bounds are provided, it searches the entire primary monitor.
        threshold: Confidence threshold to consider the result as a potential match.

    Returns:
        The absolute center coordinates of the found template object and the confidence score, or None if not found.
    """
    template_img = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template_img is None:
        raise FileNotFoundError(f"Template image not found at: {template_path}")
    return _findTemplate(template_img, bounds, threshold)


def findImageCenterFromArray(template_bgr: np.ndarray, bounds: QRect | None = None, threshold: float=0.8) -> tuple[QPoint, float] | None:
    """Like ``findImageCenter`` but takes an already-decoded BGR template array.

    Used at runtime for image WAIT_UNTIL conditions, whose template lives in the
    step (base64) rather than on disk — see ``templateFromB64``.

    Args:
        template_bgr: The template as a BGR numpy array.
        bounds: The bounds to search within. If ``None``, searches the whole primary monitor.
        threshold: Confidence threshold to consider the result as a match.

    Returns:
        The absolute center coordinates of the match and the confidence score, or None if not found.
    """
    return _findTemplate(template_bgr, bounds, threshold)


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