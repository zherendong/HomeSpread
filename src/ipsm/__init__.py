# HomeBoard — iPhone 홈화면을 PC 한 화면에서 보고 편집한다.
# Copyright (C) 2026 HomeBoard contributors
#
# 이 프로그램은 자유 소프트웨어입니다. 자유 소프트웨어 재단이 발표한 GNU 일반 공중
# 사용 허가서 3판 또는 (선택에 따라) 그 이후 판의 조건에 따라 재배포하거나 수정할
# 수 있습니다.
#
# 이 프로그램은 유용하게 쓰이기를 바라며 배포되지만 **어떠한 보증도 없습니다** —
# 상품성이나 특정 목적 적합성에 대한 묵시적 보증조차 없습니다. 자세한 것은 GNU 일반
# 공중 사용 허가서를 보십시오. 원문은 이 프로그램과 함께 `LICENSE` 로 실려 있고,
# <https://www.gnu.org/licenses/> 에서도 볼 수 있습니다.

"""HomeBoard — iPhone 홈화면을 PC 한 화면에서 보고 편집한다.

제품 이름은 `product.py` 한 곳에서만 선언한다. 이 설명글은 코드가 아니라 글이라
이름을 적어도 되지만, 코드에서는 `product.NAME` 을 읽는다.

계층:
    logging_setup  세션 로그와 산출물 (모든 계층이 쓴다)
    device         pymobiledevice3 를 감싸는 유일한 계층
    iconstate      홈화면 레이아웃 해석 (원본 보존이 제1 원칙)
    backup         쓰기 전 백업 · 복원 (쓰기는 전부 여기를 거친다)
    probe          실기기 진단 CLI
"""

from .version import VERSION_TEXT, VERSION_TUPLE  # noqa: F401

__version__ = "{}.{}.{}".format(*VERSION_TUPLE)
