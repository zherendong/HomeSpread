# 설치 스크립트 — Windows + Python 3.13 기준
#
# pip install pymobiledevice3 를 그냥 하면 lzfse 확장 빌드에서 멈춘다
# ("Microsoft Visual C++ 14.0 or greater is required"). lzfse 는 펌웨어 압축 해제용이라
# 홈화면 읽기/쓰기에는 쓰이지 않는다. 그래서 --no-deps 로 본체만 넣고
# 필요한 의존성만 골라 설치한다.
#
# 의존성을 한 줄로 몰아 설치하면 하나가 실패할 때 전부 롤백된다. 그래서 하나씩 설치하고
# 실패는 경고로만 남긴다.

$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$venv = Join-Path $root '.venv'
$py   = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path $py)) {
    Write-Host '가상환경을 만듭니다...'
    python -m venv $venv
}

& $py -m pip install --upgrade pip --quiet

Write-Host 'pymobiledevice3 설치 (의존성 제외)...'
& $py -m pip install --no-deps pymobiledevice3

$deps = @(
    'construct', 'click', 'cryptography', 'pyasn1', 'pygments', 'hexdump',
    'pyusb', 'requests', 'tqdm', 'daemonize', 'inquirer3', 'pykdebugparser',
    'arrow', 'developer-disk-image', 'opack2', 'qh3', 'parameter-decorators',
    'prompt-toolkit', 'psutil', 'zeroconf', 'python-pcapng', 'typer-injector',
    'xonsh', 'gpxpy', 'pygnuutils', 'pywin32',
    'PySide6-Essentials'   # 화면 (ADR-001). 전체 PySide6 대신 Essentials — WebEngine·3D 는 안 쓴다
)

$failed = @()
foreach ($dep in $deps) {
    Write-Host "  $dep"
    & $py -m pip install $dep --quiet
    if ($LASTEXITCODE -ne 0) { $failed += $dep }
}

if ($failed.Count -gt 0) {
    Write-Host ''
    Write-Host "설치하지 못한 항목: $($failed -join ', ')" -ForegroundColor Yellow
    Write-Host '아래 확인에서 IMPORT OK 가 나오면 그대로 진행해도 됩니다.'
}

Write-Host ''
Write-Host '확인 중...'
& $py -c "from pymobiledevice3.services.springboard import SpringBoardServicesService as S; assert hasattr(S,'set_icon_state'); print('IMPORT OK')"
& $py -c "import PySide6.QtWidgets; print('QT OK')"

if ($LASTEXITCODE -eq 0) {
    Write-Host ''
    Write-Host '준비되었습니다. iPhone을 USB로 연결하고 아래를 실행하세요:' -ForegroundColor Green
    Write-Host '  .\run_app.bat      홈화면을 펼쳐 편집하는 창'
    Write-Host '  .\run_probe.bat    연결만 확인하는 진단'
}
