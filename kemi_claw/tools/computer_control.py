"""Cross-platform desktop computer control.

GUI dependencies are imported lazily so headless CI and server deployments still work.
The primitives cover screenshots, pointer/keyboard input, hotkeys, application launch,
and basic window inspection/control where the host exposes it.
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
        raise RuntimeError("GUI control requires the optional 'computer' dependency (pyautogui).") from exc
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


async def mouse_move(x: int, y: int, duration: float = 0.15) -> dict[str, Any]:
    await asyncio.to_thread(_pyautogui().moveTo, int(x), int(y), max(0.0, float(duration)))
    return {"x": int(x), "y": int(y), "ok": True}


async def mouse_click(x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1) -> dict[str, Any]:
    pyautogui = _pyautogui()
    if x is not None and y is not None:
        await asyncio.to_thread(pyautogui.click, int(x), int(y), clicks=max(1, int(clicks)), button=button)
    else:
        await asyncio.to_thread(pyautogui.click, clicks=max(1, int(clicks)), button=button)
    return {"x": x, "y": y, "button": button, "clicks": int(clicks), "ok": True}


async def mouse_drag(x: int, y: int, duration: float = 0.3, button: str = "left") -> dict[str, Any]:
    await asyncio.to_thread(_pyautogui().dragTo, int(x), int(y), max(0.0, float(duration)), button=button)
    return {"x": int(x), "y": int(y), "button": button, "ok": True}


async def mouse_scroll(clicks: int, x: int | None = None, y: int | None = None) -> dict[str, Any]:
    pyautogui = _pyautogui()
    if x is not None and y is not None:
        await asyncio.to_thread(pyautogui.moveTo, int(x), int(y), 0)
    await asyncio.to_thread(pyautogui.scroll, int(clicks))
    return {"clicks": int(clicks), "x": x, "y": y, "ok": True}


async def keyboard_type(text: str, interval: float = 0.01) -> dict[str, Any]:
    await asyncio.to_thread(_pyautogui().write, str(text), interval=max(0.0, float(interval)))
    return {"characters": len(str(text)), "ok": True}


async def keyboard_press(key: str) -> dict[str, Any]:
    await asyncio.to_thread(_pyautogui().press, str(key))
    return {"key": str(key), "ok": True}


async def keyboard_hotkey(keys: list[str]) -> dict[str, Any]:
    if not keys:
        return {"error": "keys must not be empty"}
    await asyncio.to_thread(_pyautogui().hotkey, *[str(k) for k in keys])
    return {"keys": [str(k) for k in keys], "ok": True}


async def screen_size() -> dict[str, Any]:
    size = await asyncio.to_thread(_pyautogui().size)
    return {"width": int(size.width), "height": int(size.height)}


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
            if shutil.which("xdotool"):
                proc = await asyncio.create_subprocess_exec("xdotool", "getactivewindow", "getwindowname", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            else:
                return {"title": "", "supported": False, "note": "install xdotool for active-window metadata", "ok": True}
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode:
            return {"error": stderr.decode(errors="replace")[:500]}
        return {"title": stdout.decode(errors="replace").strip(), "ok": True}
    except ImportError:
        return {"supported": False, "note": "install pygetwindow for Windows window metadata", "ok": True}
    except Exception as exc:
        return {"error": str(exc)}


async def window_action(action: str, title: str = "") -> dict[str, Any]:
    """Focus/minimize/maximize/close a window by title where supported."""
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
            await asyncio.to_thread(getattr(win, {"focus": "activate", "minimize": "minimize", "maximize": "maximize", "restore": "restore", "close": "close"}[action]))
            return {"title": getattr(win, "title", title), "action": action, "ok": True}
        if system == "Linux" and shutil.which("wmctrl"):
            commands = {"focus": ["-a"], "minimize": ["-r", title, "-b", "add,hidden"], "maximize": ["-r", title, "-b", "add,maximized_vert,maximized_horz"], "restore": ["-r", title, "-b", "remove,hidden"], "close": ["-c"]}
            cmd = ["wmctrl", *commands[action]]
            if action in {"focus", "minimize", "maximize", "restore"} and action != "focus":
                cmd.insert(1, title)
            elif action == "close":
                cmd.append(title)
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            return {"action": action, "stdout": stdout.decode(errors="replace"), "error": stderr.decode(errors="replace") or None, "ok": proc.returncode == 0}
        return {"supported": False, "action": action, "note": "window control is not available on this host"}
    except ImportError:
        return {"supported": False, "note": "install pygetwindow for Windows window control"}
    except Exception as exc:
        return {"error": str(exc)}
