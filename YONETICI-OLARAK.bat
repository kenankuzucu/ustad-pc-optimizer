@echo off
chcp 65001 >nul
setlocal
title USTAD PC OPTIMIZER - Yonetici

rem Yonetici degilsek UAC ile kendini yeniden baslat
net session >nul 2>&1
if errorlevel 1 (
  echo  Yonetici yetkisi isteniyor... UAC penceresinde EVET deyin.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo  Yonetici yetkisi alindi. Uygulama tam yetkiyle yeniden baslatiliyor.
echo  Eski normal pencereyi kapatabilirsiniz.

rem Eski motoru kapat ki tam yetkili motor yerine gecsin
set "KLASOR=%~dp0"
if "%KLASOR:~-1%"=="\" set "KLASOR=%KLASOR:~0,-1%"
taskkill /FI "WINDOWTITLE eq USTAD-SUNUCU*" /T /F >nul 2>&1
if exist "%KLASOR%\port.txt" del "%KLASOR%\port.txt" >nul 2>&1
ping -n 3 127.0.0.1 >nul

call "%KLASOR%\USTAD-PC-OPTIMIZER.bat"
