# -*- coding: utf-8 -*-
"""v1.2.0 arayuz kaniti: 6 yeni sayfanin gercek tarayici goruntusu + JS hata yakalama."""
import os
import subprocess
import time

KOK = r"C:\Users\kenan\OneDrive\Desktop\USTAD-PC-OPTIMIZER"
PY = r"C:\Users\kenan\AppData\Local\Programs\Python\Python312\python.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.isfile(CHROME):
    CHROME = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CIK = r"C:\Users\kenan\AppData\Local\hermes\cache\scratch\ustad-ekran5"
PROFIL = r"C:\Users\kenan\AppData\Local\hermes\cache\scratch\chrome-ustad5"
os.makedirs(CIK, exist_ok=True)
PT = os.path.join(KOK, "port.txt")
if os.path.exists(PT):
    os.remove(PT)
LOGDOSYA = os.path.join(os.environ["TEMP"], "ustad-ui5.log")
log = open(LOGDOSYA, "w", encoding="utf-8")
srv = subprocess.Popen([PY, os.path.join(KOK, "sunucu.py")], cwd=KOK,
                       stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
port = None
for _ in range(80):
    if os.path.exists(PT):
        with open(PT, encoding="utf-8") as f:
            port = f.read().splitlines()[0].strip()
        break
    time.sleep(0.5)
print("PORT:", port)
if not port:
    print("PORT OKUNAMADI"); srv.kill(); raise SystemExit(1)

SAYFALAR = [("canli", "#sayfa=canli", 45),
            ("hiz", "#sayfa=hiz", 45),
            ("kurtarma", "#sayfa=kurtarma", 60),
            ("yonetim", "#sayfa=yonetim", 60),
            ("guncelleme", "#sayfa=guncelleme", 90),
            ("alarm", "#sayfa=alarm", 45)]
for anahtar, ek, bekle in SAYFALAR:
    cikti = os.path.join(CIK, "%s.png" % anahtar)
    url = "http://127.0.0.1:%s/%s" % (port, ek)
    komut = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check",
             "--window-size=1620,1180", "--force-device-scale-factor=1",
             "--user-data-dir=" + PROFIL, "--virtual-time-budget=%d" % (bekle * 1000),
             "--screenshot=" + cikti, url]
    t0 = time.time()
    try:
        subprocess.run(komut, capture_output=True, timeout=bekle + 150)
    except subprocess.TimeoutExpired:
        pass
    var = os.path.isfile(cikti)
    print("%-12s %-6s %6.1f sn  %s" % (anahtar, "TAMAM" if var else "YOK", time.time() - t0,
                                      ("%d bayt" % os.path.getsize(cikti)) if var else ""))
print("\n### MOTOR GUNLUGU (son 12 satir) ###")
log.close()
print("\n".join(open(LOGDOSYA, encoding="utf-8", errors="replace").read().splitlines()[-12:]))
srv.kill()
