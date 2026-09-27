# -*- coding: utf-8 -*-
"""sunucu.py kusur duzeltmeleri (v1.2.0)."""
import io
import re

P = r"C:/Users/kenan/OneDrive/Desktop/USTAD-PC-OPTIMIZER/sunucu.py"
s = io.open(P, encoding="utf-8").read()
yapilan = []


def degistir(eski, yeni, ad):
    global s
    if eski not in s:
        raise SystemExit("BULUNAMADI: " + ad)
    s = s.replace(eski, yeni, 1)
    yapilan.append(ad)


# ---------------------------------------------------------------- 1) GOREVLER
eski_gorev = s[s.index("def api_gorevler(ara=\"\"):"):s.index("def api_gorev_degistir(")]
yeni_gorev = '''def _gorev_kod_metni(k):
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
        # yedek yol: CIM (bazi makinelerde Get-ScheduledTask kapali olabilir)
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


'''
degistir(eski_gorev, yeni_gorev, "api_gorevler (Int32 tasmasi + kod metni + CIM yedegi)")

# ---------------------------------------------------------------- 2) AYGITLAR
eski_aygit = s[s.index("def api_aygit_sorunlu():"):s.index("def _gorev_kod_metni(")]
yeni_aygit = '''def api_aygit_sorunlu():
    v = ps_json(r"""
$h = @(Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
      $_.Status -eq 'Error' -or $_.Status -eq 'Degraded' -or $_.Status -eq 'Unknown' } |
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
    k = v.get("kodlu")
    if isinstance(k, dict):
        k = [k]
    b, k = b or [], k or []
    kod = {1: "Bu aygıt düzgün yapılandırılmamış", 3: "Sürücü bozuk veya eksik",
           10: "Aygıt başlatılamıyor", 12: "Yeterli kaynak yok",
           18: "Sürücüler yeniden kurulmalı", 19: "Kayıt defteri bozuk",
           28: "Sürücü kurulu değil", 43: "Windows bu aygıtı durdurdu (sürücü hatası)",
           45: "Aygıt şu an bağlı değil"}
    for x in k:
        if isinstance(x, dict):
            x["sade"] = kod.get(x.get("kod"), "Aygıt Yöneticisi'nden bakılmalı")
    return {"ok": True, "aygitlar": b, "adet": len(b), "kodlular": k, "kodluAdet": len(k),
            "toplamCihaz": v.get("toplamCihaz") or 0,
            "not": ("Sorunlu aygıt yok — tüm aygıtlar çalışıyor." if not b and not k
                    else "Bu aygıtların sürücüsü eksik/bozuk. Aygıt Yöneticisi'nden güncellenebilir.")}


'''
degistir(eski_aygit, yeni_aygit, "api_aygit_sorunlu (gercek hatali aygit filtresi)")

# ------------------------------------------------------------- 3) GUNCELLEME
degistir('''  $se = $s.CreateUpdateSearcher()
  $se.ServerSelection = 3
  $r = $se.Search("IsInstalled=0 and IsHidden=0")''',
         '''  $se = $s.CreateUpdateSearcher()
  $r = $null
  foreach ($mod in @(2, 0)) {
    try { $se.ServerSelection = $mod; $r = $se.Search("IsInstalled=0 and IsHidden=0"); break } catch { }
  }
  if (-not $r) { throw 'Windows Update servisine ulaşılamadı (sunucu ayarı).' }''',
         "api_guncelleme (ServerSelection 2/0 denemesi)")

# -------------------------------------------------------------- 4) YEDEK GOREVI
degistir('''    py = sys.executable
    komut = '"%s" "%s" --yedek' % (py, os.path.join(KOK, "sunucu.py"))
    ps("schtasks /Create /TN %s /TR %s /SC DAILY /ST %s /F"
       % (json.dumps(ad), json.dumps(komut), saat), 90)
    teyit = ps("schtasks /Query /TN %s /FO LIST 2>$null" % json.dumps(ad), 60)''',
         '''    py = sys.executable
    betik = os.path.join(KOK, "sunucu.py")
    komut = ("Register-ScheduledTask -TaskName '%s' -Force "
             "-Action (New-ScheduledTaskAction -Execute '%s' -Argument '\"%s\" --yedek' "
             "-WorkingDirectory '%s') "
             "-Trigger (New-ScheduledTaskTrigger -Daily -At %s) "
             "-Description 'USTAD PC OPTIMIZER gunluk otomatik klasor yedegi' | Out-Null"
             % (ad, py.replace("'", "''"), betik.replace("'", "''"),
                KOK.replace("'", "''"), saat))
    ps(komut, 180)
    teyit = ps("(Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue).TaskName" % ad, 60)''',
         "api_yedek_gorevi (Register-ScheduledTask ile kurulum)")

degistir('''        ps("schtasks /Delete /TN %s /F" % json.dumps(ad), 60)
        teyit = ps("schtasks /Query /TN %s 2>$null" % json.dumps(ad), 60)
        return {"ok": True, "kaldirildi": ad not in (teyit or ""), "mesaj": "Yedek görevi kaldırıldı."}''',
         '''        ps("Unregister-ScheduledTask -TaskName '%s' -Confirm:$false" % ad, 90)
        teyit = ps("(Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue).TaskName" % ad, 60)
        return {"ok": True, "kaldirildi": ad not in (teyit or ""),
                "mesaj": "Yedek görevi kaldırıldı." if ad not in (teyit or "")
                         else "Görev hâlâ görünüyor (yönetici gerekebilir)."}''',
         "api_yedek_gorevi (kaldirma)")

# --------------------------------------------------- 5) GOREV DEGISTIR (durust yol)
degistir('''    komut = "%s -TaskName %s -TaskPath %s" % (islem, json.dumps(ad), json.dumps(yol or "\\\\"))''',
         '''    varMi = ps("(Get-ScheduledTask -TaskName '%s' -TaskPath '%s' -ErrorAction SilentlyContinue).TaskName"
               % (ad.replace("'", "''"), (yol or "\\\\").replace("'", "''")), 60)
    varMi = bool((varMi or "").strip())
    if not varMi:
        return {"ok": False, "hata": "Görev bulunamadı: %s" % ad}
    komut = "%s -TaskName '%s' -TaskPath '%s'" % (islem, ad.replace("'", "''"),
                                                  (yol or "\\\\").replace("'", "''"))''',
         "api_gorev_degistir (once var mi kontrolu)")

# --------------------------------------- 6) HIZMET: once varlik kontrolu
degistir('''def api_hizmet_degistir(ad, islem="durdur", baslangic=None):
    if not ad:
        return {"ok": False, "hata": "Hizmet adı gerekli."}''',
         '''def api_hizmet_degistir(ad, islem="durdur", baslangic=None):
    if not ad:
        return {"ok": False, "hata": "Hizmet adı gerekli."}
    varMi = ps("(Get-CimInstance Win32_Service -Filter %s -ErrorAction SilentlyContinue | "
               "Measure-Object).Count" % json.dumps("Name='%s'" % ad), 45)
    if str(varMi).strip() in ("0", ""):
        return {"ok": False, "hata": "Hizmet bulunamadı: %s" % ad}''',
         "api_hizmet_degistir (once varlik kontrolu)")

# --------------------------------------- 7) DISK HIZI: gercek (onbelleksiz) okuma
degistir('''def api_disk_hiz():''',
         '''def _soguk_okuma(yol, blok=4 * 1024 * 1024):
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


def api_disk_hiz():''',
         "_soguk_okuma (NO_BUFFERING ile gercek okuma) eklendi")

degistir('''        sonuc.update({
            "yazmaMBs": round(boyut / MB / max(0.001, yaz), 1),
            "okumaMBs": round(okunan / MB / max(0.001, oku), 1),
            "yazmaSn": round(yaz, 2), "okumaSn": round(oku, 2),
        })''',
         '''        sonuc.update({
            "yazmaMBs": round(boyut / MB / max(0.001, yaz), 1),
            "okumaMBs": round(okunan / MB / max(0.001, oku), 1),
            "yazmaSn": round(yaz, 2), "okumaSn": round(oku, 2),
        })
        # GERCEK disk okumasi (isletim sistemi onbellegini atlar)
        soguk, ssn = _soguk_okuma(yol)
        if soguk:
            sonuc["okumaSogukMBs"] = round(soguk / MB / max(0.001, ssn), 1)
            sonuc["okumaSogukSn"] = round(ssn, 2)
        else:
            sonuc["okumaSogukNot"] = "Önbelleksiz okuma bu sistemde başlatılamadı."''',
         "api_disk_hiz (soguk okuma sonucu)")

io.open(P, "w", encoding="utf-8", newline="\\n").write(s)
print("DUZELTILDI (%d):" % len(yapilan))
for a in yapilan:
    print("  -", a)
