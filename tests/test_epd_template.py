#!/usr/bin/env python3
"""Test ЭПД template detection and prompt building."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generator import detect_template, _build_template_hint, EPD_TEMPLATE


def test_epd_template_keywords():
    """ЭПД-related descriptions should trigger 'epd' template."""
    epd_descriptions = [
        "эпд бот для грузоперевозок",
        "чек лист эпд для транспорта",
        "эдо перевозчики",
        "кэп трекер для водителей",
        "гослог регистрация",
        "переход на электронный документооборот",
        "1с-эпд интеграция",
        "диадок для транспортной компании",
        "астрал эдо",
        "сбис грузоперевозки",
    ]
    for desc in epd_descriptions:
        got = detect_template(desc)
        assert got == "epd", f"{desc!r} -> {got!r}, expected 'epd'"


def test_non_epd_templates_unchanged():
    """Other templates should still work."""
    assert detect_template("салон красоты бот") == "salon"
    assert detect_template("faq бот") == "faq"
    assert detect_template("бот записи") == "booking"
    assert detect_template("рассылка уведомлений") == "notification"
    assert detect_template("обычный бот") is None


def test_build_template_hint_epd():
    """EPD template hint should include key features."""
    hint = _build_template_hint("epd")
    assert "ЭПД" in hint
    assert "/start" in hint
    assert "/checklist" in hint
    assert "/kep" in hint
    assert "/deadline" in hint
    assert "/ready" in hint
    assert "/news" in hint
    assert "Sep 1, 2026" in hint
    assert "КЭП" in hint
    assert "Астрал" in hint or "Такском" in hint


def test_build_template_hint_salon():
    """SALON template hint should still work."""
    hint = _build_template_hint("salon")
    assert "YClients" in hint


def test_build_template_hint_none():
    """No template should return empty string."""
    assert _build_template_hint(None) == ""


if __name__ == "__main__":
    test_epd_template_keywords()
    test_non_epd_templates_unchanged()
    test_build_template_hint_epd()
    test_build_template_hint_salon()
    test_build_template_hint_none()
    print("All tests passed!")
