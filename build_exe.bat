@echo off
REM 파이썬이 없는 PC 에서도 실행되는 폴더 하나를 만든다.
REM 결과: dist\HomeSpread\ (이 폴더째 전달한다. zip 으로 묶어 건네면 편하다)
REM 옵션과 그 이유는 HomeSpread.spec 에 적혀 있다.

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [!] .venv 가 없습니다. 먼저 install.bat 을 실행해 주세요.
    exit /b 1
)

.venv\Scripts\python.exe -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller 를 설치합니다...
    .venv\Scripts\python.exe -m pip install pyinstaller
    if errorlevel 1 exit /b 1
)

REM 빌드마다 패치 숫자를 올린다. 화면에 보이는 번호로 낡은 exe 를 가려낸다.
.venv\Scripts\python.exe scripts\bump_build.py
if errorlevel 1 (
    echo [!] 버전 올리기 실패
    exit /b 1
)

REM PyInstaller 는 만들기 전에 dist\HomeSpread\ 를 통째로 지운다. 그런데 그 폴더는
REM exe 를 한 번이라도 실행하면 backups\ 와 logs\ 가 생기는 자리이기도 하다.
REM 그대로 두면 "빌드 한 번"이 조용히 "백업 전부 삭제"가 된다. 먼저 치워 둔다.
.venv\Scripts\python.exe scripts\keep_data.py stash
if errorlevel 1 (
    echo [!] 백업을 안전한 자리로 옮기지 못했습니다. 빌드를 멈춥니다.
    exit /b 1
)

echo.
echo === 프로그램을 만듭니다. 몇 분 걸립니다 ===
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean HomeSpread.spec
if errorlevel 1 (
    echo [!] 빌드 실패
    REM 빌드가 실패해도 자료는 제자리로 돌려놓는다.
    .venv\Scripts\python.exe scripts\keep_data.py restore
    exit /b 1
)

.venv\Scripts\python.exe scripts\keep_data.py restore

echo.
echo === 완료: dist\HomeSpread\HomeSpread.exe ===
echo     이 폴더째 원하는 곳에 두고 HomeSpread.exe 를 실행하면, 그 옆에
echo     logs\ backups\ 폴더가 자동으로 만들어집니다.
echo     쓰기 권한이 있는 폴더에 두세요 (바탕화면, 문서 등).
endlocal
