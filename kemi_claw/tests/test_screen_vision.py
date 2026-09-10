import asyncio
from types import SimpleNamespace
from unittest.mock import patch


def test_find_text_returns_center_from_ocr():
    from kemi_claw.tools import computer_control as cc

    async def fake_ocr_screen(*args, **kwargs):
        return {"items": [{"text": "Open", "confidence": 91.0, "x": 100, "y": 200, "width": 80, "height": 30}], "ok": True}

    with patch.object(cc, "ocr_screen", side_effect=fake_ocr_screen):
        result = asyncio.run(cc.find_text("open"))
    assert result["found"] is True
    assert (result["x"], result["y"]) == (140, 215)


def test_click_text_uses_detected_center():
    from kemi_claw.tools import computer_control as cc

    async def fake_find_text(*args, **kwargs):
        return {"found": True, "x": 20, "y": 30, "query": "Save", "ok": True}

    async def fake_click(x, y, button="left", clicks=1):
        return {"x": x, "y": y, "button": button, "ok": True}

    with patch.object(cc, "find_text", side_effect=fake_find_text), patch.object(cc, "mouse_click", side_effect=fake_click):
        result = asyncio.run(cc.click_text("Save"))
    assert result["ok"] is True
    assert result["click"]["x"] == 20
    assert result["click"]["y"] == 30
