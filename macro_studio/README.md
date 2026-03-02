# 🎬 Macro Studio

A powerful, locally-hosted desktop automation tool designed to help you build, manage, and execute complex workflows with ease. 

Other macro recorders give you a tricycle; we are handing you the keys to a Saturn V rocket. If you're a developer who looks at basic automation tools and thinks, "But can it query a database, hit three REST APIs, and then click the button?", this is for you.

## ✨ Key Features

* **Smart Task Management:** Create, organize, and manage automation tasks with real-time search filtering and nested task support.
* **Dynamic Variable System:** A dedicated workspace to create and manage variables (text, coordinates, settings, etc.) to use within your macros, complete with a visual data capture overlay.
* **Robust Profile Management:** Seamlessly switch between different automation workspaces. Create, duplicate, rename, and safely delete profiles without losing context.
* **Persistent Local Storage:** Built on a lightning-fast SQLite architecture. All profiles, tasks, and variables are automatically saved locally to `%APPDATA%`.
* **Visual Task Recorder:** Create new tasks by recording your mouse and keyboard actions—no coding required.
* **Modern UI/UX:** A sleek, dark-mode interface built with PySide6, featuring custom drag-and-drop timelines and interactive selector popups.

## ⚙️ Prerequisites & System Requirements

While Macro Studio works out of the box for standard automation, utilizing the Optical Character Recognition (OCR) features in the Vision library requires a third-party OCR engine to be installed on your system.

**Tesseract OCR (Required for Text Capture)**
If you plan to use `vision.captureScreenText()` in your macros to read text from the screen, you **must** install the Tesseract C++ binary.

**Windows Users:**
1. Download the latest installer from the [UB-Mannheim Tesseract repository](https://www.google.com/search?q=https://github.com/UB-Mannheim/tesseract/wiki).
2. Run the installer and ensure it installs to the default directory: `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. Macro Studio will automatically detect it from this location!

---

## 📦 Installation Options

### Option 1: Install via pip (The Intended Way)

```bash
pip install macro-studio

```

### Option 2: Install Standalone Executable (Windows)

If you prefer not to use Python environments, you can download the latest pre-compiled `.exe` from the [GitHub Releases page](https://github.com/theeman05/MacroStudio/releases).

1. Download the `MacroStudio-Win64.zip` file.
2. Extract the ZIP folder.
3. Double-click `MacroStudio.exe` to launch.
4. *(Note: You still need to install Tesseract OCR separately if you plan to use text-reading features!)*

## 🔗 Links

* **Source Code:** https://github.com/theeman05/MacroStudio
* **Issue Tracker:** https://github.com/theeman05/MacroStudio/issues