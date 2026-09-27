# -*- coding: utf-8 -*-
"""v1.2.0 ince ayar: (1) gorev durumu metin karsilastirma, (2) UAC'yi kullaniciya birak."""
import io

P = r"C:/Users/kenan/OneDrive/Desktop/USTAD-PC-OPTIMIZER/sunucu.py"
s = io.open(P, encoding="utf-8").read()
def d(a, b, ad):
    global s
    if a in s:
        s = s.replace(a, b, 1)
        print("  +", ad)
    else:
        print("  - ATLANDI:", ad)

# 1) teyit: State ENUM olarak sayi geliyordu (1/3) -> metne cevir
d('''    teyit = ps_json("@(Get-ScheduledTask -TaskName '%s' %s -ErrorAction SilentlyContinue | "
                    "Select-Object -ExpandProperty State) | ConvertTo-Json -Compress"
                    % (ad.replace("'", "''"), yolPs), 60)''',
  '''    teyit = ps_json("@(Get-ScheduledTask -TaskName '%s' %s -ErrorAction SilentlyContinue | "
                    "ForEach-Object { [string]$_.State }) | ConvertTo-Json -Compress"
                    % (ad.replace("'", "''"), yolPs), 60)''',
  "gorev teyidi: State -> metin")

# 2) UAC'yi kullaniciya birak: zorla=False ise yonetici penceresi ACILMAZ
d('''def api_gorev_degistir(ad, yol="\\\\", kapat=True):''',
  '''def api_gorev_degistir(ad, yol="\\\\", kapat=True, zorla=False):''',
  "api_gorev_degistir: zorla parametresi")
d('''    if not yonetici_mi() and not oldu:
        ps_admin(komut)
        return {"ok": True, "yonetici_ile": True, "dogrulandi": False,
                "mesaj": "Bu görev yönetici istiyor — yönetici penceresi açıldı."}''',
  '''    if not oldu and not yonetici_mi():
        if zorla:
            ps_admin(komut)
            return {"ok": True, "yonetici_ile": True, "dogrulandi": False,
                    "mesaj": "Görev için yönetici penceresi açıldı — işlem orada tamamlanacak."}
        return {"ok": False, "yoneticiGerekli": True, "dogrulandi": False,
                "mesaj": "Bu görev yönetici yetkisi istiyor. 'Yönetici olarak dene' düğmesine bas."}''',
  "api_gorev_degistir: UAC kullaniciya birakildi")

d('''def api_hizmet_degistir(ad, islem="durdur", baslangic=None):''',
  '''def api_hizmet_degistir(ad, islem="durdur", baslangic=None, zorla=False):''',
  "api_hizmet_degistir: zorla parametresi")
d('''    if not (isinstance(teyit, dict) and teyit):
        if not yonetici_mi():
            ps_admin(komut)
            return {"ok": True, "yonetici_ile": True, "dogrulandi": False,
                    "mesaj": "Hizmet işlemi yönetici istiyor — yönetici penceresi açıldı."}''',
  '''    if not (isinstance(teyit, dict) and teyit):
        if not yonetici_mi():
            if zorla:
                ps_admin(komut)
                return {"ok": True, "yonetici_ile": True, "dogrulandi": False,
                        "mesaj": "Hizmet için yönetici penceresi açıldı — işlem orada tamamlanacak."}
            return {"ok": False, "yoneticiGerekli": True,
                    "mesaj": "Bu hizmet yönetici yetkisi istiyor. 'Yönetici olarak dene' düğmesine bas."}''',
  "api_hizmet_degistir: UAC kullaniciya birakildi")

# 3) Diger yonetici isleri: dogrudan UAC acmak yerine durust cevap
d('''def api_geri_noktasi_olustur(aciklama=None):
    ad = (aciklama or "").strip() or ("USTAD " + time.strftime("%d.%m.%Y %H:%M"))
    if not yonetici_mi():
        ps_admin("Checkpoint-Computer''',
  '''def api_geri_noktasi_olustur(aciklama=None, zorla=False):
    ad = (aciklama or "").strip() or ("USTAD " + time.strftime("%d.%m.%Y %H:%M"))
    if not yonetici_mi() and not zorla:
        return {"ok": False, "yoneticiGerekli": True, "ad": ad,
                "mesaj": "Geri yükleme noktası yönetici yetkisi ister. 'Yönetici olarak oluştur' düğmesine bas."}
    if not yonetici_mi():
        ps_admin("Checkpoint-Computer''',
  "api_geri_noktasi_olustur: UAC kullaniciya birakildi")

d('''def api_surucu_yedek():
    """Kurulu suruculeri klasore aktarir (pnputil /export-driver)."""''',
  '''def api_surucu_yedek(zorla=False):
    """Kurulu suruculeri klasore aktarir (pnputil /export-driver)."""''',
  "api_surucu_yedek: parametre")
d('''    komut = "pnputil /export-driver * %s" % json.dumps(hedef)
    if not yonetici_mi():''',
  '''    komut = "pnputil /export-driver * %s" % json.dumps(hedef)
    if not yonetici_mi() and not zorla:
        return {"ok": False, "yoneticiGerekli": True, "hedef": hedef,
                "mesaj": "Sürücü yedeği yönetici yetkisi ister. 'Yönetici olarak yedekle' düğmesine bas."}
    if not yonetici_mi():''',
  "api_surucu_yedek: UAC kullaniciya birakildi")

d('''def api_telemetri_kapat():
    yapilan = []
    if not yonetici_mi():''',
  '''def api_telemetri_kapat(zorla=False):
    yapilan = []
    if not yonetici_mi() and not zorla:
        ps("Set-ItemProperty 'HKCU:\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\AdvertisingInfo' "
           "-Name Enabled -Value 0 -Type DWord", 60)
        return {"ok": False, "yoneticiGerekli": True,
                "mesaj": "Reklam kimliği kapatıldı. Telemetri+DiagTrack için yönetici gerekir — "
                         "'Yönetici olarak kapat' düğmesine bas."}
    if not yonetici_mi():''',
  "api_telemetri_kapat: UAC kullaniciya birakildi")

d('''def api_yazici_temizle():
    if not yonetici_mi():''',
  '''def api_yazici_temizle(zorla=False):
    if not yonetici_mi() and not zorla:
        return {"ok": False, "yoneticiGerekli": True,
                "mesaj": "Yazıcı kuyruğu temizliği yönetici yetkisi ister. "
                         "'Yönetici olarak temizle' düğmesine bas."}
    if not yonetici_mi():''',
  "api_yazici_temizle: UAC kullaniciya birakildi")

# 4) Rotalar: zorla bayragini gecir
d('''            if y == "/api/geri-noktasi":
                return self._gonder(api_geri_noktasi_olustur(v.get("aciklama")))''',
  '''            if y == "/api/geri-noktasi":
                return self._gonder(api_geri_noktasi_olustur(v.get("aciklama"), bool(v.get("zorla"))))''',
  "rota: geri-noktasi zorla")
d('''            if y == "/api/surucu-yedek":
                return self._gonder(api_surucu_yedek())''',
  '''            if y == "/api/surucu-yedek":
                return self._gonder(api_surucu_yedek(bool(v.get("zorla"))))''',
  "rota: surucu-yedek zorla")
d('''                return self._gonder(api_gorev_degistir(v.get("ad", ""), v.get("yol") or "\\\\",
                                                       bool(v.get("kapat", True))))''',
  '''                return self._gonder(api_gorev_degistir(v.get("ad", ""), v.get("yol") or "\\\\",
                                                       bool(v.get("kapat", True)),
                                                       bool(v.get("zorla"))))''',
  "rota: gorev zorla")
d('''                return self._gonder(api_hizmet_degistir(v.get("ad", ""), v.get("islem") or "durdur",
                                                        v.get("baslangic")))''',
  '''                return self._gonder(api_hizmet_degistir(v.get("ad", ""), v.get("islem") or "durdur",
                                                        v.get("baslangic"), bool(v.get("zorla"))))''',
  "rota: hizmet zorla")
d('''            if y == "/api/telemetri/kapat":
                return self._gonder(api_telemetri_kapat())''',
  '''            if y == "/api/telemetri/kapat":
                return self._gonder(api_telemetri_kapat(bool(v.get("zorla"))))''',
  "rota: telemetri zorla")
d('''            if y == "/api/yazici/temizle":
                return self._gonder(api_yazici_temizle())''',
  '''            if y == "/api/yazici/temizle":
                return self._gonder(api_yazici_temizle(bool(v.get("zorla"))))''',
  "rota: yazici zorla")

io.open(P, "w", encoding="utf-8", newline="").write(s)
print("boyut:", len(s))
