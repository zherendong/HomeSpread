"""화면에 보이는 말을 한 곳에서 고른다.

원문은 한국어다. `tr()` 은 지금 언어의 사전에서 찾고, 없으면 **원문을 그대로**
돌려준다 — 번역이 빠져도 앱이 말을 잃지 않는다. 빈칸이 뜨는 것보다 한국어가 뜨는
편이 낫다. 빠뜨린 것은 사람 눈이 아니라 시험이 잡는다 (`tests/test_core.py` 의
`test_every_translatable_string_has_an_english_entry`).

**로그는 번역하지 않는다.** 로그는 우리가 읽는 것이고, 언어가 섞이면 같은 사건을
검색으로 모을 수 없다.

값이 들어가는 문장은 `tr("...{n}개").format(n=...)` 로 쓴다. 완성된 문장을 열쇠로
삼으면 숫자마다 다른 열쇠가 되어 사전이 끝없이 늘어난다.
"""

from __future__ import annotations

import json
import locale
from pathlib import Path
from typing import Callable, Optional

#: 고를 수 있는 언어. 값은 **그 언어로 쓴** 이름이다 — 목록에서 자기 말을 찾을 수
#: 있어야 하고, 지금 언어가 무엇이든 그것은 변하지 않는다.
LANGUAGES: dict[str, str] = {"zh_CN": "简体中文", "en": "English", "ko": "한국어"}

DEFAULT_LANGUAGE = "zh_CN"

# Pure model callers use the source language until the application calls start().
# This Chinese edition starts in Chinese regardless of the Mac's system language.
_current = "ko"
_catalog: dict[str, str] = {}
_listeners: list[Callable[[], None]] = []


def language() -> str:
    return _current


def tr(text: str) -> str:
    """이 문구를 지금 언어로. 사전에 없으면 원문 그대로."""
    return _catalog.get(text, text)


#: 짧은 이름. 문장 안에서 `_("...")` 로 쓰면 원문이 눈에 그대로 남는다.
_ = tr


def defer(text: str) -> str:
    """지금은 옮기지 말고 원문 그대로 두라는 표시. 쓰는 자리에서 `tr()` 로 옮긴다.

    모듈 맨 바깥의 표에 `tr()` 을 적으면 **불러올 때 한 번** 옮겨지고 그대로 굳는다.
    그 뒤로 언어를 바꿔도 그 표만 옛 말로 남는데, 하필 그런 표는 기기 오류 안내처럼
    평소에 안 보이는 것이라 한참 뒤에야 드러난다. 그래서 표에는 이 표시를 적는다 —
    번역 열쇠로는 세어지되, 옮기는 일은 쓰는 순간으로 미뤄진다.
    """
    return text


def set_language(code: str) -> None:
    """언어를 바꾸고, 화면들에게 다시 그리라고 알린다."""
    global _current, _catalog
    if not isinstance(code, str) or code not in LANGUAGES:
        raise ValueError(f"모르는 언어입니다: {code}")
    _current = code
    _catalog = _load_catalog(code)
    for listener in list(_listeners):
        listener()


def on_language_changed(callback: Callable[[], None]) -> None:
    """언어가 바뀌면 불러 달라. 창이 스스로 다시 그리기 위해 쓴다."""
    _listeners.append(callback)


def off_language_changed(callback: Callable[[], None]) -> None:
    """닫은 창은 명단에서 뺀다.

    빼지 않으면 Qt 쪽이 이미 지워진 창을 다시 그리려다 터진다. 창이 하나뿐인
    지금은 잘 드러나지 않지만, 그런 종류일수록 나중에 엉뚱한 곳에서 나타난다.
    """
    if callback in _listeners:
        _listeners.remove(callback)


def _load_catalog(code: str) -> dict[str, str]:
    if code == "zh_CN":
        from .translations_zh import TRANSLATIONS

        return TRANSLATIONS
    if code == "en":
        from .translations_en import TRANSLATIONS

        return TRANSLATIONS
    return {}


# --------------------------------------------------------------- 저장과 시작

def settings_path() -> Path:
    """설정 파일 자리. 자료 폴더 안이라 exe 를 옮겨도 함께 따라간다."""
    from .paths import data_root

    return data_root() / "settings.json"


def load_settings() -> dict:
    """저장된 설정. 읽을 수 없으면 빈 것으로 친다 — 설정 하나 때문에 앱이 안 뜨면 안 된다."""
    try:
        with settings_path().open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(values: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(values, handle, ensure_ascii=False, indent=2)


def system_language() -> str:
    """Map the system locale to a supported language, including Chinese locales."""
    try:
        tag = locale.getlocale()[0] or ""
    except (ValueError, TypeError):  # 드물게 지역 설정이 깨진 PC 가 있다
        tag = ""
    normalized = tag.replace("-", "_").lower()
    if normalized.startswith("zh") or "chinese" in normalized:
        return "zh_CN"
    if normalized.startswith("ko") or "korean" in normalized:
        return "ko"
    return "en"


def start(preferred: Optional[str] = None) -> str:
    """Use an explicit preference, saved choice, or this edition's Chinese default."""
    code = preferred or load_settings().get("language") or DEFAULT_LANGUAGE
    if not isinstance(code, str) or code not in LANGUAGES:
        code = DEFAULT_LANGUAGE
    set_language(code)
    return code


def choose(code: str) -> None:
    """사용자가 고른 언어. 저장까지 한다 — 다음에 켤 때도 같아야 한다."""
    set_language(code)
    values = load_settings()
    values["language"] = code
    save_settings(values)
