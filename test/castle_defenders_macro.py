import re
from macro_studio import (MacroStudio, CaptureMode, TaskInterruptedException, taskWaitForResume,
                          taskHoldKey, taskMouseClick, taskSleep)
from macro_studio.vision import captureScreenText
from enum import Enum, auto

class StepKey(Enum):
    START_POINT = auto()
    WAVE_RECT = auto()
    END_WAVE = auto()

castle_macro = MacroStudio("Castle Defenders Macro")

def moveCharacter():
    """Periodically moves the character while running the macros"""
    while True:
        yield from taskHoldKey("W", 2)
        yield from taskHoldKey("A", 4)
        yield from taskHoldKey("S", 2)
        yield from taskHoldKey("D", 4)

def isWaveGreater(text, threshold):
    match = re.search(r'\d+', text)
    return match and int(match.group()) > threshold or False

def monitorMatchStatus():
    """Monitors the match status and starts or stops the game"""
    while True:
        try:
            wave_text = captureScreenText(castle_macro.getVar(StepKey.WAVE_RECT))
            if not wave_text or isWaveGreater(wave_text, castle_macro.getVar(StepKey.END_WAVE)):
                # Wave is greater than target, or match not started, select stop/start button
                yield from taskMouseClick(castle_macro.getVar(StepKey.START_POINT))

            yield from taskSleep(2)
        except TaskInterruptedException:
            yield from taskWaitForResume()


castle_macro.addVar(StepKey.START_POINT, CaptureMode.POINT, None, "Select start/stop button position")
castle_macro.addVar(StepKey.WAVE_RECT, CaptureMode.REGION, None, "Click and drag to set wave region")
castle_macro.addVar(StepKey.END_WAVE, int, 100)

character_controller = castle_macro.addBasicTask(moveCharacter)
wave_mon_controller = castle_macro.addBasicTask(monitorMatchStatus)

if __name__ == '__main__':
    castle_macro.launch()