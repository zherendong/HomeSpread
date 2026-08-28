"""제품 이름과 후원 창구 — 선언 한 곳.

**이름과 부제를 나눠 두는 이유가 이 파일의 전부다.**

Apple 상표 지침은 자기 제품 **이름 안에** Apple 상표(`iOS`·`iPhone`)를 넣는 것을
금지하고, 호환성 표기는 이름 **아래의 부제**로만 허용한다. 스토어 심사에서 걸리는
자리도 정확히 "앱 이름" 칸이다. 그래서 이름(`NAME`)과 호환성 표기(`TAGLINE`)를
따로 두고, 스토어의 이름 칸에는 `NAME` 만 넣는다. 둘을 붙여 쓰는 곳은 창 제목이나
정보 창처럼 스토어 밖의 자리뿐이다.

후원 주소도 여기 있다. 창에서 주소를 짓지 않는 이유는 같다 — 창구가 바뀌었을 때
고칠 자리가 하나여야 하고, 주소가 제대로 만들어지는지는 창을 띄우지 않고도 시험할
수 있어야 한다.
"""

from __future__ import annotations

#: 스토어의 "앱 이름" 칸에 그대로 들어간다. Apple 상표를 넣지 않는다.
NAME = "HomeSpread"

#: 이름 아래에 붙는 부제. 여기서는 호환성 표기가 허용된다.
TAGLINE = "Mobile layout manager for iOS"

#: exe 에 새겨지는 저작권 줄. 소스 머리말과 같은 말이어야 하므로 여기서 한 번 짓는다.
COPYRIGHT = f"Copyright (C) 2026 {NAME} contributors"

#: exe 의 "회사 이름" 칸. 회사가 없는 GPL 프로젝트라 기여자를 그대로 적는다.
#:
#: **비워 두는 것이 가장 나쁘다.** 2026-08-26 에 Defender 가 우리 exe 를
#: `Trojan:Win32/Bearfoos.B!ml` 로 격리했다 — `!ml` 은 기계학습의 추정이고, 그 추정이
#: 나쁜 쪽으로 기우는 조건 중 하나가 **서명도 없고 버전 리소스도 비어 있는 실행 파일**
#: 이다. 서명은 스토어가 해 주지만 버전 리소스는 우리가 넣어야 한다. 이름을 대는 것은
#: 오탐을 줄이는 일이자, 받은 사람이 속성 창에서 이것이 무엇인지 볼 수 있게 하는 일이다.
PUBLISHER = f"{NAME} contributors"

#: 후원을 받는 GitHub 계정. 저장소를 가진 계정과 같은 것이어야 한다.
DONATE_ACCOUNT = "humanlyj"


def donate_url() -> str:
    """GitHub Sponsors 후원 주소.

    **처음에는 PayPal 이었고, 그것은 열리지 않았다(2026-08-28).** 받는 계정이 한국에
    등록돼 있으면 PayPal 은 `Donations aren't supported in this organization's country`
    로 막는다. 비즈니스 계정으로 올려도 풀리지 않고, 한국 계정은 애초에 국내 후원자
    에게서 받는 경로 자체가 없다. GitHub Sponsors 는 Stripe **Connect Express** 를
    쓰는데 그쪽은 한국을 받아 준다 — 실제로 계정을 열어 확인했다.

    주소는 손잡이 하나로 짓는다. 계정을 옮기는 날 고칠 자리가 `DONATE_ACCOUNT` 한
    줄이어야 하고, `.github/FUNDING.yml` 이 적는 것도 주소가 아니라 이 손잡이다.

    대신 알아 둘 것이 하나 있다 — **후원하려면 GitHub 계정이 필요하다.** 이 앱의
    사용자는 개발자가 아닐 수 있으므로, 단추에 어디로 가는지를 이름으로 적어 둔다.
    """
    return f"https://github.com/sponsors/{DONATE_ACCOUNT}"


#: 이 프로그램 전체의 라이선스. `pymobiledevice3` 가 GPL 이고 우리는 그것을 함께
#: 실어 배포하므로 선택의 여지가 없다 — 함께 묶어 내보내는 순간 전체가 GPL 이 된다.
LICENSE_SPDX = "GPL-3.0-or-later"

#: 소스를 받을 수 있는 곳. GPL 은 실행 파일을 건네준 사람에게 소스를 받을 길을
#: 함께 주기를 요구한다. 정보 창이 이 주소를 링크로 보여준다.
#: 저장소를 옮기면 여기부터 고친다 — 닿지 않는 주소는 없는 주소와 같고, GPL 아래에서
#: 그것은 의무 불이행이다. 2026-08-26 에 저장소를 `HomeBoard` 에서 옮겼다 — 이름을
#: 먼저 갈고 주소는 저장소가 실제로 옮겨진 뒤에 갈았다. 순서를 뒤집으면 그 사이에
#: 나간 판본이 없는 주소를 안내한다.
SOURCE_URL = "https://github.com/humanlyj/HomeSpread"

#: 개인정보 처리방침 원문의 주소. Partner Center 가 Win32 제품에 **언제나** 요구하는
#: 칸이고(정책 10.5.1), 방침은 exe 안에도 실려 정보 창에서 읽을 수 있다. 두 곳이
#: 같은 파일을 가리키므로 어긋날 자리가 없다.
PRIVACY_URL = f"{SOURCE_URL}/blob/main/PRIVACY.md"
