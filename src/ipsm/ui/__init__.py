"""화면 계층. 이 아래에서만 Qt 를 안다 (ADR-001).

`layout.py`, `iconstate.py`, `device.py`, `backup.py`, `icons.py` 는 Qt 를 모른다.
그 경계가 지켜지는 한 UI 를 통째로 갈아치워도 안전 규약과 모델은 그대로 남는다.
"""
