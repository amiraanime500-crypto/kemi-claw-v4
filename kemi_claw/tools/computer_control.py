"""Cross-platform desktop computer control.

GUI dependencies are imported lazily so headless CI and server deployments still work.
The primitives cover screenshots, pointer/keyboard input, hotkeys, clipboard text,
application launch, and basic window inspection/control where the host exposes it.
"""
from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from typing import Any


def _pyautogui():
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("GUI control requires the desktop dependencies (pyautogui).") from exc
    pyautogui.PAUSE = 0.05
    return pyautogui


def _screenshot_path(path: str | None) -> str:
    if path:
        return os.path.abspath(os.path.expanduser(path))
    root = os.path.join(os.getcwd(), ".kemi", "screenshots")
    os.makedirs(root, exist_ok=True)
    import time
    return os.path.join(root, f"screen-{int(time.time() * 1000)}.png")


async def screen_capture(path: str | None = None) -> dict[str, Any]:
    """Capture the current desktop and save it as a PNG."""
    target = _screenshot_path(path)
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    image = await asyncio.to_thread(_pyautogui().screenshot)
    await asyncio.to_thread(image.save, target)
    return {"path": target, "width": image.width, "height": image.height, "ok": True}


async def screen_size() -> dict[str, Any]:
    size = await asyncio.to_thread(_pyautogui().size)
    return {"width": int(size.width), "height": int(size.height)}


async def mouse_position() -> dict[str, Any]:
    point = await asyncio.to_thread(_pyautogui().position)
    return {"x": int(point.x), "y": int(point.y), "ok": True}


async def mouse_move(x: int, y: int, duration: float = 0.15) -> dict[str, Any]:
    await asyncio.to_thread(_pyautogui().moveTo, int(x), int(y), max(0.0, float(duration)))
    return {"x": int(x), "y": int(y), "ok": True}


async def mouse_click(x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1) -> dict[str, Any]:
    button = str(button).lower()
    if button not in {"left", "middle", "right"}:
        return {"error": "button must be left, middle, or right"}
    pyautogui = _pyautogui()
    if x is not None and y is not None:
        await asyncio.to_thread(pyautogui.click, int(x), int(y), clicks=max(1, int(clicks)), button=button)
    else:
        await asyncio.to_thread(pyautogui.click, clicks=max(1, int(clicks)), button=button)
    return {"x": x, "y": y, "button": button, "clicks": max(1, int(clicks)), "ok": True}


async def mouse_drag(x: int, y: int, duration: float = 0.3, button: str = "left") -> dict[str, Any]:
    button = str(button).lower()
    if button not in {"left", "middle", "right"}:
        return {"error": "button must be left, middle, or right"}
    await asyncio.to_thread(_pyautogui().dragTo, int(x), int(y), max(0.0, float(duration)), button=button)
    return {"x": int(x), "y": int(y), "button": button, "ok": True}


async def mouse_scroll(clicks: int, x: int | None = None, y: int | None = None) -> dict[str, Any]:
    pyautogui = _pyautogui()
    if x is not None and y is not None:
        await asyncio.to_thread(pyautogui.moveTo, int(x), int(y), 0)
    await asyncio.to_thread(pyautogui.scroll, int(clicks))
    return {"clicks": int(clicks), "x": x, "y": y, "ok": True}


async def clipboard_set(text: str) -> dict[str, Any]:
    try:
        import pyperclip
        await asyncio.to_thread(pyperclip.copy, str(text))
        return {"characters": len(str(text)), "ok": True}
    except Exception as exc:
        return {"error": f"clipboard unavailable: {exc}"}


async def clipboard_get() -> dict[str, Any]:
    try:
        import pyperclip
        text = await asyncio.to_thread(pyperclip.paste)
        return {"text": str(text), "characters": len(str(text)), "ok": True}
    except Exception as exc:
        return {"error": f"clipboard unavailable: {exc}"}


async def keyboard_type(text: str, interval: float = 0.01) -> dict[str, Any]:
    text = str(text)
    try:
        pyautogui = _pyautogui()
        if text.isascii():
            await asyncio.to_thread(pyautogui.write, text, interval=max(0.0, float(interval)))
            return {"characters": len(text), "mode": "direct", "ok": True}
        import pyperclip
        await asyncio.to_thread(pyperclip.copy, text)
        modifier = "command" if platform.system() == "Darwin" else "ctrl"
        await asyncio.to_thread(pyautogui.hotkey, modifier, "v")
        return {"characters": len(text), "mode": "clipboard-paste", "ok": True}
    except Exception as exc:
        return {"error": f"keyboard input failed: {exc}"}


async def keyboard_press(key: str) -> dict[str, Any]:
    await asyncio.to_thread(_pyautogui().press, str(key))
    return {"key": str(key), "ok": True}


async def keyboard_hotkey(keys: list[str]) -> dict[str, Any]:
    if not keys:
        return {"error": "keys must not be empty"}
    await asyncio.to_thread(_pyautogui().hotkey, *[str(k) for k in keys])
    return {"keys": [str(k) for k in keys], "ok": True}


async def launch_app(command: str, args: list[str] | None = None) -> dict[str, Any]:
    """Launch a desktop application without waiting for it to exit."""
    command = str(command).strip()
    if not command:
        return {"error": "command is required"}
    argv = [command] + [str(x) for x in (args or [])]
    try:
        if platform.system() == "Windows":
            proc = await asyncio.to_thread(subprocess.Popen, argv, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        else:
            proc = await asyncio.to_thread(subprocess.Popen, argv, start_new_session=True)
        return {"pid": proc.pid, "command": argv, "ok": True}
    except FileNotFoundError:
        return {"error": f"application not found: {command}"}
    except Exception as exc:
        return {"error": str(exc)}


async def active_window() -> dict[str, Any]:
    """Return a best-effort description of the active window."""
    system = platform.system()
    try:
        if system == "Windows":
            import pygetwindow as gw
            win = await asyncio.to_thread(gw.getActiveWindow)
            return {"title": getattr(win, "title", "") if win else "", "ok": True}
        if system == "Darwin":
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        else:
            if not shutil.which("xdotool"):
                return {"title": "", "supported": False, "note": "install xdotool for active-window metadata", "ok": True}
            proc = await asyncio.create_subprocess_exec("xdotool", "getactivewindow", "getwindowname", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode:
            return {"error": stderr.decode(errors="replace")[:500]}
        return {"title": stdout.decode(errors="replace").strip(), "ok": True}
    except ImportError:
        return {"supported": False, "note": "install pygetwindow for Windows window metadata", "ok": True}
    except Exception as exc:
        return {"error": str(exc)}


async def list_windows() -> dict[str, Any]:
    """Best-effort list of visible windows on the host."""
    system = platform.system()
    try:
        if system == "Windows":
            import pygetwindow as gw
            windows = await asyncio.to_thread(gw.getAllWindows)
            return {"windows": [{"title": getattr(w, "title", ""), "x": getattr(w, "left", None), "y": getattr(w, "top", None), "width": getattr(w, "width", None), "height": getattr(w, "height", None)} for w in windows if getattr(w, "title", "")], "ok": True}
        if system == "Linux" and shutil.which("wmctrl"):
            proc = await asyncio.create_subprocess_exec("wmctrl", "-lG", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if proc.returncode:
                return {"error": stderr.decode(errors="replace")[:500]}
            windows = []
            for line in stdout.decode(errors="replace").splitlines():
                parts = line.split(None, 6)
                if len(parts) >= 7:
                    windows.append({"id": parts[0], "x": int(parts[2]), "y": int(parts[3]), "width": int(parts[4]), "height": int(parts[5]), "title": parts[6]})
            return {"windows": windows, "ok": True}
        return {"windows": [], "supported": False, "note": "window listing is not available on this host", "ok": True}
    except Exception as exc:
        return {"error": str(exc)}


async def window_action(action: str, title: str = "") -> dict[str, Any]:
    """Focus/minimize/maximize/restore/close a window by title where supported."""
    system = platform.system()
    action = str(action).lower()
    if action not in {"focus", "minimize", "maximize", "restore", "close"}:
        return {"error": "action must be focus, minimize, maximize, restore, or close"}
    try:
        if system == "Windows":
            import pygetwindow as gw
            matches = await asyncio.to_thread(gw.getWindowsWithTitle, title)
            if not matches:
                return {"error": f"window not found: {title}"}
            win = matches[0]
            method = {"focus": "activate", "minimize": "minimize", "maximize": "maximize", "restore": "restore", "close": "close"}[action]
            await asyncio.to_thread(getattr(win, method))
            return {"title": getattr(win, "title", title), "action": action, "ok": True}
        if system == "Linux" and shutil.which("wmctrl"):
            if action == "focus":
                cmd = ["wmctrl", "-a", title]
            elif action == "close":
                cmd = ["wmctrl", "-c", title]
            elif action == "minimize":
                cmd = ["wmctrl", "-r", title, "-b", "add,hidden"]
            elif action == "maximize":
                cmd = ["wmctrl", "-r", title, "-b", "add,maximized_vert,maximized_horz"]
            else:
                cmd = ["wmctrl", "-r", title, "-b", "remove,hidden"]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            return {"action": action, "stdout": stdout.decode(errors="replace"), "error": stderr.decode(errors="replace") or None, "ok": proc.returncode == 0}
        return {"supported": False, "action": action, "note": "window control is not available on this host", "ok": True}
    except ImportError:
        return {"supported": False, "note": "install pygetwindow for Windows window control", "ok": True}
    except Exception as exc:
        return {"error": str(exc)}
