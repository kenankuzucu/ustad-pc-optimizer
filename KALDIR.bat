@echo off
chcp 65001 >nul
setlocal
title USTAD PC OPTIMIZER - Kaldirma
color 0C

set "HEDEF=%LOCALAPPDATA%\USTAD-PC-OPTIMIZER"
set "MASAUSTU=%USERPROFILE%\OneDrive\Desktop"
if not exist "%MASAUSTU%" set "MASAUSTU=%USERPROFILE%\Desktop"

echo.
echo  ================================================================
echo    USTAD PC OPTIMIZER  -  KALDIRMA
echo  ================================================================
echo.
echo  Silinecek kurulum : %HEDEF%
echo  Silinecek kisayol : USTAD PC OPTIMIZER (masaustu)
echo  Silinecek kisayol : USTAD PC OPTIMIZER - Yonetici (masaustu)
echo.
echo  (Bu klasordeki kaynak dosyalara DOKUNULMAZ.)
echo.
pause

taskkill /FI "WINDOWTITLE eq USTAD-SUNUCU*" /T /F >nul 2>&1
powershell -NoProfile -Command ^
 "$m='%MASAUSTU%'; $u=[string][char]0x00DC+'STAD PC OPTIMIZER'; $y=' (Y'+[char]0x00F6+'netici)';" ^
 "foreach ($f in @(($u+'.lnk'),($u+$y+'.lnk'),'Ustad PC Optimizer.lnk','Ustad PC Optimizer - Yonetici.lnk')) {" ^
 "  $p = Join-Path $m $f; if (Test-Path $p) { Remove-Item $p -Force } }" >nul 2>&1
if exist "%HEDEF%" rmdir /S /Q "%HEDEF%" >nul 2>&1

if exist "%HEDEF%" (
  echo  [!] Kurulum klasoru tamamen silinemedi.
  echo      Elle silin: %HEDEF%
) else (
  echo  [OK] Kurulum ve kisayollar silindi.
)
echo.
pause
exit /b 0
