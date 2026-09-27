# -*- coding: utf-8 -*-
"""v1.2.1 düzeltme kanıt kartı (masaüstü PNG)."""
import os
from PIL import Image, ImageDraw, ImageFont

EKRAN = r"C:\Users\kenan\AppData\Local\hermes\cache\scratch\ustad-ekran6"
CIK = r"C:\Users\kenan\OneDrive\Desktop\USTAD-PC-OPTIMIZER-V121-DUZELTME-2026-09-27.png"
EN = 1620
ARKA = (4, 12, 24)
BASLIK = (12, 32, 56)
BEYAZ = (234, 245, 255)
SOLUK = (142, 174, 208)
KIRMIZI = (252, 165, 165)
YESIL = (134, 239, 172)
SARI = (253, 224, 71)
MAVI = (125, 211, 252)


def yazi(boy, kalin=False):
    for ad in (("segoeuib.ttf" if kalin else "segoeui.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(ad, boy)
        except Exception:
            continue
    return ImageFont.load_default()


F13, F15, F17, F20, F30 = yazi(13), yazi(15), yazi(17, True), yazi(20, True), yazi(30, True)

KONULAR = [
    ("BELİRTİ", KIRMIZI, [
        "Panel açılıyordu ama ORTASI BOŞ kalıyordu; altta \"Sistem ölçülüyor…\" yazısı takılı kalıyordu.",
        "Yeni sayfalar (Canlı İzleme, Hız Testi, Kurtarma, Görev & Hizmet, Güncelleme, Alarm) hiç açılmıyordu.",
    ]),
    ("SEBEP 1 — kapsam hatası", SARI, [
        "$saf / apiHizli / hazirCek yardımcıları yanlış kapsamda tanımlıydı: sayfa kodları çağırınca",
        "\"is not defined\" hatası alıyor ve orta alan boş kalıyordu.  → modül kapsamına taşındı.",
    ]),
    ("SEBEP 2 — nöbet döngüsü motoru öldürüyordu", SARI, [
        ".bat nöbet döngüsü pencere başlığına bakıp çalışan motoru kapatıyordu; ayrıca 6 sn'de bir",
        "PowerShell çalıştırıyordu. → Nöbet kaldırıldı, yerine PANEL KALP ATIŞI geldi (motor 5 dk sessizlikte kapanır).",
    ]),
    ("SEBEP 3 — ağır ölçümler isteği bekletiyordu", SARI, [
        "Ağ taraması 29 sn, sistem tarama 5 sn sürüyor ve isteği bloke ediyordu (\"hep düşünüyor\").",
        "→ \"Bayat veriyi hemen ver, arkada tazele\" mantığı: ölçüm yoksa \"hazırlanıyor\" der, panel kendiliğinden sorar.",
    ]),
    ("DOĞRULAMA (bu bilgisayarda, gerçek tarayıcı)", YESIL, [
        "22/22 sayfa açıldı · 0 JavaScript hatası · panel 5 saniyede dolu geldi",
        "Kalp atışı testi: vuruş yok → motor kendini kapattı ve port.txt sildi · vuruş var → motor açık kaldı",
        "Hız: ağ taraması 29,3 sn → 0,01 sn · sistem tarama 4,7 sn → 0,02 sn · görevler 2,75 sn → 0,02 sn",
        "Kaynak klasör = kurulu sürüm (birebir aynı) · motor testi 36/36 GEÇTİ",
    ]),
]

GORSELLER = [("panel.png", "ANA PANEL — sistem durumu, sağlık puanı, hızlı işlemler"),
             ("canli.png", "CANLI İZLEME — gerçek CPU/RAM/Disk grafikleri, sıcaklık/fan \"desteklemiyor\", bağlantılar"),
             ("alarm.png", "ALARM & BİLDİRİM — eşikler, sesli uyarı, Telegram (ölçülen gerçek değerler)")]

satir_sayisi = sum(2 + len(satirlar) for _, _, satirlar in KONULAR)
yuk = 150 + satir_sayisi * 24 + 60
resimler = []
for dosya, aciklama in GORSELLER:
    yol = os.path.join(EKRAN, dosya)
    if os.path.isfile(yol):
        im = Image.open(yol).convert("RGB")
        im = im.resize((EN, int(im.height * EN / im.width)), Image.LANCZOS)
        resimler.append((im, aciklama))
TOPLAM = yuk + sum(im.height + 54 for im, _ in resimler) + 40
tuval = Image.new("RGB", (EN, TOPLAM), ARKA)
ciz = ImageDraw.Draw(tuval)
ciz.rectangle([0, 0, EN, 112], fill=BASLIK)
ciz.text((30, 22), "ÜSTAD PC OPTIMIZER v1.2.1 — \"PANEL BOŞ KALIYORDU\" DÜZELTİLDİ", font=F30, fill=BEYAZ)
ciz.text((32, 66), "3 kök neden bulundu ve giderildi · 27.09.2026 · tüm doğrulamalar gerçek makinede yapıldı",
         font=F17, fill=MAVI)
y = 132
for baslik, renk, satirlar in KONULAR:
    ciz.text((30, y), baslik, font=F20, fill=renk)
    y += 26
    for sa in satirlar:
        ciz.text((44, y), sa, font=F15, fill=BEYAZ)
        y += 24
    y += 18
for im, aciklama in resimler:
    ciz.rectangle([0, y, EN, y + 34], fill=(9, 26, 46))
    ciz.text((22, y + 8), aciklama, font=F15, fill=(198, 228, 255))
    y += 34
    tuval.paste(im, (0, y))
    ciz.rectangle([0, y, EN, y + im.height], outline=(28, 66, 104), width=2)
    y += im.height + 20
ciz.text((22, TOPLAM - 30), "Kenan Kuzucu · ÜSTAD PC OPTIMIZER · tüm ölçümler yerel, hiçbir veri dışarı gönderilmedi.",
         font=F13, fill=SOLUK)
tuval.save(CIK, "PNG", optimize=True)
print("KANIT:", CIK)
print("%d x %d · %.1f MB" % (tuval.width, tuval.height, os.path.getsize(CIK) / 1048576))
