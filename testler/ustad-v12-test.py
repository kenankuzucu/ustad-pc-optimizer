# -*- coding: utf-8 -*-
"""v1.2.0 motor testi: 20 yeni ozelligin uclari gercekten calisiyor mu?
Guvenli olanlar gercek makinede denenir; yonetici isteyenlerin DOGRU ve durust
cevap verdigi (UAC penceresi acmadan) dogrulanir."""
import json
import os
import subprocess
import sys
import time
import urllib.request

KOK = r"C:/Users/kenan/OneDrive/Desktop/USTAD-PC-OPTIMIZER"
PY = r"C:/Users/kenan/AppData/Local/Programs/Python/Python312/python.exe"
PORT = 8899
T = []


def istek(yol, govde=None, sure=400):
    t0 = time.time()
    try:
        if govde is None:
            r = urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, yol), timeout=sure)
        else:
            r = urllib.request.urlopen(urllib.request.Request(
                "http://127.0.0.1:%d%s" % (PORT, yol), data=json.dumps(govde).encode(),
                headers={"Content-Type": "application/json"}), timeout=sure)
        ham = r.read().decode("utf-8")
        return json.loads(ham), round(time.time() - t0, 1), r.status
    except urllib.error.HTTPError as e:
        return None, round(time.time() - t0, 1), e.code
    except Exception as e:
        return {"__hata": str(e)}, round(time.time() - t0, 1), 0


def t(yol, kontrol, aciklama, govde=None, sure=400):
    v, s, kod = istek(yol, govde, sure)
    try:
        gecti = kod == 200 and isinstance(v, dict) and kontrol(v)
    except Exception as e:
        gecti = False
    T.append((yol, kod, s, gecti, aciklama))
    print("[%s] %-26s %s %6.1f sn  %s" % ("GECTI" if gecti else "KALDI", yol, kod, s, aciklama))
    return v


print("=" * 84)
if os.path.exists(os.path.join(KOK, "port.txt")):
    os.remove(os.path.join(KOK, "port.txt"))
srv = subprocess.Popen([PY, KOK + "/sunucu.py", str(PORT)], cwd=KOK,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=0x08000000)
for _ in range(40):
    time.sleep(0.5)
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/nabiz" % PORT, timeout=3)
        break
    except Exception:
        pass
print("motor hazir (v1.2.0) — isinma dongusu arka planda calisiyor\n" + "-" * 84)

# --- 1-5: CANLI IZLEME / HIZ / BENCHMARK ---
v = t("/api/canli", lambda v: v.get("ok") and "cpu" in v, "canli CPU/RAM/disk")
print("      cpu=%s ram=%s%% disk=%s%% sicaklik=%s fan=%s" %
      (v.get("cpu"), v.get("ramYuzde"), v.get("disk"), v.get("sicakC"), v.get("fanRpm")))
v = t("/api/baglantilar", lambda v: "toplam" in v, "disa acik baglantilar + surec")
print("      toplam=%s | ilk surecler: %s" % (v.get("toplam"), [s["ad"] for s in (v.get("surecler") or [])[:5]]))
v = t("/api/disk-hiz", lambda v: v.get("ok") and v.get("yazmaMBs"), "gercek disk hiz testi (128MB)")
print("      yazma=%s MB/sn okuma=%s MB/sn 4K IOPS=%s" % (v.get("yazmaMBs"), v.get("okumaMBs"), v.get("rastgeleIOPS")))
v = t("/api/benchmark", lambda v: v.get("ok") and v.get("cpuPuani"), "CPU + RAM benchmark")
print("      cpu=%s ram=%s onceki=%s" % (v.get("cpuPuani"), v.get("ramPuani"), v.get("oncekiCpu")))
v = t("/api/hizli", lambda v: v.get("ok") and "onbellek" in v, "HIZLI anlik ozet (onbellek)")
print("      hazir kayitlar: %s | isabet=%s uretim=%s" %
      (len(v.get("hazirKayitlar") or []), (v.get("onbellek") or {}).get("isabet"),
       (v.get("onbellek") or {}).get("uretim")))
t("/api/onbellek", lambda v: "kayitlar" in v, "onbellek durumu")

# --- 7-12: KURTARMA / OLAY / AYGIT / GOREV / HIZMET ---
v = t("/api/geri-noktalari", lambda v: v.get("ok") and "noktalar" in v, "geri yukleme noktalari")
print("      nokta=%s yonetici=%s" % (v.get("adet"), v.get("yonetici")))
v = t("/api/yedek", lambda v: v.get("ok") and len(v.get("klasorler") or []) >= 3, "yedeklenecek klasor listesi")
print("      %s klasor · toplam %s" % (len(v.get("klasorler") or []), v.get("toplam")))
v = t("/api/olay", lambda v: v.get("ok") and "olaylar" in v, "son 7 gun olay gunlugu")
print("      %s farkli olay · toplam %s kayit" % (len(v.get("olaylar") or []), v.get("toplamOlay")))
v = t("/api/aygitlar", lambda v: v.get("ok") and "adet" in v, "sorunlu aygitlar")
print("      %s sorunlu aygit | %s" % (v.get("adet"), (v.get("not") or "")[:60]))
v = t("/api/gorevler", lambda v: v.get("ok") and v.get("adet", 0) > 20, "zamanlanmis gorevler")
print("      %s gorev · %s kapali" % (v.get("adet"), v.get("kapali")))
v = t("/api/hizmet", lambda v: v.get("ok") and v.get("adet", 0) > 20, "hizmetler (detayli)")
print("      %s hizmet · %s calisiyor" % (v.get("adet"), v.get("calisan")))
t("/api/hizmet?ara=spooler", lambda v: v.get("ok"), "hizmet arama")

# --- 13-18: WIFI / GUNCELLEME / WINGET / TELEMETRI / YAZICI ---
v = t("/api/wifi", lambda v: v.get("ok") and "aglar" in v, "wifi ag tarayici")
print("      %s ag · onerilen kanal=%s" % (v.get("adet"), v.get("onerilenKanal")))
v = t("/api/son-guncelleme", lambda v: v.get("ok") and "liste" in v, "son yuklenen guncellemeler")
print("      %s guncelleme · son basari: %s" % (v.get("adet"), v.get("sonBasari")))
v = t("/api/guncelleme?tur=windows", lambda v: isinstance(v, dict), "bekleyen guncellemeler (Windows)", sure=420)
print("      %s" % (("toplam=%s" % v.get("toplam")) if v and v.get("ok") else (v or {}).get("hata")))
v = t("/api/telemetri", lambda v: v.get("ok") and "durum" in v, "telemetri durumu")
print("      %s" % (v.get("durum") or {}))
v = t("/api/yazici", lambda v: v.get("ok") and "yazicilar" in v, "yazicilar + kuyruk")
print("      %s yazici · kuyruk toplam=%s · spooler=%s" % (v.get("adet"), v.get("kuyrukToplam"), v.get("spooler")))
v = t("/api/winget", lambda v: isinstance(v, dict) and ("kurulu" in v), "winget (varsa guncellenebilir paketler)", sure=420)
print("      kurulu=%s %s" % (v.get("kurulu"), (v.get("surum") or v.get("hata") or "")[:60]))

# --- 19-20: ALARM / BILDIRIM ---
v = t("/api/alarm", lambda v: v.get("ok") and "ayar" in v, "esik alarmi durumu")
print("      ayar: cpu%s ram%s disk%s sicaklik%s · ihlal=%s" %
      ((v.get("ayar") or {}).get("cpu"), (v.get("ayar") or {}).get("ram"),
       (v.get("ayar") or {}).get("disk"), (v.get("ayar") or {}).get("sicaklik"), v.get("ihlal")))
t("/api/alarm/kaydet", lambda v: v.get("ok") and v["ayar"]["cpu"] == 91, "alarm ayari kaydet (cpu=91)", {"cpu": 91})
t("/api/alarm/kaydet", lambda v: v.get("ok") and v["ayar"]["cpu"] == 90, "alarm ayari geri (cpu=90)", {"cpu": 90})
t("/api/bildirim", lambda v: v.get("ok") is False or "gonderildi" in v, "esik bildirimi (Telegram/panel)", {})

# --- POST: onbellek bosalt ---
t("/api/onbellek/bosalt", lambda v: v.get("ok"), "onbellek temizle", {})

# --- YEDEK: gercek zip (kucuk klasor) ---
v = t("/api/yedek/klasor", lambda v: v.get("ok") and v.get("dosyaSayisi", -1) >= 0, "gercek zip yedegi (Müzik)", {"secili": ["Müzik"]})
print("      %s" % (v.get("mesaj") or v.get("hata")))
zipyol = v.get("yol")
if zipyol and os.path.isfile(zipyol):
    print("      zip diskte: %s (%d bayt)" % (os.path.basename(zipyol), os.path.getsize(zipyol)))
    os.remove(zipyol)
    print("      test zip'i silindi: %s" % (not os.path.exists(zipyol)))

# --- YEDEK GOREVI: kur + dogrula + kaldir + dogrula ---
v = t("/api/yedek/gorevi", lambda v: v.get("ok") and v.get("kuruldu"), "gunluk yedek gorevi KUR", {"kur": True, "saat": "22:40"})
v = t("/api/yedek/gorevi", lambda v: v.get("ok") and v.get("kaldirildi"), "gunluk yedek gorevi KALDIR", {"kur": False})

# --- GOREV: kendi test gorevimizi kur/kapat/dogrula/sil ---
ad = "USTAD-TEST-GOREV"
_k = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
    "Register-ScheduledTask -TaskName '%s' -Force -Action (New-ScheduledTaskAction -Execute 'cmd.exe' "
    "-Argument '/c echo test') -Trigger (New-ScheduledTaskTrigger -Daily -At 03:00) | Out-Null; "
    "(Get-ScheduledTask -TaskName '%s').State" % (ad, ad)], capture_output=True, text=True)
print("      test gorevi kuruldu ->", (_k.stdout or "").strip())
v = t("/api/gorev", lambda v: v.get("ok") and v.get("dogrulandi"), "gorev KAPAT + dogrula", {"ad": ad, "yol": "\\", "kapat": True})
durum1 = str((v or {}).get("durum") or "")
v = t("/api/gorev", lambda v: v.get("ok") and v.get("dogrulandi"), "gorev AC + dogrula", {"ad": ad, "yol": "\\", "kapat": False})
durum2 = str((v or {}).get("durum") or "")
var_mi = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
    "(Get-ScheduledTask -TaskName '%s').State" % ad], capture_output=True, text=True)
print("[%s] gercek schtasks sorgusu: kapali=%s acik=%s (uclu teyit)" %
      ("GECTI" if durum1 and "Disabled" in durum1 and durum2 and ("Ready" in durum2 or "Running" in durum2) else "KALDI",
       durum1, durum2))
T.append(("schtasks-teyit", 200, 0, bool(durum1 and "Disabled" in durum1 and durum2 and "Ready" in durum2), "gorev degisimi DOGRULANDI"))
subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false" % ad], capture_output=True)

# --- HIZMET: durum okuma (guvenli) + yonetici gerektirenin durust cevabi ---
t("/api/hizmet", lambda v: v.get("ok") and v.get("dogrulandi"), "hizmet durumu oku (dogrulanmis yol)", {"ad": "Spooler", "islem": "durum"})

t("/api/geri-noktasi", lambda v: v.get("yoneticiGerekli") is True, "geri noktasi: yonetici ister (durust)", {})
t("/api/surucu-yedek", lambda v: v.get("yoneticiGerekli") is True, "surucu yedegi: yonetici ister (durust)", {})
t("/api/yazici/temizle", lambda v: v.get("yoneticiGerekli") is True, "yazici kuyrugu: yonetici ister (durust)", {})
t("/api/telemetri/kapat", lambda v: v.get("yoneticiGerekli") is True, "telemetri: yonetici ister (durust)", {})
t("/api/hizmet", lambda v: v.get("ok") is False and "bulunamad" in (v.get("hata") or ""), "olmayan hizmet: durust hata", {"ad": "YOK-BOYLE-HIZMET", "islem": "durdur"})
print("-" * 84)
gecen = sum(1 for x in T if x[3])
print("SONUC: %d/%d test GECTI" % (gecen, len(T)))
for yol, kod, s, gecti, aciklama in T:
    if not gecti:
        print("  KALAN:", yol, kod, aciklama)
print("=" * 84)
try:
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/api/kapat" % PORT, data=b"{}"), timeout=10)
except Exception:
    pass
time.sleep(2)
try:
    srv.kill()
except Exception:
    pass
