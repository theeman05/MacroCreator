import pydirectinput, pyperclip
import numpy as np
from typing import Generator, Iterator
from contextlib import contextmanager
from PySide6.QtCore import QPoint
from pydirectinput import MOUSE_PRIMARY

from macro_studio.core.types_and_enums import TaskInterruptedException

pydirectinput.PAUSE = 0.0

def taskSleep(duration: float=.01) -> Generator[float]:
    """Pauses the task execution for a specified duration.

    This is a non-blocking operation that yields control back to the worker
    for the given duration. It allows the application to remain responsive
    while the task is "sleeping".

    Args:
        duration: The time in seconds to pause the task. Defaults to 0.01 seconds.

    Yields:
        The duration in seconds to sleep.

    Raises:
        TaskInterruptedException: If the task is hard-paused while sleeping.
    """
    yield duration

def taskWaitForResume() -> Iterator[None]:
    """Yields control until the controller's hard-pause state is cleared.

    This function is non-blocking and will cause the task to wait indefinitely
    until the main application signals that it should resume.

    Yields:
        None: Indicates that the task should wait for an external resume signal.
    """
    yield None

@contextmanager
def holdKey(key_name: str) -> Iterator[None]:
    """Context manager to hold down a keyboard key and ensure its release.

    This context manager handles pressing a key down at the start of the `with`
    block and guarantees that the key is released when exiting the block,
    even if an exception occurs.

    Args:
        key_name: The name of the key to hold down (e.g., 'shift', 'a', 'enter').

    Yields:
        None: The execution context within the `with` statement.
    """
    pydirectinput.keyDown(key_name)
    try:
        yield  # Run the block inside the 'with' statement
    finally:
        pydirectinput.keyUp(key_name)

def taskHoldKey(key_name: str, duration: float) -> Iterator[float | None]:
    """Holds a keyboard key for a specified duration within a task.

    This function presses a key, holds it for the given duration using `taskSleep`,
    and then releases it. If the task is hard-paused during the hold, the key
    is released immediately, and the task waits for resume.

    Args:
        key_name: The name of the key to hold down.
        duration: The duration in seconds to hold the key.

    Yields:
        float: The duration to sleep from `taskSleep`, or None from `taskWaitForResume`.
    """
    try:
        with holdKey(key_name):
            yield from taskSleep(duration)
    except TaskInterruptedException:
        yield from taskWaitForResume()

@contextmanager
def mouseClick(coords: QPoint=None, button: str=MOUSE_PRIMARY) -> Iterator[None]:
    """Context manager to perform a mouse click (press and release).

    This context manager presses a mouse button at specified coordinates (or current
    position if `coords` is None) at the start of the `with` block. It guarantees
    the mouse button is released when exiting the block, even if an exception occurs.
    A small random offset is added to the release coordinates if `coords` are provided
    to simulate human-like mouse movement.

    Args:
        coords: A QPoint object specifying the (x, y) coordinates for the click.
            If None, the current mouse position is used. Defaults to None.
        button: The mouse button to press ('left', 'right', 'middle').
            Defaults to MOUSE_PRIMARY ('left').

    Yields:
        None: The execution context within the `with` statement.
    """
    x = y = None
    if coords: x, y = coords.x(), coords.y()
    pydirectinput.mouseDown(x, y, button, tween=.05)
    try:
        yield  # Run the block inside the 'with' statement
    finally:
        if coords:
            pydirectinput.mouseUp(x + np.random.randint(-5, 5), y + np.random.randint(-5, 5), button, tween=.05)
        else:
            pydirectinput.mouseUp(None, None, button)

def taskMouseClick(coords: QPoint=None, button: str=MOUSE_PRIMARY) -> Iterator[float | None]:
    """Performs a mouse click (press and release) within a task.

    This function presses a mouse button at the given coordinates, yields
    for a short duration using `taskSleep`, and then releases the button.
    If the task is hard-paused during the click, the mouse button is released
    immediately, and the task waits for resume.

    Args:
        coords: A QPoint object specifying the (x, y) coordinates for the click.
            If None, the current mouse position is used. Defaults to None.
        button: The mouse button to use ('left', 'right', 'middle').
            Defaults to MOUSE_PRIMARY ('left').

    Yields:
        float: The duration to sleep from `taskSleep`, or None from `taskWaitForResume`.
    """
    try:
        with mouseClick(coords, button):
            yield from taskSleep(.1)
    except TaskInterruptedException:
        yield from taskWaitForResume()

def taskPasteText(text_to_paste: str) -> Generator[float]:
    """Pastes the given text using Ctrl+V after copying it to the clipboard.

    This function temporarily stores the current clipboard content, copies
    the `text_to_paste` to the clipboard, simulates a Ctrl+V key combination,
    and then restores the original clipboard content.

    Args:
        text_to_paste: The string content to be pasted.

    Yields:
        float: The duration to sleep from `taskSleep`.
    """
    if not text_to_paste:
        return

    original_clipboard = pyperclip.paste()
    try:
        pyperclip.copy(text_to_paste)

        yield from taskSleep(0.05)

        pydirectinput.keyDown('ctrl')
        pydirectinput.press('v')
        pydirectinput.keyUp('ctrl')

        yield from taskSleep(0.05)
    finally:
        pyperclip.copy(original_clipboard)