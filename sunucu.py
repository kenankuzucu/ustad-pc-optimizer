# -*- coding: utf-8 -*-
"""
ÜSTAD PC OPTIMIZER - gerçek motor (motor + yerel sunucu)
Kenan Kuzucu icin - USTAD PC OPTIMIZER
Sadece Python standart kutuphanesi kullanilir. Harici paket GEREKMEZ.
"""
import os, sys, re, json, time, shutil, ctypes, subprocess, threading, socket, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

SURUM = "1.2.1"
KOK = os.path.dirname(os.path.abspath(__file__))
AYAR_DOSYA = os.path.join(KOK, "ayar.json")
PORT = int(os.environ.get("USTAD_PORT", "8891"))

# ----------------------------------------------------------------------------
# yardimcilar
# ----------------------------------------------------------------------------

def yonetici_mi():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ps(betik, timeout=90):
    """PowerShell betigini calistirir, stdout'u dondurur (UTF-8)."""
    tam = ("$ErrorActionPreference='SilentlyContinue';"
           "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
           "$OutputEncoding=[Text.Encoding]::UTF8;" + betik)
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", tam],
            capture_output=True, timeout=timeout)
        return p.stdout.decode("utf-8", "replace").strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def ps_json(betik, timeout=90):
    c = ps(betik, timeout)
    if not c:
        return None
    i, j = c.find("{"), c.rfind("}")
    k, l = c.find("["), c.rfind("]")
    if i >= 0 and (k < 0 or i < k):
        c2 = c[i:j + 1]
    elif k >= 0:
        c2 = c[k:l + 1]
    else:
        c2 = c
    try:
        return json.loads(c2)
    except Exception:
        pass
    # Cok satirli/karisik cikti: son JSON satirini dene (uyari satirlari araya girebilir)
    for satir in reversed(c.strip().splitlines()):
        s = satir.strip()
        if s[:1] in ("{", "["):
            try:
                return json.loads(s)
            except Exception:
                continue
    return None


# ============================================================================
# HIZ KATMANI — onbellek (panel ANINDA cevap versin, makine bogulmasin)
# ============================================================================

_ONB = {}
_ONB_KILIT = threading.Lock()
_ONB_SAYAC = {"isabet": 0, "uretim": 0, "toplamSn": 0.0}
_ISINMA_UCAN = set()          # su an arka planda olculen anahtarlar
_ISINMA_KILIT = threading.Lock()
_ISINMA_KAPALI = False        # True ise: her sey senkron (test/kapali mod)

# --- Panel kalp atisi (nobet) -------------------------------------------------
# Panel her 20 saniyede /api/nabiz'e vurur. Nabiz kesilirse motor kendini kapatir.
# Boylece pencere kapaninca motor ortada kalmaz; .bat'in kirilgan pencere-basligi
# kontrolune gerek kalmaz (o kontrol yanlislikla motoru olduruyordu).
SON_NABIZ = {"t": time.time()}
NOBET_SN = float(os.environ.get("USTAD_NOBET_SN", "300"))   # 5 dk: arka plandaki sekme yavaslasa da motor kapanmaz
NOBET_KAPALI = ("--kal" in sys.argv) or (os.environ.get("USTAD_NOBET", "1") == "0")


def nabiz_vur():
    SON_NABIZ["t"] = time.time()


def nobet_dongusu():
    """Kalp atisi kesilirse sureci kapatir (panel kapanmis demektir)."""
    if NOBET_KAPALI:
        return
    time.sleep(60)
    while True:
        try:
            bosluk = time.time() - SON_NABIZ["t"]
            if bosluk > NOBET_SN:
                try:
                    pt = os.path.join(KOK, "port.txt")
                    if os.path.isfile(pt):
                        os.remove(pt)
                except Exception:
                    pass
                print("Nobet: panel %d saniyedir sessiz - motor kapatiliyor." % int(bosluk))
                sys.stdout.flush()
                os._exit(0)
        except Exception:
            pass
        time.sleep(10)


def _arka_olcum(anahtar, uret):
    """Kayit yoksa/bayatsa olcumu ARKA PLANDA yapar; istegi ASLA bekletmez."""
    with _ONB_KILIT:
        if anahtar in _ISINMA_UCAN:
            return False
        _ISINMA_UCAN.add(anahtar)

    def _is():
        try:
            v = uret()
            with _ONB_KILIT:
                _ONB[anahtar] = (time.time(), v)
                _ONB_SAYAC["uretim"] += 1
        except Exception:
            pass
        finally:
            with _ONB_KILIT:
                _ISINMA_UCAN.discard(anahtar)

    threading.Thread(target=_is, daemon=True).start()
    return True


def onbellekli(anahtar, ttl, uret, bekle=True):
    """Ayni olcumu ttl saniye boyunca tekrar kullanir.

    ONEMLI (v1.2.1): taze veri yoksa istek BEKLETILMEZ —
      * kayit varsa (bayat olsa bile) ANINDA bayat veri dondurulur,
        tazeleme arkada yapilir (stale-while-revalidate),
      * kayit hic yoksa ve bekle=False ise 'hazirlaniyor' doner + arka planda olculur,
      * yalnizca bekle=True ve kayit yokken olcum senkron yapilir.
    Boylece panelde hicbir sayfa 'dusunuyor' halinde takili kalmaz.
    """
    simdi = time.time()
    with _ONB_KILIT:
        k = _ONB.get(anahtar)
        if k and (simdi - k[0]) < ttl:
            _ONB_SAYAC["isabet"] += 1
            return k[1]
    if _ISINMA_KAPALI:
        bekle = True
    if not bekle and k is not None:
        _arka_olcum(anahtar, uret)
        return k[1]
    if not bekle:
        _arka_olcum(anahtar, uret)
        return {"hazirlaniyor": True, "mesaj": "Ölçüm arka planda hazırlanıyor, birkaç saniye sonra gelir."}
    if k is not None:
        _arka_olcum(anahtar, uret)
        return k[1]
    t0 = time.time()
    try:
        v = uret()
    except Exception:
        v = {"hata": traceback.format_exc()}
    with _ONB_KILIT:
        _ONB[anahtar] = (time.time(), v)
        _ONB_SAYAC["uretim"] += 1
        _ONB_SAYAC["toplamSn"] += time.time() - t0
    return v


def onbellek_durum():
    """Onbellekteki kayitlar + isabet orani (hiz gostergesi)."""
    simdi = time.time()
    with _ONB_KILIT:
        kayit = [{"anahtar": a, "yasSn": round(simdi - v[0], 1)}
                 for a, v in sorted(_ONB.items(), key=lambda x: x[1][0])]
        isabet = _ONB_SAYAC["isabet"]
        uretim = _ONB_SAYAC["uretim"]
        toplam = _ONB_SAYAC["toplamSn"]
    return {"ok": True, "kayitlar": kayit, "kayitSayisi": len(kayit), "isabet": isabet,
            "uretim": uretim, "ortUretimSn": round(toplam / max(1, uretim), 2),
            "isabetOrani": round(100.0 * isabet / max(1, isabet + uretim), 1)}


def onbellek_bosalt():
    """Elle tazeleme: sonraki istekler olcumleri yeniden yapar."""
    with _ONB_KILIT:
        adet = len(_ONB)
        _ONB.clear()
        _ONB_SAYAC.update({"isabet": 0, "uretim": 0, "toplamSn": 0.0})
    return {"ok": True, "temizlenen": adet,
            "mesaj": "%d kayıt temizlendi — tüm ölçümler yeniden yapılacak." % adet}


def paralel(gorevler, timeout=120):
    """{ad: fonksiyon} gorevlerini AYNI ANDA calistirir (tek bekleme, dolu panel)."""
    sonuc = {}
    kilit = threading.Lock()

    def _sar(ad, fn):
        try:
            v = fn()
        except Exception as e:
            v = {"hata": str(e)}
        with kilit:
            sonuc[ad] = v

    isler = [threading.Thread(target=_sar, args=(a, f), daemon=True) for a, f in gorevler.items()]
    for t in isler:
        t.start()
    bitis = time.time() + timeout
    for t in isler:
        t.join(max(0.1, bitis - time.time()))
    return sonuc


def ps_admin(betik):
    """Yonetici gerektiren komutu UAC ile ayri pencerede calistirir."""
    try:
        sarilmis = ("Start-Process -FilePath 'powershell' -Verb RunAs -ArgumentList "
                    "'-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-Command',"
                    + json.dumps(betik))
        subprocess.Popen(["powershell", "-NoProfile", "-Command", sarilmis],
                         creationflags=0x08000000)
        return True
    except Exception:
        return False


def boyut_yuru(yol, derinlik=0):
    """Bir klasorun toplam bayt ve dosya sayisini olcer (kilitli dosyalari atlar)."""
    toplam, adet = 0, 0
    if not yol or not os.path.isdir(yol):
        return 0, 0
    yigin = [yol]
    while yigin:
        d = yigin.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            yigin.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            toplam += e.stat(follow_symlinks=False).st_size
                            adet += 1
                    except Exception:
                        pass
        except Exception:
            pass
    return toplam, adet


def tr_boyut(b):
    b = float(b)
    for birim in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or birim == "TB":
            return ("%.0f %s" % (b, birim)) if birim == "B" else ("%.1f %s" % (b, birim))
        b /= 1024.0


def insan(b):
    return tr_boyut(b)


def alt_klasorler(yol, esik=5):
    """Verilen klasorun altindaki en buyuk alt klasorleri PARALEL olcer (disk analizi)."""
    sonuc = []
    if not os.path.isdir(yol):
        return sonuc
    adaylar = []
    try:
        for ad in os.listdir(yol):
            p = os.path.join(yol, ad)
            try:
                if os.path.isdir(p) and not os.path.islink(p):
                    adaylar.append(p)
            except Exception:
                pass
    except Exception:
        pass

    def olc(p):
        try:
            b, a = boyut_yuru(p)
            return {"ad": os.path.basename(p), "yol": p, "bayt": b, "dosya": a,
                    "boyut": insan(b)}
        except Exception:
            return None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as havuz:
        for x in havuz.map(olc, adaylar):
            if x and x["bayt"] > esik * 1024 * 1024:
                sonuc.append(x)
    sonuc.sort(key=lambda x: -x["bayt"])
    return sonuc


def temizlik_kategorileri():
    """Gercek temizlenebilir konumlarin listesi."""
    L = os.environ.get("LOCALAPPDATA", "")
    A = os.environ.get("APPDATA", "")
    W = os.environ.get("WINDIR", r"C:\Windows")
    T = os.environ.get("TEMP", "")
    yollar = []
    # gecici dosyalar
    yol_s = [T, os.environ.get("TMP", ""), os.path.join(W, "Temp")]
    yol_s = [y for y in yol_s if y and os.path.isdir(y)]
    yollar.append({"id": "gecici", "ad": "Geçici Dosyalar",
                   "aciklama": "%TEMP% ve C:\\Windows\\Temp", "yollar": yol_s,
                   "yonetici": False, "renk": "#3b82f6"})
    # tarayici onbellegi
    tb = []
    for tarayici in ("Google\\Chrome", "Microsoft\\Edge", "BraveSoftware\\Brave-Browser",
                     "Mozilla\\Firefox\\Profiles"):
        kok = os.path.join(L, tarayici)
        if not os.path.isdir(kok):
            continue
        try:
            for r, d, f in os.walk(kok):
                for ad in list(d):
                    if ad.lower() in ("cache", "code cache", "gpucache", "cache2",
                                      "startupcache", "shadercache", "grshadercache"):
                        tb.append(os.path.join(r, ad))
                if r.count(os.sep) - kok.count(os.sep) > 2:
                    d[:] = []
        except Exception:
            pass
    yollar.append({"id": "tarayici", "ad": "Tarayıcı Önbelleği",
                   "aciklama": "Chrome, Edge, Brave, Firefox internet onbellegi",
                   "yollar": tb, "yonetici": False, "renk": "#22c55e"})
    # windows update artiklari
    yollar.append({"id": "update", "ad": "Windows Update Artıkları",
                   "aciklama": "Indirilmis guncelleme paketleri",
                   "yollar": [os.path.join(W, "SoftwareDistribution", "Download")],
                   "yonetici": True, "renk": "#0ea5e9"})
    # geri donusum kutusu
    yollar.append({"id": "geri-donusum", "ad": "Geri Dönüşüm Kutusu",
                   "aciklama": "Silinen dosyalarin bekledigi alan",
                   "yollar": [os.path.splitdrive(W)[0] + "\\$Recycle.Bin"],
                   "yonetici": True, "renk": "#f472b6"})
    # diger onbellekler
    diger = [os.path.join(W, "Prefetch"),
             os.path.join(W, "Logs", "CBS"),
             os.path.join(L, "Microsoft", "Windows", "Explorer"),
             os.path.join(L, "Microsoft", "Windows", "WER"),
             os.path.join(L, "CrashDumps"),
             os.path.join(W, "SoftwareDistribution", "DeliveryOptimization"),
             os.path.join(L, "D3DSCache"),
             os.path.join(L, "NVIDIA", "DXCache"),
             os.path.join(L, "Temp", "Diagnostics")]
    yollar.append({"id": "diger", "ad": "Diğer Önbellekler",
                   "aciklama": "Kucuk resim, hata raporu, prefetch, gölge onbellek",
                   "yollar": [y for y in diger if os.path.exists(y)],
                   "yonetici": False, "renk": "#a78bfa"})
    return yollar


# ----------------------------------------------------------------------------
# API islevleri
# ----------------------------------------------------------------------------

def api_durum():
    v = ps_json(r"""
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor
$d  = Get-PSDrive C
$calis = (Get-Date) - $os.LastBootUpTime
[pscustomobject]@{
  cpuAd   = ($cpu | Select-Object -First 1).Name
  cpuCekirdek = ($cpu | Select-Object -First 1).NumberOfCores
  cpuYuk  = [int]((($cpu | Measure-Object -Property LoadPercentage -Average).Average))
  ramToplam = [int64]$os.TotalVisibleMemorySize * 1024
  ramBos    = [int64]$os.FreePhysicalMemory * 1024
  diskToplam= [int64]$d.Used + [int64]$d.Free
  diskBos   = [int64]$d.Free
  osAd    = $os.Caption
  osSurum = $os.Version
  osYapi  = $os.BuildNumber
  calismaSn = [int64]$calis.TotalSeconds
  baslangic = $os.LastBootUpTime.ToString('dd.MM.yyyy HH:mm')
} | ConvertTo-Json -Compress""", timeout=60)
    if not v:
        return {"hata": "sistem bilgisi okunamadi"}
    rt = v.get("ramToplam") or 1
    rb = v.get("ramBos") or 0
    v["ramKullanilan"] = rt - rb
    v["ramYuzde"] = round((rt - rb) * 100.0 / rt)
    dt = v.get("diskToplam") or 1
    db = v.get("diskBos") or 0
    v["diskKullanilan"] = dt - db
    v["diskYuzde"] = round((dt - db) * 100.0 / dt)
    v["yukseltilebilir"] = not yonetici_mi()
    # saglik puani
    puan = 100
    puan -= max(0, (v["ramYuzde"] - 55)) * 0.7
    puan -= max(0, (v["diskYuzde"] - 75)) * 1.1
    puan -= max(0, (v["cpuYuk"] - 40)) * 0.35
    v["puan"] = max(5, min(100, int(round(puan))))
    if v["puan"] >= 85:
        v["puanYazi"] = "MÜKEMMEL DURUMDA"
    elif v["puan"] >= 70:
        v["puanYazi"] = "İYİ DURUMDA"
    elif v["puan"] >= 50:
        v["puanYazi"] = "İYİLEŞTİRİLMELİ"
    else:
        v["puanYazi"] = "BAKIM GEREKLİ"
    return v


def api_temizlik_tara():
    kat = []
    toplam = 0
    for k in temizlik_kategorileri():
        b, a = 0, 0
        for y in k["yollar"]:
            sb, sa = boyut_yuru(y)
            b += sb
            a += sa
        k2 = dict(k)
        k2.pop("yollar", None)
        k2["bayt"] = b
        k2["dosya"] = a
        k2["boyut"] = insan(b)
        k2["erisim"] = (not k["yonetici"]) or yonetici_mi() or not os.path.exists(
            (k["yollar"] or [""])[0])
        kat.append(k2)
        toplam += b
    kat.sort(key=lambda x: -x["bayt"])
    return {"kategoriler": kat, "toplam": toplam, "toplamYazi": insan(toplam),
            "yonetici": yonetici_mi()}


def api_temizlik_temizle(secili):
    silinen_bayt, silinen_dosya, hata, detay = 0, 0, 0, []
    for k in temizlik_kategorileri():
        if k["id"] not in secili:
            continue
        kb, kd = 0, 0
        for y in k["yollar"]:
            if not os.path.isdir(y):
                continue
            try:
                for ad in os.listdir(y):
                    p = os.path.join(y, ad)
                    try:
                        if os.path.isdir(p) and not os.path.islink(p):
                            sb, sa = boyut_yuru(p)
                            shutil.rmtree(p, ignore_errors=True)
                            if not os.path.exists(p):
                                kb += sb
                                kd += sa
                        else:
                            sb = os.path.getsize(p)
                            os.remove(p)
                            kb += sb
                            kd += 1
                    except Exception:
                        hata += 1
            except Exception:
                hata += 1
        detay.append({"ad": k["ad"], "bayt": kb, "boyut": insan(kb),
                      "dosya": kd, "renk": k["renk"]})
        silinen_bayt += kb
        silinen_dosya += kd
    return {"silinenBayt": silinen_bayt, "silinenYazi": insan(silinen_bayt),
            "silinenDosya": silinen_dosya, "atlanan": hata, "detay": detay}


def api_programlar():
    v = ps_json(r"""
$y = @()
$kollar = @(
 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')
foreach ($k in $kollar) {
  $y += Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | ForEach-Object {
    [pscustomobject]@{
      ad = $_.DisplayName
      surum = $_.DisplayVersion
      yayinci = $_.Publisher
      boyut = if ($_.EstimatedSize) { [int64]$_.EstimatedSize * 1024 } else { 0 }
      tarih = $_.InstallDate
      kaldir = $_.UninstallString
      yer = $_.InstallLocation
      anahtar = $_.PSPath
    }
  }
}
$y | ConvertTo-Json -Compress""", timeout=90)
    if not v:
        return {"programlar": [], "toplam": 0}
    if isinstance(v, dict):
        v = [v]
    gorulen = set()
    sonuc = []
    for p in v:
        ad = (p.get("ad") or "").strip()
        if not ad or ad.lower() in gorulen:
            continue
        gorulen.add(ad.lower())
        b = p.get("boyut") or 0
        sonuc.append({"ad": ad, "surum": p.get("surum") or "-",
                      "yayinci": p.get("yayinci") or "-",
                      "boyut": b, "boyutYazi": insan(b) if b else "—",
                      "tarih": p.get("tarih") or "-",
                      "kaldirma": p.get("kaldir") or "",
                      "yer": p.get("yer") or ""})
    sonuc.sort(key=lambda x: x["ad"].lower())
    return {"programlar": sonuc, "toplam": len(sonuc)}


def api_program_kaldir(ad, kaldirma):
    if not kaldirma:
        return {"ok": False, "mesaj": "Bu programın kaldırma komutu kayıtlı değil."}
    komut = kaldirma.strip()
    komut = re.sub(r"(?i)msiexec(\.exe)?\s*/I", "msiexec /X", komut, count=1)
    try:
        subprocess.Popen(["cmd", "/c", komut], creationflags=0x00000010)
        return {"ok": True, "mesaj": "%s için kaldırma sihirbazı açıldı. Ekrandaki pencereden onaylayın." % ad}
    except Exception as e:
        return {"ok": False, "mesaj": "Kaldırma başlatılamadı: %s" % e}


def api_baslangic():
    v = ps_json(r"""
$y = @()
foreach ($s in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run',
                 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run',
                 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run')) {
  $k = Get-Item $s -ErrorAction SilentlyContinue
  if ($k) {
    $kim = 'Tüm kullanıcılar'
    if ($s -like 'HKCU*') { $kim = 'Sen' }
    foreach ($n in $k.GetValueNames()) {
      $y += [pscustomobject]@{ ad=$n; komut=[string]$k.GetValue($n); kapsam=$s; tur='Kayıt Defteri'; kullanici=$kim }
    }
  }
}
foreach ($p in @("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup",
                 "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup")) {
  Get-ChildItem $p -ErrorAction SilentlyContinue | ForEach-Object {
    $y += [pscustomobject]@{ ad=$_.Name; komut=$_.FullName; kapsam=$p; tur='Başlangıç Klasörü'; kullanici='Sen' }
  }
}
foreach ($g in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
                 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run')) {
  $k = Get-Item $g -ErrorAction SilentlyContinue
  if ($k) {
    foreach ($n in $k.GetValueNames()) {
      for ($i=0; $i -lt $y.Count; $i++) {
        if ($y[$i].ad -eq $n -and $y[$i].tur -eq 'Kayıt Defteri') {
          $b = $k.GetValue($n)
          $kap = $true
          if ($b -and $b.Length -gt 0 -and $b[0] -eq 2) { $kap = $false }
          $y[$i] | Add-Member -NotePropertyName kapali -NotePropertyValue $kap -Force
        }
      }
    }
  }
}
@($y) | ConvertTo-Json -Compress -Depth 4""", timeout=60)
    if not v:
        return {"ogeler": [], "toplam": 0}
    if isinstance(v, dict):
        v = [v]
    for o in v:
        if "kapali" not in o:
            o["kapali"] = False
    return {"ogeler": v, "toplam": len(v), "yonetici": yonetici_mi()}


def api_baslangic_degistir(ad, kapsam, tur, kapat):
    """Baslangic ogesini kapatir/acar. Kayit defteri icin StartupApproved anahtari kullanilir."""
    if tur == "Kayıt Defteri":
        onay = ("HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StartupApproved\\Run"
                if kapsam.upper().startswith("HKCU") else
                "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StartupApproved\\Run")
        betik = r"""
$y = '%s'
if (-not (Test-Path $y)) { New-Item -Path $y -Force | Out-Null }
if ($y -like 'HKLM*') { $b = if ('%s' -eq 'kapat') { [byte[]](3,0,0,0,0,0,0,0,0,0,0,0) } else { [byte[]](2,0,0,0,0,0,0,0,0,0,0,0) } }
else { $b = if ('%s' -eq 'kapat') { [byte[]](3,0,0,0,0,0,0,0,0,0,0,0) } else { [byte[]](2,0,0,0,0,0,0,0,0,0,0,0) } }
Set-ItemProperty -Path $y -Name '%s' -Value $b -Type Binary -Force
'ok'""" % (onay, "kapat" if kapat else "ac", "kapat" if kapat else "ac", ad.replace("'", "''"))
        c = ps(betik, timeout=40)
        if "ok" in c.lower():
            return {"ok": True, "mesaj": "%s %s." % (ad, "kapatıldı" if kapat else "açıldı")}
        if not yonetici_mi() and kapsam.upper().startswith("HKLM"):
            ps_admin(betik)
            return {"ok": True, "mesaj": "Yönetici onayı istendi; pencerede Evet deyin."}
        return {"ok": False, "mesaj": "Değişiklik uygulanamadı (yönetici gerekebilir)."}
    else:
        # baslangic klasoru: .lnk dosyasini yedekleyip geri getir
        p = kapsam
        ad_yol = None
        for r, d, f in os.walk(p):
            for x in f:
                if x.lower() == ad.lower():
                    ad_yol = os.path.join(r, x)
        if not ad_yol:
            return {"ok": False, "mesaj": "Öge bulunamadı."}
        yedek = os.path.join(KOK, "yedek")
        os.makedirs(yedek, exist_ok=True)
        try:
            if kapat:
                shutil.move(ad_yol, os.path.join(yedek, ad))
            else:
                shutil.move(os.path.join(yedek, ad), ad_yol)
            return {"ok": True, "mesaj": "%s %s." % (ad, "kapatıldı" if kapat else "açıldı")}
        except Exception as e:
            return {"ok": False, "mesaj": "Uygulanamadı: %s" % e}


def api_guvenlik():
    v = ps_json(r"""
$m = Get-MpComputerStatus -ErrorAction SilentlyContinue
$t = Get-MpThreatDetection -ErrorAction SilentlyContinue | Sort-Object InitialDetectionTime -Descending | Select-Object -First 12
$g = Get-MpThreat -ErrorAction SilentlyContinue
$imza = ''
$imzaT = ''
$tar = ''
if ($m) {
  $imza = [string]$m.AntivirusSignatureVersion
  if ($m.AntivirusSignatureLastUpdated) { $imzaT = $m.AntivirusSignatureLastUpdated.ToString('dd.MM.yyyy HH:mm') }
  if ($m.QuickScanEndTime) { $tar = $m.QuickScanEndTime.ToString('dd.MM.yyyy') }
}
$av = @()
Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction SilentlyContinue | ForEach-Object {
  $av += [pscustomobject]@{ ad=$_.displayName; durum=$_.productState }
}
[pscustomobject]@{
  antivirus = if ($m) { [bool]$m.AntivirusEnabled } else { $false }
  gercekZamanli = if ($m) { [bool]$m.RealTimeProtectionEnabled } else { $false }
  kurcalama = if ($m) { [bool]$m.IsTamperProtected } else { $false }
  imzaSurum = $imza
  imzaTarih = $imzaT
  sonTarama = $tar
  urunler = $av
  tehditler = @($t | ForEach-Object { [pscustomobject]@{ ad=$_.ThreatName; tarih=$_.InitialDetectionTime.ToString('dd.MM.yyyy HH:mm'); durum=$_.ThreatStatusID } })
  tehditSayisi = @($g).Count
} | ConvertTo-Json -Compress -Depth 5""", timeout=90)
    duvar = ps_json(r"""
@(Get-NetFirewallProfile -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ ad=$_.Name; durum=if ($_.Enabled) {'AÇIK'} else {'KAPALI'} }
}) | ConvertTo-Json -Compress -Depth 3""", timeout=40)
    v = v or {}
    if isinstance(duvar, dict):
        duvar = [duvar]
    v["guvenlikDuvari"] = duvar or []
    # gizlilik: iz kalintilari
    A = os.environ.get("APPDATA", "")
    L = os.environ.get("LOCALAPPDATA", "")
    izler = [
        {"ad": "Son Kullanılan Dosyalar", "yol": os.path.join(A, "Microsoft", "Windows", "Recent")},
        {"ad": "Atlanan Kısayollar", "yol": os.path.join(A, "Microsoft", "Windows", "Recent", "AutomaticDestinations")},
        {"ad": "Küçük Resim Önbelleği", "yol": os.path.join(L, "Microsoft", "Windows", "Explorer")},
        {"ad": "Gezinme İzleri (Jump List)", "yol": os.path.join(A, "Microsoft", "Windows", "Recent", "CustomDestinations")},
    ]
    for i in izler:
        b, a = boyut_yuru(i["yol"])
        i["bayt"] = b
        i["boyut"] = insan(b)
    v["izler"] = izler
    return v


def api_gizlilik_temizle():
    A = os.environ.get("APPDATA", "")
    L = os.environ.get("LOCALAPPDATA", "")
    hedefler = [os.path.join(A, "Microsoft", "Windows", "Recent"),
                os.path.join(L, "Microsoft", "Windows", "Explorer"),
                os.path.join(A, "Microsoft", "Windows", "Recent", "CustomDestinations"),
                os.path.join(A, "Microsoft", "Windows", "Recent", "AutomaticDestinations")]
    sayi, bayt = 0, 0
    for h in hedefler:
        if not os.path.isdir(h):
            continue
        for ad in os.listdir(h):
            p = os.path.join(h, ad)
            try:
                if os.path.isdir(p):
                    sb, sa = boyut_yuru(p)
                    shutil.rmtree(p, ignore_errors=True)
                    sayi += sa
                    bayt += sb
                else:
                    bayt += os.path.getsize(p)
                    os.remove(p)
                    sayi += 1
            except Exception:
                pass
    ps(r"Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU' -Recurse -Force", 30)
    ps(r"Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths' -Recurse -Force", 30)
    ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue", 40)
    return {"ok": True, "dosya": sayi, "bayt": bayt, "boyut": insan(bayt),
            "mesaj": "%d iz kaydı silindi (%s)." % (sayi, insan(bayt))}


def api_tarama():
    """Sistem taramasi: gercek olcumler."""
    s = api_durum()
    sonuc = []
    disk = ps_json(r"""
$d = Get-PhysicalDisk | Select-Object -First 2
[pscustomobject]@{
  ad = ($d | Select-Object -First 1).FriendlyName
  saglik = ($d | Select-Object -First 1).HealthStatus
  medya = ($d | Select-Object -First 1).MediaType
  sicaklik = (Get-CimInstance -Namespace root/wmi -ClassName MSStorageDriver_ATAPISmartData -ErrorAction SilentlyContinue | Select-Object -First 1).VendorSpecific
} | ConvertTo-Json -Compress""", timeout=60) or {}
    sonuc.append({"baslik": "Disk Sağlığı",
                  "deger": "%s · %s · %s" % (disk.get("ad", "Bilinmiyor"),
                                             disk.get("saglik", "?"), disk.get("medya", "?")),
                  "durum": "iyi" if (disk.get("saglik") or "").lower().startswith("healthy") else "uyari"})
    sonuc.append({"baslik": "Bellek (RAM)", "deger": "%s / %s (%d%%)" % (
        insan(s.get("ramKullanilan", 0)), insan(s.get("ramToplam", 0)), s.get("ramYuzde", 0)),
        "durum": "iyi" if s.get("ramYuzde", 0) < 80 else "uyari"})
    sonuc.append({"baslik": "Disk Alanı", "deger": "%s boş / %s (%d%% dolu)" % (
        insan(s.get("diskBos", 0)), insan(s.get("diskToplam", 0)), s.get("diskYuzde", 0)),
        "durum": "iyi" if s.get("diskYuzde", 0) < 85 else "uyari"})
    # yeniden baslatma bekleyen guncelleme
    bekleyen = ps(r"""
$b1 = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$b2 = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
if ($b1 -or $b2) { 'VAR' } else { 'YOK' }""", 40)
    sonuc.append({"baslik": "Yeniden Başlatma Bekliyor",
                  "deger": bekleyen or "bilinmiyor",
                  "durum": "uyari" if "VAR" in (bekleyen or "") else "iyi"})
    # sistem dosyasi butunlugu
    dism = ps("DISM /Online /Cleanup-Image /CheckHealth", timeout=120)
    hasar = "yok"
    if re.search(r"(?i)hasarl|corrupt|repairable", dism):
        hasar = "saptandı"
    sonuc.append({"baslik": "Windows Bileşen Deposu",
                  "deger": ("Yönetici yetkisi gerekli" if not yonetici_mi() and not dism else
                            ("Hasarlı bileşen " + hasar if hasar == "saptandı" else "Sağlıklı — hasar yok")),
                  "durum": "uyari" if hasar == "saptandı" else "iyi"})
    # olay gunlugu hatalari
    olay = ps(r"(Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 200 -ErrorAction SilentlyContinue | Measure-Object).Count", 90)
    try:
        sayi = int((olay or "0").strip())
    except Exception:
        sayi = 0
    sonuc.append({"baslik": "Sistem Olay Günlüğü (son 200 kayıt)",
                  "deger": "%d kritik/hatalı olay" % sayi,
                  "durum": "iyi" if sayi < 15 else "uyari"})
    # gecici dosya yuku
    tt = api_temizlik_tara()
    sonuc.append({"baslik": "Temizlenebilir Dosyalar", "deger": tt["toplamYazi"],
                  "durum": "iyi" if tt["toplam"] < 2 * 1024 ** 3 else "uyari"})
    # baslangic ogesi sayisi
    bs = api_baslangic()
    sonuc.append({"baslik": "Başlangıçta Açılan Program", "deger": "%d öge" % bs["toplam"],
                  "durum": "iyi" if bs["toplam"] <= 12 else "uyari"})
    sonuc.append({"baslik": "Yönetici Yetkisi",
                  "deger": "Var (tam erişim)" if yonetici_mi() else "Yok — bazı işlemler sınırlı",
                  "durum": "iyi" if yonetici_mi() else "uyari"})
    iyi = sum(1 for x in sonuc if x["durum"] == "iyi")
    return {"kontroller": sonuc, "iyi": iyi, "toplam": len(sonuc),
            "puan": s.get("puan"), "puanYazi": s.get("puanYazi"), "durum": s}


def api_servisler():
    v = ps_json(r"""
@(Get-Process | Where-Object { $_.WorkingSet -gt 20MB } | Sort-Object WorkingSet -Descending |
  Select-Object -First 16 | ForEach-Object {
    [pscustomobject]@{ ad=$_.ProcessName; gorunen=$_.ProcessName; pid=$_.Id; ram=[int64]$_.WorkingSet }
  }) | ConvertTo-Json -Compress -Depth 3""", timeout=60)
    if not v:
        return {"servisler": []}
    if isinstance(v, dict):
        v = [v]
    for s in v:
        s["ramYazi"] = insan(s.get("ram") or 0)
    return {"servisler": v}


def api_ram_temizle():
    b = ps(r"""
Add-Type -Namespace USTAD -Name Bellek -MemberDefinition @'
[DllImport("psapi.dll")] public static extern bool EmptyWorkingSet(IntPtr hProcess);
[DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int c);
[DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
'@
$once = [int64](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory
$n = 0
Get-Process | ForEach-Object {
  try {
    $h = [USTAD.Bellek]::OpenProcess(0x1F0FFF, $false, $_.Id)
    if ($h -ne [IntPtr]::Zero) { [USTAD.Bellek]::EmptyWorkingSet($h) | Out-Null; [USTAD.Bellek]::CloseHandle($h) | Out-Null; $n++ }
  } catch {}
}
Start-Sleep -Milliseconds 900
$sonra = [int64](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory
"$n|$once|$sonra" """, timeout=120).strip()
    try:
        parca = (b or "0|0|0").split("|")
        n = int(parca[0]); once = int(parca[1]) * 1024; sonra = int(parca[2]) * 1024
        kazanc = max(0, sonra - once)
    except Exception:
        n, kazanc = 0, 0
    d = api_durum()
    return {"ok": True, "islem": n, "kazanc": kazanc, "kazancYazi": insan(kazanc),
            "ramYuzde": d.get("ramYuzde"), "ramYazi": "%s / %s" % (
                insan(d.get("ramKullanilan", 0)), insan(d.get("ramToplam", 0))),
            "mesaj": "%d sürecin çalışma kümesi boşaltıldı. Yaklaşık %s bellek serbest bırakıldı." % (n, insan(kazanc))}


def api_disk_analiz(yol="C:\\"):
    alt = alt_klasorler(yol)
    buyuk = []
    yigin = [yol]
    sayac = 0
    while yigin and sayac < 60000:
        d = yigin.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    sayac += 1
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if not e.name.startswith(("$", "System Volume")):
                                yigin.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            b = e.stat(follow_symlinks=False).st_size
                            if b > 80 * 1024 * 1024:
                                buyuk.append({"ad": e.name, "yol": e.path, "bayt": b})
                    except Exception:
                        pass
        except Exception:
            pass
    buyuk.sort(key=lambda x: -x["bayt"])
    for x in buyuk:
        x["boyut"] = insan(x["bayt"])
    d = api_durum()
    return {"klasorler": alt[:12], "dosyalar": buyuk[:15], "taranan": sayac,
            "diskBos": insan(d.get("diskBos", 0)), "diskToplam": insan(d.get("diskToplam", 0)),
            "diskBosBayt": d.get("diskBos", 0), "diskYuzde": d.get("diskYuzde", 0),
            "diskKullanilan": insan(d.get("diskKullanilan", 0))}


def api_yonetici():
    if yonetici_mi():
        return {"ok": True, "mesaj": "Uygulama zaten yönetici yetkisiyle çalışıyor."}
    bat = os.path.join(KOK, "YONETICI-OLARAK.bat")
    if not os.path.isfile(bat):
        return {"ok": False, "mesaj": "YONETICI-OLARAK.bat bulunamadı."}
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
                          "Start-Process -FilePath '%s' -Verb RunAs" % bat],
                         creationflags=0x08000000)
        return {"ok": True, "mesaj": "Yönetici sürümü başlatılıyor. "
                                     "Windows izin penceresinde 'Evet' deyin; "
                                     "yeni panel açılınca bu pencereyi kapatabilirsiniz."}
    except Exception as e:
        return {"ok": False, "mesaj": "Başlatılamadı: %s" % e}


def api_araç_calistir(kimlik):
    ARAÇLAR = {
        "dism-check": ("Windows Bileşen Deposu Kontrolü (DISM)",
                       "DISM /Online /Cleanup-Image /CheckHealth", True),
        "dism-restore": ("Windows Bileşen Deposu Onarımı (DISM RestoreHealth)",
                         "DISM /Online /Cleanup-Image /RestoreHealth", True),
        "sfc": ("Sistem Dosyası Taraması ve Onarımı (SFC)",
                "sfc /scannow", True),
        "sfc-verify": ("Sistem Dosyası Doğrulaması (SFC verifyonly)",
                       "sfc /verifyonly", True),
        "chkdsk": ("Disk Hatası Taraması (CHKDSK, sadece okuma)",
                   "chkdsk C: ", True),
        "disk-temizle": ("Disk Temizleme Aracı (cleanmgr)",
                         "Start-Process cleanmgr", False),
        "birlestir": ("Disk Birleştirme / TRIM (defrag C: /O)",
                      "defrag C: /O", True),
        "disk-yonetimi": ("Disk Yönetimi", "Start-Process diskmgmt.msc", True),
        "aygit-yoneticisi": ("Aygıt Yöneticisi", "Start-Process devmgmt.msc", False),
        "hizmetler": ("Hizmetler", "Start-Process services.msc", False),
        "olay-goruntuleyici": ("Olay Görüntüleyicisi", "Start-Process eventvwr.msc", False),
        "gorev-yoneticisi": ("Görev Yöneticisi", "Start-Process taskmgr", False),
        "kaynak-izleyici": ("Kaynak İzleyicisi", "Start-Process resmon", False),
        "sistem-bilgisi": ("Sistem Bilgisi Raporu (msinfo32)",
                           "Start-Process msinfo32", False),
        "guvenlik-duvari": ("Güvenlik Duvarı Ayarları (wf.msc)",
                            "Start-Process wf.msc", True),
        "guncelleme": ("Windows Update", "Start-Process 'ms-settings:windowsupdate'", False),
        "dns-temizle": ("DNS Önbelleğini Temizle", "ipconfig /flushdns", True),
        "ag-sifirla": ("Ağ Yığınını Sıfırla (winsock + TCP/IP)", "netsh winsock reset; netsh int ip reset", True),
        "geri-yukleme": ("Sistem Geri Yükleme Noktası Oluştur",
                         "Checkpoint-Computer -Description 'USTAD PC OPTIMIZER' -RestorePointType MODIFY_SETTINGS", True),
        "enerji": ("Enerji Verimliliği Raporu",
                   "powercfg /energy /duration 10 /output $env:USERPROFILE\\Desktop\\USTAD-enerji-raporu.html", True),
        "batarya": ("Batarya Sağlık Raporu (laptop)",
                    "powercfg /batteryreport /output $env:USERPROFILE\\Desktop\\USTAD-batarya-raporu.html", False),
        "guvenli-mod": ("Güvenli Mod'da Yeniden Başlatma Onayı",
                        "bcdedit /enum {current}", True),
        "sistem-dosyalari": ("Korunan Sistem Dosyalarını Göster",
                             "Get-ChildItem $env:WINDIR -Filter '*.sys' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 15 FullName", False),
        "acik-portlar": ("Açık Portları ve Dinleyen Servisleri Göster",
                         "Get-NetTCPConnection -State Listen | Sort-Object LocalPort | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize", False),
        "wifi-sifre": ("Kayıtlı Wi-Fi Ağlarını Listele",
                       "(netsh wlan show profiles) | Select-String ':' ", False),
        "temizlik-rapor": ("Sistem Dosyası Temizliği (DISM StartComponentCleanup)",
                           "DISM /Online /Cleanup-Image /StartComponentCleanup", True),
        "kapatma-hizli": ("Hızlı Başlatmayı Aç/Kapat",
                          "powercfg /hibernate on; powercfg /hibernate off", True),
        "defender-tara": ("Microsoft Defender Hızlı Tarama",
                          "Start-MpScan -ScanType QuickScan; Write-Host 'Tarama bitti.'", True),
        "defender-guncelle": ("Virüs İmzalarını Güncelle",
                              "Update-MpSignature", True),
    }
    a = ARAÇLAR.get(kimlik)
    if not a:
        return {"ok": False, "mesaj": "Bilinmeyen araç: %s" % kimlik}
    ad, komut, yon = a
    if yon and not yonetici_mi():
        ps_admin(komut)
        return {"ok": True, "yonetici": True,
                "mesaj": "%s başlatıldı. Windows yönetici izni soracak — 'Evet' deyin, işlem ayrı pencerede sürecek." % ad}
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
                          "$host.UI.RawUI.WindowTitle='" + ad.replace("'", "") + "';" + komut],
                         creationflags=0x00000010)
        return {"ok": True, "yonetici": False,
                "mesaj": "%s çalıştırıldı (ayrı pencerede)." % ad}
    except Exception as e:
        return {"ok": False, "mesaj": "Çalıştırılamadı: %s" % e}


def api_zorla_ara(ad):
    if not ad or len(ad) < 3:
        return {"klasorler": [], "kayitlar": [], "uyari": "En az 3 harf yazın."}
    kokler = [os.environ.get("ProgramFiles", r"C:\Program Files"),
              os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
              os.environ.get("ProgramData", r"C:\ProgramData"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), ""),
              os.path.join(os.environ.get("APPDATA", ""), "")]
    anahtar = re.sub(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ]", "", ad.lower())[:12]
    bulunan = []
    for k in kokler:
        if not k or not os.path.isdir(k):
            continue
        try:
            for x in os.listdir(k):
                xs = re.sub(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ]", "", x.lower())
                if anahtar and (anahtar in xs or xs in anahtar) and len(xs) >= 3:
                    p = os.path.join(k, x)
                    if os.path.isdir(p):
                        b, a2 = boyut_yuru(p)
                        bulunan.append({"ad": x, "yol": p, "bayt": b, "boyut": insan(b), "dosya": a2})
        except Exception:
            pass
    bulunan.sort(key=lambda z: -z["bayt"])
    kayit = ps_json(r"""
$anahtar = '%s'
$y = @()
foreach ($k in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
                 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
                 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
  Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "*$anahtar*" } | ForEach-Object {
    $y += [pscustomobject]@{ ad=$_.DisplayName; anahtar=$_.PSPath; kaldir=$_.UninstallString }
  }
}
$y | ConvertTo-Json -Compress""" % ad.replace("'", "''"), 60)
    if isinstance(kayit, dict):
        kayit = [kayit]
    return {"klasorler": bulunan[:15], "kayitlar": kayit or [],
            "uyari": "" if (bulunan or kayit) else "Bu isimle kalıntı bulunamadı — temiz görünüyor."}


def api_zorla_sil(yollar, anahtarlar):
    silinen, bayt, hata = 0, 0, []
    for y in yollar or []:
        try:
            b, _ = boyut_yuru(y)
            shutil.rmtree(y, ignore_errors=True)
            if not os.path.exists(y):
                silinen += 1
                bayt += b
            else:
                hata.append(y + " (kilitli veya yetki yok)")
        except Exception as e:
            hata.append("%s: %s" % (y, e))
    for a in anahtarlar or []:
        ps("Remove-Item -LiteralPath '%s' -Recurse -Force" % a.replace("'", "''"), 40)
    return {"ok": True, "silinen": silinen, "bayt": bayt, "boyut": insan(bayt),
            "hatalar": hata, "mesaj": "%d klasör silindi, %s alan kazanıldı." % (silinen, insan(bayt))}


def api_rapor():
    d = api_durum()
    t = api_temizlik_tara()
    b = api_baslangic()
    p = api_programlar()
    g = api_guvenlik()
    tarih = time.strftime("%d.%m.%Y %H:%M")
    return {"tarih": tarih, "durum": d, "temizlik": t, "baslangic": b,
            "programSayisi": p.get("toplam"), "guvenlik": g}


def api_rapor_kaydet():
    r = api_rapor()
    d = r["durum"]
    satir = []
    satir.append("ÜSTAD PC OPTIMIZER — SİSTEM RAPORU")
    satir.append("Tarih: " + r["tarih"])
    satir.append("=" * 62)
    satir.append("Bilgisayar   : %s %s (Yapı %s)" % (d.get("osAd"), d.get("osSurum"), d.get("osYapi")))
    satir.append("İşlemci      : %s (%s çekirdek)" % (d.get("cpuAd"), d.get("cpuCekirdek")))
    satir.append("Bellek       : %s / %s (%d%%)" % (insan(d.get("ramKullanilan", 0)),
                                                   insan(d.get("ramToplam", 0)), d.get("ramYuzde", 0)))
    satir.append("Disk (C:)    : %s boş / %s (%d%% dolu)" % (insan(d.get("diskBos", 0)),
                                                            insan(d.get("diskToplam", 0)), d.get("diskYuzde", 0)))
    satir.append("Sağlık Puanı : %s/100  (%s)" % (d.get("puan"), d.get("puanYazi")))
    satir.append("Çalışma Süresi: %s" % _sure(d.get("calismaSn", 0)))
    satir.append("")
    satir.append("TEMİZLENEBİLİR DOSYALAR — toplam %s" % r["temizlik"]["toplamYazi"])
    for k in r["temizlik"]["kategoriler"]:
        satir.append("  - %-28s %10s  (%d dosya)" % (k["ad"], k["boyut"], k["dosya"]))
    satir.append("")
    satir.append("BAŞLANGIÇTA AÇILAN ÖGELER (%d)" % r["baslangic"]["toplam"])
    for o in r["baslangic"]["ogeler"]:
        satir.append("  [%s] %s" % ("KAPALI" if o.get("kapali") else "AÇIK", o.get("ad")))
    satir.append("")
    satir.append("KURULU PROGRAM SAYISI: %s" % r["programSayisi"])
    guv = r["guvenlik"] or {}
    satir.append("")
    satir.append("GÜVENLİK")
    satir.append("  Antivirüs koruması : %s" % ("AÇIK" if guv.get("antivirus") else "KAPALI"))
    satir.append("  Gerçek zamanlı     : %s" % ("AÇIK" if guv.get("gercekZamanli") else "KAPALI"))
    satir.append("  İmza sürümü        : %s (%s)" % (guv.get("imzaSurum"), guv.get("imzaTarih")))
    satir.append("  Tespit edilen tehdit: %s" % guv.get("tehditSayisi", "?"))
    satir.append("")
    satir.append("Bu rapor ÜSTAD PC OPTIMIZER v%s tarafından bilgisayarınızda üretildi." % SURUM)
    satir.append("Hiçbir veri internet'e gönderilmedi — tüm ölçümler yerel.")
    metin = "\n".join(satir)
    masa = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if not os.path.isdir(masa):
        masa = os.path.join(os.path.expanduser("~"), "Desktop")
    ad = "USTAD-PC-OPTIMIZER-RAPOR-%s.txt" % time.strftime("%Y-%m-%d")
    yol = os.path.join(masa, ad)
    try:
        with open(yol, "w", encoding="utf-8-sig") as f:
            f.write(metin)
    except Exception as e:
        return {"ok": False, "mesaj": "Rapor yazılamadı: %s" % e}
    return {"ok": True, "yol": yol, "metin": metin, "mesaj": "Rapor masaüstüne kaydedildi: %s" % ad}


def _sure(sn):
    sn = int(sn or 0)
    g, k = divmod(sn, 86400)
    s, d = divmod(k, 3600)
    dk, _ = divmod(d, 60)
    if g:
        return "%d gün %d saat %d dakika" % (g, s, dk)
    if s:
        return "%d saat %d dakika" % (s, dk)
    return "%d dakika" % dk


def api_otomatik_temizlik_durum():
    try:
        with open(AYAR_DOSYA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"otomatikTemizlik": False, "tema": "lacivert", "sonTemizlik": ""}


def api_ayar_kaydet(v):
    a = api_otomatik_temizlik_durum()
    a.update(v or {})
    try:
        with open(AYAR_DOSYA, "w", encoding="utf-8") as f:
            json.dump(a, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return {"ok": True, "ayar": a}


# ============================================================================
# USTAD KASASI — geri alinabilir silme (yanlis silmeye karsi sigorta)
# ============================================================================

KASA = os.path.join(KOK, "kasa")


def kasa_boyut():
    b, a = boyut_yuru(KASA)
    return b, a


def kasa_ekle(yollar, islem="temizlik"):
    """Verilen dosya/klasorleri kasaya TASIR (kopyalamaz). Geri alinabilir."""
    if not yollar:
        return None
    os.makedirs(KASA, exist_ok=True)
    kid = time.strftime("%Y%m%d-%H%M%S")
    kok = os.path.join(KASA, kid)
    veri = os.path.join(kok, "dosyalar")
    os.makedirs(veri, exist_ok=True)
    kayitlar = []
    toplam = 0
    for i, y in enumerate(yollar):
        if not os.path.exists(y):
            continue
        ad = os.path.basename(y.rstrip("\\/")) or ("oge%d" % i)
        hedef = os.path.join(veri, "%03d_%s" % (i, ad))
        try:
            b = 0
            if os.path.isdir(y):
                b, _ = boyut_yuru(y)
                shutil.move(y, hedef)
            else:
                b = os.path.getsize(y)
                shutil.move(y, hedef)
            toplam += b
            kayitlar.append({"kaynak": y, "kasa": os.path.relpath(hedef, kok),
                             "bayt": b, "tur": "klasor" if os.path.isdir(hedef) else "dosya"})
        except Exception:
            pass
    if not kayitlar:
        try:
            os.rmdir(veri)
            os.rmdir(kok)
        except Exception:
            pass
        return None
    with open(os.path.join(kok, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"id": kid, "tarih": time.strftime("%d.%m.%Y %H:%M"), "islem": islem,
                   "bayt": toplam, "ogeler": kayitlar}, f, ensure_ascii=False, indent=2)
    return {"id": kid, "adet": len(kayitlar), "bayt": toplam}


def api_kasa():
    lista = []
    tb = 0
    if os.path.isdir(KASA):
        for ad in sorted(os.listdir(KASA), reverse=True):
            m = os.path.join(KASA, ad, "manifest.json")
            if os.path.isfile(m):
                try:
                    with open(m, encoding="utf-8") as f:
                        v = json.load(f)
                    v["boyut"] = insan(v.get("bayt", 0))
                    v["boyutYazi"] = v["boyut"]
                    v["adet"] = len(v.get("ogeler", []))
                    lista.append(v)
                    tb += v.get("bayt", 0)
                except Exception:
                    pass
    return {"partiler": lista, "toplam": insan(tb), "toplamBayt": tb,
            "yol": KASA, "sayi": len(lista)}


def api_kasa_geri(kid, secili=None):
    kok = os.path.join(KASA, kid)
    m = os.path.join(kok, "manifest.json")
    if not os.path.isfile(m):
        return {"ok": False, "mesaj": "Kasa partisi bulunamadı."}
    with open(m, encoding="utf-8") as f:
        v = json.load(f)
    geri, hata = 0, 0
    for o in v.get("ogeler", []):
        if secili and o["kaynak"] not in secili:
            continue
        kaynak = o["kaynak"]
        kasaYolu = os.path.join(kok, o["kasa"])
        try:
            if not os.path.exists(kasaYolu):
                hata += 1
                continue
            ust = os.path.dirname(kaynak)
            if ust and not os.path.isdir(ust):
                os.makedirs(ust, exist_ok=True)
            if os.path.exists(kaynak):
                hata += 1
                continue
            shutil.move(kasaYolu, kaynak)
            geri += 1
        except Exception:
            hata += 1
    if geri and not secili:
        shutil.rmtree(kok, ignore_errors=True)
    return {"ok": True, "geri": geri, "hata": hata,
            "mesaj": "%d öge eski yerine geri konuldu." % geri}


def api_kasa_bosalt(kid=None):
    b = 0
    if kid:
        p = os.path.join(KASA, kid)
        if os.path.isdir(p):
            b, _ = boyut_yuru(p)
            shutil.rmtree(p, ignore_errors=True)
    else:
        b, _ = boyut_yuru(KASA)
        shutil.rmtree(KASA, ignore_errors=True)
    return {"ok": True, "boyut": insan(b),
            "mesaj": "%s kalıcı olarak silindi (artık geri alınamaz)." % insan(b)}


# ============================================================================
# TURBO MOD — olcum + tek tus uygulama + geri alma
# ============================================================================

TURBO_YEDEK = os.path.join(KOK, "turbo-yedek.json")
GUC_NIHAI = "e9a42b02-d5df-448d-aa00-03f14749eb61"

TURBO_MADDELER = [
    ("guc-nihai", "Nihai Performans Güç Planı", "Islemciyi sürekli tam hızda tutar (Windows'un gizli planı)", False),
    ("gorsel", "Görsel Efektleri Kıs", "Animasyonları ve gölgeleri performans moduna alır", False),
    ("menugecikme", "Menü ve Pencere Gecikmesini Kapat", "Menüler anında açılır, kapanma animasyonu kalkar", False),
    ("gamedvr", "Oyun Çubuğu Kaydını Kapat", "Arka planda oyun kaydı yapmayı bırakır (oyun modu açık kalır)", False),
    ("arkapp", "Arka Plan Uygulama İzinlerini Kapat", "Uygulamalar kapalıyken arka planda çalışmaz", False),
    ("gorev", "Gereksiz Zamanlanmış Görevleri Kapat", "Telemetri/geri bildirim görevlerini devre dışı bırakır", True),
    ("telemetri", "Telemetri Hizmetlerini Kapat", "DiagTrack ve dmwappushservice durdurulur", True),
    ("sysmain", "SysMain (Prefetch) Kapat", "SSD'de tartışmalı: RAM'i biraz rahatlatır, açılışı yavaşlatabilir", True),
    ("dns", "En Hızlı DNS Sunucusunu Uygula", "Bu bilgisayarda ölçüp en hızlı DNS sunucusunu ayarlar", True),
]


def _reg_oku(yol, ad):
    v = ps_json("""
$p='%s'; $n='%s'
$k=Get-ItemProperty -Path $p -Name $n -ErrorAction SilentlyContinue
$o = if ($k) { [pscustomobject]@{ var=$true; deger=$k.$n } } else { [pscustomobject]@{ var=$false; deger=$null } }
$o | ConvertTo-Json -Compress""" % (yol, ad), 30)
    if not isinstance(v, dict):
        return {"var": False, "deger": None}
    return v


def turbo_olcum():
    guc = ps(r"powercfg /getactivescheme", 20)
    nihai = ps(r"powercfg /list | Select-String 'Nihai|Ultimate'", 20)
    gorsel = _reg_oku(r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting")
    dvr = _reg_oku(r"HKCU:\System\GameConfigStore", "GameDVR_Enabled")
    menu = _reg_oku(r"HKCU:\Control Panel\Desktop", "MenuShowDelay")
    ark = ps(r"(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' -ErrorAction SilentlyContinue).Count", 30)
    tel = ps(r"@(Get-Service DiagTrack,dmwappushservice -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Running' }).Count", 30)
    sys = ps(r"(Get-Service SysMain -ErrorAction SilentlyContinue).Status", 30)
    gorev = ps(r"@(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.State -ne 'Disabled' -and ($_.TaskName -match 'Feedback|CEIP|Compat|Customer|Diagnos|Telemetry') }).Count", 60)
    ping = ps(r"[int]((Test-Connection 8.8.8.8 -Count 6 -ErrorAction SilentlyContinue | Measure-Object -Property ResponseTime -Average).Average)", 60)
    d = api_durum()
    try:
        arkS = int((ark or "0").strip())
    except Exception:
        arkS = 0
    try:
        telS = int((tel or "0").strip())
    except Exception:
        telS = 0
    try:
        gorS = int((gorev or "0").strip())
    except Exception:
        gorS = 0
    try:
        pingS = int((ping or "0").strip())
    except Exception:
        pingS = 0
    return {
        "gucPlani": (guc or "").split("(")[-1].rstrip(")").strip() if guc else "bilinmiyor",
        "gucGUID": (guc or "").split(":")[1].strip().split(" ")[0] if ":" in (guc or "") else "",
        "nihaiVar": "Nihai" in (nihai or "") or "Ultimate" in (nihai or ""),
        "nihaiAktif": "Nihai" in (guc or "") or "Ultimate" in (guc or ""),
        "gorsel": gorsel.get("deger"),
        "gameDvr": dvr.get("deger"),
        "menuGecikme": menu.get("deger"),
        "arkaPlanUygulama": arkS,
        "telemetriAktif": telS,
        "sysmain": (sys or "").strip() or "yok",
        "acikGorev": gorS,
        "pingMs": pingS,
        "cpuYuk": d.get("cpuYuk"), "ramYuzde": d.get("ramYuzde"),
        "ramKullanilan": d.get("ramKullanilan"), "sistemPuan": d.get("puan"),
    }


def api_turbo_tara():
    o = turbo_olcum()
    maddeler = []
    for kid, ad, ac, yon in TURBO_MADDELER:
        gerekli = True
        if kid == "guc-nihai":
            gerekli = not o["nihaiAktif"]
        elif kid == "gorsel":
            gerekli = o["gorsel"] != 2
        elif kid == "menugecikme":
            gerekli = str(o["menuGecikme"]) != "0"
        elif kid == "gamedvr":
            gerekli = o["gameDvr"] != 0
        elif kid == "arkapp":
            gerekli = o["arkaPlanUygulama"] > 0
        elif kid == "gorev":
            gerekli = o["acikGorev"] > 0
        elif kid == "telemetri":
            gerekli = o["telemetriAktif"] > 0
        elif kid == "sysmain":
            gerekli = (o["sysmain"] or "").lower().startswith("running") or "Çalışıyor" in (o["sysmain"] or "")
        elif kid == "dns":
            gerekli = True
        maddeler.append({"id": kid, "ad": ad, "aciklama": ac, "yonetici": yon, "gerekli": gerekli})
    # turbo puani
    puan = 100
    if not o["nihaiAktif"]:
        puan -= 18
    if o["gorsel"] != 2:
        puan -= 10
    if str(o["menuGecikme"]) != "0":
        puan -= 6
    if o["gameDvr"] != 0:
        puan -= 8
    if o["arkaPlanUygulama"] > 0:
        puan -= 8
    if o["telemetriAktif"] > 0:
        puan -= 14
    if o["acikGorev"] > 0:
        puan -= 8
    if o["pingMs"] and o["pingMs"] > 45:
        puan -= 10
    puan = max(5, min(100, puan))
    return {"olcum": o, "maddeler": maddeler, "puan": puan,
            "yedekVar": os.path.isfile(TURBO_YEDEK),
            "uygulanabilir": sum(1 for m in maddeler if m["gerekli"])}


def _yedek_yaz(v):
    y = {}
    if os.path.isfile(TURBO_YEDEK):
        try:
            with open(TURBO_YEDEK, encoding="utf-8") as f:
                y = json.load(f)
        except Exception:
            y = {}
    y.setdefault("maddeler", {})
    y["maddeler"].update(v)
    y["tarih"] = time.strftime("%d.%m.%Y %H:%M")
    with open(TURBO_YEDEK, "w", encoding="utf-8") as f:
        json.dump(y, f, ensure_ascii=False, indent=2)


def api_turbo_uygula(secili):
    once = turbo_olcum()
    rapor = []
    yedek = {}
    yon_gerekli = False
    for kid in (secili or []):
        if kid == "guc-nihai":
            r = ps("powercfg -duplicatescheme " + GUC_NIHAI, 30)
            yeni = ""
            for satir in (r or "").splitlines():
                if "GUID" in satir:
                    yeni = satir.split(":")[1].strip().split(" ")[0]
            if yeni:
                ps("powercfg /setactive " + yeni, 30)
            yedek["guc-nihai"] = {"tip": "guc", "onceki": once.get("gucGUID", "")}
            son = ps("powercfg /getactivescheme", 20)
            rapor.append({"ad": "Nihai Performans Güç Planı",
                          "durum": "uygulandı" if "Nihai" in (son or "") else "uygulanamadı",
                          "detay": son or ""})
        elif kid == "gorsel":
            yedek["gorsel"] = {"tip": "reg", "yol": r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                               "ad": "VisualFXSetting", "vardi": once.get("gorsel") is not None,
                               "deger": once.get("gorsel")}
            ps(r"New-Item -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' -Force | Out-Null;"
               r"New-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects'"
               r" -Name VisualFXSetting -Value 2 -PropertyType DWord -Force | Out-Null", 30)
            rapor.append({"ad": "Görsel Efektler Performans Modu", "durum": "uygulandı",
                          "detay": "VisualFXSetting = 2 (en iyi performans)"})
        elif kid == "menugecikme":
            yedek["menugecikme"] = {"tip": "reg", "yol": r"HKCU:\Control Panel\Desktop", "ad": "MenuShowDelay",
                                    "vardi": once.get("menuGecikme") is not None, "deger": once.get("menuGecikme")}
            ps(r"New-ItemProperty -Path 'HKCU:\Control Panel\Desktop' -Name MenuShowDelay -Value '0' -PropertyType String -Force | Out-Null;"
               r"New-ItemProperty -Path 'HKCU:\Control Panel\Desktop' -Name TaskbarAnimations -Value 0 -PropertyType DWord -Force | Out-Null;"
               r"New-ItemProperty -Path 'HKCU:\Control Panel\Desktop\WindowMetrics' -Name MinAnimate -Value '0' -PropertyType String -Force | Out-Null", 30)
            rapor.append({"ad": "Menü ve Pencere Gecikmesi", "durum": "uygulandı",
                          "detay": "MenuShowDelay=0, animasyonlar kapalı"})
        elif kid == "gamedvr":
            yedek["gamedvr"] = {"tip": "reg", "yol": r"HKCU:\System\GameConfigStore", "ad": "GameDVR_Enabled",
                                "vardi": once.get("gameDvr") is not None, "deger": once.get("gameDvr")}
            ps(r"New-Item -Path 'HKCU:\System\GameConfigStore' -Force | Out-Null;"
               r"New-ItemProperty -Path 'HKCU:\System\GameConfigStore' -Name GameDVR_Enabled -Value 0 -PropertyType DWord -Force | Out-Null;"
               r"New-Item -Path 'HKCU:\Software\Microsoft\GameBar' -Force | Out-Null;"
               r"New-ItemProperty -Path 'HKCU:\Software\Microsoft\GameBar' -Name AutoGameModeEnabled -Value 1 -PropertyType DWord -Force | Out-Null", 30)
            rapor.append({"ad": "Oyun Çubuğu Kaydı", "durum": "uygulandı",
                          "detay": "GameDVR kapatıldı, oyun modu açık bırakıldı"})
        elif kid == "arkapp":
            yedek["arkapp"] = {"tip": "liste"}
            ps(r"$k=Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' -ErrorAction SilentlyContinue;"
               r"foreach($a in $k){ New-ItemProperty -Path $a.PSPath -Name Disabled -Value 1 -PropertyType DWord -Force | Out-Null }; $k.Count", 40)
            rapor.append({"ad": "Arka Plan Uygulama İzinleri", "durum": "uygulandı",
                          "detay": "%d uygulama için arka plan izni kapatıldı (geri alınabilir)" % once.get("arkaPlanUygulama", 0)})
        elif kid == "gorev":
            yon_gerekli = True
            yedek["gorev"] = {"tip": "gorev", "onceki": once.get("acikGorev")}
            ps(r"Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.State -ne 'Disabled' -and ($_.TaskName -match 'Feedback|CEIP|Compat|Customer|Diagnos|Telemetry|Maps|OneDrive') } | Disable-ScheduledTask -ErrorAction SilentlyContinue | Out-Null; 'ok'", 90)
            rapor.append({"ad": "Zamanlanmış Görevler", "durum": "uygulandı",
                          "detay": "Telemetri/geri bildirim görevleri devre dışı bırakıldı"})
        elif kid == "telemetri":
            yon_gerekli = True
            yedek["telemetri"] = {"tip": "hizmet", "onceki": "Running" if once.get("telemetriAktif") else "Stopped"}
            ps(r"foreach($s in 'DiagTrack','dmwappushservice'){ Stop-Service $s -Force -ErrorAction SilentlyContinue; Set-Service $s -StartupType Disabled -ErrorAction SilentlyContinue }; 'ok'", 60)
            dur = ps(r"@(Get-Service DiagTrack,dmwappushservice -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Running' }).Count", 30)
            rapor.append({"ad": "Telemetri Hizmetleri",
                          "durum": "uygulandı" if (dur or "").strip() in ("0", "") else "kısmen",
                          "detay": "DiagTrack / dmwappushservice durduruldu"})
        elif kid == "sysmain":
            yon_gerekli = True
            yedek["sysmain"] = {"tip": "hizmet", "onceki": once.get("sysmain")}
            ps(r"Stop-Service SysMain -Force -ErrorAction SilentlyContinue; Set-Service SysMain -StartupType Disabled -ErrorAction SilentlyContinue; 'ok'", 60)
            rapor.append({"ad": "SysMain (Prefetch)", "durum": "uygulandı",
                          "detay": "SSD'de tartışmalı — istemezsen geri alabilirsin"})
        elif kid == "dns":
            yon_gerekli = True
            h = api_ag_dns_yaris()
            en = (h.get("enHizli") or {}).get("sunucu", "")
            adap = h.get("adaptor", "")
            if en and adap:
                ok = ps("netsh interface ip set dns name='%s' static %s; netsh interface ip add dns name='%s' %s index=2; 'ok'"
                        % (adap, en, adap, ("1.0.0.1" if en == "1.1.1.1" else "8.8.4.4")), 60)
                yedek["dns"] = {"tip": "dns", "adaptor": adap, "onceki": h.get("dnsMevcut", "")}
                rapor.append({"ad": "En Hızlı DNS", "durum": "uygulandı" if ok else "uygulanamadı",
                              "detay": "%s -> %s (%s ms)" % (adap, en, (h.get("enHizli") or {}).get("ms", "?"))})
            else:
                rapor.append({"ad": "En Hızlı DNS", "durum": "uygulanamadı", "detay": "adaptör bulunamadı"})
    _yedek_yaz(yedek)
    time.sleep(1.2)
    sonra = turbo_olcum()
    return {"ok": True, "rapor": rapor, "once": once, "sonra": sonra, "yoneticiGerekli": yon_gerekli,
            "mesaj": "%d madde uygulandı." % len(rapor)}


def api_turbo_geri_al():
    if not os.path.isfile(TURBO_YEDEK):
        return {"ok": False, "mesaj": "Geri alınacak yedek yok."}
    with open(TURBO_YEDEK, encoding="utf-8") as f:
        y = json.load(f)
    yapilan = []
    m = y.get("maddeler", {})
    g = m.get("guc-nihai")
    if g and g.get("onceki"):
        ps("powercfg /setactive " + g["onceki"], 30)
        yapilan.append("Güç planı eski hâline döndü")
    for kid in ("gorsel", "menugecikme", "gamedvr"):
        v = m.get(kid)
        if not v:
            continue
        if v.get("vardi") and v.get("deger") is not None:
            ps("Set-ItemProperty -Path '%s' -Name '%s' -Value %s -Force" % (v["yol"], v["ad"], v["deger"]), 30)
        else:
            ps("Remove-ItemProperty -Path '%s' -Name '%s' -Force -ErrorAction SilentlyContinue" % (v["yol"], v["ad"]), 30)
        yapilan.append(v["ad"] + " eski hâline döndü")
    if m.get("arkapp"):
        ps(r"$k=Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' -ErrorAction SilentlyContinue;"
           r"foreach($a in $k){ Remove-ItemProperty -Path $a.PSPath -Name Disabled -Force -ErrorAction SilentlyContinue }; 'ok'", 40)
        yapilan.append("Arka plan izinleri açıldı")
    if m.get("telemetri"):
        ps(r"foreach($s in 'DiagTrack','dmwappushservice'){ Set-Service $s -StartupType Automatic -ErrorAction SilentlyContinue; Start-Service $s -ErrorAction SilentlyContinue }; 'ok'", 60)
        yapilan.append("Telemetri hizmetleri geri açıldı")
    if m.get("sysmain"):
        ps(r"Set-Service SysMain -StartupType Automatic -ErrorAction SilentlyContinue; Start-Service SysMain -ErrorAction SilentlyContinue; 'ok'", 60)
        yapilan.append("SysMain geri açıldı")
    if m.get("gorev"):
        ps(r"Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match 'Feedback|CEIP|Compat|Customer|Diagnos|Telemetry|Maps|OneDrive' } | Enable-ScheduledTask -ErrorAction SilentlyContinue | Out-Null; 'ok'", 90)
        yapilan.append("Zamanlanmış görevler geri açıldı")
    d = m.get("dns")
    if d and d.get("adaptor"):
        if "dhcp" in (d.get("onceki") or "").lower():
            ps("netsh interface ip set dns name='%s' dhcp" % d["adaptor"], 40)
        yapilan.append("DNS eski hâline döndü")
    try:
        os.remove(TURBO_YEDEK)
    except Exception:
        pass
    return {"ok": True, "yapilan": yapilan,
            "mesaj": "TURBO geri alındı (%d ayar)." % len(yapilan)}


# ============================================================================
# DERIN TEMIZLEME
# ============================================================================

def _yinelenen_bul(kokler, minbayt=8 * 1024 * 1024, limit=6000):
    """Ayni boyuttaki dosyalari SHA-256 ile gruplar."""
    import hashlib
    boyut_harita = {}
    sayi = 0
    for kok in kokler:
        if not os.path.isdir(kok):
            continue
        for r, d, f in os.walk(kok):
            d[:] = [x for x in d if not x.startswith(("$", "."))]
            for ad in f:
                sayi += 1
                if sayi > limit:
                    break
                p = os.path.join(r, ad)
                try:
                    b = os.path.getsize(p)
                    if b >= minbayt:
                        boyut_harita.setdefault(b, []).append(p)
                except Exception:
                    pass
            if sayi > limit:
                break
        if sayi > limit:
            break
    gruplar = []
    kazanc = 0
    for b, yollar in boyut_harita.items():
        if len(yollar) < 2:
            continue
        hashler = {}
        for p in yollar:
            try:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for parca in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(parca)
                hashler.setdefault(h.hexdigest(), []).append(p)
            except Exception:
                pass
        for h, ps_ in hashler.items():
            if len(ps_) > 1:
                ps_.sort(key=len)
                fazla = ps_[1:]
                kb = b * len(fazla)
                kazanc += kb
                gruplar.append({"bayt": b, "boyut": insan(b), "kopya": len(ps_) - 1,
                                "tutulacak": ps_[0], "fazla": fazla, "kazanc": kb,
                                "kazancYazi": insan(kb)})
    gruplar.sort(key=lambda x: -x["kazanc"])
    return gruplar, sayi, kazanc


def _bos_klasorler(kokler, gun=180, limit=400):
    sinir = time.time() - gun * 86400
    bulunan = []
    for kok in kokler:
        if not os.path.isdir(kok):
            continue
        for r, d, f in os.walk(kok, topdown=False):
            try:
                if os.path.basename(r).startswith(("$", ".")):
                    continue
                icerik = os.listdir(r)
                if icerik:
                    continue
                st = os.stat(r)
                if st.st_mtime < sinir:
                    b = 0
                    bulunan.append({"yol": r, "bayt": b, "boyut": "boş",
                                    "tarih": time.strftime("%d.%m.%Y", time.localtime(st.st_mtime))})
                    if len(bulunan) >= limit:
                        return bulunan
            except Exception:
                pass
    return bulunan


def api_derin_tara():
    kategoriler = []
    # 1) WinSxS bilesen deposu
    win = ""
    if yonetici_mi():
        win = ps("DISM /Online /Cleanup-Image /AnalyzeComponentStore", 240)
    analiz = []
    for satir in (win or "").splitlines():
        s = satir.strip()
        if s and any(k in s for k in ("Bileşen Deposu", "Component Store", "Geri Kazanılabilir", "Reclaimable",
                                      "Öneri", "Recommend", "Gerçek Boyut", "Actual Size", "Paylaşılan", "Shared",
                                      "Yedekler", "Backups", "Önbellek", "Cache")):
            analiz.append(s)
    kategoriler.append({"id": "winsxs", "ad": "Windows Bileşen Deposu (WinSxS)",
                        "aciklama": "Eski güncelleme bileşenleri — tipik 1-8 GB kazanç",
                        "yonetici": True, "erisim": yonetici_mi(),
                        "detay": analiz or ["Yönetici modda çalıştırınca analiz dolar."],
                        "bayt": 0, "boyut": "analiz gerekir", "adet": 0})
    # 2) surucu paketleri
    ham = ps("pnputil /enum-drivers", 120)
    paketler = []
    mevcut = {}
    for satir in (ham or "").splitlines():
        s = satir.strip()
        if s.startswith("Published Name") or s.startswith("Yayımlanan Ad"):
            mevcut = {"ad": s.split(":", 1)[-1].strip()}
            paketler.append(mevcut)
        elif ":" in s and mevcut:
            k, _, v = s.partition(":")
            k = k.strip().lower()
            if "class" in k or "sınıf" in k:
                mevcut["sinif"] = v.strip()
            elif "provider" in k or "sağlayıcı" in k:
                mevcut["saglayici"] = v.strip()
            elif "version" in k or "sürüm" in k:
                mevcut["surum"] = v.strip()
            elif "date" in k or "tarih" in k:
                mevcut["tarih"] = v.strip()
    kategoriler.append({"id": "surucu", "ad": "Artık Sürücü Paketleri",
                        "aciklama": "Kurulu cihazlara ait eski sürücü yüklemeleri",
                        "yonetici": True, "erisim": yonetici_mi(),
                        "detay": [p.get("ad", "") for p in paketler[:40]],
                        "liste": paketler, "bayt": 0, "boyut": "%d paket" % len(paketler),
                        "adet": len(paketler)})
    # 3) log ve dump
    W = os.environ.get("WINDIR", r"C:\Windows")
    L = os.environ.get("LOCALAPPDATA", "")
    yollar = [os.path.join(W, "Logs"), os.path.join(W, "Minidump"),
              os.path.join(W, "LiveKernelReports"), os.path.join(L, "CrashDumps"),
              os.path.join(W, "MEMORY.DMP"), os.path.join(W, "Logs", "CBS"),
              os.path.join(W, "Logs", "DISM")]
    b3, a3 = 0, 0
    for y in yollar:
        sb, sa = boyut_yuru(y)
        b3 += sb
        a3 += sa
    kategoriler.append({"id": "loglar", "ad": "Windows Kayıt ve Hata Dosyaları",
                        "aciklama": "Log, minidump, kurulum kayıtları",
                        "yonetici": True, "erisim": True, "yollar": [y for y in yollar if os.path.exists(y)],
                        "detay": ["%s = %s" % (y, insan(boyut_yuru(y)[0])) for y in yollar if os.path.exists(y)],
                        "bayt": b3, "boyut": insan(b3), "adet": a3})
    # 4) golge kopya
    gol = ps("vssadmin list shadowstorage", 60)
    golGe = sum(1 for s in (gol or "").splitlines() if "Kullanılan" in s or "Used" in s)
    kategoriler.append({"id": "golge", "ad": "Eski Geri Yükleme Noktaları",
                        "aciklama": "Gölge kopya alanı (yönetici gerekir)",
                        "yonetici": True, "erisim": yonetici_mi(),
                        "detay": [s.strip() for s in (gol or "").splitlines() if s.strip()][:8],
                        "bayt": 0, "boyut": "yönetici gerekir" if not yonetici_mi() else "ölçüldü", "adet": golGe})
    # 5) yinelenen dosyalar
    K = os.path.expanduser("~")
    kokler = [os.path.join(K, x) for x in ("Downloads", "Desktop", "Documents", "Pictures", "Videos", "Music")]
    kokler = [k for k in kokler if os.path.isdir(k)]
    gruplar, tarandi, kazanc = _yinelenen_bul(kokler)
    kategoriler.append({"id": "yinelenen", "ad": "Yinelenen (Çift) Dosyalar",
                        "aciklama": "Aynı içerikli büyük dosyalar — bir kopya tutulur",
                        "yonetici": False, "erisim": True, "liste": gruplar,
                        "detay": ["%s x%d  (%s)" % (g["tutulacak"], g["kopya"] + 1, g["boyut"]) for g in gruplar[:12]],
                        "bayt": kazanc, "boyut": insan(kazanc), "adet": sum(g["kopya"] for g in gruplar)})
    # 6) bos klasorler (yalniz kullanici klasorleri - guvenli)
    bos = _bos_klasorler([os.path.join(K, x) for x in ("Downloads", "Documents", "Pictures", "Videos", "Music")])
    kategoriler.append({"id": "bosklasor", "ad": "Boş Klasörler (180+ gün)",
                        "aciklama": "Yalnızca Belgeler/İndirilenler/Resimler/Video/Müzik içinde",
                        "yonetici": False, "erisim": True, "liste": bos,
                        "detay": [b["yol"] for b in bos[:12]],
                        "bayt": 0, "boyut": "%d klasör" % len(bos), "adet": len(bos)})
    # 7) olu kisayollar
    olu = []
    for yer in (os.path.join(K, "Desktop"), os.environ.get("APPDATA", ""),
                os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows",
                             "Start Menu", "Programs")):
        if not yer or not os.path.isdir(yer):
            continue
        for r, d, f in os.walk(yer):
            for ad in f:
                if ad.lower().endswith(".lnk"):
                    p = os.path.join(r, ad)
                    h = ps(r"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath" % p.replace("'", "''"), 20)
                    if h and not os.path.exists(h.strip()):
                        olu.append({"yol": p, "hedef": h.strip()})
            if len(olu) > 200:
                break
    kategoriler.append({"id": "kisayol", "ad": "Ölü Kısayollar",
                        "aciklama": "Hedefi artık var olmayan .lnk dosyaları",
                        "yonetici": False, "erisim": True, "liste": olu,
                        "detay": ["%s -> %s" % (o["yol"], o["hedef"]) for o in olu[:12]],
                        "bayt": 0, "boyut": "%d kısayol" % len(olu), "adet": len(olu)})
    kb, ka = kasa_boyut()
    return {"kategoriler": kategoriler, "kasa": {"bayt": kb, "boyut": insan(kb), "dosya": ka},
            "yonetici": yonetici_mi(), "bosAlan": api_durum().get("diskBos", 0)}


def api_derin_temizle(tip, secim=None, yonetici_ile=False):
    secim = secim or []
    if tip == "loglar":
        W = os.environ.get("WINDIR", r"C:\Windows")
        L = os.environ.get("LOCALAPPDATA", "")
        hedef = []
        for y in (os.path.join(W, "Logs"), os.path.join(W, "Minidump"),
                  os.path.join(W, "LiveKernelReports"), os.path.join(L, "CrashDumps")):
            if os.path.isdir(y):
                for ad in os.listdir(y):
                    hedef.append(os.path.join(y, ad))
        p = os.path.join(W, "MEMORY.DMP")
        if os.path.isfile(p):
            hedef.append(p)
        k = kasa_ekle(hedef, "derin-log")
        # INF/log artıkları kasaya taşınmaz, doğrudan silinir
        for y in (os.path.join(W, "Logs", "CBS"), os.path.join(W, "Logs", "DISM")):
            for ad in (os.listdir(y) if os.path.isdir(y) else []):
                try:
                    p2 = os.path.join(y, ad)
                    if os.path.isfile(p2) and p2.endswith((".log", ".cab", ".txt")):
                        os.remove(p2)
                except Exception:
                    pass
        return {"ok": True, "kasa": k,
                "mesaj": "%s kasaya alındı (geri alınabilir)." % (insan((k or {}).get("bayt", 0)))}
    if tip == "bosklasor":
        k = kasa_ekle(secim, "bos-klasor")
        return {"ok": True, "kasa": k,
                "mesaj": "%d boş klasör kasaya alındı." % ((k or {}).get("adet", 0))}
    if tip == "kisayol":
        # kasaya almak yerine doğrudan sil (kısayol zararsız)
        n = 0
        for p in secim:
            try:
                os.remove(p)
                n += 1
            except Exception:
                pass
        return {"ok": True, "mesaj": "%d ölü kısayol silindi." % n}
    if tip == "yinelenen":
        k = kasa_ekle(secim, "yinelenen-dosya")
        return {"ok": True, "kasa": k,
                "mesaj": "%s değerinde %d fazla kopya kasaya alındı." % (
                    insan((k or {}).get("bayt", 0)), (k or {}).get("adet", 0))}
    if tip == "winsxs":
        betik = "DISM /Online /Cleanup-Image /StartComponentCleanup /ResetBase"
        if yonetici_mi():
            r = ps(betik, 900)
            return {"ok": True, "cikti": r or "(çıktı alınamadı)",
                    "mesaj": "Bileşen deposu temizliği tamamlandı (yönetici)."}
        ps_admin(betik)
        return {"ok": True, "yonetici": True,
                "mesaj": "Windows yönetici izni istendi — 'Evet' deyin. "
                         "Temizlik ayrı pencerede 5-15 dakika sürebilir."}
    if tip == "golge":
        if yonetici_mi():
            r = ps("vssadmin delete shadows /for=C: /oldest /quiet", 300)
            return {"ok": True, "cikti": r or "en eski geri yükleme noktası silindi",
                    "mesaj": "En eski gölge kopya silindi."}
        ps_admin("vssadmin delete shadows /for=C: /oldest")
        return {"ok": True, "yonetici": True, "mesaj": "Yönetici izni istendi — 'Evet' deyin."}
    if tip == "surucu":
        if not secim:
            return {"ok": False, "mesaj": "Sürücü paketi seçilmedi."}
        betik = "; ".join("pnputil /delete-driver %s /uninstall /force" % s for s in secim)
        if yonetici_mi():
            r = ps(betik, 600)
            return {"ok": True, "cikti": r or "", "mesaj": "%d sürücü paketi silindi." % len(secim)}
        ps_admin(betik)
        return {"ok": True, "yonetici": True,
                "mesaj": "Yönetici izni istendi — 'Evet' deyin. DİKKAT: kullanımdaki bir sürücüyü "
                         "silmek aygıtı devre dışı bırakabilir."}
    return {"ok": False, "mesaj": "Bilinmeyen derin temizlik türü: %s" % tip}


# ============================================================================
# AG & HIZ
# ============================================================================

def api_ag_dns_yaris():
    adap = ps(r"(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -notmatch 'VPN|Virtual|Kaspersky' } | Select-Object -First 1).Name", 40)
    adap = (adap or "").strip()
    if not adap:
        a2 = ps(r"(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).InterfaceAlias", 40)
        adap = (a2 or "").strip()
    dns_mevcut = ps(r"(Get-DnsClientServerAddress -InterfaceAlias '%s' -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses -join ','" % adap, 40)
    gw = ps(r"(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1).NextHop", 40)
    gw = (gw or "").strip()
    denenecek = []
    if gw:
        denenecek.append(("Router (modem)", gw))
    denenecek += [("Cloudflare", "1.1.1.1"), ("Google DNS", "8.8.8.8"),
                  ("Quad9", "9.9.9.9"), ("OpenDNS", "208.67.222.222")]
    sonuc = []
    for ad, ip in denenecek:
        c = ps(r"$t=@(); 1..3 | ForEach-Object { $t += (Measure-Command { Resolve-DnsName microsoft.com -Server '%s' -DnsOnly -ErrorAction SilentlyContinue }).TotalMilliseconds }; [math]::Round(($t | Measure-Object -Average).Average)" % ip, 60)
        try:
            ms = int(float((c or "0").strip()))
        except Exception:
            ms = 9999
        if ms < 9000:
            sonuc.append({"ad": ad, "sunucu": ip, "ms": ms})
    sonuc.sort(key=lambda x: x["ms"])
    return {"sonuc": sonuc, "enHizli": sonuc[0] if sonuc else None, "adaptor": adap,
            "dnsMevcut": (dns_mevcut or "").strip(), "gecit": gw}


def api_ag_tara():
    ping = ps_json(r"""
$r = Test-Connection 8.8.8.8 -Count 20 -ErrorAction SilentlyContinue
if ($r) {
  $s = $r | Measure-Object -Property ResponseTime -Average -Minimum -Maximum
  $dizi = @($r | ForEach-Object { $_.ResponseTime })
  $sapma = 0
  if ($dizi.Count -gt 1) {
    $ort = $s.Average
    $toplam = 0
    foreach ($x in $dizi) { $toplam += [math]::Pow(($x - $ort), 2) }
    $sapma = [math]::Round([math]::Sqrt($toplam / $dizi.Count), 1)
  }
  [pscustomobject]@{
    ortalama = [int][math]::Round($s.Average); enAz = $s.Minimum; enCok = $s.Maximum
    jitter = $sapma; basarili = $dizi.Count; gonderilen = 20
  } | ConvertTo-Json -Compress
} else { [pscustomobject]@{ ortalama=0; enAz=0; enCok=0; jitter=0; basarili=0; gonderilen=20 } | ConvertTo-Json -Compress }""", 120)
    ping = ping or {}
    if not ping.get("basarili"):
        ping = {"ortalama": 0, "enAz": 0, "enCok": 0, "jitter": 0, "basarili": 0, "gonderilen": 20}
    ping["kayip"] = 20 - ping.get("basarili", 0)
    ping["kayipYuzde"] = round(ping["kayip"] * 100.0 / 20)
    ping["kalite"] = ("MÜKEMMEL" if ping["ortalama"] < 30 and ping["kayip"] == 0 else
                      "İYİ" if ping["ortalama"] < 60 and ping["kayip"] <= 1 else
                      "ORTA" if ping["ortalama"] < 120 else "ZAYIF")
    dns = api_ag_dns_yaris()
    ad = ps_json(r"""
@(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | ForEach-Object {
  [pscustomobject]@{ ad=$_.Name; tip=$_.InterfaceDescription
                     hiz=[int64]$_.Speed; hizYazi=[string]$_.LinkSpeed; durum=$_.Status; mac=$_.MacAddress }
}) | ConvertTo-Json -Compress -Depth 3""", 60)
    if isinstance(ad, dict):
        ad = [ad]
    if not isinstance(ad, list):
        ad = []
    portlar = ps_json(r"""
@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Sort-Object LocalPort -Unique | Select-Object -First 40 | ForEach-Object {
  $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
  [pscustomobject]@{ port=$_.LocalPort; adres=$_.LocalAddress; pid=$_.OwningProcess
                     surec=if($p){$p.ProcessName}else{'?'} }
}) | ConvertTo-Json -Compress -Depth 3""", 90)
    if isinstance(portlar, dict):
        portlar = [portlar]
    if not isinstance(portlar, list):
        portlar = []
    return {"ping": ping, "dns": dns, "adaptorler": ad or [], "portlar": portlar or [],
            "wifi": [s.strip() for s in (ps("netsh wlan show interfaces", 40) or "").splitlines() if ":" in s and s.strip()][:12]}


def api_ag_hiz():
    r = ps_json(r"""
$ProgressPreference='SilentlyContinue'
$t0=Get-Date
try { $x=Invoke-WebRequest -Uri 'https://speed.cloudflare.com/__down?bytes=25000000' -TimeoutSec 60 -UseBasicParsing; $s=((Get-Date)-$t0).TotalSeconds
  $mbps=[math]::Round(($x.RawContentLength*8/$s/1MB),1); $ind=[math]::Round($x.RawContentLength/1MB,2) } catch { $mbps=0; $ind=0 }
$t1=Get-Date
try { $veri=New-Object byte[] 5000000; (New-Object Random).NextBytes($veri)
  $y=Invoke-WebRequest -Uri 'https://speed.cloudflare.com/__up' -Method POST -Body $veri -TimeoutSec 60 -UseBasicParsing
  $s2=((Get-Date)-$t1).TotalSeconds; $up=[math]::Round((5000000*8/$s2/1MB),1) } catch { $up=0 }
[pscustomobject]@{ indirilenMbps=$mbps; indirilenMB=$ind; yuklenenMbps=$up } | ConvertTo-Json -Compress""", 240)
    v = r or {}
    if not v.get("indirilenMbps"):
        return {"ok": False, "mesaj": "Hız ölçümü yapılamadı (internet bağlantısı veya güvenlik duvarı engeli)."}
    v["ok"] = True
    v["mesaj"] = "İndirme %s Mbps · Yükleme %s Mbps" % (v.get("indirilenMbps"), v.get("yuklenenMbps"))
    return v


def api_ag_dns_uygula(sunucu, adaptor=None, geri=False):
    adap = adaptor or ps(r"(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -notmatch 'VPN|Virtual|Kaspersky' } | Select-Object -First 1).Name", 40)
    adap = (adap or "").strip()
    if not adap:
        return {"ok": False, "mesaj": "Aktif ağ adaptörü bulunamadı."}
    if geri:
        b = "netsh interface ip set dns name='%s' dhcp" % adap
    else:
        if not sunucu:
            return {"ok": False, "mesaj": "DNS sunucusu seçilmedi."}
        yedek = "1.0.0.1" if sunucu == "1.1.1.1" else ("8.8.4.4" if sunucu == "8.8.8.8" else "")
        b = "netsh interface ip set dns name='%s' static %s" % (adap, sunucu)
        if yedek:
            b += "; netsh interface ip add dns name='%s' %s index=2" % (adap, yedek)
    if not yonetici_mi():
        ps_admin(b)
        return {"ok": True, "yonetici": True,
                "mesaj": "Yönetici izni istendi — 'Evet' deyin. DNS %s için %s uygulanacak." % (
                    adap, "otomatik (modem) olarak geri alınacak" if geri else sunucu)}
    r = ps(b, 60)
    dogrula = ps(r"(Get-DnsClientServerAddress -InterfaceAlias '%s' -AddressFamily IPv4).ServerAddresses -join ','" % adap, 40)
    return {"ok": True, "yanit": r or "", "yeni": (dogrula or "").strip(),
            "mesaj": "%s adaptörünün DNS'i güncellendi." % adap}


# ============================================================================
# BAKIM ZAMANLAYICI
# ============================================================================

BAKIM_GOREV = "USTAD-PC-OPTIMIZER-BAKIM"


def api_zamanlayici():
    v = ps_json(r"""
$a = Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue
$o = if ($a) {
  $b = $a.Triggers | Select-Object -First 1
  [pscustomobject]@{ var=$true; durum=$a.State.ToString()
    saat=if($b){$b.StartBoundary}else{''}; sonCalisma=if($a.LastRunTime){$a.LastRunTime.ToString('dd.MM.yyyy HH:mm')}else{'hiç'} }
} else { [pscustomobject]@{ var=$false; durum='yok'; saat=''; sonCalisma='' } }
$o | ConvertTo-Json -Compress""" % BAKIM_GOREV, 60)
    if not isinstance(v, dict):
        v = {"var": False, "durum": "yok", "saat": "", "sonCalisma": "", "okunamadi": True}
    v["gunlukDosya"] = os.path.join(KOK, "bakim-gunlugu.txt")
    v["sonGunluk"] = ""
    try:
        with open(os.path.join(KOK, "bakim-gunlugu.txt"), encoding="utf-8") as f:
            satirlar = f.read().strip().splitlines()
        v["sonGunluk"] = " | ".join(satirlar[-3:])
    except Exception:
        pass
    return v


def api_zamanlayici_kur(saat="09:00"):
    try:
        hh, dd = [int(x) for x in (saat or "09:00").split(":")[:2]]
        if not (0 <= hh <= 23 and 0 <= dd <= 59):
            raise ValueError
    except Exception:
        return {"ok": False, "mesaj": "Saat biçimi yanlış (örn: 09:30)."}
    py = sys.executable
    betik = os.path.join(KOK, "sunucu.py")
    b = (r"$a=New-ScheduledTaskAction -Execute '%s' -Argument '\"%s\" --bakim' -WorkingDirectory '%s';"
         r"$t=New-ScheduledTaskTrigger -Daily -At %02d:%02d;"
         r"$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun;"
         r"try { Register-ScheduledTask -TaskName '%s' -Action $a -Trigger $t -Settings $s -Force -ErrorAction Stop | Out-Null }"
         r" catch { 'HATA: ' + $_.Exception.Message }"
         r"if (Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue) { 'DOGRULANDI' } else { 'OLUSMADI' }"
         % (py, betik, KOK, hh, dd, BAKIM_GOREV, BAKIM_GOREV))
    r = ps(b, 90)
    r = r or ""
    if "DOGRULANDI" in r:
        return {"ok": True, "dogrulandi": True,
                "mesaj": "Günlük bakım görevi kuruldu (her gün %02d:%02d)." % (hh, dd)}
    return {"ok": False, "dogrulandi": False,
            "mesaj": "Görev kurulamadı: %s" % (r.strip()[:300] or "bilinmeyen hata")}


def api_zamanlayici_kaldir():
    ps(r"Unregister-ScheduledTask -TaskName '%s' -Confirm:$false -ErrorAction SilentlyContinue" % BAKIM_GOREV, 60)
    kontrol = ps(r"if (Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue) { 'VAR' } else { 'YOK' }" % BAKIM_GOREV, 60)
    kaldi = "YOK" in (kontrol or "")
    return {"ok": kaldi, "dogrulandi": kaldi,
            "mesaj": "Bakım görevi kaldırıldı." if kaldi else "Görev kaldırılamadı (hâlâ görünüyor)."}


def bakim_calistir():
    """--bakim modu: gunluk otomatik bakim + masaustune rapor."""
    satir = ["[%s] USTAD PC OPTIMIZER günlük bakım" % time.strftime("%d.%m.%Y %H:%M")]
    t = api_temizlik_temizle(["gecici", "tarayici", "diger", "update", "geri-donusum"] if yonetici_mi()
                             else ["gecici", "tarayici", "diger"])
    satir.append("  temizlik: %s (%d dosya, %d atlandı)" % (t["silinenYazi"], t["silinenDosya"], t["atlanan"]))
    try:
        g = api_gizlilik_temizle()
        satir.append("  gizlilik: %s" % g.get("mesaj", ""))
    except Exception:
        pass
    try:
        k = api_kasa_bosalt()
        satir.append("  kasa boşaltma: %s" % k.get("mesaj", ""))
    except Exception:
        pass
    r = api_rapor_kaydet()
    satir.append("  rapor: %s" % (r.get("yol") or r.get("mesaj")))
    with open(os.path.join(KOK, "bakim-gunlugu.txt"), "a", encoding="utf-8") as f:
        f.write("\n".join(satir) + "\n")
    print("\n".join(satir))
    return 0


# ============================================================================
# DONANIM
# ============================================================================

def api_donanim():
    d = ps_json(r"""
$disk = @(Get-Disk | Where-Object { $_.BusType -ne 'USB' -or $_.Size -gt 0 } | ForEach-Object {
  $f = Get-Partition -DiskNumber $_.Number -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter } | Select-Object -First 1
  [pscustomobject]@{ ad=$_.FriendlyName; boyut=[int64]$_.Size; saglik=$_.HealthStatus.ToString()
    durum=$_.OperationalStatus -join '/'; tur=$_.BusType.ToString(); surucu=if($f){[string]$f.DriveLetter + ':'}else{'-'} }
})
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram = @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
  [pscustomobject]@{ boyut=[int64]$_.Capacity; hiz=$_.Speed; uretici=$_.Manufacturer; slot=$_.DeviceLocator }
})
$gpu = @(Get-CimInstance Win32_VideoController | ForEach-Object { [pscustomobject]@{ ad=$_.Name; ram=[int64]$_.AdapterRAM; surum=$_.DriverVersion } })
[pscustomobject]@{
  cpu = [pscustomobject]@{ ad=$cpu.Name; cekirdek=$cpu.NumberOfCores; mantiksal=$cpu.NumberOfLogicalProcessors
    hiz=$cpu.MaxClockSpeed; soket=$cpu.SocketDesignation }
  diskler = $disk; ramler = $ram; ekranKartlari = $gpu
  sistem = (Get-CimInstance Win32_ComputerSystem).Model
  uretici = (Get-CimInstance Win32_ComputerSystem).Manufacturer
  bios = (Get-CimInstance Win32_BIOS).SMBIOSBIOSVersion
} | ConvertTo-Json -Compress -Depth 5""", 120)
    if not isinstance(d, dict):
        d = {}
    for x in d.get("diskler", []) or []:
        x["boyutYazi"] = insan(x.get("boyut") or 0)
    for x in d.get("ramler", []) or []:
        x["boyutYazi"] = insan(x.get("boyut") or 0)
    for x in d.get("ekranKartlari", []) or []:
        x["ramYazi"] = insan(x.get("ram") or 0)
    bat = ps(r"""
$b = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
if ($b) {
  $f = Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue
  $s = Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData -ErrorAction SilentlyContinue
  $v = [pscustomobject]@{ var=$true; tasarim=$s.DesignedCapacity; tam=$f.FullChargedCapacity }
} else { $v = [pscustomobject]@{ var=$false; tasarim=$null; tam=$null } }
$v | ConvertTo-Json -Compress""", 60)
    if not isinstance(bat, dict):
        try:
            bat = json.loads((bat or "").strip().splitlines()[-1]) if (bat or "").strip() else None
        except Exception:
            bat = None
    d["batarya"] = bat if isinstance(bat, dict) else {"var": False, "not": "okunamadı"}
    d["surucuPaket"] = 0
    try:
        d["surucuPaket"] = int(ps(r"(pnputil /enum-drivers | Select-String 'Published Name|Yayımlanan Ad').Count", 90) or "0")
    except Exception:
        pass
    d["ssdSicaklik"] = ps(r"""
try {
  $t = Get-CimInstance -Namespace root/wmi -ClassName MSStorageDriver_ATAPISmartData -ErrorAction Stop
  'SMART okunabilir'
} catch { 'DESTEKLENMIYOR' }""", 40)
    return d


# ============================================================================
# WORD UYUMLU RAPOR (.doc)
# ============================================================================

def api_rapor_word():
    r = api_rapor()
    d = r["durum"]
    t = r["temizlik"]
    g = r["guvenlik"] or {}
    tr = api_turbo_tara()
    ag = {"ping": {}, "dns": {"sonuc": []}}
    try:
        ag = api_ag_tara()
    except Exception:
        pass
    def satir(ad, deger, renk="#dbeafe"):
        return ('<tr><td class="a">%s</td><td class="b">%s</td></tr>' % (ad, deger))
    ic = []
    ic.append("<h1>ÜSTAD PC OPTIMIZER — SİSTEM VE BAKIM RAPORU</h1>")
    ic.append('<p class="alt">Tarih: %s &nbsp;·&nbsp; Bilgisayar: %s &nbsp;·&nbsp; '
              'Bu rapor kendi bilgisayarınızda üretildi, hiçbir veri internet\'e gönderilmedi.</p>' % (r["tarih"], d.get("osAd")))
    ic.append('<h2>1. GENEL DURUM</h2><table>')
    ic.append(satir("İşletim sistemi", "%s (Yapı %s)" % (d.get("osAd"), d.get("osYapi"))))
    ic.append(satir("İşlemci", "%s — %s çekirdek" % (d.get("cpuAd"), d.get("cpuCekirdek"))))
    ic.append(satir("Bellek", "%s / %s (%d%%)" % (insan(d.get("ramKullanilan", 0)), insan(d.get("ramToplam", 0)), d.get("ramYuzde", 0))))
    ic.append(satir("Disk (C:)", "%s boş / %s (%d%% dolu)" % (insan(d.get("diskBos", 0)), insan(d.get("diskToplam", 0)), d.get("diskYuzde", 0))))
    ic.append(satir("Sağlık puanı", "%s / 100 — %s" % (d.get("puan"), d.get("puanYazi"))))
    ic.append(satir("TURBO puanı", "%s / 100 — uygulanabilir madde: %s" % (tr["puan"], tr["uygulanabilir"])))
    ic.append(satir("Çalışma süresi", _sure(d.get("calismaSn", 0))))
    ic.append("</table>")
    ic.append('<h2>2. TEMİZLENEBİLİR ALANLAR — toplam %s</h2><table>' % t["toplamYazi"])
    for k in t["kategoriler"]:
        ic.append(satir(k["ad"], "%s (%d dosya)" % (k["boyut"], k["dosya"])))
    ic.append("</table>")
    ic.append('<h2>3. TURBO MOD DURUMU</h2><table>')
    o = tr["olcum"]
    ic.append(satir("Aktif güç planı", o["gucPlani"]))
    ic.append(satir("Nihai Performans planı", "AKTİF" if o["nihaiAktif"] else ("kurulu ama aktif değil" if o["nihaiVar"] else "kurulu değil")))
    ic.append(satir("Görsel efekt ayarı", "performans modu" if o["gorsel"] == 2 else ("ayar yok (varsayılan)" if o["gorsel"] is None else str(o["gorsel"]))))
    ic.append(satir("Oyun çubuğu kaydı", "kapalı" if o["gameDvr"] == 0 else "açık/varsayılan"))
    ic.append(satir("Arka plan izinli uygulama", str(o["arkaPlanUygulama"])))
    ic.append(satir("Telemetri hizmeti (çalışan)", str(o["telemetriAktif"])))
    ic.append(satir("SysMain durumu", str(o["sysmain"])))
    ic.append(satir("Menü gecikme ayarı", str(o["menuGecikme"] if o["menuGecikme"] is not None else "ayar yok")))
    ic.append(satir("Gecikme (ping 8.8.8.8)", "%s ms" % o["pingMs"]))
    ic.append("</table>")
    ic.append('<h2>4. AĞ ÖLÇÜMLERİ</h2><table>')
    p = ag.get("ping") or {}
    ic.append(satir("Gecikme ortalaması", "%s ms (en az %s / en çok %s)" % (p.get("ortalama"), p.get("enAz"), p.get("enCok"))))
    ic.append(satir("Dalgalanma (jitter)", "%s ms" % p.get("jitter")))
    ic.append(satir("Paket kaybı", "%s / %s (%s%%)" % (p.get("kayip"), p.get("gonderilen"), p.get("kayipYuzde"))))
    for x in (ag.get("dns") or {}).get("sonuc", []):
        ic.append(satir("DNS — %s" % x["ad"], "%s ms (%s)" % (x["ms"], x["sunucu"])))
    ic.append("</table>")
    ic.append('<h2>5. BAŞLANGIÇTA AÇILAN ÖGELER (%d)</h2><table>' % r["baslangic"]["toplam"])
    for x in r["baslangic"]["ogeler"]:
        ic.append(satir(x.get("ad"), "KAPALI" if x.get("kapali") else "AÇIK"))
    ic.append("</table>")
    ic.append('<h2>6. GÜVENLİK</h2><table>')
    ic.append(satir("Kurulu antivirüs", ", ".join([u.get("ad", "?") for u in (g.get("urunler") or [])]) or "algılanamadı"))
    ic.append(satir("Defender gerçek zamanlı", "AÇIK" if g.get("gercekZamanli") else "kapalı"))
    ic.append(satir("Güvenlik duvarı", " · ".join(["%s: %s" % (z.get("ad"), z.get("durum")) for z in (g.get("guvenlikDuvari") or [])]) or "okunamadı"))
    ic.append(satir("Kurulu program sayısı", str(r.get("programSayisi"))))
    ic.append("</table>")
    ic.append('<h2>7. DÜRÜST SINIRLAR</h2><table>')
    ic.append(satir("SSD sıcaklığı / kalan ömür", "Bu donanımda okunamıyor (SMART köprüsü desteklenmiyor) — uydurma değer gösterilmez."))
    ic.append(satir("Yönetici gerektiren işlemler", "WinSxS temizliği, gölge kopya, sürücü silme, DNS değiştirme, telemetri kapatma."))
    ic.append(satir("Ölçülmeyen", "Gerçek oyun FPS'i, donanım sıcaklıkları, kullanıcı bazlı ağ limitleri ölçülmedi."))
    ic.append("</table>")
    html = """<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word'>
<head><meta charset="utf-8"><title>ÜSTAD PC OPTIMIZER Raporu</title>
<style>
body{font-family:'Segoe UI',Calibri,sans-serif;font-size:11pt;color:#0f172a}
h1{background:#0b2545;color:#fff;padding:14px 18px;font-size:19pt;margin:0 0 6px 0;letter-spacing:1px}
h2{background:#12416b;color:#ffffff;padding:8px 14px;font-size:13pt;margin:18px 0 6px 0;letter-spacing:.5px}
p.alt{color:#475569;font-size:10pt;margin:0 0 10px 0}
table{width:100%;border-collapse:collapse;margin-bottom:8px}
td{padding:6px 10px;border-bottom:1px solid #cbd5e1;font-size:10.5pt}
td.a{width:34%;color:#0b2545;font-weight:600;background:#eef4fb}
tr:nth-child(even) td{background:#f8fafc}
</style></head><body>""" + "\n".join(ic) + """
<p class="alt">Bu belge ÜSTAD PC OPTIMIZER v%s tarafından Kenan Kuzucu için üretildi.</p>
</body></html>""" % SURUM
    masa = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if not os.path.isdir(masa):
        masa = os.path.join(os.path.expanduser("~"), "Desktop")
    ad = "USTAD-PC-OPTIMIZER-RAPOR-%s.doc" % time.strftime("%Y-%m-%d")
    yol = os.path.join(masa, ad)
    try:
        with open(yol, "w", encoding="utf-8-sig") as f:
            f.write(html)
    except Exception as e:
        return {"ok": False, "mesaj": "Rapor yazılamadı: %s" % e}
    return {"ok": True, "yol": yol, "mesaj": "Renkli Word raporu masaüstüne kaydedildi: %s" % ad}


# ============================================================================
# GECMIS — saglik puani gecmisi + acilis suresi kayitlari
# ============================================================================

GECMIS_DOSYA = os.path.join(KOK, "gecmis.json")
GECMIS_ARALIK = 600  # saniye: en sik bu kadar sik kayit alinir


def _gecmis_oku():
    try:
        with open(GECMIS_DOSYA, encoding="utf-8") as f:
            v = json.load(f)
        if isinstance(v, dict) and isinstance(v.get("anlik"), list):
            return v
    except Exception:
        pass
    return {"anlik": []}


def _gecmis_kaydet(v):
    try:
        with open(GECMIS_DOSYA, "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def api_gecmis():
    """Saglik puani gecmisi (en fazla 10 dakikada bir kayit) + DISM acilis kayitlari."""
    g = _gecmis_oku()
    anlik = g.get("anlik", [])
    simdi = time.time()
    yeni = False
    if not anlik or (simdi - float(anlik[-1].get("ts", 0))) >= GECMIS_ARALIK:
        d = api_durum()
        anlik.append({"ts": int(simdi), "tarih": time.strftime("%d.%m.%Y %H:%M"),
                      "puan": d.get("puan"), "cpu": d.get("cpuYuk"), "ram": d.get("ramYuzde"),
                      "disk": d.get("diskYuzde"), "bos": d.get("diskBos")})
        anlik = anlik[-240:]
        g["anlik"] = anlik
        _gecmis_kaydet(g)
        yeni = True
    acilis = ps_json(r"""
$g = @(Get-WinEvent -LogName 'Microsoft-Windows-Diagnostics-Performance/Operational' -MaxEvents 40 -ErrorAction SilentlyContinue |
  Where-Object { $_.Id -in 100, 101, 102, 103 } | ForEach-Object {
    $x = [xml]$_.ToXml()
    $ms = 0
    foreach ($n in $x.Event.EventData.Data) { if ($n.Name -match 'BootTime|MainPathBootTime') { $ms = [int]$n.'#text' } }
    [pscustomobject]@{ id=$_.Id; tarih=$_.TimeCreated.ToString('dd.MM.yyyy HH:mm'); ms=$ms
                       olay=if($_.Id -eq 100){'Açılış'}elseif($_.Id -eq 101){'Kapanış'}else{'Bekleme/Gecikme'} }
  })
@($g) | ConvertTo-Json -Compress -Depth 3""", 120)
    if isinstance(acilis, dict):
        acilis = [acilis]
    if not isinstance(acilis, list):
        acilis = []
    return {"anlik": anlik, "kayitSayisi": len(anlik), "yeniKayit": yeni,
            "acilis": acilis, "aralikSn": GECMIS_ARALIK,
            "acilisVar": bool(acilis), "yol": GECMIS_DOSYA}


# ============================================================================
# PENCERE — panel penceresini gercekten kucult / buyut / kapat (Win32 API)
# ============================================================================

def _pencere_bul():
    """Basligi 'PC OPTIMIZER' olan gorunur tarayici penceresini bulur."""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return []
    u = ctypes.windll.user32
    bulunan = []
    TIP = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lp):
        try:
            if not u.IsWindowVisible(hwnd):
                return True
            n = u.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            tbuf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(hwnd, tbuf, n + 1)
            baslik = tbuf.value
            if "PC OPTIMIZER" not in baslik.upper():
                return True
            cbuf = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(hwnd, cbuf, 256)
            sinif = cbuf.value
            if sinif.startswith("Chrome_WidgetWin") or "MozillaWindowClass" in sinif:
                bulunan.append((hwnd, baslik, sinif))
        except Exception:
            pass
        return True

    try:
        u.EnumWindows(TIP(_cb), 0)
    except Exception:
        return []
    return bulunan


def api_pencere(islem):
    """islem: kucult | buyut | kapat | durum"""
    import ctypes
    u = ctypes.windll.user32
    SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
    p = _pencere_bul()
    if not p:
        return {"ok": False, "hata": "Panel penceresi bulunamadı (tarayıcı penceresi kapalı olabilir)."}
    hwnd, baslik, sinif = p[0]
    durum_once = {"kucultulmus": bool(u.IsIconic(hwnd)), "buyutulmus": bool(u.IsZoomed(hwnd))}
    if islem == "kucult":
        u.ShowWindow(hwnd, SW_MINIMIZE)
    elif islem == "buyut":
        if u.IsZoomed(hwnd):
            u.ShowWindow(hwnd, SW_RESTORE)
        else:
            u.ShowWindow(hwnd, SW_MAXIMIZE)
    elif islem == "kapat":
        u.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(0.6)
    if islem == "kapat":
        hala = bool(u.IsWindow(hwnd))
        return {"ok": True, "islem": islem, "kapandi": not hala,
                "mesaj": "Panel penceresi kapatıldı." if not hala else "Kapatma isteği gönderildi.",
                "pencere": baslik}
    durum = {"kucultulmus": bool(u.IsIconic(hwnd)), "buyutulmus": bool(u.IsZoomed(hwnd))}
    yazi = {"kucult": "Panel küçültüldü — görev çubuğundan geri açabilirsin.",
            "buyut": "Panel büyütüldü." if durum["buyutulmus"] else "Panel eski boyutuna döndü.",
            "durum": "Pencere durumu okundu."}.get(islem, "Tamam.")
    return {"ok": True, "islem": islem, "once": durum_once, "sonra": durum,
            "pencere": baslik, "mesaj": yazi}


# ============================================================================
# v1.2.0 — A) CANLI IZLEME · HIZ TESTI · BENCHMARK · HIZLI CEVAP
# ============================================================================

BENCH_DOSYA = os.path.join(KOK, "bench.json")
ALARM_DOSYA = os.path.join(KOK, "alarm.json")


def _json_oku(yol, varsayilan):
    try:
        with open(yol, encoding="utf-8") as f:
            v = json.load(f)
        if isinstance(v, dict):
            return v
    except Exception:
        pass
    return dict(varsayilan)


def _json_yaz(yol, v):
    try:
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def canli_olcum():
    """Anlik CPU / RAM / disk / sicaklik / fan (tek PowerShell cagrisi)."""
    v = ps_json(r"""
$cpu = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'").PercentProcessorTime
$os  = Get-CimInstance Win32_OperatingSystem
$dk  = (Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name='_Total'").PercentDiskTime
$sicak = $null
try { $t = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | Select-Object -First 1
      if ($t) { $sicak = [math]::Round(($t.CurrentTemperature / 10) - 273.15, 1) } } catch { $sicak = $null }
$fan = $null
try { $f = Get-CimInstance Win32_Fan -ErrorAction Stop | Select-Object -First 1; if ($f) { $fan = [int]$f.DesiredSpeed } } catch { $fan = $null }
$hiz = 0
try { $hiz = [int](Get-CimInstance Win32_Processor | Select-Object -First 1).CurrentClockSpeed } catch { $hiz = 0 }
$top = [math]::Round($os.TotalVisibleMemorySize / 1024)
$bos = [math]::Round($os.FreePhysicalMemory / 1024)
[pscustomobject]@{
  cpu = [int]$cpu
  ramToplamMB = [int]$top
  ramBosMB = [int]$bos
  ramYuzde = [int](100 - ($bos / [math]::Max(1,$top) * 100))
  disk = [int]$dk
  sicakC = $sicak
  fanRpm = $fan
  cpuMhz = $hiz
  sureSn = [int]((Get-Date) - $os.LastBootUpTime).TotalSeconds
} | ConvertTo-Json -Compress""", 45)
    if not isinstance(v, dict):
        v = {}
    v["ok"] = bool(v)
    v["zaman"] = time.strftime("%H:%M:%S")
    if not v.get("sicakC"):
        v["sicakNot"] = "Bu donanım sıcaklık sensörü yayınlamıyor (ACPI termal bölge desteklenmiyor)."
    if not v.get("fanRpm"):
        v["fanNot"] = "Fan devri bu donanımda okunamıyor."
    return v


def api_canli():
    return onbellekli("canli", 4, canli_olcum)


def baglanti_olcum():
    """Disariya acik baglantilar + onlari acan surecler."""
    v = ps_json(r"""
$surec = @{}
Get-Process | ForEach-Object { $surec[[int]$_.Id] = $_.ProcessName }
$l = @(Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue |
  Where-Object { $_.RemoteAddress -notmatch '^(127\.|::1|0\.0\.0\.0)' } |
  ForEach-Object {
    [pscustomobject]@{
      uzak = $_.RemoteAddress; port = [int]$_.RemotePort
      pid = [int]$_.OwningProcess
      surec = if ($surec.ContainsKey([int]$_.OwningProcess)) { $surec[[int]$_.OwningProcess] } else { '?' }
      yerelPort = [int]$_.LocalPort
    }
  } | Sort-Object surec, uzak)
@($l) | ConvertTo-Json -Compress -Depth 3""", 60)
    if isinstance(v, dict):
        v = [v]
    if not isinstance(v, list):
        v = []
    ozet = {}
    for x in v:
        if isinstance(x, dict):
            ozet[x.get("surec", "?")] = ozet.get(x.get("surec", "?"), 0) + 1
    return {"baglantilar": v[:120], "toplam": len(v),
            "surecler": sorted([{"ad": k, "adet": s} for k, s in ozet.items()],
                               key=lambda x: -x["adet"])[:12]}


def api_baglantilar():
    return onbellekli("baglantilar", 12, baglanti_olcum)


def _soguk_okuma(yol, blok=4 * 1024 * 1024):
    """Windows FILE_FLAG_NO_BUFFERING ile GERCEK disk okumasi (RAM onbellegini atlar)."""
    import ctypes
    import mmap
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = ctypes.c_void_p
        k32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        k32.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                 ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        h = k32.CreateFileW(str(yol), 0x80000000, 1, None, 3, 0x20000000, None)
        if not h or h == 0xFFFFFFFFFFFFFFFF:
            return None, None
        buf = mmap.mmap(-1, blok)
        taban = ctypes.addressof(ctypes.c_char.from_buffer(buf))
        n = ctypes.c_uint32(0)
        okunan = 0
        t0 = time.time()
        try:
            while True:
                if not k32.ReadFile(ctypes.c_void_p(h), ctypes.c_void_p(taban), blok,
                                    ctypes.byref(n), None):
                    break
                if n.value == 0:
                    break
                okunan += n.value
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))
            buf.close()
        return okunan, time.time() - t0
    except Exception:
        return None, None


def api_disk_hiz():
    """Gercek disk hizi: yazma, okuma (128 MB) + 4K rastgele yazma (IOPS)."""
    import random
    tmp = os.environ.get("TEMP") or KOK
    yol = os.path.join(tmp, "ustad-hiztest.bin")
    MB = 1024 * 1024
    blok = 1 * MB
    adet = 128
    veri = os.urandom(blok)
    sonuc = {"ok": True, "testMB": adet}
    try:
        t0 = time.time()
        with open(yol, "wb") as f:
            for _ in range(adet):
                f.write(veri)
            f.flush()
            os.fsync(f.fileno())
        yaz = time.time() - t0
        boyut = os.path.getsize(yol)
        t0 = time.time()
        okunan = 0
        with open(yol, "rb") as f:
            while True:
                b = f.read(blok)
                if not b:
                    break
                okunan += len(b)
        oku = time.time() - t0
        sonuc.update({
            "yazmaMBs": round(boyut / MB / max(0.001, yaz), 1),
            "okumaMBs": round(okunan / MB / max(0.001, oku), 1),
            "yazmaSn": round(yaz, 2), "okumaSn": round(oku, 2),
        })
        soguk, ssn = _soguk_okuma(yol)
        if soguk:
            sonuc["okumaSogukMBs"] = round(soguk / MB / max(0.001, ssn), 1)
            sonuc["okumaSogukSn"] = round(ssn, 2)
        else:
            sonuc["okumaSogukNot"] = "Önbelleksiz okuma bu sistemde başlatılamadı."
        # 4K rastgele yazma
        parca = 4096
        kucuk = os.urandom(parca)
        t0 = time.time()
        with open(yol, "r+b") as f:
            for _ in range(1500):
                f.seek(random.randrange(0, max(1, boyut - parca)))
                f.write(kucuk)
            f.flush()
            os.fsync(f.fileno())
        rsn = time.time() - t0
        sonuc["rastgeleIOPS"] = int(1500 / max(0.001, rsn))
        sonuc["rastgeleSn"] = round(rsn, 2)
    except Exception as e:
        sonuc = {"ok": False, "hata": str(e)}
    finally:
        try:
            os.remove(yol)
        except Exception:
            pass
    # gecmise kaydet
    if sonuc.get("ok"):
        g = _json_oku(BENCH_DOSYA, {"disk": [], "cpu": [], "ram": []})
        g.setdefault("disk", []).append({"tarih": time.strftime("%d.%m.%Y %H:%M"),
                                         "yazma": sonuc["yazmaMBs"], "okuma": sonuc["okumaMBs"],
                                         "iops": sonuc.get("rastgeleIOPS")})
        g["disk"] = g["disk"][-30:]
        _json_yaz(BENCH_DOSYA, g)
        sonuc["gecmis"] = g["disk"][-8:]
    return sonuc


def _cpu_bench(tekrar=3):
    en_iyi = None
    for _ in range(tekrar):
        t0 = time.time()
        s = 0
        for i in range(900000):
            s += (i * i) % 7919
        sn = time.time() - t0
        puan = round(900000 / max(0.0001, sn) / 1000.0, 2)
        en_iyi = puan if en_iyi is None else max(en_iyi, puan)
    return en_iyi


def _ram_bench():
    t0 = time.time()
    a = bytearray(64 * 1024 * 1024)
    for i in range(0, len(a), 4096):
        a[i] = 7
    b = bytes(a)
    c = bytearray(b)
    sn = time.time() - t0
    return round((64 * 3) / max(0.001, sn) / 100.0, 2)   # MB/sn (yaz+kopya+kopya)


def api_benchmark():
    """CPU + RAM gercek olcum; onceki sonuclarla karsilastirir."""
    cpu = _cpu_bench()
    ram = _ram_bench()
    g = _json_oku(BENCH_DOSYA, {"disk": [], "cpu": [], "ram": []})
    oncekiCpu = g["cpu"][-1]["cpu"] if g.get("cpu") else None
    g.setdefault("cpu", []).append({"tarih": time.strftime("%d.%m.%Y %H:%M"), "cpu": cpu})
    g.setdefault("ram", []).append({"tarih": time.strftime("%d.%m.%Y %H:%M"), "ram": ram})
    g["cpu"] = g["cpu"][-30:]
    g["ram"] = g["ram"][-30:]
    _json_yaz(BENCH_DOSYA, g)
    return {"ok": True, "cpuPuani": cpu, "ramPuani": ram, "oncekiCpu": oncekiCpu,
            "fark": (None if oncekiCpu is None else round(cpu - oncekiCpu, 2)),
            "cpuGecmis": g["cpu"][-10:], "ramGecmis": g["ram"][-10:],
            "birim": "puan (yüksek = hızlı)"}


def api_hizli():
    """Panelin ACILIS aninda kullandigi hazir ozet (onbellekten, ~0 sn)."""
    simdi = time.time()
    with _ONB_KILIT:
        hazir = {a: {"yasSn": round(simdi - v[0], 1)} for a, v in _ONB.items()}
    c = _ONB.get("canli")
    d = _ONB.get("durum")
    a = _ONB.get("alarm")
    return {"ok": True, "hazirKayitlar": sorted(hazir.keys()),
            "canli": (c[1] if c else None), "durum": (d[1] if d else None),
            "alarm": (a[1] if a else None), "onbellek": onbellek_durum()}


# ============================================================================
# v1.2.0 — B) KURTARMA · BAKIM · OLAY & AYGIT
# ============================================================================

UNDO_DOSYA = os.path.join(KOK, "geri-al.json")


def _undo_ekle(kayit):
    u = _json_oku(UNDO_DOSYA, {"kayitlar": []})
    u.setdefault("kayitlar", []).append(kayit)
    u["kayitlar"] = u["kayitlar"][-200:]
    _json_yaz(UNDO_DOSYA, u)


def api_geri_noktalari():
    v = ps_json(r"""
$c = if (Get-Command Get-ComputerRestorePoint -ErrorAction SilentlyContinue) {
  @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{ sira=[int]$_.SequenceNumber; aciklama=[string]$_.Description
                       tarih=$_.CreationTime.ToString('dd.MM.yyyy HH:mm') } })
} else { @() }
[pscustomobject]@{ noktalar=@($c); koruma=(Get-CimInstance -ClassName Win32_ShadowStorage -ErrorAction SilentlyContinue | Measure-Object).Count } | ConvertTo-Json -Compress -Depth 4""", 90)
    if not isinstance(v, dict):
        v = {}
    n = v.get("noktalar")
    if isinstance(n, dict):
        n = [n]
    return {"ok": True, "noktalar": n or [], "adet": len(n or []),
            "yonetici": yonetici_mi(),
            "not": "Geri yükleme noktası oluşturmak yönetici ister."}


def api_geri_noktasi_olustur(aciklama=None, zorla=False):
    ad = (aciklama or "").strip() or ("USTAD " + time.strftime("%d.%m.%Y %H:%M"))
    if not yonetici_mi() and not zorla:
        return {"ok": False, "yoneticiGerekli": True, "ad": ad,
                "mesaj": "Geri yükleme noktası yönetici yetkisi ister. 'Yönetici olarak oluştur' düğmesine bas."}
    if not yonetici_mi():
        ps_admin("Checkpoint-Computer -Description %s -RestorePointType 'MODIFY_SETTINGS'"
                 % json.dumps(ad))
        return {"ok": True, "yonetici_ile": True,
                "mesaj": "Geri yükleme noktası için yönetici penceresi açıldı: " + ad}
    c = ps("Checkpoint-Computer -Description %s -RestorePointType 'MODIFY_SETTINGS'; "
           "$r = Get-ComputerRestorePoint | Select-Object -First 1 | "
           "ForEach-Object { $_.Description + ' | ' + $_.CreationTime } ; $r" % json.dumps(ad),
           600)
    return {"ok": True, "olustu": ad in (c or ""), "cikti": c,
            "mesaj": ("Geri yükleme noktası oluşturuldu: " + ad) if ad in (c or "")
                     else "Komut çalıştı, teyit okunamadı."}


def api_surucu_yedek(zorla=False):
    """Kurulu suruculeri klasore aktarir (pnputil /export-driver)."""
    hedef = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop",
                         "USTAD-SURUCU-YEDEK-" + time.strftime("%d.%m.%Y"))
    if not os.path.isdir(os.path.dirname(hedef)):
        hedef = os.path.join(KOK, "surucu-yedek-" + time.strftime("%d.%m.%Y"))
    komut = "pnputil /export-driver * %s" % json.dumps(hedef)
    if not yonetici_mi() and not zorla:
        return {"ok": False, "yoneticiGerekli": True, "hedef": hedef,
                "mesaj": "Sürücü yedeği yönetici yetkisi ister. 'Yönetici olarak yedekle' düğmesine bas."}
    if not yonetici_mi():
        ps_admin(komut + "; Write-Host 'BITTI'; pause")
        return {"ok": True, "yonetici_ile": True, "hedef": hedef,
                "mesaj": "Sürücü yedeği için yönetici penceresi açıldı → " + hedef}
    c = ps(komut, 900)
    sayi = len([x for x in os.listdir(hedef)]) if os.path.isdir(hedef) else 0
    return {"ok": True, "hedef": hedef, "surucuSayisi": sayi,
            "mesaj": "%d sürücü paketi yedeklendi → %s" % (sayi, hedef), "cikti": (c or "")[-400:]}


def _yedeklenecek_klasorler():
    kok = os.path.expanduser("~")
    adaylar = [("Belgeler", os.path.join(kok, "Documents")), ("Masaüstü", os.path.join(kok, "Desktop")),
               ("Resimler", os.path.join(kok, "Pictures")), ("Videolar", os.path.join(kok, "Videos")),
               ("Müzik", os.path.join(kok, "Music")), ("İndirilenler", os.path.join(kok, "Downloads"))]
    out = []
    for ad, yol in adaylar:
        if os.path.isdir(yol):
            try:
                b = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(yol) for f in fs)
            except Exception:
                b = 0
            out.append({"ad": ad, "yol": yol, "bayt": b, "boyut": insan(b)})
    return out


def api_yedek_liste():
    d = _json_oku(BENCH_DOSYA, {"disk": [], "cpu": [], "ram": []})
    hedef = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if not os.path.isdir(hedef):
        hedef = os.path.join(os.path.expanduser("~"), "Desktop")
    klasorler = _yedeklenecek_klasorler()
    return {"ok": True, "klasorler": klasorler,
            "toplamBayt": sum(k["bayt"] for k in klasorler),
            "toplam": insan(sum(k["bayt"] for k in klasorler)),
            "varsayilanHedef": hedef, "gecmis": d.get("yedek", [])}


def api_yedek_klasor(secili=None, hedef=None):
    import zipfile
    secili = secili or []
    klasorler = {k["ad"]: k["yol"] for k in _yedeklenecek_klasorler()}
    secili = [s for s in secili if s in klasorler]
    if not secili:
        return {"ok": False, "hata": "Yedeklenecek klasör seçilmedi."}
    hedef = hedef or os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if not os.path.isdir(hedef):
        hedef = os.path.join(os.path.expanduser("~"), "Desktop")
    ad = "USTAD-YEDEK-%s.zip" % time.strftime("%Y-%m-%d_%H-%M")
    yol = os.path.join(hedef, ad)
    sayi = 0
    try:
        with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for s in secili:
                kok = klasorler[s]
                for dp, _, fs in os.walk(kok):
                    for f in fs:
                        tam = os.path.join(dp, f)
                        try:
                            if os.path.getsize(tam) > 2000 * 1024 * 1024:
                                continue
                            z.write(tam, os.path.join(s, os.path.relpath(tam, kok)))
                            sayi += 1
                        except Exception:
                            continue
    except Exception as e:
        return {"ok": False, "hata": str(e)}
    b = os.path.getsize(yol)
    d = _json_oku(BENCH_DOSYA, {"disk": [], "cpu": [], "ram": []})
    d.setdefault("yedek", []).append({"tarih": time.strftime("%d.%m.%Y %H:%M"), "dosya": ad,
                                      "boyut": insan(b), "klasor": ", ".join(secili)})
    d["yedek"] = d["yedek"][-20:]
    _json_yaz(BENCH_DOSYA, d)
    return {"ok": True, "yol": yol, "dosyaSayisi": sayi, "boyut": insan(b),
            "mesaj": "%d dosya yedeklendi (%s) → %s" % (sayi, insan(b), yol)}


def api_yedek_gorevi(kur=True, saat="21:00"):
    """Gunluk otomatik klasor yedegi (zamanlanmis gorev)."""
    ad = "USTAD-PC-OPTIMIZER-YEDEK"
    if not kur:
        ps("Unregister-ScheduledTask -TaskName '%s' -Confirm:$false" % ad, 90)
        teyit = ps("(Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue).TaskName" % ad, 60)
        return {"ok": True, "kaldirildi": ad not in (teyit or ""), "mesaj": "Yedek görevi kaldırıldı."}
    py = sys.executable
    betik = os.path.join(KOK, "sunucu.py")
    komut = ("Register-ScheduledTask -TaskName '%s' -Force "
             "-Action (New-ScheduledTaskAction -Execute '%s' -Argument '\"%s\" --yedek' "
             "-WorkingDirectory '%s') "
             "-Trigger (New-ScheduledTaskTrigger -Daily -At %s) "
             "-Description 'USTAD PC OPTIMIZER gunluk otomatik klasor yedegi' | Out-Null"
             % (ad, py.replace("'", "''"), betik.replace("'", "''"),
                KOK.replace("'", "''"), saat))
    ps(komut, 180)
    teyit = ps("(Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue).TaskName" % ad, 60)
    return {"ok": True, "kuruldu": ad in (teyit or ""), "saat": saat, "gorev": ad,
            "mesaj": "Günlük yedek görevi %s için kuruldu." % saat if ad in (teyit or "")
                     else "Görev kurulamadı."}


def api_olay_gunlugu(gun=7):
    """Son N gunun kritik/onemli olaylari, sade Turkce ozetli."""
    v = ps_json(r"""
$b = (Get-Date).AddDays(-%d)
$o = @(Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2,3;StartTime=$b} -MaxEvents 400 -ErrorAction SilentlyContinue |
  Group-Object ProviderName, Id | ForEach-Object {
    $ilk = $_.Group[0]
    [pscustomobject]@{
      kaynak = [string]$ilk.ProviderName
      id = [int]$ilk.Id
      seviye = if ($ilk.Level -eq 1) {'KRİTİK'} elseif ($ilk.Level -eq 2) {'HATA'} else {'UYARI'}
      adet = [int]$_.Count
      son = $ilk.TimeCreated.ToString('dd.MM.yyyy HH:mm')
      mesaj = ([string]$ilk.Message -replace '\s+',' ').Substring(0, [math]::Min(150, ([string]$ilk.Message).Length))
    }
  } | Sort-Object -Property @{Expression='adet';Descending=$true})
[pscustomobject]@{ olaylar=@($o); toplam=($o | Measure-Object -Property adet -Sum).Sum } | ConvertTo-Json -Compress -Depth 4
""" % int(gun), 120)
    if not isinstance(v, dict):
        v = {}
    o = v.get("olaylar")
    if isinstance(o, dict):
        o = [o]
    return {"ok": True, "olaylar": o or [], "toplamOlay": v.get("toplam") or 0, "gun": gun,
            "not": "Sistem günlüğü (System) okundu — kritik/hata/uyarı seviyeleri."}


def api_aygit_sorunlu():
    v = ps_json(r"""
$h = @(Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
      $_.Status -eq 'Error' -or $_.Status -eq 'Degraded' } |
  ForEach-Object {
    [pscustomobject]@{ ad=[string]$_.FriendlyName; sinif=[string]$_.Class
                       durum=[string]$_.Status; id=[string]$_.InstanceId }
  })
$k = @(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object {
      $_.ConfigManagerErrorCode -ne 0 -and $_.ConfigManagerErrorCode -ne 45 } |
  ForEach-Object {
    [pscustomobject]@{ ad=[string]$_.Name; kod=[int]$_.ConfigManagerErrorCode
                       aciklama=[string]$_.Status }
  })
[pscustomobject]@{ bozuk=@($h); kodlu=@($k); toplamCihaz=@(Get-PnpDevice -ErrorAction SilentlyContinue).Count } |
  ConvertTo-Json -Compress -Depth 4""", 240)
    if not isinstance(v, dict):
        v = {}
    b = v.get("bozuk")
    if isinstance(b, dict):
        b = [b]
    kk = v.get("kodlu")
    if isinstance(kk, dict):
        kk = [kk]
    b, kk = b or [], kk or []
    kod = {1: "Bu aygıt düzgün yapılandırılmamış", 3: "Sürücü bozuk veya eksik",
           10: "Aygıt başlatılamıyor", 12: "Yeterli kaynak yok",
           18: "Sürücüler yeniden kurulmalı", 19: "Kayıt defteri bozuk",
           28: "Sürücü kurulu değil", 43: "Windows bu aygıtı durdurdu (sürücü hatası)",
           45: "Aygıt şu an bağlı değil"}
    for x in kk:
        if isinstance(x, dict):
            x["sade"] = kod.get(x.get("kod"), "Aygıt Yöneticisi'nden bakılmalı")
    return {"ok": True, "aygitlar": b, "adet": len(b), "kodlular": kk, "kodluAdet": len(kk),
            "toplamCihaz": v.get("toplamCihaz") or 0,
            "not": ("Sorunlu aygıt yok — tüm aygıtlar çalışıyor." if not b and not kk
                    else "Bu aygıtların sürücüsü eksik/bozuk. Aygıt Yöneticisi'nden güncellenebilir.")}


def _gorev_kod_metni(k):
    """Zamanlanmis gorev sonuc kodunu sade Turkce'ye cevirir."""
    try:
        n = int(str(k).strip() or "-1")
    except Exception:
        return ""
    d = {
        "0": "Başarılı", "1": "Hatalı (kod 1)", "267009": "Şu an çalışıyor",
        "267010": "Devre dışı", "267011": "Hiç çalışmadı", "267012": "Kullanıcı oturumu yok",
        "267013": "Sona erdi (durduruldu)", "267014": "Sona erdi (sistem kapandı)",
        "267015": "Sona erdi (süre aşıldı)", "-2147024891": "Yetki yok",
        "2147942401": "Program bulunamadı", "2147942402": "Program başlatılamadı",
        "3221225786": "İptal edildi (Ctrl+C)", "2147943716": "Program yolu hatalı",
    }
    t = d.get(str(n))
    if t:
        return t
    if n > 0x80000000:
        return "Hata kodu 0x%X" % n
    return "Kod %d" % n


def api_gorevler(ara=""):
    v = ps_json(r"""
$t = @(Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object {
  $ad = [string]$_.TaskName
  $yol = [string]$_.TaskPath
  $durum = [string]$_.State
  $yayin = [string]$_.Author
  $son = ''
  $kod = ''
  try {
    $b = Get-ScheduledTaskInfo -TaskName $ad -TaskPath $yol -ErrorAction Stop
    if ($b) {
      $kod = [string]$b.LastTaskResult
      if ($b.LastRunTime) { $son = $b.LastRunTime.ToString('dd.MM.yyyy HH:mm') }
    }
  } catch { }
  $tet = ''
  try { $tet = (($_.Triggers | ForEach-Object { [string]$_.CimClass.CimClassName }) -join ',') } catch { }
  [pscustomobject]@{ ad=$ad; yol=$yol; durum=$durum; yayin=$yayin; son=$son; sonucKod=$kod; tetik=$tet }
} | Sort-Object durum, ad)
[pscustomobject]@{ gorevler=@($t); toplam=$t.Count } | ConvertTo-Json -Compress -Depth 4""", 240)
    if not isinstance(v, dict):
        v = {}
    if not v.get("gorevler") and not v.get("toplam"):
        v = ps_json(r"""
$c = @(Get-CimInstance -Namespace root/Microsoft/Windows/TaskScheduler -ClassName MSFT_ScheduledTask -ErrorAction SilentlyContinue |
  ForEach-Object {
    [pscustomobject]@{ ad=[string]$_.TaskName; yol=[string]$_.TaskPath; durum=[string]$_.State
                       yayin=[string]$_.Author; son=''; sonucKod=''; tetik='' }
  })
[pscustomobject]@{ gorevler=@($c); toplam=$c.Count } | ConvertTo-Json -Compress -Depth 4""", 240)
        if not isinstance(v, dict):
            v = {}
    g = v.get("gorevler")
    if isinstance(g, dict):
        g = [g]
    g = g or []
    for x in g:
        if isinstance(x, dict):
            x["kodMetni"] = _gorev_kod_metni(x.get("sonucKod"))
            x["acik"] = str(x.get("durum")) in ("Ready", "Running")
    a = (ara or "").strip().lower()
    if a:
        g = [x for x in g if a in str(x.get("ad", "")).lower() or a in str(x.get("yol", "")).lower()]
    return {"ok": True, "gorevler": g, "adet": len(g), "toplam": v.get("toplam") or len(g),
            "kapali": len([x for x in g if str(x.get("durum")) == "Disabled"]),
            "calisan": len([x for x in g if str(x.get("durum")) == "Running"])}


def api_gorev_degistir(ad, yol="\\", kapat=True, zorla=False):
    if not ad:
        return {"ok": False, "hata": "Görev adı gerekli."}
    islem = "Disable-ScheduledTask" if kapat else "Enable-ScheduledTask"
    yolPs = ("-TaskPath '%s'" % (yol or "\\").replace("'", "''")) if (yol or "\\").strip("\\") else ""
    varMi = ps("(Get-ScheduledTask -TaskName '%s' %s -ErrorAction SilentlyContinue).TaskName"
               % (ad.replace("'", "''"), yolPs), 60)
    if not (varMi or "").strip():
        return {"ok": False, "hata": "Görev bulunamadı: %s" % ad}
    komut = "%s -TaskName '%s' %s" % (islem, ad.replace("'", "''"), yolPs)
    merkez = ps(komut + " | Out-Null", 90)
    teyit = ps_json("@(Get-ScheduledTask -TaskName '%s' %s -ErrorAction SilentlyContinue | "
                    "ForEach-Object { [string]$_.State }) | ConvertTo-Json -Compress"
                    % (ad.replace("'", "''"), yolPs), 60)
    durum = str(teyit) if teyit is not None else ""
    oldu = ("Disabled" in durum) if kapat else ("Ready" in durum or "Running" in durum)
    if oldu or merkez is not None:
        _undo_ekle({"tur": "gorev", "ad": ad, "yol": yol, "oncekiDurum": "Disabled" if not kapat else "Ready",
                    "tarih": time.strftime("%d.%m.%Y %H:%M"), "aciklama": "Görev %s" % ("kapatıldı" if kapat else "açıldı")})
    if not oldu and not yonetici_mi():
        if zorla:
            ps_admin(komut)
            return {"ok": True, "yonetici_ile": True, "dogrulandi": False,
                    "mesaj": "Görev için yönetici penceresi açıldı — işlem orada tamamlanacak."}
        return {"ok": False, "yoneticiGerekli": True, "dogrulandi": False,
                "mesaj": "Bu görev yönetici yetkisi istiyor. 'Yönetici olarak dene' düğmesine bas."}
    return {"ok": True, "dogrulandi": bool(oldu), "durum": durum,
            "mesaj": "%s %s." % (ad, "kapatıldı" if kapat else "açıldı") if oldu
                     else "Komut gönderildi, teyit alınamadı (yönetici gerekebilir)."}


def api_hizmetler_detay(ara=""):
    v = ps_json(r"""
$s = @(Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ ad=[string]$_.Name; etiket=[string]$_.DisplayName
                     durum=[string]$_.State; baslangic=[string]$_.StartMode
                     pid=[int]$_.ProcessId }
} | Sort-Object etiket)
[pscustomobject]@{ hizmetler=@($s); toplam=$s.Count } | ConvertTo-Json -Compress -Depth 3""", 120)
    if not isinstance(v, dict):
        v = {}
    s = v.get("hizmetler")
    if isinstance(s, dict):
        s = [s]
    s = s or []
    a = (ara or "").strip().lower()
    if a:
        s = [x for x in s if a in str(x.get("ad", "")).lower() or a in str(x.get("etiket", "")).lower()]
    return {"ok": True, "hizmetler": s, "adet": len(s), "toplam": v.get("toplam") or 0,
            "calisan": len([x for x in s if str(x.get("durum")) == "Running"]),
            "yonetici": yonetici_mi()}


def api_hizmet_degistir(ad, islem="durdur", baslangic=None, zorla=False):
    if not ad:
        return {"ok": False, "hata": "Hizmet adı gerekli."}
    varMi = ps("(Get-CimInstance Win32_Service -Filter %s -ErrorAction SilentlyContinue | "
               "Measure-Object).Count" % json.dumps("Name='%s'" % ad), 45)
    if str(varMi).strip() in ("0", ""):
        return {"ok": False, "hata": "Hizmet bulunamadı: %s" % ad}
    onceki = ps_json("Get-CimInstance Win32_Service -Filter %s | "
                     "Select-Object State,StartMode | ConvertTo-Json -Compress" % json.dumps("Name='%s'" % ad), 45)
    if not isinstance(onceki, dict):
        onceki = {}
    if islem == "durum":
        return {"ok": True, "dogrulandi": bool(onceki), "sonra": onceki,
                "mesaj": "%s → %s (%s)" % (ad, onceki.get("State"), onceki.get("StartMode"))}
    if islem == "baslat":
        komut = "Start-Service -Name %s" % json.dumps(ad)
    elif islem == "baslangic" and baslangic in ("Automatic", "Manual", "Disabled"):
        komut = "Set-Service -Name %s -StartupType %s" % (json.dumps(ad), baslangic)
    else:
        komut = "Stop-Service -Name %s -Force" % json.dumps(ad)
    c = ps(komut + " -ErrorAction Stop", 120)
    teyit = ps_json("@(Get-CimInstance Win32_Service -Filter %s | "
                    "Select-Object State,StartMode) | ConvertTo-Json -Compress" % json.dumps("Name='%s'" % ad),
                    45)
    if isinstance(teyit, list) and teyit:
        teyit = teyit[0]
    if isinstance(teyit, dict) and teyit:
        _undo_ekle({"tur": "hizmet", "ad": ad, "onceki": onceki, "tarih": time.strftime("%d.%m.%Y %H:%M"),
                    "aciklama": "Hizmet %s" % islem})
        _undo_ekle_ozet()

    if not (isinstance(teyit, dict) and teyit):
        if not yonetici_mi():
            if zorla:
                ps_admin(komut)
                return {"ok": True, "yonetici_ile": True, "dogrulandi": False,
                        "mesaj": "Hizmet için yönetici penceresi açıldı — işlem orada tamamlanacak."}
            return {"ok": False, "yoneticiGerekli": True,
                    "mesaj": "Bu hizmet yönetici yetkisi istiyor. 'Yönetici olarak dene' düğmesine bas."}
        return {"ok": False, "hata": "Hizmet durumu okunamadı: " + (c or "")[:200]}
    return {"ok": True, "dogrulandi": True, "sonra": teyit, "once": onceki, "hataMetni": (c or "")[:200],
            "mesaj": "%s → %s (%s)" % (ad, teyit.get("State"), teyit.get("StartMode"))}


def _undo_ekle_ozet():
    return True


# ============================================================================
# v1.2.0 — C) AG · GUNCELLEME · TELEMETRI · YAZICI
# ============================================================================

def _wifi_aglar():
    c = ps("netsh wlan show networks mode=bssid", 60)
    aglar = []
    if not c:
        return aglar
    su = None
    for satir in c.splitlines():
        s = satir.strip()
        if s.startswith("SSID ") and "BSSID" not in s:
            if su:
                aglar.append(su)
            su = {"ssid": s.split(":", 1)[1].strip() if ":" in s else "", "sinyal": None,
                  "kanal": None, "bant": "", "bssid": ""}
        elif su is not None:
            if s.lower().startswith("signal") or s.lower().startswith("sinyal"):
                try:
                    su["sinyal"] = int(re.sub(r"[^0-9]", "", s.split(":", 1)[1]))
                except Exception:
                    pass
            elif s.lower().startswith("channel") or s.lower().startswith("kanal"):
                try:
                    su["kanal"] = int(re.sub(r"[^0-9]", "", s.split(":", 1)[1]))
                    su["bant"] = "2.4 GHz" if su["kanal"] and su["kanal"] <= 14 else "5 GHz"
                except Exception:
                    pass
            elif s.lower().startswith("bssid"):
                su["bssid"] = s.split(":", 1)[1].strip()[:17]
    if su:
        aglar.append(su)
    return aglar


def api_wifi():
    aglar = _wifi_aglar()
    kanal = {}
    for a in aglar:
        if a.get("kanal"):
            kanal[a["kanal"]] = kanal.get(a["kanal"], 0) + 1
    en_kalabalik = sorted(kanal.items(), key=lambda x: -x[1])[:1]
    bos = [k for k in range(1, 14) if k not in kanal]
    return {"ok": True, "aglar": aglar[:40], "adet": len(aglar),
            "kanalYogunluk": sorted([{"kanal": k, "ag": v} for k, v in kanal.items()], key=lambda x: x["kanal"]),
            "enKalabalikKanal": (en_kalabalik[0][0] if en_kalabalik else None),
            "onerilenKanal": (bos[0] if bos else (en_kalabalik[0][0] if en_kalabalik else None)),
            "not": "Yönlendiricinde en boş kanalı seçmen hızını artırır." if bos else
                   "Tüm 2.4 GHz kanalları dolu — 5 GHz tercih et."}


def _guncelleme_tara(tur="hepsi"):
    """Windows Update COM ile bekleyen guncellemeleri arar (yavas: 20-90 sn)."""
    filtre = ("$_.Type -eq 'Driver'" if tur == "surucu" else
              ("$_.Type -ne 'Driver'" if tur == "windows" else "$true"))
    return ps_json(r"""
try {
  $s = New-Object -ComObject Microsoft.Update.Session
  $se = $s.CreateUpdateSearcher()
  $r = $null
  foreach ($mod in @(2, 0)) {
    try { $se.ServerSelection = $mod; $r = $se.Search("IsInstalled=0 and IsHidden=0"); break } catch { }
  }
  if (-not $r) { throw 'Windows Update servisine ulaşılamadı (sunucu ayarı).' }
  $l = @()
  foreach ($u in $r.Updates) {
    if (-not (%s)) { continue }
    $l += [pscustomobject]@{
      baslik = [string]$u.Title
      tur = ([string]$u.Type)
      kb = ((([string]$u.Title) | Select-String -Pattern 'KB\d+' -AllMatches).Matches.Value -join ',')
      boyutMB = [math]::Round([double]$u.MaxDownloadSize / 1MB, 1)
    }
  }
  [pscustomobject]@{ ok=$true; guncellemeler=@($l); toplam=$l.Count
                     sonKontrol=(Get-Date).ToString('dd.MM.yyyy HH:mm') } | ConvertTo-Json -Compress -Depth 4
} catch { [pscustomobject]@{ ok=$false; hata=[string]$_.Exception.Message } | ConvertTo-Json -Compress }
""" % filtre, 300)


def api_guncelleme(tur="hepsi"):
    return onbellekli("guncelleme_" + tur, 900, lambda: _guncelleme_tara(tur))


def api_son_guncellemeler():
    v = ps_json(r"""
$h = @(Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending |
  Select-Object -First 12 | ForEach-Object {
    [pscustomobject]@{ kb=[string]$_.HotFixID; aciklama=[string]$_.Description
                       tarih= if ($_.InstalledOn) { ([datetime]$_.InstalledOn).ToString('dd.MM.yyyy') } else { '' } }
  })
$s = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\Results\Install' -ErrorAction SilentlyContinue).LastSuccessTime
[pscustomobject]@{ liste=@($h); sonBasari=[string]$s } | ConvertTo-Json -Compress -Depth 3""", 120)
    if not isinstance(v, dict):
        v = {}
    l = v.get("liste")
    if isinstance(l, dict):
        l = [l]
    return {"ok": True, "liste": l or [], "sonBasari": v.get("sonBasari") or "",
            "adet": len(l or [])}


def api_winget():
    c = ps("winget --version", 60)
    if not c or "winget" not in c.lower() or "bulunamad" in c.lower() or "not recognized" in c.lower():
        return {"ok": False, "kurulu": False,
                "hata": "winget kurulu değil (Microsoft Store → App Installer ile kurulur)."}
    liste = ps("winget upgrade --include-unknown --accept-source-agreements 2>$null", 240)
    satirlar = [s for s in (liste or "").splitlines() if s.strip()]
    paketler = []
    for s in satirlar:
        if "---" in s or not s.strip():
            continue
        p = re.split(r"\s{2,}", s.strip())
        if len(p) >= 3 and p[0] not in ("Name", "Ad"):
            paketler.append({"ad": p[0], "id": p[1] if len(p) > 1 else "",
                             "mevcut": p[2] if len(p) > 2 else "", "yeni": p[3] if len(p) > 3 else ""})
    return {"ok": True, "kurulu": True, "surum": c.strip(), "paketler": paketler[:60],
            "adet": len(paketler)}


def api_winget_guncelle(hepsi=True, kimlik=None):
    if hepsi:
        def _is():
            return ps("winget upgrade --all --include-unknown --silent "
                      "--accept-source-agreements --accept-package-agreements 2>&1", 1800)
        threading.Thread(target=lambda: _is(), daemon=True).start()
        return {"ok": True, "mesaj": "Tüm paketler arka planda güncelleniyor (winget penceresi açık değil, "
                                     "sonuç panelde 'winget' listesinde görünür)."}
    if not kimlik:
        return {"ok": False, "hata": "Paket kimliği gerekli."}
    c = ps("winget upgrade --id %s --silent --accept-source-agreements "
           "--accept-package-agreements 2>&1" % json.dumps(kimlik), 900)
    return {"ok": True, "cikti": (c or "")[-500:]}


def api_telemetri():
    v = ps_json(r"""
$t = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection' -ErrorAction SilentlyContinue).AllowTelemetry
$reklam = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo' -ErrorAction SilentlyContinue).Enabled
$dm = (Get-Service DiagTrack -ErrorAction SilentlyContinue).Status
[pscustomobject]@{
  telemetri = if ($null -eq $t) { 3 } else { [int]$t }
  reklamKimlik = if ($null -eq $reklam) { 1 } else { [int]$reklam }
  diagTrack = [string]$dm
  hedefler = 'Telemetri 0 · Reklam kimliği kapalı · DiagTrack durdurulmuş'
} | ConvertTo-Json -Compress""", 90)
    if not isinstance(v, dict):
        v = {}
    return {"ok": True, "durum": v, "yonetici": yonetici_mi()}


def api_telemetri_kapat(zorla=False):
    yapilan = []
    if not yonetici_mi() and not zorla:
        ps("Set-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo' "
           "-Name Enabled -Value 0 -Type DWord", 60)
        return {"ok": False, "yoneticiGerekli": True,
                "mesaj": "Reklam kimliği kapatıldı. Telemetri+DiagTrack için yönetici gerekir — "
                         "'Yönetici olarak kapat' düğmesine bas."}
    if not yonetici_mi():
        ps_admin("New-Item -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection' -Force | Out-Null; "
                 "Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection' "
                 "-Name AllowTelemetry -Value 0 -Type DWord; "
                 "Set-Service DiagTrack -StartupType Disabled; Stop-Service DiagTrack -Force; "
                 "Write-Host 'TELEMETRI KAPATILDI'; pause")
        ps("Set-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo' "
           "-Name Enabled -Value 0 -Type DWord", 60)
        return {"ok": True, "yonetici_ile": True,
                "mesaj": "Reklam kimliği kapatıldı; telemetri için yönetici penceresi açıldı."}
    ps("New-Item -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection' -Force | Out-Null; "
       "Set-ItemProperty 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection' "
       "-Name AllowTelemetry -Value 0 -Type DWord; "
       "Set-Service DiagTrack -StartupType Disabled; Stop-Service DiagTrack -Force", 180)
    ps("Set-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo' "
       "-Name Enabled -Value 0 -Type DWord", 60)
    teyit = api_telemetri()
    return {"ok": True, "dogrulandi": teyit["durum"].get("telemetri") == 0, "sonra": teyit["durum"],
            "mesaj": "Telemetri 0'a çekildi, DiagTrack durduruldu."}


def api_yazici():
    v = ps_json(r"""
$y = @(Get-Printer -ErrorAction SilentlyContinue | ForEach-Object {
  $k = @(Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue)
  [pscustomobject]@{ ad=[string]$_.Name; durum=[string]$_.PrinterStatus
                     kuyruk=$k.Count; varsayilan=[bool]$_.Default }
})
$s = (Get-Service Spooler -ErrorAction SilentlyContinue).Status
[pscustomobject]@{ yazicilar=@($y); spooler=[string]$s } | ConvertTo-Json -Compress -Depth 3""", 120)
    if not isinstance(v, dict):
        v = {}
    y = v.get("yazicilar")
    if isinstance(y, dict):
        y = [y]
    y = y or []
    return {"ok": True, "yazicilar": y, "adet": len(y), "spooler": v.get("spooler") or "?",
            "kuyrukToplam": sum(int(x.get("kuyruk") or 0) for x in y)}


def api_yazici_temizle(zorla=False):
    if not yonetici_mi() and not zorla:
        return {"ok": False, "yoneticiGerekli": True,
                "mesaj": "Yazıcı kuyruğu temizliği yönetici yetkisi ister. "
                         "'Yönetici olarak temizle' düğmesine bas."}
    if not yonetici_mi():
        ps_admin("Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue | "
                 "Remove-PrintJob -ErrorAction SilentlyContinue }; "
                 "Restart-Service Spooler -Force; Write-Host 'KUYRUK TEMIZLENDI'; pause")
        return {"ok": True, "yonetici_ile": True, "mesaj": "Yazıcı kuyruğu temizliği için yönetici penceresi açıldı."}
    ps("Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue | "
       "Remove-PrintJob -ErrorAction SilentlyContinue }; Restart-Service Spooler -Force", 180)
    teyit = api_yazici()
    return {"ok": True, "dogrulandi": teyit["kuyrukToplam"] == 0, "sonra": teyit["kuyrukToplam"],
            "mesaj": "Yazıcı kuyrukları temizlendi, spooler yeniden başlatıldı."}


# ============================================================================
# v1.2.0 — D) ESIK ALARMI + SESLI UYARI + BILDIRIM
# ============================================================================

def _alarm_varsayilan():
    return {"acik": True, "cpu": 95, "ram": 90, "disk": 90, "sicaklik": 85,
            "telegramToken": "", "telegramChat": "", "sesliUyari": True,
            "sonUyari": "", "sonUyariSn": 0}


def api_alarm():
    a = _json_oku(ALARM_DOSYA, _alarm_varsayilan())
    d = onbellekli("durum", 20, api_durum)
    ihlal = []
    if a.get("acik") and isinstance(d, dict):
        try:
            if int(d.get("cpuYuk") or 0) >= int(a.get("cpu", 90)):
                ihlal.append("İşlemci %%%s (eşik %%%s)" % (d.get("cpuYuk"), a.get("cpu")))
            if int(d.get("ramYuzde") or 0) >= int(a.get("ram", 90)):
                ihlal.append("Bellek %%%s (eşik %%%s)" % (d.get("ramYuzde"), a.get("ram")))
            if int(d.get("diskYuzde") or 0) >= int(a.get("disk", 90)):
                ihlal.append("Disk %%%s (eşik %%%s)" % (d.get("diskYuzde"), a.get("disk")))
            c = _ONB.get("canli")
            sc = (c[1].get("sicakC") if c else None)
            if sc and float(sc) >= float(a.get("sicaklik", 85)):
                ihlal.append("Sıcaklık %s°C (eşik %s°C)" % (sc, a.get("sicaklik")))
        except Exception:
            pass
    return {"ok": True, "ayar": a, "ihlal": ihlal, "alarmVar": bool(ihlal),
            "kontrol": d if isinstance(d, dict) else {}}


def api_alarm_kaydet(v):
    a = _json_oku(ALARM_DOSYA, _alarm_varsayilan())
    for k in ("acik", "sesliUyari"):
        if k in v:
            a[k] = bool(v[k])
    for k in ("cpu", "ram", "disk", "sicaklik"):
        if k in v:
            try:
                a[k] = max(1, min(99, int(v[k])))
            except Exception:
                pass
    for k in ("telegramToken", "telegramChat"):
        if k in v:
            a[k] = str(v[k]).strip()
    _json_yaz(ALARM_DOSYA, a)
    return {"ok": True, "ayar": a, "mesaj": "Alarm ayarları kaydedildi."}


def api_bildirim():
    """Esik asilirsa Telegram'a haber verir (token varsa). Panel sesli uyariyi kendi yapar."""
    a = _json_oku(ALARM_DOSYA, _alarm_varsayilan())
    durum = api_alarm()
    ihlal = durum.get("ihlal") or []
    if not ihlal:
        return {"ok": True, "gonderildi": False, "mesaj": "Eşik aşılmadı, bildirim yok."}
    if time.time() - float(a.get("sonUyariSn") or 0) < 600:
        return {"ok": True, "gonderildi": False, "mesaj": "Son uyarıdan 10 dakika geçmedi (tekrar gönderilmedi).",
                "ihlal": ihlal}
    metin = "ÜSTAD PC OPTIMIZER — UYARI\n" + "\n".join("- " + x for x in ihlal) + \
            "\nBilgisayar: " + socket.gethostname() + " · " + time.strftime("%d.%m.%Y %H:%M")
    tok, soh = a.get("telegramToken"), a.get("telegramChat")
    if tok and soh:
        try:
            import urllib.request as _u
            import urllib.parse as _p
            veri = _p.urlencode({"chat_id": soh, "text": metin}).encode()
            _u.urlopen("https://api.telegram.org/bot%s/sendMessage" % tok, data=veri, timeout=15).read()
            a["sonUyari"] = metin
            a["sonUyariSn"] = int(time.time())
            _json_yaz(ALARM_DOSYA, a)
            return {"ok": True, "gonderildi": True, "kanal": "telegram", "mesaj": "Telegram'a gönderildi.", "ihlal": ihlal}
        except Exception as e:
            return {"ok": False, "gonderildi": False, "hata": "Telegram gönderilemedi: %s" % e, "ihlal": ihlal}
    a["sonUyari"] = metin
    a["sonUyariSn"] = int(time.time())
    _json_yaz(ALARM_DOSYA, a)
    return {"ok": True, "gonderildi": False, "kanal": "panel",
            "mesaj": "Telegram ayarlı değil — uyarı yalnız panelde gösterilecek.", "mesajMetni": metin, "ihlal": ihlal}


def api_geri_al_liste():
    u = _json_oku(UNDO_DOSYA, {"kayitlar": []})
    return {"ok": True, "kayitlar": list(reversed(u.get("kayitlar", [])[-40:])),
            "adet": len(u.get("kayitlar", []))}


# ----------------------------------------------------------------------------
# HTTP sunucu
# ----------------------------------------------------------------------------

class Istek(BaseHTTPRequestHandler):
    server_version = "USTAD-PC-OPTIMIZER/" + SURUM

    def log_message(self, *a):
        pass

    def _gonder(self, veri, tur="application/json; charset=utf-8", kod=200):
        if isinstance(veri, (dict, list)):
            govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        elif isinstance(veri, str):
            govde = veri.encode("utf-8")
        else:
            govde = veri
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(govde)
        except Exception:
            pass

    def do_GET(self):
        u = urlparse(self.path)
        y = u.path
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if y in ("/", "/index.html"):
                with open(os.path.join(KOK, "index.html"), "rb") as f:
                    return self._gonder(f.read(), "text/html; charset=utf-8")
            if y.startswith("/assets/"):
                p = os.path.join(KOK, y.lstrip("/").replace("/", os.sep))
                if os.path.isfile(p):
                    tur = "image/png" if p.lower().endswith(".png") else "application/octet-stream"
                    with open(p, "rb") as f:
                        return self._gonder(f.read(), tur)
                return self._gonder("yok", kod=404)
            if y == "/nabiz":
                return self._gonder({"ok": True, "surum": SURUM, "yonetici": yonetici_mi()})
            if y == "/api/durum":
                nabiz_vur()
                return self._gonder(onbellekli("durum", 15, api_durum, bekle=False))
            if y == "/api/temizlik/tara":
                return self._gonder(api_temizlik_tara())
            if y == "/api/programlar":
                return self._gonder(onbellekli("programlar", 600, api_programlar, bekle=False))
            if y == "/api/baslangic":
                return self._gonder(onbellekli("baslangic", 180, api_baslangic, bekle=False))
            if y == "/api/guvenlik":
                return self._gonder(onbellekli("guvenlik", 120, api_guvenlik, bekle=False))
            if y == "/api/tarama":
                return self._gonder(onbellekli("tarama", 240, api_tarama, bekle=False))
            if y == "/api/servisler":
                return self._gonder(onbellekli("servisler", 90, api_servisler, bekle=False))
            if y == "/api/ram":
                return self._gonder(api_ram_temizle())
            if y == "/api/disk":
                return self._gonder(api_disk_analiz(q.get("yol", "C:\\")))
            if y == "/api/rapor":
                return self._gonder(api_rapor())
            if y == "/api/ayar":
                return self._gonder(api_otomatik_temizlik_durum())
            if y == "/api/turbo":
                return self._gonder(api_turbo_tara())
            if y == "/api/derin":
                return self._gonder(api_derin_tara())
            if y == "/api/ag":
                return self._gonder(onbellekli("ag", 240, api_ag_tara, bekle=False))
            if y == "/api/ag/hiz":
                return self._gonder(api_ag_hiz())
            if y == "/api/kasa":
                return self._gonder(api_kasa())
            if y == "/api/zamanlayici":
                return self._gonder(api_zamanlayici())
            if y == "/api/donanim":
                return self._gonder(onbellekli("donanim", 600, api_donanim, bekle=False))
            if y == "/api/gecmis":
                return self._gonder(api_gecmis())
            if y == "/api/pencere":
                return self._gonder(api_pencere("durum"))
            if y == "/api/nabiz":
                nabiz_vur()
                return self._gonder({"ok": True, "surum": SURUM, "yonetici": yonetici_mi(),
                                     "adres": "http://127.0.0.1:%d" % PORT, "pid": os.getpid()})
            # --- v1.2.0 uçları (okuma) ---
            q = parse_qs(urlparse(self.path).query)
            def _q(ad, varsayilan=None):
                v = q.get(ad)
                return (v[0] if isinstance(v, list) and v else varsayilan)
            if y == "/api/hizli":
                return self._gonder(api_hizli())
            if y == "/api/onbellek":
                return self._gonder(onbellek_durum())
            if y == "/api/canli":
                return self._gonder(api_canli())
            if y == "/api/baglantilar":
                return self._gonder(api_baglantilar())
            if y == "/api/disk-hiz":
                return self._gonder(api_disk_hiz())
            if y == "/api/benchmark":
                return self._gonder(api_benchmark())
            if y == "/api/geri-noktalari":
                return self._gonder(api_geri_noktalari())
            if y == "/api/yedek":
                return self._gonder(api_yedek_liste())
            if y == "/api/olay":
                _g = int(_q("gun", "7") or 7)
                return self._gonder(onbellekli("olay%d" % _g, 300, lambda: api_olay_gunlugu(_g), bekle=False))
            if y == "/api/aygitlar":
                return self._gonder(api_aygit_sorunlu())
            if y == "/api/gorevler":
                _a = _q("ara", "") or ""
                return self._gonder(onbellekli("gorevler" + _a.lower(), 300, lambda: api_gorevler(_a), bekle=False))
            if y == "/api/hizmet":
                _a = _q("ara", "") or ""
                return self._gonder(onbellekli("hizmet" + _a.lower(), 180, lambda: api_hizmetler_detay(_a), bekle=False))
            if y == "/api/wifi":
                return self._gonder(api_wifi())
            if y == "/api/guncelleme":
                return self._gonder(api_guncelleme(_q("tur", "hepsi")))
            if y == "/api/son-guncelleme":
                return self._gonder(api_son_guncellemeler())
            if y == "/api/winget":
                return self._gonder(api_winget())
            if y == "/api/telemetri":
                return self._gonder(api_telemetri())
            if y == "/api/yazici":
                return self._gonder(api_yazici())
            if y == "/api/alarm":
                return self._gonder(api_alarm())
            if y == "/api/geri-al":
                return self._gonder(api_geri_al_liste())
            return self._gonder({"hata": "bilinmeyen uç: " + y}, kod=404)
        except Exception:
            return self._gonder({"hata": traceback.format_exc()}, kod=500)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            ham = self.rfile.read(n) if n else b""
            v = json.loads(ham.decode("utf-8")) if ham else {}
        except Exception:
            v = {}
        y = urlparse(self.path).path
        try:
            if y == "/api/temizlik/temizle":
                return self._gonder(api_temizlik_temizle(v.get("secili") or []))
            if y == "/api/pencere":
                return self._gonder(api_pencere(v.get("islem") or "durum"))
            # --- v1.2.0 uçları (işlem) ---
            if y == "/api/onbellek/bosalt":
                return self._gonder(onbellek_bosalt())
            if y == "/api/geri-noktasi":
                return self._gonder(api_geri_noktasi_olustur(v.get("aciklama"), bool(v.get("zorla"))))
            if y == "/api/surucu-yedek":
                return self._gonder(api_surucu_yedek(bool(v.get("zorla"))))
            if y == "/api/yedek/klasor":
                return self._gonder(api_yedek_klasor(v.get("secili"), v.get("hedef")))
            if y == "/api/yedek/gorevi":
                return self._gonder(api_yedek_gorevi(bool(v.get("kur", True)), v.get("saat") or "21:00")
                                    if v.get("kur") is not False else api_yedek_gorevi(False))
            if y == "/api/gorev":
                return self._gonder(api_gorev_degistir(v.get("ad", ""), v.get("yol") or "\\",
                                                       bool(v.get("kapat", True)),
                                                       bool(v.get("zorla"))))
            if y == "/api/hizmet":
                return self._gonder(api_hizmet_degistir(v.get("ad", ""), v.get("islem") or "durdur",
                                                        v.get("baslangic"), bool(v.get("zorla"))))
            if y == "/api/winget/guncelle":
                return self._gonder(api_winget_guncelle(bool(v.get("hepsi", True)), v.get("kimlik")))
            if y == "/api/telemetri/kapat":
                return self._gonder(api_telemetri_kapat(bool(v.get("zorla"))))
            if y == "/api/yazici/temizle":
                return self._gonder(api_yazici_temizle(bool(v.get("zorla"))))
            if y == "/api/alarm/kaydet":
                return self._gonder(api_alarm_kaydet(v))
            if y == "/api/bildirim":
                return self._gonder(api_bildirim())
            if y == "/api/program/kaldir":
                return self._gonder(api_program_kaldir(v.get("ad", ""), v.get("kaldirma", "")))
            if y == "/api/baslangic/degistir":
                return self._gonder(api_baslangic_degistir(v.get("ad", ""), v.get("kapsam", ""),
                                                          v.get("tur", "Kayıt Defteri"), bool(v.get("kapat"))))
            if y == "/api/gizlilik/temizle":
                return self._gonder(api_gizlilik_temizle())
            if y == "/api/arac":
                return self._gonder(api_araç_calistir(v.get("id", "")))
            if y == "/api/zorla/ara":
                return self._gonder(api_zorla_ara(v.get("ad", "")))
            if y == "/api/zorla/sil":
                return self._gonder(api_zorla_sil(v.get("yollar"), v.get("anahtarlar")))
            if y == "/api/rapor/kaydet":
                return self._gonder(api_rapor_kaydet())
            if y == "/api/ayar/kaydet":
                return self._gonder(api_ayar_kaydet(v))
            if y == "/api/yonetici":
                return self._gonder(api_yonetici())
            if y == "/api/turbo/uygula":
                return self._gonder(api_turbo_uygula(v.get("secili") or []))
            if y == "/api/turbo/geri":
                return self._gonder(api_turbo_geri_al())
            if y == "/api/derin/temizle":
                return self._gonder(api_derin_temizle(v.get("tip", ""), v.get("secim") or []))
            if y == "/api/ag/dns":
                return self._gonder(api_ag_dns_uygula(v.get("sunucu", ""), v.get("adaptor"),
                                                       bool(v.get("geri"))))
            if y == "/api/kasa/geri":
                return self._gonder(api_kasa_geri(v.get("id", ""), v.get("secim")))
            if y == "/api/kasa/bosalt":
                return self._gonder(api_kasa_bosalt(v.get("id")))
            if y == "/api/zamanlayici/kur":
                return self._gonder(api_zamanlayici_kur(v.get("saat", "09:00")))
            if y == "/api/zamanlayici/kaldir":
                return self._gonder(api_zamanlayici_kaldir())
            if y == "/api/rapor/word":
                return self._gonder(api_rapor_word())
            if y == "/api/kapat":
                self._gonder({"ok": True})
                # Kesin kapanis: ONCE port.txt temizligi (daemon thread shutdown sonrasi
                # yarida kesilebilir), SONRA yumusak kapanis + surec sonu.
                def _kapat():
                    try:
                        pt = os.path.join(KOK, "port.txt")
                        with open(pt, encoding="utf-8") as f:
                            satirlar = f.read().splitlines()
                        if len(satirlar) > 1 and satirlar[1].strip() == str(os.getpid()):
                            os.remove(pt)
                    except Exception:
                        pass
                    try:
                        self.server.shutdown()
                    except Exception:
                        pass
                    os._exit(0)
                threading.Thread(target=_kapat, daemon=True).start()
                return
            return self._gonder({"hata": "bilinmeyen uç: " + y}, kod=404)
        except Exception:
            return self._gonder({"hata": traceback.format_exc()}, kod=500)


# ----------------------------------------------------------------------------
# ISINMA (warm-up): agir olcumleri arka planda taze tutar -> panel ANINDA acilir
# ----------------------------------------------------------------------------

ISINMA = [
    ("canli", 4, api_canli),
    ("durum", 15, api_durum),
    ("baglantilar", 12, api_baglantilar),
    ("alarm", 20, api_alarm),
    ("servisler", 90, api_servisler),
    ("guvenlik", 120, api_guvenlik),
    ("wifi", 120, api_wifi),
    ("yazici", 120, api_yazici),
    ("baslangic", 180, api_baslangic),
    ("hizmet", 180, lambda: api_hizmetler_detay("")),
    ("tarama", 240, api_tarama),
    ("olay7", 300, lambda: api_olay_gunlugu(7)),
    ("aygitlar", 300, api_aygit_sorunlu),
    ("gorevler", 300, lambda: api_gorevler("")),
    ("programlar", 600, api_programlar),
    ("donanim", 600, api_donanim),
]



def isinma_dongusu():
    """Agir uclari onbellege tazele. Ayni anda en fazla 3 olcum (makineyi bogmaz)."""
    time.sleep(2)
    while True:
        try:
            simdi = time.time()
            for ad, ara, fn in ISINMA:
                with _ISINMA_KILIT:
                    if ad in _ISINMA_UCAN or len(_ISINMA_UCAN) >= 2:
                        continue
                    k = _ONB.get(ad)
                    if k and (simdi - k[0]) < ara:
                        continue
                    _ISINMA_UCAN.add(ad)

                def _is(ad=ad, fn=fn):
                    try:
                        v = fn()
                        with _ONB_KILIT:
                            _ONB[ad] = (time.time(), v)
                    except Exception:
                        pass
                    finally:
                        with _ISINMA_KILIT:
                            _ISINMA_UCAN.discard(ad)

                threading.Thread(target=_is, daemon=True).start()
        except Exception:
            pass
        time.sleep(5)


def yedek_calistir():
    """--yedek modu: gunluk otomatik yedek (zamanlanmis gorev bunu cagirir)."""
    d = _json_oku(BENCH_DOSYA, {"disk": [], "cpu": [], "ram": []})
    secili = d.get("yedekSecili") or ["Belgeler", "Masaüstü", "Resimler"]
    r = api_yedek_klasor(secili)
    satir = "[%s] %s\n" % (time.strftime("%d.%m.%Y %H:%M"), r.get("mesaj") or r.get("hata"))
    try:
        with open(os.path.join(KOK, "yedek-gunlugu.txt"), "a", encoding="utf-8") as f:
            f.write(satir)
    except Exception:
        pass
    print(satir.strip())
    return 0 if r.get("ok") else 1


def main():
    global PORT
    if "--bakim" in sys.argv:
        return bakim_calistir()
    if "--yedek" in sys.argv:
        return yedek_calistir()
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        PORT = int(sys.argv[1])
    s = None
    for dene in range(PORT, PORT + 12):
        try:
            s = ThreadingHTTPServer(("127.0.0.1", dene), Istek)
            PORT = dene
            break
        except OSError:
            continue
    if s is None:
        print("BOS PORT BULUNAMADI")
        return 1
    try:
        with open(os.path.join(KOK, "port.txt"), "w", encoding="utf-8") as f:
            f.write("%d\n%d" % (PORT, os.getpid()))
    except Exception:
        pass
    print("USTAD PC OPTIMIZER v%s" % SURUM)
    print("Adres   : http://127.0.0.1:%d" % PORT)
    print("Yonetici: %s" % ("EVET" if yonetici_mi() else "HAYIR"))
    sys.stdout.flush()
    # arka plan isinma dongusu: panel acilir acilmaz hazir veri bulur
    threading.Thread(target=isinma_dongusu, daemon=True).start()
    threading.Thread(target=nobet_dongusu, daemon=True).start()
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
