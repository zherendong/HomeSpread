"""세션 진단 로그 (REQ-004).

실기기 연결 세션에서 무슨 일이 있었는지 사후에 재구성할 수 있게 만드는 것이 목적이다.
문제 신고와 개선점 발굴의 유일한 근거이므로, 로그는 덮어쓰지 않고 세션마다 새로 만든다.

기록 위치:
    logs/{이름}_{YYYYMMDD_HHMMSS}.log        사람이 읽는 로그
    logs/{이름}_{YYYYMMDD_HHMMSS}/           같은 세션의 원본 산출물 (iconState 등)

원본 iconState는 크고 반복적이라 로그 본문에 넣으면 로그를 못 읽게 된다.
별도 파일로 저장하고 로그에는 경로와 요약만 남긴다.

**산출물 폴더는 실제로 넣을 것이 생길 때 만든다.** 미리 만들어 두면 기기에 한 번도
닿지 않고 끝난 실행마다 빈 폴더가 하나씩 쌓여, 정작 내용이 든 폴더를 찾을 수 없게
된다. 폴더가 있다는 것 자체가 "이 세션은 기기에서 무언가를 받아 왔다"는 표시다.

**오래된 세션은 스스로 지운다** (`KEEP_SESSIONS`). 세션마다 새 파일을 만드는 이유는
문제 신고 하나가 실행 하나에 대응해야 하기 때문이지, 영원히 쌓으려는 것이 아니다.
"""

from __future__ import annotations

import io
import json
import logging
import platform
import plistlib
import re
import shutil
import sys
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from .safeio import atomic_private_write, private_directory

_LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FORMAT = "%H:%M:%S"

_session: Optional["Session"] = None

#: 남겨 둘 세션 수. 문제 신고는 대개 방금 일어난 일이라 오래된 기록은 자리만 차지한다.
#: 그렇다고 한 벌만 남기면 "어제는 됐는데"를 대조할 수 없어, 며칠치가 남을 만큼만 둔다.
KEEP_SESSIONS = 20

#: 우리가 만든 세션 기록만 골라내는 자물쇠. 사용자가 `logs/` 에 따로 둔 파일은
#: 이 모양을 갖지 않으므로 정리 대상이 되지 않는다 — 남의 파일을 지우면 안 된다.
_SESSION_STEM = re.compile(r"^[A-Za-z0-9_-]+_(\d{8}_\d{6})(?:_\d{6}_[a-f0-9]{12})?$")


def prune_sessions(log_dir: Path, keep: int = KEEP_SESSIONS) -> int:
    """오래된 세션 기록(로그·산출물 폴더·보고서 zip)을 지운다.

    지우는 것은 되돌릴 수 없으므로 범위를 좁게 잡는다: `logs/` 안에서, 우리가 지은
    이름 모양(`{이름}_{날짜}_{시각}`)에 맞는 것만, 최신 `keep` 개를 뺀 나머지만.
    지우다 실패해도 예외를 올리지 않는다 — 로그 정리 때문에 앱이 못 뜨는 것이
    가장 나쁜 결말이다.
    """
    log = logging.getLogger("session")
    stems = sorted(
        {path.stem for path in log_dir.glob("*.log") if _SESSION_STEM.match(path.stem)},
        key=lambda stem: (_SESSION_STEM.match(stem).group(1), stem),
    )  # 이름 끝에 날짜·시각이 붙어 있어 이름순 = 시간순이다
    if len(stems) <= keep:
        return 0

    removed = 0
    for stem in stems[: len(stems) - keep]:
        for target in (log_dir / f"{stem}.log", log_dir / stem, log_dir / f"{stem}_report.zip"):
            try:
                if target.is_symlink():
                    continue
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                else:
                    continue
                removed += 1
            except OSError as exc:  # 사용 중인 파일 등 — 다음 실행에서 다시 시도한다
                log.debug("오래된 기록을 지우지 못했다: %s (%s)", target.name, exc)
    if removed:
        log.debug("오래된 세션 기록 %d개 정리 (최근 %d개는 남긴다)", removed, keep)
    return removed


def mask(value: Optional[str], keep: int = 4) -> str:
    """UDID 같은 식별자를 앞 몇 글자만 남기고 가린다 (REQ-004).

    로그는 문제 신고용으로 공유될 수 있다. 진단에 필요한 것은 '같은 기기인가'뿐이므로
    앞자리만 남기면 충분하다. 전체 값은 어디에도 남기지 않는다.
    """
    if not value:
        return "(없음)"
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return text[:keep] + "*" * (len(text) - keep)


def _console_supports(sample: str) -> bool:
    """이 콘솔이 해당 글자를 출력할 수 있는지 확인한다.

    한국어 Windows 콘솔의 기본 코드페이지(cp949)에는 체크표시 같은 기호가 없다.
    진단 도구가 기호 하나 때문에 UnicodeEncodeError 로 죽는 것은 최악의 실패다 —
    정작 알아야 할 원인이 그 예외에 묻힌다. 그래서 출력 전에 미리 확인한다.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        sample.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


# 콘솔이 감당하는 기호만 고른다. 파일 로그는 UTF-8이므로 원래 기호가 그대로 남는다.
_FANCY = _console_supports("✔✗ⓘ⚠")

MARK_START = "▶" if _console_supports("▶") else ">"
MARK_OK = "✔" if _FANCY else "[OK]"
MARK_FAIL = "✗" if _FANCY else "[FAIL]"
MARK_INFO = "ⓘ" if _FANCY else "[i]"
MARK_WARN = "⚠" if _FANCY else "[!]"
RULE_CHAR = "─" if _console_supports("─") else "-"
DASH = "—" if _console_supports("—") else "-"

# iPhone UDID 형태: 00008110-XXXXXXXXXXXXXXXX (신형) 또는 40자리 16진수 (구형).
# 우리가 직접 남기는 값은 mask() 를 거치지만, 라이브러리 예외 메시지와 스택트레이스에는
# 원본이 그대로 실려 온다. 사용자가 로그를 공유할 수 있으므로 출력 직전에 한 번 더 지운다.
_UDID_PATTERNS = (
    # 신형: 8자리-16자리. 구분자 "-" 는 남겨야 로그에서 형태를 알아볼 수 있다.
    re.compile(r"\b([0-9A-Fa-f]{4})([0-9A-Fa-f]{4}-[0-9A-Fa-f]{16})\b"),
    # usbmuxd can omit the hyphen on current devices.
    re.compile(r"\b([0-9A-Fa-f]{4})([0-9A-Fa-f]{20})\b"),
    # 구형: 40자리 연속 16진수
    re.compile(r"\b([0-9A-Fa-f]{4})([0-9A-Fa-f]{36})\b"),
)


def _redact(text: str) -> str:
    for pattern in _UDID_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "*" * len(m.group(2)), text)
    return text


class _SafeFormatter(logging.Formatter):
    """UDID를 지운 뒤 내보낸다.

    필터가 아니라 포매터에 두는 이유: 필터는 메시지만 볼 수 있고, UDID는 대부분
    라이브러리 예외의 스택트레이스에 실려 온다. 포매터는 트레이스백까지 붙인
    최종 문자열을 다루므로 새는 곳이 없다.
    """

    def format(self, record: logging.LogRecord) -> str:
        return _redact(super().format(record))


class _ConsoleFormatter(_SafeFormatter):
    """콘솔용 — 스택트레이스를 붙이지 않는다.

    사용자에게 필요한 것은 '무엇을 해야 하는가'이지 Python 호출 스택이 아니다.
    트레이스백이 화면을 덮으면 정작 그 아래 안내 문구를 놓친다.
    추적 정보는 파일 로그에 온전히 남으므로 잃는 것은 없다.
    """

    def format(self, record: logging.LogRecord) -> str:
        saved_exc, saved_text = record.exc_info, record.exc_text
        record.exc_info, record.exc_text = None, None
        try:
            return super().format(record)
        finally:
            record.exc_info, record.exc_text = saved_exc, saved_text


class Session:
    """하나의 실행 = 하나의 세션 = 하나의 로그 파일 + 하나의 산출물 폴더."""

    def __init__(self, root: Path, name: Optional[str] = None) -> None:
        self.started_at = datetime.now()
        stamp = self.started_at.strftime("%Y%m%d_%H%M%S_%f")
        name = name or "session"
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Invalid session name")
        self.id = f"{name}_{stamp}_{uuid.uuid4().hex[:12]}"

        self.log_dir = root / "logs"
        private_directory(self.log_dir)
        self.log_path = self.log_dir / f"{self.id}.log"
        atomic_private_write(self.log_path, b"")
        # 만들지 않는다 — `save_artifact()` 가 넣을 것이 생겼을 때 만든다.
        self.artifact_dir = self.log_dir / self.id

        self._install_handlers()
        self._log_environment()
        prune_sessions(self.log_dir)

    # ------------------------------------------------------------------ setup

    def _install_handlers(self) -> None:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            # 닫아 준다. 떼어내기만 하면 앞 세션의 로그 파일이 열린 채로 남아,
            # 정리하려는 쪽(오래된 기록 정리·임시 폴더 삭제)이 막힌다.
            try:
                handler.close()
            except Exception:  # pragma: no cover - 이미 닫힌 핸들러 등
                pass

        # 파일에는 전부 남긴다. 사후 분석에서 무엇이 필요할지 미리 알 수 없다.
        file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_SafeFormatter(_LOG_FORMAT, _DATE_FORMAT))
        root_logger.addHandler(file_handler)

        # 화면에는 사용자가 따라갈 수 있는 수준만.
        # 마지막 방어선: 예상 못 한 글자가 섞여도 로깅이 죽지 않게 한다.
        # (기호는 위에서 이미 낮췄지만, 기기가 보내는 앱 이름에 무엇이 들어올지는 모른다)
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:  # pragma: no cover - 재설정 불가한 스트림
            pass
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(_ConsoleFormatter("%(message)s"))
        root_logger.addHandler(console)


        # 라이브러리 내부 로그는 파일에만 (INFO 이상은 화면에도 나오면 시끄럽다).
        # Pairing/session internals are not needed for ordinary diagnostics.
        logging.getLogger("pymobiledevice3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("zeroconf").setLevel(logging.WARNING)

    def _log_environment(self) -> None:
        log = logging.getLogger("session")
        log.debug("=" * 70)
        log.debug("session id      : %s", self.id)
        log.debug("started at      : %s", self.started_at.isoformat())
        log.debug("log file        : %s", self.log_path)
        # 아직 없는 자리다. 기기에서 무언가를 받아 오면 그때 만들어진다.
        log.debug("artifact dir    : %s (필요할 때 만든다)", self.artifact_dir)
        log.debug("platform        : %s", platform.platform())
        log.debug("python          : %s", sys.version.replace("\n", " "))
        try:
            from importlib.metadata import version

            log.debug("pymobiledevice3 : %s", version("pymobiledevice3"))
        except Exception as exc:  # pragma: no cover - 진단 정보일 뿐
            log.debug("pymobiledevice3 : 버전 확인 실패 (%s)", exc)
        log.debug("=" * 70)

    # -------------------------------------------------------------- artifacts

    def save_artifact(self, name: str, data: Any, *, fmt: str = "json") -> Path:
        """원본 데이터를 파일로 보존하고 경로를 로그에 남긴다.

        iconState 같은 원본은 나중에 형식 해석이 틀렸다고 밝혀져도 다시 파싱할 수 있어야
        한다. 그래서 해석 결과가 아니라 받은 그대로를 저장한다.
        """
        log = logging.getLogger("session")
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError("Invalid artifact name")
        private_directory(self.artifact_dir)
        if fmt == "plist":
            path = self.artifact_dir / f"{name}.plist"
            # 이진 형식. XML plist 는 날짜의 소수점 이하를 버리므로 '원본 그대로'가 되지 못한다.
            atomic_private_write(path, plistlib.dumps(data, fmt=plistlib.FMT_BINARY), replace=True)
        elif fmt == "bytes":
            path = self.artifact_dir / name
            atomic_private_write(path, data, replace=True)
        else:
            path = self.artifact_dir / f"{name}.json"
            atomic_private_write(path, json.dumps(
                data, indent=2, ensure_ascii=False, default=str
            ).encode("utf-8"), replace=True)
        log.debug("artifact 저장: %s (%d bytes)", path.name, path.stat().st_size)
        return path

    # ---------------------------------------------------------------- export

    def export_zip(self, dest: Optional[Path] = None) -> Path:
        """세션 하나를 통째로 zip으로 묶는다. 문제 신고용."""
        log = logging.getLogger("session")
        for handler in logging.getLogger().handlers:
            handler.flush()

        dest = dest or (self.log_dir / f"{self.id}_report.zip")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(self.log_path, self.log_path.name)
            items = sorted(self.artifact_dir.rglob("*")) if self.artifact_dir.exists() else []
            for item in items:
                if item.is_file() and not item.is_symlink():
                    zf.write(item, f"{self.id}/{item.relative_to(self.artifact_dir)}")
        atomic_private_write(dest, output.getvalue(), replace=True)
        log.info("진단 보고서 생성: %s", dest)
        return dest


def start_session(root: Path, name: Optional[str] = None) -> Session:
    global _session
    _session = Session(root, name)
    return _session


def current_session() -> Session:
    if _session is None:
        raise RuntimeError("세션이 시작되지 않았다. start_session()을 먼저 호출하라.")
    return _session


@contextmanager
def step(logger: logging.Logger, description: str) -> Iterator[dict]:
    """하나의 동작을 시작·소요시간·결과와 함께 기록한다.

    실기기 문제는 대부분 '어느 단계에서 얼마나 걸리다 무엇으로 실패했는가'로 좁혀진다.
    예외는 스택트레이스 전체를 남기고 그대로 다시 던진다 — 로그가 삼키면 안 된다.
    """
    context: dict = {}
    logger.info("%s %s", MARK_START, description)
    started = time.perf_counter()
    try:
        yield context
    except Exception:
        elapsed = (time.perf_counter() - started) * 1000
        logger.exception("%s %s %s 실패 (%.0f ms)", MARK_FAIL, description, DASH, elapsed)
        raise
    else:
        elapsed = (time.perf_counter() - started) * 1000
        detail = f" {DASH} {context['result']}" if "result" in context else ""
        logger.info("%s %s (%.0f ms)%s", MARK_OK, description, elapsed, detail)
