# -*- coding: utf-8 -*-
"""v1.2.1 kanıt görüntüleri: ÇALIŞAN kurulu motordan (8891) 6 sayfa, 1620x1000.
Motor zaten çalışıyorsa onu kullanır; port.txt yoksa kendi motorunu açar."""
import os
import subprocess
import time
import urllib.request

KOK = r"C:\Users\kenan\OneDrive\Desktop\USTAD-PC-OPTIMIZER"
PY = r"C:\Users\kenan\AppData\Local\Programs\Python\Python312\python.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.isfile(CHROME):
    CHROME = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CIK = r"C:\Users\kenan\AppData\Local\hermes\cache\scratch\ustad-ekran6"
PROFIL = r"C:\Users\kenan\AppData\Local\hermes\cache\scratch\chrome-ustad6"
os.makedirs(CIK, exist_ok=True)

PORT = 8891
srv = None
try:
    urllib.request.urlopen("http://127.0.0.1:%d/api/nabiz" % PORT, timeout=4).read()
    print("Mevcut motor kullanılıyor (port %d)" % PORT)
except Exception:
    srv = subprocess.Popen([PY, os.path.join(KOK, "sunucu.py")], cwd=KOK,
                           stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                           creationflags=0x08000000)
    time.sleep(9)
    print("Yeni motor açıldı (port %d)" % PORT)

SAYFALAR = [("panel", "#sayfa=panel", 18), ("canli", "#sayfa=canli", 22),
            ("hiz", "#sayfa=hiz", 18), ("kurtarma", "#sayfa=kurtarma", 30),
            ("yonetim", "#sayfa=yonetim", 30), ("guncelleme", "#sayfa=guncelleme", 30),
            ("alarm", "#sayfa=alarm", 20)]
for anahtar, ek, bekle in SAYFALAR:
    cikti = os.path.join(CIK, "%s.png" % anahtar)
    url = "http://127.0.0.1:%d/?v=131%s" % (PORT, ek)
    komut = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check",
             "--window-size=1620,1000", "--force-device-scale-factor=1",
             "--user-data-dir=" + PROFIL, "--virtual-time-budget=%d" % (bekle * 1000),
             "--screenshot=" + cikti, url]
    t0 = time.time()
    try:
        subprocess.run(komut, capture_output=True, timeout=bekle + 120)
    except subprocess.TimeoutExpired:
        pass
    var = os.path.isfile(cikti)
    print("%-12s %-6s %6.1f sn  %s" % (anahtar, "TAMAM" if var else "YOK", time.time() - t0,
                                      ("%d bayt" % os.path.getsize(cikti)) if var else ""))
if srv:
    srv.kill()
print("KANIT GORUNTULERI:", CIK)
