@echo off
chcp 949 > nul
title MY ETF 급여명세서 - 로컬 실행
cd /d "%~dp0"

echo.
echo   ======================================================
echo      MY ETF 급여명세서   로컬에서 켭니다
echo   ======================================================
echo.

rem --- 파이썬 찾기 ------------------------------------------------------
rem .venv 가 있으면 그걸 쓰고, 없으면 시스템에 깔린 파이썬을 씁니다.
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" --version >nul 2>&1
if errorlevel 1 (
  echo   [!] 파이썬을 찾지 못했습니다.
  echo.
  echo       https://www.python.org/downloads/  에서 설치하실 때
  echo       "Add Python to PATH" 체크박스를 꼭 켜 주세요.
  echo.
  pause
  exit /b 1
)

rem --- 처음 한 번만 설치 -------------------------------------------------
"%PY%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
  echo   처음 실행이라 필요한 것들을 설치합니다.
  echo   인터넷 상태에 따라 몇 분 걸릴 수 있어요. 창을 닫지 마세요.
  echo.
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   [!] 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행해 주세요.
    echo.
    pause
    exit /b 1
  )
  echo.
)

echo   브라우저가 곧 자동으로 열립니다.
echo   주소:  http://localhost:8501
echo.
echo   * 처음 화면이 뜨는 데 20초쯤 걸릴 수 있습니다
echo     (TIGER 분배금 자료를 달마다 받아오느라 그렇습니다. 그 뒤로는 바로 뜹니다)
echo.
echo   끄실 때는 이 검은 창을 닫으시면 됩니다.
echo   ------------------------------------------------------
echo.

rem --server.headless false 라야 브라우저가 자동으로 열립니다.
rem (.streamlit\config.toml 의 headless=true 는 배포 서버용 설정입니다)
"%PY%" -m streamlit run app.py --server.port 8501 --server.headless false

echo.
echo   앱이 종료되었습니다.
pause
