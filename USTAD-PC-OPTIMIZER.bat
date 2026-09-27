@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title USTAD PC OPTIMIZER - Baslatici
color 0A

set "KLASOR=%~dp0"
if "%KLASOR:~-1%"=="\" set "KLASOR=%KLASOR:~0,-1%"
set "VERI=%LOCALAPPDATA%\USTAD-PC-OPTIMIZER"
set "PY="
set "PORT="
set "MOTOR_PID="

echo.
echo  ================================================================
echo    USTAD PC OPTIMIZER  -  Baslatiliyor
echo    Sistem Temizle / Hizlandir / Koru / Yonet
echo  ================================================================
echo.

rem ---------- 1) Python bul ----------
for %%D in (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  "%ProgramFiles%\Python312\python.exe"
  "%ProgramFiles%\Python311\python.exe"
) do if not defined PY if exist %%D set "PY=%%~D"

if not defined PY (
  for /f "delims=" %%L in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PY set "PY=%%L"
)
if not defined PY (
  for /f "delims=" %%L in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PY set "PY=%%L"
)
if not defined PY (
  for /f "delims=" %%L in ('where python 2^>nul') do if not defined PY (
    echo %%L | findstr /I "WindowsApps" >nul || set "PY=%%L"
  )
)

if not defined PY (
  echo  [HATA] Python bulunamadi.
  echo.
  echo   Cozum: https://www.python.org/downloads/ adresinden Python 3 kurun.
  echo   Kurulum ekraninda "Add python.exe to PATH" kutusunu isaretleyin.
  echo.
  pause
  exit /b 1
)
echo  Python        : %PY%

rem ---------- 2) Sunucu zaten calisiyor mu ----------
if exist "%KLASOR%\port.txt" (
  set "P1="
  set "P2="
  for /f "usebackq delims=" %%L in ("%KLASOR%\port.txt") do (
    if not defined P1 ( set "P1=%%L" ) else ( if not defined P2 set "P2=%%L" )
  )
  set "PORT=!P1!"
  set "MOTOR_PID=!P2!"
)

set "BEN_BASLATTIM="
if defined PORT (
  curl -s -m 3 "http://127.0.0.1:!PORT!/nabiz" >nul 2>&1
  if not errorlevel 1 (
    echo  Sunucu zaten acik : port !PORT!
  ) else (
    set "PORT="
    set "MOTOR_PID="
  )
)

rem ---------- 3) Sunucuyu baslat ----------
if not defined PORT (
  if exist "%KLASOR%\port.txt" del "%KLASOR%\port.txt" >nul 2>&1
  echo  Motor baslatiliyor...
  start /min "USTAD-SUNUCU" "%PY%" "%KLASOR%\sunucu.py"
  set "BEN_BASLATTIM=1"
  set /a DENEME=0
  :PORT_BEKLE
  if exist "%KLASOR%\port.txt" (
    set "P1="
    set "P2="
    for /f "usebackq delims=" %%L in ("%KLASOR%\port.txt") do (
      if not defined P1 ( set "P1=%%L" ) else ( if not defined P2 set "P2=%%L" )
    )
    if defined P1 (
      set "PORT=!P1!"
      set "MOTOR_PID=!P2!"
      goto PORT_HAZIR
    )
  )
  set /a DENEME+=1
  if !DENEME! GEQ 40 goto PORT_YOK
  ping -n 2 127.0.0.1 >nul
  goto PORT_BEKLE
)

:PORT_YOK
if not defined PORT (
  echo.
  echo  [HATA] Motor acilamadi - 40 saniye bekledim ama hazir olmadi.
  echo.
  echo   Cozum sirayla:
  echo    1^) Antivirus/Kaspersky uyarisi varsa "Izin ver" deyin.
  echo    2^) "%KLASOR%\sunucu.py" dosyasini sag tik - Yonetici olarak calistir.
  echo    3^) Bilgisayari yeniden baslatip tekrar deneyin.
  echo.
  pause
  exit /b 2
)

:PORT_HAZIR
echo  Motor hazir    : port %PORT%  (PID %MOTOR_PID%)

rem ---------- 4) Tarayici bul ----------
set "TARAYICI="
for %%B in (
  "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
  "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
  "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
  "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
  "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
) do if not defined TARAYICI if exist %%B set "TARAYICI=%%~B"

if not defined TARAYICI (
  echo  [HATA] Chrome veya Edge bulunamadi.
  echo   Adresi elle acin : http://127.0.0.1:%PORT%
  echo.
  pause
  exit /b 3
)

rem ---------- 5) Uygulama penceresini ac ----------
echo  Pencere aciliyor...
start "" "%TARAYICI%" --app=http://127.0.0.1:%PORT%/?v=131 --window-size=1620,1000 ^
 --user-data-dir="%VERI%\tarayici-profil" --no-first-run --no-default-browser-check ^
 --disable-features=Translate,MediaRouter --disable-background-networking

rem ---------- 6) Nobet ----------
rem Motor artik KENDI kendini kapatir: panel kapaninca kalp atisi kesilir ve
rem motor ~2,5 dakika sonra kendini kapatir. Bu dongu yalnizca bekler ve
rem port.txt dosyasini temizler. (Eski surum pencere basligina bakip yanlislikla
rem calisan motoru olduruyordu - kaldirildi.)
:NOBET
ping -n 11 127.0.0.1 >nul
if defined MOTOR_PID (
  tasklist /FI "PID eq !MOTOR_PID!" 2>nul | findstr /I "!MOTOR_PID!" >nul
  if errorlevel 1 goto TEMIZLE
) else (
  curl -s -m 3 "http://127.0.0.1:!PORT!/nabiz" >nul 2>&1
  if errorlevel 1 goto TEMIZLE
)
goto NOBET

:TEMIZLE
if exist "%KLASOR%\port.txt" del "%KLASOR%\port.txt" >nul 2>&1
echo  Motor kapandi. Gorusuruz.
exit /b 0
