# -*- coding: utf-8 -*-
"""HIZ KANITI: isinma (warm-up) dongusu paneli ne kadar hizlandirdi? Gercek olcum."""
import json
import os
import subprocess
import time
import urllib.request

KOK = r"C:/Users/kenan/OneDrive/Desktop/USTAD-PC-OPTIMIZER"
PY = r"C:/Users/kenan/AppData/Local/Programs/Python/Python312/python.exe"
PORT = 8897


def olc(yol, tekrar=3):
    sureler = []
    for _ in range(tekrar):
        t0 = time.time()
        try:
            urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, yol), timeout=180).read()
            sureler.append(time.time() - t0)
        except Exception as e:
            sureler.append(None)
    return sureler


PT = os.path.join(KOK, "port.txt")
if os.path.exists(PT):
    os.remove(PT)
srv = subprocess.Popen([PY, os.path.join(KOK, "sunucu.py"), str(PORT)], cwd=KOK,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=0x08000000)
for _ in range(60):
    time.sleep(0.5)
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/nabiz" % PORT, timeout=3)
        break
    except Exception:
        pass

print("=" * 88)
print("USTAD PC OPTIMIZER v1.2.0 — HIZ KANITI (gercek olcum, saniye)")
print("=" * 88)
print("Motor acildi. Isinma dongusu arka planda ağır olcumleri onbellege dolduruyor.\n")
UCLAR = ["/api/canli", "/api/durum", "/api/tarama", "/api/guvenlik", "/api/programlar",
         "/api/servisler", "/api/donanim", "/api/olay", "/api/ag", "/api/gorevler", "/api/hizmet"]
sonuc = {}
for bekle, etiket in ((0, "MOTOR YENI ACILDI (isinma bitmedi)"), (25, "ISINMA TAMAMLANDI (25 sn sonra)")):
    time.sleep(bekle)
    print("--- %s ---" % etiket)
    print("%-18s %s" % ("UÇ", "ölçümler (sn)"))
    for u in UCLAR:
        s = olc(u, 3)
        metin = "  ".join(("--" if x is None else "%.2f" % x) for x in s)
        print("%-18s %s" % (u, metin))
        sonuc.setdefault(u, []).append(s)
    print("")

# onbellek durumu
try:
    d = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/onbellek" % PORT, timeout=30).read())
    print("Önbellek: %d hazır kayıt · %d istek önbellekten karşılandı · %d ölçüm üretildi · "
          "isabet oranı %%%s · ortalama ölçüm %s sn" %
          (d["kayitSayisi"], d["isabet"], d["uretim"], d["isabetOrani"], d["ortUretimSn"]))
    print("Hazır kayıtlar: " + ", ".join(x["anahtar"] for x in d["kayitlar"]))
except Exception as e:
    print("önbellek okunamadı:", e)

# panel acilis (HTML) suresi
s = olc("/", 3)
print("\nPanel sayfası (HTML) açılış: " + "  ".join("%.3f" % x for x in s) + " sn")

# ilk vs sonuncu karsilastirma
print("\n%-18s %10s %10s %10s" % ("UÇ", "1. ölçüm", "2. ölçüm", "3. ölçüm"))
for u in UCLAR:
    a, b = sonuc[u][0], sonuc[u][1]
    print("%-18s %10s %10s %10s" % (u,
        "%.2f" % a[0] if a[0] else "--", "%.2f" % a[1] if a[1] else "--",
        "%.2f" % b[0] if b[0] else "--"))
print("=" * 88)
try:
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/api/kapat" % PORT, data=b"{}"), timeout=10)
except Exception:
    pass
time.sleep(1.5)
try:
    srv.kill()
except Exception:
    pass
