# ÜSTAD PC OPTIMIZER — v1.2.1

Kenan Kuzucu için yazılmış **gerçek Windows bakım / izleme / kurtarma paneli**.
Masaüstünde bir uygulama penceresi olarak açılır; arkasında **salt Python standart kütüphanesi** ile
yazılmış gerçek bir Windows motoru çalışır (hiçbir harici paket, hiçbir bulut bağlantısı yoktur —
telemetri, reklam kimliği, uzak sunucu yok; tüm ölçümler bu bilgisayarda yapılır).

> Bu depo, çalışan sürümün **eksiksiz yedeğidir**: uygulama kaynakları + kurulu sürümün durum
> dosyaları + doğrulama betikleri + gerçek ekran görüntüsü kanıtları.

---

## Depo içeriği

| Yol | Ne var |
|---|---|
| `index.html` | Panel arayüzü (tek dosya, 22 sayfa, Türkçe) |
| `sunucu.py` | Windows motoru + yerel HTTP sunucusu (port 8891, salt 127.0.0.1) |
| `OKU-BENI.txt` | Kullanıcı kılavuzu: 22 sayfa tek tek, doğrulama notları, dürüst sınırlar |
| `USTAD-PC-OPTIMIZER.bat` | Başlatıcı: motoru açar, pencereyi açar, nöbeti tutar |
| `YONETICI-OLARAK.bat` | Yönetici haklarıyla başlatıcı |
| `KURULUM.bat` / `KALDIR.bat` | Kurulum (kısayollar) / kaldırma |
| `assets/` | Amblem, bayrak+taç, arma görselleri (panel başlığı) |
| `ikon.ico` | Kısayol simgesi |
| `araclar/` | Windows araç panosu çıktı klasörü |
| `yedekler/` | v1.2.0 panel dosyası + kurulu sürümün durum JSON'ları (ayar/geçmiş/alarm) |
| `testler/` | Motor + arayüz doğrulama betikleri (aşağıda) |
| `kanitlar/` | Gerçek makinede alınmış ekran görüntüsü kanıtları + Word-uyumlu rapor |

### Doğrulama betikleri (`testler/`)

- `ustad-v12-test.py` — motor uçlarının tam testi (36 kontrol; yönetici gerektirenlerin dürüst cevap
  verip vermediği dâhil)
- `ustad-pencere-test.py` — gerçek Win32 pencere düğmeleri (küçült / büyüt / kapat) testi
- `ustad-hiz-kanit.py` — hız katmanı ölçümü (ılk açılış / ısınma sonrası karşılaştırması)
- `ustad-ekran5.py`, `ustad-ekran6.py` — gerçek tarayıcıda sayfa ekran görüntüsü üretimi
- `v121-kanit-karti.py` — kanıt kartı (PNG) üretici
- `v12-tamamla.py`, `v12-ince-ayar.py`, `v121-saglam.py` — yama/iyileştirme betikleri (tarihsel)
- `kurt-temizle.py` — görsel temizleme yardımcısı

---

## Kurulum ve kullanım

1. `KURULUM.bat` dosyasına çift tıkla (masaüstüne kısayolları kurar, uygulamayı
   `%LOCALAPPDATA%\USTAD-PC-OPTIMIZER` altına kopyalar).
2. Masaüstündeki **ÜSTAD PC OPTIMIZER** kısayoluna bas → panel açılır.
   Yönetici gerektiren işleri kullanacaksan **ÜSTAD PC OPTIMIZER (Yönetici)** kısayolunu kullan.
3. Paneli kapatınca motor 5 dakika içinde kendini kapatır ve `port.txt` dosyasını siler.

Kurulum gerekmeden denemek için: `sunucu.py` dosyasını çalıştır, çıkan adresi tarayıcıda aç.

---

## Sürüm geçmişi

| Sürüm | Ne geldi |
|---|---|
| v1.0.0 | Panel + temel motor (temizlik, performans, program yönetimi, zorla kaldırma) |
| v1.1.0 | 29 madde: sistem tarama, TURBO mod, derin temizleme, ağ & hız, donanım, disk, araçlar, güvenlik, raporlar, ayarlar + gerçek Win32 pencere düğmeleri |
| v1.2.0 | 20 yeni özellik: canlı izleme, hız testi/benchmark, kurtarma & yedek, görev & hizmet yönetimi, güncelleme & gizlilik, alarm & bildirim + **hız katmanı** (önbellek + ısınma döngüsü) → 22 sayfa |
| v1.2.1 | **“Panel boş kalıyor / hep düşünüyor” hatası düzeltildi**: kapsam hatası giderildi, kırılgan pencere-nöbeti kaldırılıp yerine panel kalp atışı geldi, ağır ölçümler artık isteği bekletmiyor (bayat veriyi hemen ver, arkada tazele) |

---

## Doğrulama (bu makinede ölçüldü)

| Ölçüm | Sonuç |
|---|---|
| Motor uç testi | **36/36 GEÇTİ** (`testler/ustad-v12-test.py`) |
| Arayüz sayfaları | **22/22 sayfa açıldı, 0 JavaScript hatası** |
| Kalp atışı testi | Vuruş yok → motor kendini kapattı ve `port.txt` sildi · panel açıkken motor açık kaldı |
| Hız (ilk açılış → ısınma sonrası) | ağ taraması 29,30 sn → **0,01 sn** · sistem tarama 4,69 → **0,02** · donanım 3,82 → **0,02** · görevler (206) 2,75 → **0,02** · canlı ölçüm 2,06 → **0,02** |
| Kaynak = kurulu sürüm | `diff` ile birebir aynı |
| Ölçülen sistem | Windows 11 Pro 26200 · Intel i3-10100F @3,60 GHz · 15,9 GB RAM · 3 SSD (hepsi Healthy) |

Kanıt görselleri `kanitlar/` klasöründe: panel, canlı izleme, hız testi, kurtarma, yönetim,
güncelleme, alarm sayfaları ve hız tablosu.

---

## Mimari özeti

- **Motor:** `http.server.ThreadingHTTPServer`, yalnız `127.0.0.1` dinler; port 8891'den başlar,
  doluysa 8891–8903 arasında boş port arar. Seçilen port + motor PID `port.txt` dosyasına yazılır.
- **Hız katmanı:** `onbellekli(anahtar, ttl, üret, bekle=False)` — kayıt varsa bayat olsa bile anında
  döner ve tazeleme arka planda yapılır; kayıt yoksa `{"hazirlaniyor": true}` döner, ölçüm arka
  planda tamamlanır. `isinma_dongusu()` ağır ölçümleri (en çok 2 eş zamanlı) sıcak tutar.
- **Kalp atışı / nöbet:** Panel 20 saniyede bir `/api/nabiz` çağırır. Motor son vuruşu hatırlar;
  `NOBET_SN` (varsayılan 300 sn) boyunca vuruş gelmezse `port.txt` silinip süreç kapanır.
  `--kal` argümanı ya da `USTAD_NOBET=0` nöbeti kapatır (geliştirme için `USTAD_NOBET_SN` ile
  eşik değiştirilebilir).
- **Yönetici işleri:** Panel gizlice yetki yükseltmez. İş yönetici istiyorsa
  `{"yoneticiGerekli": true, "mesaj": ...}` döner, arayüz sorar; onay verilirse `zorla: true` ile
  ikinci istek gider ve UAC penceresi açılır.
- **Geri alınabilir işlemler:** Silinen/taşınan her şey önce `kasa/` klasörüne gider; görev/hizmet
  değişiklikleri kaydedilir ve geri alınabilir.

## Dürüst sınırlar

- **CPU/fan sıcaklığı bu makinede okunamıyor** (ACPI termal bölge yayınlanmıyor) → panel uydurma
  değer göstermek yerine “**desteklemiyor**” yazar.
- Geri yükleme noktası, sürücü yedeği, telemetri kapatma, yazıcı kuyruğu temizliği ve bazı
  görev/hizmet değişiklikleri **yönetici** gerektirir; panel bunu söyler ve sorar.
- `winget` kurulu değilse program güncelleme listesi boş görünür (şu an böyle).
- Telegram bildirimi isteğe bağlıdır; bot token + sohbet kimliği girilmezse yalnız panel uyarır.

## Sırlar / gizlilik notu

Bu depoda **hiçbir gizli anahtar, şifre veya token yoktur** (Telegram alanları boş gelir, kullanıcı
kendi doldurur). Tarayıcı profili, önbellek ve geçici dosyalar (`tarayici-profil/`, `__pycache__/`,
`port.txt`) bilinçli olarak yedeğe alınmamıştır.

---

**Ölçümler bu bilgisayarda yapıldı; hiçbir veri dışarı gönderilmedi.**
