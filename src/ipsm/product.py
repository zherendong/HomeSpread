"""제품 이름과 후원 창구 — 선언 한 곳.

**이름과 부제를 나눠 두는 이유가 이 파일의 전부다.**

Apple 상표 지침은 자기 제품 **이름 안에** Apple 상표(`iOS`·`iPhone`)를 넣는 것을
금지하고, 호환성 표기는 이름 **아래의 부제**로만 허용한다. 스토어 심사에서 걸리는
자리도 정확히 "앱 이름" 칸이다. 그래서 이름(`NAME`)과 호환성 표기(`TAGLINE`)를
따로 두고, 스토어의 이름 칸에는 `NAME` 만 넣는다. 둘을 붙여 쓰는 곳은 창 제목이나
정보 창처럼 스토어 밖의 자리뿐이다.

후원 주소도 여기 있다. 창에서 주소를 짓지 않는 이유는 같다 — 계정이 바뀌었을 때
고칠 자리가 하나여야 하고, 주소가 제대로 만들어지는지는 창을 띄우지 않고도 시험할
수 있어야 한다.
"""

from __future__ import annotations

from urllib.parse import urlencode

#: 스토어의 "앱 이름" 칸에 그대로 들어간다. Apple 상표를 넣지 않는다.
NAME = "HomeBoard"

#: 이름 아래에 붙는 부제. 여기서는 호환성 표기가 허용된다.
TAGLINE = "Mobile layout manager for iOS"

#: 후원을 받는 PayPal 계정.
DONATE_ACCOUNT = "forad@ujak.net"

#: 후원 창에 적히는 항목 이름. 무엇에 쓰는 돈인지는 사용자가 결제 화면에서도 봐야 한다.
DONATE_ITEM = f"{NAME} open source development"

DONATE_CURRENCY = "USD"


def donate_url() -> str:
    """PayPal 후원 주소.

    PayPal.Me 손잡이가 아니라 계정 주소로 받으므로 `/donate/` 창구를 쓴다. 값은
    직접 잇지 않고 `urlencode` 로 만든다 — 계정 주소의 `@` 처럼 그대로 두면
    주소가 깨지는 글자가 있다.

    `no_recurring=1` 은 정기 결제 칸을 접어 둔다. 한 번 응원하려던 사람이 매달
    빠져나가는 것을 뒤늦게 아는 일이 없어야 한다.
    """
    query = urlencode(
        {
            "business": DONATE_ACCOUNT,
            "item_name": DONATE_ITEM,
            "currency_code": DONATE_CURRENCY,
            "no_recurring": "1",
        }
    )
    return f"https://www.paypal.com/donate/?{query}"


#: 이 프로그램 전체의 라이선스. `pymobiledevice3` 가 GPL 이고 우리는 그것을 함께
#: 실어 배포하므로 선택의 여지가 없다 — 함께 묶어 내보내는 순간 전체가 GPL 이 된다.
LICENSE_SPDX = "GPL-3.0-or-later"

#: 소스를 받을 수 있는 곳. GPL 은 실행 파일을 건네준 사람에게 소스를 받을 길을
#: 함께 주기를 요구한다. 정보 창이 이 주소를 링크로 보여준다.
#: 저장소를 옮기면 여기부터 고친다 — 닿지 않는 주소는 없는 주소와 같고, GPL 아래에서
#: 그것은 의무 불이행이다.
SOURCE_URL = "https://github.com/humanlyj/HomeBoard"

#: 개인정보 처리방침 원문의 주소. Partner Center 가 Win32 제품에 **언제나** 요구하는
#: 칸이고(정책 10.5.1), 방침은 exe 안에도 실려 정보 창에서 읽을 수 있다. 두 곳이
#: 같은 파일을 가리키므로 어긋날 자리가 없다.
PRIVACY_URL = f"{SOURCE_URL}/blob/main/PRIVACY.md"
