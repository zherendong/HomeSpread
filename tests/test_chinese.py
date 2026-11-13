"""Chinese catalog coverage and startup preferences; no connected device required."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import re
from string import Formatter
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipsm import i18n
from ipsm.translations_en import TRANSLATIONS as ENGLISH
from ipsm.translations_zh import TRANSLATIONS as CHINESE


def translation_keys() -> set[str]:
    keys: set[str] = set()
    for path in (ROOT / "src" / "ipsm").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in {"tr", "defer", "_"}:
                argument = node.args[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    keys.add(argument.value)
    return keys


class ChineseCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = i18n.language()

    def tearDown(self) -> None:
        i18n.set_language(self.previous)

    def test_every_source_message_and_english_entry_has_chinese(self) -> None:
        self.assertEqual(set(), (translation_keys() | set(ENGLISH)) - set(CHINESE))

    def test_translations_preserve_format_fields(self) -> None:
        def fields(text: str) -> Counter:
            return Counter(
                (field, spec, conversion)
                for _, field, spec, conversion in Formatter().parse(text)
                if field is not None
            )

        for key, value in CHINESE.items():
            with self.subTest(key=key):
                self.assertEqual(fields(key), fields(value))
                # Diagnostic CLI logging uses %-style formatting.
                self.assertEqual(re.findall(r"%[sd]", key), re.findall(r"%[sd]", value))
                self.assertTrue(value.strip())
                self.assertIsNone(re.search(r"[\uac00-\ud7af]", value))

    def test_first_launch_is_chinese_even_on_english_mac(self) -> None:
        with patch.object(i18n, "load_settings", return_value={}):
            with patch.object(i18n, "system_language", return_value="en"):
                self.assertEqual("zh_CN", i18n.start())
        self.assertEqual("从设备读取", i18n.tr("기기에서 읽기"))
        self.assertEqual("应用修改", i18n.tr("적용"))

    def test_explicit_and_saved_preferences_are_preserved(self) -> None:
        with patch.object(i18n, "load_settings", return_value={"language": "en"}):
            self.assertEqual("en", i18n.start())
            self.assertEqual("ko", i18n.start("ko"))
            self.assertEqual("zh_CN", i18n.start("zh_CN"))
        for invalid in ("invalid", ["en"], {"code": "en"}, 7):
            with patch.object(i18n, "load_settings", return_value={"language": invalid}):
                self.assertEqual("zh_CN", i18n.start())

    def test_chinese_preference_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(i18n, "settings_path", return_value=Path(directory) / "settings.json"):
                i18n.choose("zh_CN")
                i18n.set_language("en")
                self.assertEqual("zh_CN", i18n.start())
                self.assertEqual("备份并应用", i18n.tr("백업하고 적용"))

    def test_chinese_locale_variants(self) -> None:
        for locale in ("zh_CN", "zh-Hans-CN", "zh_TW", "Chinese_China"):
            with self.subTest(locale=locale):
                with patch.object(i18n.locale, "getlocale", return_value=(locale, "UTF-8")):
                    self.assertEqual("zh_CN", i18n.system_language())


if __name__ == "__main__":
    unittest.main()
