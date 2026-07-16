import sys

from macro_studio.core.data.profile import Profile
from macro_studio.ui.main_window import MainWindow


if __name__ == "__main__":
    debug_vars = {}

    profile = Profile("Ui Test")

    window = MainWindow(profile)

    window.show()
    sys.exit(window.app.exec())