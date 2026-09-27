# -*- coding: utf-8 -*-
"""v1.2.1 sağlamlaştırma:
1) goster() her sayfayı hata korumalı çağırır -> orta alan ASLA boş kalmaz
2) motorBekle() motor gelince sayfayı kendiliğinden açar (3 sn'de bir dener)
3) basla() hata korumalı + /api/ayar ve /api/nabiz için yeniden deneme
4) kenar çubuğu sürüm yazısı v1.2.1
Dosya tmp'e yazılır, sonra os.replace ile yerine konur (0-byte riski yok).
"""
import io
import os
import shutil

KOK = r"C:/Users/kenan/OneDrive/Desktop/USTAD-PC-OPTIMIZER"
P = os.path.join(KOK, "index.html")
s = io.open(P, encoding="utf-8").read()
o = s
yapilan = []

# ---------- 0) yedek ----------
shutil.copyfile(P, P + ".v120-yedek")
yapilan.append("yedek: index.html.v120-yedek")

# ---------- 1) goster() hata korumalı ----------
eski_goster = """function goster(ad){
  AKTIF = ad;
  if(location.hash !== '#sayfa='+ad) history.replaceState(null,'','#sayfa='+ad);
  $$('#menu .oge').forEach(o=>o.classList.toggle('aktif', o.dataset.sayfa===ad));
  const p = SAYFALAR[ad];
  if(p){ p(); } else { SAYFALAR.panel(); }
}"""
yeni_goster = """/* Sayfa çizimi hata korumalı: bir sayfa patlarsa orta alan boş kalmaz,
   motor çalışmıyorsa panel kendini toparlar. */
var MOTOR_BEKLIYOR = null;
function sayfaHata(ad, e){
  const o = document.getElementById('orta');
  if(o && !(o.innerText||'').trim()){
    o.innerHTML = '<div class="kutu"><h2>\\u26a0 SAYFA YÜKLENEMEDİ <span class="sag">' + ad + '</span></h2>'
      + '<div class="alt" style="margin:4px 0 10px">Sebep: ' + (e && e.message ? e.message : String(e)) + '</div>'
      + '<div class="serit"><div class="sol"><div class="baslik">Motor çalışıyor mu?</div>'
      + '<div class="alt">Panel her 3 saniyede bir yeniden dener; motor açılır açılmaz bu sayfa kendiliğinden gelir.</div></div>'
      + '<button class="dev-buton" id="tekrarDene">Tekrar dene</button></div></div>';
    const b = document.getElementById('tekrarDene');
    if(b) b.onclick = ()=> goster(ad);
  }
  const s2 = document.getElementById('altSol');
  if(s2) s2.innerHTML = '<b style="color:#fca5a5">Motor yanıt vermiyor</b> \\u2014 yeniden bağlanılıyor\\u2026';
  motorBekle();
}
function motorBekle(){
  if(MOTOR_BEKLIYOR) return;
  MOTOR_BEKLIYOR = setInterval(async ()=>{
    try{
      const n = await apiGet('/api/nabiz');
      if(n && n.ok){
        clearInterval(MOTOR_BEKLIYOR); MOTOR_BEKLIYOR = null;
        const s3 = document.getElementById('altSol');
        if(s3) s3.innerHTML = '\\u25cf Sistem korunuyor \\u2014 tüm ölçümler yerel, veri gönderilmiyor';
        goster(AKTIF || 'panel');
      }
    }catch(e){}
  }, 3000);
}
function goster(ad){
  AKTIF = ad;
  if(location.hash !== '#sayfa='+ad) history.replaceState(null,'','#sayfa='+ad);
  $$('#menu .oge').forEach(o=>o.classList.toggle('aktif', o.dataset.sayfa===ad));
  const p = SAYFALAR[ad] || SAYFALAR.panel;
  try{
    const r = p();
    if(r && typeof r.catch === 'function') r.catch(function(e){ sayfaHata(ad, e); });
  }catch(e){ sayfaHata(ad, e); }
}"""
assert eski_goster in s, "goster() bulunamadi"
s = s.replace(eski_goster, yeni_goster, 1)
yapilan.append("goster() + motorBekle() + sayfaHata()")

# ---------- 2) basla(): dayanıklı başlangıç ----------
eski_basla = """(async function basla(){
  const a = await apiGet('/api/ayar');
  AYAR = Object.assign(AYAR, a);
  altCubukGuncelle();"""
yeni_basla = """/* Motor henüz ayakta değilse kısa aralıklarla bekler (20 x 1,5 sn). */
async function dayanikliCek(yol, varsayilan, deneme){
  deneme = deneme || 20;
  for(let i=0;i<deneme;i++){
    try{
      const v = await apiGet(yol);
      if(v && !v.hata) return v;
    }catch(e){}
    const s1 = document.getElementById('altSol');
    if(s1) s1.innerHTML = '<span class="yukleniyor"></span> Motor bekleniyor\\u2026 (' + (i+1) + '/' + deneme + ')';
    await new Promise(r=>setTimeout(r, 1500));
  }
  throw new Error('Motor 30 saniyedir yanıt vermiyor');
}
(async function basla(){
  try{
  const a = await dayanikliCek('/api/ayar', {});
  AYAR = Object.assign(AYAR, a);
  altCubukGuncelle();"""
assert eski_basla in s, "basla() basi bulunamadi"
s = s.replace(eski_basla, yeni_basla, 1)
yapilan.append("basla() try + dayanikliCek")

eski_nabiz = """  const n = await apiGet('/api/nabiz');
  $saf('#altAdmin').textContent = 'Yetki: ' + (n.yonetici?'YÖNETİCİ (tam)':'normal kullanıcı');"""
yeni_nabiz = """  const n = await dayanikliCek('/api/nabiz', {});
  $saf('#altAdmin').textContent = 'Yetki: ' + (n.yonetici?'YÖNETİCİ (tam)':'normal kullanıcı');"""
assert eski_nabiz in s
s = s.replace(eski_nabiz, yeni_nabiz, 1)
yapilan.append("/api/nabiz dayanikli")

# basla() gövdesinin sonu: kapanıştan önce catch ekle
eski_son = """  setInterval(async ()=>{
    try{ const d = await apiGet('/api/durum'); altDurumYaz(d); }catch(e){}
  }, 20000);
})();"""
yeni_son = """  setInterval(async ()=>{
    try{ const d = await apiGet('/api/durum'); altDurumYaz(d); }catch(e){}
  }, 20000);
  } catch(hucre){
    try{ goster(AKTIF || 'panel'); }catch(e2){}
    sayfaHata(AKTIF || 'panel', hucre);
  }
})();"""
if eski_son in s:
    s = s.replace(eski_son, yeni_son, 1)
    yapilan.append("basla() catch eklendi")
else:
    print("UYARI: basla() sonu kaliplla eslesmedi, catch eklenemedi")

# ---------- 3) kenar çubuğu sürüm yazısı ----------
s = s.replace("SYSTEM CLEAN • PERFORMANCE • SECURITY<br>v1.1.0",
              "SYSTEM CLEAN • PERFORMANCE • SECURITY<br>v1.2.1", 1)
yapilan.append("kenar cubugu surum: v1.2.1")

# ---------- yaz (tmp + replace) ----------
tmp = P + ".tmp"
io.open(tmp, "w", encoding="utf-8", newline="").write(s)
okunan = io.open(tmp, encoding="utf-8").read()
assert okunan == s and "function motorBekle()" in okunan and "dayanikliCek" in okunan
os.replace(tmp, P)
print("YAPILDI:", " | ".join(yapilan))
print("boyut: %d -> %d" % (len(o), len(s)))
