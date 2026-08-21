@echo off
REM 파이썬이 없는 PC 에서도 실행되는 폴더 하나를 만든다.
REM 결과: dist\HomeBoard\ (이 폴더째 전달한다. zip 으로 묶어 건네면 편하다)
REM 옵션과 그 이유는 HomeBoard.spec 에 적혀 있다.

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

echo.
echo === 프로그램을 만듭니다. 몇 분 걸립니다 ===
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean HomeBoard.spec
if errorlevel 1 (
    echo [!] 빌드 실패
    exit /b 1
)

echo.
echo === 완료: dist\HomeBoard\HomeBoard.exe ===
echo     이 폴더째 원하는 곳에 두고 HomeBoard.exe 를 실행하면, 그 옆에
echo     logs\ backups\ cache\ 폴더가 자동으로 만들어집니다.
echo     쓰기 권한이 있는 폴더에 두세요 (바탕화면, 문서 등).
endlocal
