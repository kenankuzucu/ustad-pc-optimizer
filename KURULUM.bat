@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title USTAD PC OPTIMIZER - Kurulum
color 0A

set "KAYNAK=%~dp0"
if "%KAYNAK:~-1%"=="\" set "KAYNAK=%KAYNAK:~0,-1%"
set "HEDEF=%LOCALAPPDATA%\USTAD-PC-OPTIMIZER"
set "MASAUSTU=%USERPROFILE%\OneDrive\Desktop"
if not exist "%MASAUSTU%" set "MASAUSTU=%USERPROFILE%\Desktop"

echo.
echo  ================================================================
echo    USTAD PC OPTIMIZER  v1.0.0  -  KURULUM
echo    Kenan Kuzucu icin ozel surum
echo  ================================================================
echo.
echo  Kurulum yeri : %HEDEF%
echo  Kisayol      : %MASAUSTU%
echo.
echo  Bu program bilgisayariniza kurulur, hicbir veri internet'e gitmez.
echo.
pause

rem ---------- 1) Python kontrolu ----------
set "PY="
for %%D in (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
) do if not defined PY if exist %%D set "PY=%%~D"
if not defined PY (
  for /f "delims=" %%L in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PY set "PY=%%L"
)
if not defined PY (
  echo  [!] Python bulunamadi.
  echo      Program calismasi icin Python 3 gerekir.
  echo      https://www.python.org/downloads/ adresinden kurun ve
  echo      "Add python.exe to PATH" kutusunu isaretleyin.
  echo      Kurulum devam ediyor - Python'u sonra da kurabilirsiniz.
  echo.
) else (
  echo  [OK] Python bulundu: %PY%
)

rem ---------- 2) Dosyalari kopyala ----------
echo  Dosyalar kopyalaniyor...
if exist "%HEDEF%" (
  taskkill /FI "WINDOWTITLE eq USTAD-SUNUCU*" /T /F >nul 2>&1
  ping -n 2 127.0.0.1 >nul
)
if not exist "%HEDEF%" mkdir "%HEDEF%"
if not exist "%HEDEF%\assets" mkdir "%HEDEF%\assets"
if not exist "%HEDEF%\araclar" mkdir "%HEDEF%\araclar"

copy /Y "%KAYNAK%\sunucu.py" "%HEDEF%\sunucu.py" >nul
copy /Y "%KAYNAK%\index.html" "%HEDEF%\index.html" >nul
copy /Y "%KAYNAK%\ikon.ico" "%HEDEF%\ikon.ico" >nul
copy /Y "%KAYNAK%\USTAD-PC-OPTIMIZER.bat" "%HEDEF%\USTAD-PC-OPTIMIZER.bat" >nul
copy /Y "%KAYNAK%\YONETICI-OLARAK.bat" "%HEDEF%\YONETICI-OLARAK.bat" >nul
copy /Y "%KAYNAK%\KALDIR.bat" "%HEDEF%\KALDIR.bat" >nul
copy /Y "%KAYNAK%\OKU-BENI.txt" "%HEDEF%\OKU-BENI.txt" >nul
copy /Y "%KAYNAK%\assets\*.png" "%HEDEF%\assets\" >nul

if not exist "%HEDEF%\sunucu.py" (
  echo  [HATA] Kopyalama basarisiz. Klasoru yonetici olarak acip tekrar deneyin.
  pause
  exit /b 1
)
echo  [OK] Dosyalar kopyalandi.

rem ---------- 3) Masaustu kisayollari ----------
echo  Kisayollar olusturuluyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$w = New-Object -ComObject WScript.Shell;" ^
 "$m = '%MASAUSTU%'; $h = '%HEDEF%';" ^
 "$u = [string][char]0x00DC + 'STAD PC OPTIMIZER';" ^
 "$y = ' (Y' + [char]0x00F6 + 'netici)';" ^
 "$a = $w.CreateShortcut($m + '\' + $u + '.lnk');" ^
 "$a.TargetPath = $h + '\USTAD-PC-OPTIMIZER.bat';" ^
 "$a.WorkingDirectory = $h; $a.WindowStyle = 7; $a.IconLocation = $h + '\ikon.ico,0';" ^
 "$a.Description = 'Ustad PC Optimizer - Sistem Temizle / Hizlandir / Koru / Yonet';" ^
 "$a.Save();" ^
 "$b = $w.CreateShortcut($m + '\' + $u + $y + '.lnk');" ^
 "$b.TargetPath = $h + '\YONETICI-OLARAK.bat';" ^
 "$b.WorkingDirectory = $h; $b.WindowStyle = 7; $b.IconLocation = $h + '\ikon.ico,0';" ^
 "$b.Description = 'Ustad PC Optimizer - tam yetkili surum';" ^
 "$b.Save();" ^
 "if ((Test-Path ($m + '\' + $u + '.lnk')) -and (Test-Path ($m + '\' + $u + $y + '.lnk'))) { Write-Host '  [OK] Masaustu kisayollari hazir.'; exit 0 } else { exit 5 }"

if errorlevel 5 (
  echo  [!] Kisayol olusturulamadi. Programi su dosyadan acabilirsiniz:
  echo      %HEDEF%\USTAD-PC-OPTIMIZER.bat
) else (
  echo  [OK] Kisayol 1 : USTAD PC OPTIMIZER
  echo  [OK] Kisayol 2 : USTAD PC OPTIMIZER - Yonetici
)

echo.
echo  ================================================================
echo    KURULUM TAMAMLANDI
echo  ================================================================
echo.
echo   Masaustundeki "USTAD PC OPTIMIZER" kisayoluna cift tiklayin.
echo   Kisayolda siyah pencere cikmaz, dogrudan panel acilir.
echo.
echo   Panel kapaninca motor otomatik kapanir.
echo   Programi silmek icin: %HEDEF% klasorunu silin.
echo.
pause
exit /b 0
