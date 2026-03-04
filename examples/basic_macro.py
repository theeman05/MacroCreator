import time
from macro_studio import MacroStudio, Controller, taskSleep


# --8<-- [start:basic_logic]
# 1. Define a standalone task function
# This task just counts time and proves that it can be paused by someone else.
def anotherTask(controller: Controller):
    controller.log("Starting secondary task...")
    start_time = time.time()

    # This loop runs until the task finishes
    # If paused externally, macroSleep handles the waiting automatically.
    yield from taskSleep(5)

    elapsed = time.time() - start_time
    controller.log(f"Secondary task finished! Total Elapsed: {elapsed:.2f}s")


# 2. Define the Main Macro Class
class BasicMacro:
    def __init__(self, studio: MacroStudio):
        # Register the tasks so the engine knows about them.
        # We store the controller for 'anotherTask' so we can manipulate it later.
        self.other_task_ctrl = studio.addBasicTask(anotherTask)

        # Register our main coordination task
        studio.addBasicTask(self.mainCoordinator)

    def mainCoordinator(self, controller: Controller):
        """
        This task acts as the 'Manager'. It starts, pauses, and resumes the other task.
        """
        controller.log("Manager: Starting sequence...")

        # Let the other task run for 1 second
        yield from taskSleep(1)

        controller.log("Manager: ⏸️ Pausing the secondary task now!")
        self.other_task_ctrl.pause()

        # Wait while the other task is frozen
        yield from taskSleep(2)

        controller.log("Manager: ▶️ Resuming the secondary task!")
        self.other_task_ctrl.resume()

        # Wait for everything to finish
        yield from taskSleep(2)
        controller.log("Manager: Sequence complete.")

if __name__ == '__main__':
    # Instantiates the studio with the profile name "Basic Macro"
    studio = MacroStudio("Basic Macro")

    # Registers tasks from our macro
    BasicMacro(studio)

    # Launches the application
    studio.launch()

# --8<-- [end:basic_logic]