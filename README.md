# Python Macro Studio

[![Documentation](https://img.shields.io/badge/docs-Zensical-blue.svg)](https://theeman05.github.io/MacroStudio/)
![License](https://img.shields.io/badge/license-GPLv3-blue.svg) 
![Python](https://img.shields.io/badge/python-3.10%2B-blue) 
![Status](https://img.shields.io/badge/status-Active%20Development-green) 
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-yellow.svg)](https://buymeacoffee.com/dbhs)

**Limitless automation, powered by Python.**

---

**Macro Studio** is a robust automation framework that bridges the gap between simple macro recorders and complex software development. Unlike traditional click-recorders, this engine allows you to script logic in pure Python, giving you access to the full power of the language—from computer vision (OpenCV) to API requests—while managing the lifecycle of your tasks through a sleek, user-friendly GUI.

## ⌨️ Code Example

Automating a simple click-loop is as easy as writing a Python generator:

```python
def checkHealth(controller):
    # Sample a pixel and react in sub-milliseconds
    if captureScreenColor(controller.getVar("health_bar_pt")) == COLORS.RED:
        # Hold the key for 1 second, guaranteeing its release
        with holdKey("q"):
            yield from taskSleep(1)
```

![Human Benchmark Gif](https://raw.githubusercontent.com/theeman05/MacroStudio/master/docs/assets/HumanBenchmark.gif)

👉 **[Watch the Showcase on YouTube](https://youtu.be/p550JDNzMPk)** 👈

![Task Manager UI](https://raw.githubusercontent.com/theeman05/MacroStudio/master/docs/assets/TaskManager.png)

---

## 📚 Official Documentation

**[Read the full documentation here!](https://theeman05.github.io/MacroStudio/)**

To keep this README clean, all tutorials, API references, and advanced guides have been moved to our official documentation site. Visit the link above to find:
* ⚙️ **Engine API & Task Controllers:** How to run, pause, and stop threaded Python tasks safely.
* 🖱️ **Actions Library:** Thread-safe mouse and keyboard simulators.
* 👁️ **Vision Library:** OpenCV and Tesseract OCR integration.
* 💡 **Runnable Examples:** Copy-pasteable scripts to jumpstart your development.

---

## 🚀 Key Features

* **♾️ Infinite Possibilities:** Other macro recorders give you a tricycle; we are handing you the keys to a Saturn V rocket. If you can code it in Python, you can automate it.
* **🎛️ Visual Task Manager:** Real-time, graphical interface for monitoring and controlling the execution flow of background threads.
* **📂 Profile & Variable Management:** Expose script variables directly to the GUI so users can tweak settings without touching your code.
* **🎥 Visual Task Recorder:** A built-in, no-code recorder that can export sequences directly into standalone Python scripts.

---

## 🧠 Why I Built Macro Studio

If you've ever tried to build a desktop bot in Python, you already know the pain points. 

Standard automation libraries rely on sluggish screen-grabbing methods, and managing concurrent tasks usually means fighting Python's Global Interpreter Lock (GIL). You end up with heavy OS threads, `time.sleep()` bottlenecks, and a macro that either stutters or completely freezes your computer. 

The alternative? Paying for expensive, clunky, closed-source macro recorders that haven't been updated in a decade and trap you in proprietary scripting languages. 

I wanted an engine that respected Python's capabilities. **Macro Studio was built to solve this by rethinking the architecture:**

* **Stackless Coroutines:** Instead of heavy OS threads, basic tasks use a generator-based `yield` architecture for cooperative multitasking. This allows the engine to pause, resume, and interrupt tasks in fractions of a millisecond without burning CPU cycles.
* **O(1) Memory Polling:** By bypassing artificial library delays and hooking directly into the Windows GDI via `mss`, pixel-scanning happens at raw hardware speed.
* **100% Python:** No proprietary syntax. If you can write Python, you can integrate APIs, AI, or custom computer vision straight into your macros.

I built Macro Studio to be the tool I wished I had, and I'm keeping it free and open-source so the community finally has a modern, high-performance automation framework.

---

## 📦 Installation

### Option 1: Install via pip (Recommended)
```bash
pip install macro-studio

```

### Option 2: Standalone Executable (Windows)

If you prefer not to use Python environments, you can download the latest pre-compiled `.exe` from the [GitHub Releases page](https://github.com/theeman05/MacroStudio/releases).

1. Download the `MacroStudio-Win64.zip` file.
2. Extract the ZIP folder.
3. Double-click `MacroStudio.exe` to launch.

*(Note: You must install [Tesseract OCR](https://github.com/tesseract-ocr/tessdoc) separately if you plan to use text-reading computer vision features!)*

---

## 🤝 Contributing & Support

Contributions are welcome! Whether you are fixing bugs, adding new features, or creating example tasks, I would love to see your work.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

If you find this studio helpful and want to support its development, consider buying me a coffee! It helps keep the updates coming.

<a href="https://buymeacoffee.com/dbhs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## 📄 License

Distributed under the **GNU GPLv3 License**. See `LICENSE` for more information.
*This means that if you modify and distribute this engine or build a product on top of it, you must keep it open-source.*