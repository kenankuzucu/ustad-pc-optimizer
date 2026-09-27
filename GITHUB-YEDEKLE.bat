@echo off
chcp 65001 >nul
title USTAD PC OPTIMIZER - GitHub yedek
color 0B

set "KLASOR=%~dp0"
if "%KLASOR:~-1%"=="\" set "KLASOR=%KLASOR:~0,-1%"
cd /d "%KLASOR%"

set "PY="
for %%D in (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
) do if not defined PY if exist %%D set "PY=%%~D"

if not defined PY (
  for /f "delims=" %%L in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PY set "PY=%%L"
)

echo.
echo  ================================================================
echo    USTAD PC OPTIMIZER  -  GitHub yedegi
echo  ================================================================
echo.

if not defined PY (
  echo  [HATA] Python bulunamadi.
  pause
  exit /b 1
)

"%PY%" "%KLASOR%\araclar\github-yedekle.py" %*

echo.
pause
