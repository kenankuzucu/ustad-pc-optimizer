# -*- coding: utf-8 -*-
"""Tek tusluk GitHub yedegi (USTAD PC OPTIMIZER).

Kullanim:  GITHUB-YEDEKLE.bat  [aciklama]
Ne yapar :  degisen dosyalari ekler, commit eder ve GitHub'a push eder.
Token    :  %LOCALAPPDATA%\\hermes\\.env icindeki GITHUB_TOKEN (ekrana YAZILMAZ).
Cikti    :  push sonrasi uzak commit sha'si yerel ile karsilastirilir; ayni degilse HATA yazar.
"""
import io
import json
import os
import subprocess
import sys
import urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", ".env")
KULLANICI = "kenankuzucu"
DEPO = "ustad-pc-optimizer"
DAL = "main"


def token_oku():
    if not os.path.isfile(ENV):
        return None
    for satir in io.open(ENV, encoding="utf-8", errors="replace"):
        s = satir.strip()
        if s.startswith("GITHUB_TOKEN="):
            v = s.split("=", 1)[1].strip().strip('"').strip("'")
            if v:
                return v
    return None


def git(*args, env=None):
    p = subprocess.run(["git", "-C", KOK] + list(args), capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    aciklama = " ".join(sys.argv[1:]).strip() or "otomatik yedek"
    tok = token_oku()
    if not tok:
        print("[HATA] GITHUB_TOKEN bulunamadi:", ENV)
        return 1

    kod, cikti = git("rev-parse", "--is-inside-work-tree")
    if kod != 0:
        print("[HATA] Bu klasor bir git deposu degil. Once kurulum gerekir.")
        return 1

    git("add", "-A")
    kod, durum = git("status", "--porcelain")
    if durum.strip():
        kod, cikti = git("-c", "user.name=" + KULLANICI,
                         "-c", "user.email=" + KULLANICI + "@users.noreply.github.com",
                         "commit", "-m", "yedek: " + aciklama)
        if kod != 0:
            print("[HATA] commit yapilamadi:\n" + cikti)
            return 1
        print("Commit atildi:", aciklama)
    else:
        print("Degisiklik yok - mevcut surum yedekleniyor.")

    ortam = dict(os.environ)
    ortam["GITHUB_TOKEN"] = tok
    ortam["GIT_TERMINAL_PROMPT"] = "0"
    yardimci = "credential.helper=!f() { echo username=%s; echo password=$GITHUB_TOKEN; }; f" % KULLANICI
    kod, cikti = git("-c", yardimci, "push", "-u", "origin", DAL, env=ortam)
    cikti = cikti.replace(tok, "***TOKEN***")
    if kod != 0:
        print("[HATA] push basarisiz:\n" + cikti)
        return 1
    print("Push tamam.")

    # dogrulama: uzak sha == yerel sha
    _, yerel = git("rev-parse", "HEAD")
    yerel = yerel.strip()
    istek = urllib.request.Request(
        "https://api.github.com/repos/%s/%s/commits/%s" % (KULLANICI, DEPO, DAL),
        headers={"Authorization": "Bearer " + tok, "User-Agent": "ustad-yedek",
                 "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(istek, timeout=45) as c:
            uzak = json.loads(c.read().decode("utf-8"))["sha"]
    except Exception as e:
        print("[UYARI] Uzak dogrulama yapilamadi:", e)
        return 0
    if uzak == yerel:
        print("DOGRULANDI: uzak commit yerel ile ayni ->", yerel[:12])
        print("Depo: https://github.com/%s/%s" % (KULLANICI, DEPO))
        return 0
    print("[HATA] Uzak commit yerelden FARKLI  yerel %s | uzak %s" % (yerel[:12], uzak[:12]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
