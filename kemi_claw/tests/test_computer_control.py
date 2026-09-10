import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, patch


def test_keyboard_type_uses_clipboard_for_unicode():
    from kemi_claw.tools import computer_control as cc

    fake_pyautogui = SimpleNamespace(
        PAUSE=0,
        write=Mock(),
        hotkey=Mock(),
    )
    fake_clipboard = SimpleNamespace(copy=Mock())

    with patch.object(cc, "_pyautogui", return_value=fake_pyautogui), patch.dict("sys.modules", {"pyperclip": fake_clipboard}):
        result = asyncio.run(cc.keyboard_type("مرحبا", 0))

    assert result["ok"] is True
    assert result["mode"] == "clipboard-paste"
    fake_clipboard.copy.assert_called_once_with("مرحبا")
    fake_pyautogui.hotkey.assert_called_once()
    fake_pyautogui.write.assert_not_called()


def test_mouse_click_rejects_invalid_button():
    from kemi_claw.tools.computer_control import mouse_click

    result = asyncio.run(mouse_click(button="bad"))
    assert result["error"]


def test_linux_window_action_builds_correct_wmctrl_command():
    from kemi_claw.tools import computer_control as cc

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_create(*args, **kwargs):
        assert args == ("wmctrl", "-r", "Terminal", "-b", "add,maximized_vert,maximized_horz")
        return FakeProc()

    with patch.object(cc.platform, "system", return_value="Linux"), patch.object(cc.shutil, "which", return_value="/usr/bin/wmctrl"), patch.object(cc.asyncio, "create_subprocess_exec", side_effect=fake_create):
        result = asyncio.run(cc.window_action("maximize", "Terminal"))

    assert result["ok"] is True
