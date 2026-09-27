# -*- coding: utf-8 -*-
"""sag-kurt.png icindeki CIZILI sahte pencere dugmelerini (─ ▫ ✕ kutulari + mavi cark) siler.
YAZIYA dokunmaz. Kural:
  - mavi kural (b-r>=10, b>=20): dugme govdeleri + cark  (yazi bolgesi haric)
  - parlak kural SADECE ust dugme satirinda (y 6-42, x>=440)
  - cark dikdortgeni (500-544, 56-100)
Yontem: maskeyi genislet -> cevreden difuzyonla doldur -> yalnizca DIS kenarda yumusak gecis.
Orijinal her zaman sag-kurt-orijinal.png'den okunur (betik tekrar kosarsa bozulmaz)."""
import os
import shutil

from PIL import Image, ImageChops, ImageFilter

KL = r"C:\Users\kenan\OneDrive\Desktop\USTAD-PC-OPTIMIZER\assets"
KAY = os.path.join(KL, "sag-kurt.png")
YEDEK = os.path.join(KL, "sag-kurt-orijinal.png")
if not os.path.exists(YEDEK):
    shutil.copy2(KAY, YEDEK)
    print("yedek olusturuldu:", YEDEK)

im = Image.open(YEDEK).convert("RGB")
W, H = im.size
print("kaynak boyut:", im.size)

BOLGE = (368, 0, 551, 130)
R = im.crop(BOLGE)
rw, rh = R.size
rp = R.load()

mask = Image.new("L", (rw, rh), 0)
mp = mask.load()
sayi = 0
for y in range(rh):
    for x in range(rw):
        r, g, b = rp[x, y]
        gx, gy = BOLGE[0] + x, BOLGE[1] + y
        parlak = (r + g + b) / 3.0
        mavi = (b - r) >= 10 and b >= 20 and (gy <= 46 or gx >= 498)
        ust_dugme = parlak >= 46 and 6 <= gy <= 42 and gx >= 440
        cark = 498 <= gx <= 546 and 54 <= gy <= 102
        if mavi or ust_dugme or cark:
            mp[x, y] = 255
            sayi += 1
print("isaretli piksel:", sayi, "(%.1f%%" % (100.0 * sayi / (rw * rh)) + ")")

mask = mask.filter(ImageFilter.MaxFilter(11))          # isaretten genis
mask = mask.filter(ImageFilter.GaussianBlur(2.0))

calis = R.copy()
for tur in range(18):
    yumusak = calis.filter(ImageFilter.GaussianBlur(16))
    calis = Image.composite(yumusak, calis, mask)

# yumusak gecis SADECE bolgenin sol/alt/ust dis kenarinda; isaret alani her zaman temiz kalir
kenar = Image.new("L", (rw, rh), 0)
kp = kenar.load()
for y in range(rh):
    for x in range(rw):
        sol = min(1.0, x / 34.0)
        alt = min(1.0, (rh - y) / 22.0)
        ust = min(1.0, (y + 6) / 6.0)
        kp[x, y] = int(255 * min(sol, alt, ust))
kenar = kenar.filter(ImageFilter.GaussianBlur(6))

tam_mask = ImageChops.lighter(mask, kenar)             # isaret + yumusak dis kenar
sonuc = Image.composite(calis, R, tam_mask)

cikti = im.copy()
cikti.paste(sonuc, (BOLGE[0], BOLGE[1]))
cikti.save(KAY, "PNG")
print("temizlendi ->", KAY)

kalan = 0
for y in range(0, 112):
    for x in range(400, W):
        r, g, b = cikti.getpixel((x, y))
        if (b - r) >= 25 and b >= 60:
            kalan += 1
print("kalan guclu mavi (cark/dugme) piksel:", kalan)
kontrol = os.path.join(os.environ["TEMP"], "kurt-temiz-kontrol.png")
cikti.crop((290, 0, W, H)).resize(((W - 290) * 3, H * 3), Image.LANCZOS).save(kontrol)
print("kontrol gorseli:", kontrol)
