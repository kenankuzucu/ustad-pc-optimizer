# -*- coding: utf-8 -*-
"""Pencere dugmelerini GERCEK panel penceresinde dener:
kucult -> IsIconic, buyut -> IsZoomed, kapat -> pencere kapanir."""
import ctypes
import json
import os
import subprocess
import time
import urllib.request

from ctypes import wintypes

KOK = r"C:\Users\kenan\OneDrive\Desktop\USTAD-PC-OPTIMIZER"
PY = r"C:\Users\kenan\AppData\Local\Programs\Python\Python312\python.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 8897
PROFIL = r"C:\Users\kenan\AppData\Local\hermes\cache\scratch\chrome-pencere"
u = ctypes.windll.user32


def istek(yol, govde=None):
    if govde is None:
        r = urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, yol), timeout=30)
    else:
        r = urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:%d%s" % (PORT, yol), data=json.dumps(govde).encode(),
            headers={"Content-Type": "application/json"}), timeout=30)
    return json.loads(r.read().decode("utf-8"))


def pencere():
    bul = []
    TIP = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _l):
        if not u.IsWindowVisible(h):
            return True
        n = u.GetWindowTextLengthW(h)
        if n <= 0:
            return True
        b = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(h, b, n + 1)
        if "PC OPTIMIZER" in b.value.upper():
            c = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(h, c, 256)
            bul.append((h, b.value, c.value))
        return True
    u.EnumWindows(TIP(cb), 0)
    return bul


print("=" * 70)
if os.path.exists(os.path.join(KOK, "port.txt")):
    os.remove(os.path.join(KOK, "port.txt"))
srv = subprocess.Popen([PY, os.path.join(KOK, "sunucu.py"), str(PORT)], cwd=KOK,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=0x08000000)
for _ in range(40):
    time.sleep(0.5)
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/nabiz" % PORT, timeout=3)
        break
    except Exception:
        pass
print("motor hazir")

kr = subprocess.Popen([CHROME, "--app=http://127.0.0.1:%d" % PORT, "--window-size=1620,1000",
                       "--no-first-run", "--no-default-browser-check",
                       "--user-data-dir=" + PROFIL],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("panel penceresi aciliyor...")
p = []
for _ in range(30):
    time.sleep(1)
    p = pencere()
    if p:
        break
print("bulunan pencere:", p)
if not p:
    print("PENCERE BULUNAMADI"); srv.kill(); kr.kill(); raise SystemExit(1)
hwnd = p[0][0]

print("-" * 70)
print("1) ilk durum  :", istek("/api/pencere", {"islem": "durum"}))
print("2) kucult     :", istek("/api/pencere", {"islem": "kucult"}))
time.sleep(1.0)
print("   IsIconic   :", bool(u.IsIconic(hwnd)), "(True olmali)")
print("3) buyut      :", istek("/api/pencere", {"islem": "buyut"}))
time.sleep(1.0)
print("   IsZoomed   :", bool(u.IsZoomed(hwnd)), "(True olmali)")
print("4) eski boyut :", istek("/api/pencere", {"islem": "buyut"}))
time.sleep(1.0)
print("   IsZoomed   :", bool(u.IsZoomed(hwnd)), "(False olmali)")
print("-" * 70)
print("5) kapat      :", istek("/api/pencere", {"islem": "kapat"}))
time.sleep(2.5)
print("   IsWindow   :", bool(u.IsWindow(hwnd)), "(False olmali)")
print("=" * 70)
try:
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/api/kapat" % PORT, data=b"{}"), timeout=10)
except Exception:
    pass
time.sleep(2)
for x in (srv, kr):
    try:
        x.kill()
    except Exception:
        pass
print("temizlendi")
