# RE/MAX ÇARŞI İlan Botu V12

Windows ve macOS masaüstü uygulaması.

## V12 kritik değişiklik

Sahibinden taraması artık QtWebEngine DOM üzerinden yapılmaz. `TARA` düğmesi görünür **Google Chrome + Playwright** tarayıcısını açar. Uygulamanın içindeki Sahibinden sekmesi yalnızca önizleme ve manuel gezinme içindir.

### Tarama akışı

1. Web Sekmeleri > İlan Tarayıcı bölümünde kaynak seçilir.
2. `TARA` basılır.
3. Google Chrome görünür şekilde açılır.
4. Seçili mağazanın liste görünümündeki tüm ilan bağlantıları sayfalar boyunca toplanır.
5. Her ilan tek tek açılır ve analiz edilir.
6. İlerleme `1 / toplam`, `2 / toplam` biçiminde görünür.
7. CAPTCHA / robot kontrolü çıkarsa Chrome açık kalır. Kullanıcı doğrulamayı tamamlar ve masaüstü uygulamada `DEVAM ET` basar.
8. Yalnızca tarama tam başarıyla biterse seçili kaynağın SQLite kayıtları değiştirilir.
9. Diğer kaynakların ilanları korunur.

### Saklanan bilgiler

Kaynak, danışman/ilan sahibi, görünür telefon, ilan başlığı, fiyat, bölge, oda, m², satılık/kiralık, emlak türü, ilan tarihi ve doğrudan Sahibinden ilan URL'si.

## Kurulum macOS

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
pytest -v
python -m remax_bot.app
```

## Kurulum Windows

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium
pytest -v
python -m remax_bot.app
```

Program önce kurulu Google Chrome'u kullanmayı dener. Chrome bulunamazsa Playwright Chromium'a düşer. Playwright için ayrı kalıcı profil kullanılır; ilk Sahibinden girişinden sonra oturum bu profilde korunur.


## V14
- Sahibinden satır seçimi tıklanabilir öğe-merkezli değil, ilan satırı-merkezli yapıldı.
- Fiyat + tarih/konum içeren satırlar önce bulunur, sonra ilan başlığı seçilir.
- JavaScript DOM taraması sonuç vermezse Playwright locator tabanlı Shadow DOM uyumlu fallback çalışır.
- Hata mesajında tr/link/fiyat adayı/body uzunluğu ve locator tarama sayıları gösterilir.
- Başarısız tarama veritabanını değiştirmez.


# V15
- RE/MAX ÇARŞI ve ÇARŞI 2 kaynakları remax.com.tr portföy sayfalarına çevrildi.
- Excel (.xlsx) / CSV ilan listesi içe aktarma eklendi.
- Manuel ilan ekleme eklendi.
- Ortak ilan havuzu ve mükerrer güncelleme eklendi.
- #? bot yardım komutu eklendi.
- #...# dışındaki normal mesajlar yok sayılır.
- Komut test alanı Ayarlar bölümüne eklendi.

# V16
- Ayrı Chrome/Playwright penceresi kaldırıldı.
- RE/MAX taraması uygulamanın kendi gömülü WebEngine sekmesinde çalışır.
- Portföy URL'leri `/tr/portfoy/P...` ve `P########` kodlarından toplanır.
- 2, 3, ... sayfa butonları program içinde otomatik tıklanır.
- Toplanan portföyler aynı gömülü sekmede tek tek açılarak detayları okunur.
- Excel/CSV ve manuel ilan ekleme sistemi korunmuştur.
- `#?` yardım ve `#...#` komut motoru korunmuştur.


# V17 - Shadow DOM kart taraması
- Ayrı Chrome açılmaz; tarama uygulamanın içindeki RE/MAX sekmesinde yapılır.
- RE/MAX kartları Shadow DOM dahil recursive olarak bulunur.
- 1. karta tıkla -> detayları oku -> geri dön -> 2. karta tıkla akışı uygulanır.
- Sayfadaki kartlar bitince 2, 3, ... sayfa düğmeleri aynı gömülü tarayıcıda tıklanır.
- Detaylardan portföy no, başlık, fiyat, bölge, oda, m², tür, tarih, danışman, telefon ve RE/MAX linki alınır.
- Excel/CSV, manuel ilan ve #? komut sistemi korunur.

# V18 - Playwright RE/MAX tarama motoru
V17 Qt DOM taraması yerine Playwright Chromium kullanır. TARA seçilen ofisin tüm /tr/portfoy/P... bağlantılarını sayfalardan toplar ve her detay sayfasını okuyarak veritabanını günceller.

İlk kurulum:
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
python -m remax_bot.app

# V20 - WhatsApp Web uyumluluk düzeltmesi
- WhatsApp Web için ayrı QWebEngineProfile kullanılır.
- Güncel Chrome 136 User-Agent tanımlandı.
- WhatsApp çerezleri ve oturumu ayrı kalıcı profilde saklanır.
- Türkçe Accept-Language ayarı eklendi.
- RE/MAX tarama profili bu değişiklikten etkilenmez.


# V22 - WhatsApp grup algılama düzeltmesi
- Açık grup başlığı satır sonları korunarak okunur; üye listesi grup adına karışmaz.
- Grup zaten açıksa soldaki sohbet listesinde tekrar aranmaz.
- Mesajlar hem message-in/message-out hem data-id satırlarından okunur.
- Aynı mesaj içinde #...# komutu ayrıca ayıklanır.
- Bot hesabından gönderilen #...# komutları da sorgulanır.


# V23
- WhatsApp grup araması tamamen kaldırıldı.
- Bot WhatsApp sekmesinde kullanıcının açık tuttuğu sohbeti dinler.
- Ayarlara AÇIK SOHBETİ BOT GRUBU YAP düğmesi eklendi.
- Hem gelen hem giden #...# komutları işlenir.
- Normal mesajlar yok sayılır.


# V24
- WhatsApp'ta grup arama ve açık sohbet başlığı okuma kaldırıldı.
- Bot yalnızca WhatsApp Web sekmesinde o anda açık olan sohbeti dinler.
- Ayarlardaki grup adı yalnızca bilgi/etiket amaçlıdır.
- Bot başlatmak için grup adı zorunlu değildir.
- Hem gelen hem giden #...# komutları işlenir.
- Normal mesajlar yok sayılır; bot cevapları yeniden komut olarak işlenmez.


# V26 - Selenium WhatsApp motoru
- WhatsApp mesaj okuma/gönderme motoru, daha önce çalışan pregate-mail-bot projesindeki Selenium yaklaşımına geçirildi.
- Qt WebEngine artık botun mesaj okuma motoru değildir; yalnızca uygulama içi WhatsApp görüntüleme sekmesi olarak kalır.
- Botu Başlat gerçek Chrome'u kalıcı profil ile açar. İlk kullanımda QR okutulur, sonraki açılışlarda oturum korunur.
- Ayarlardaki grup adı varsa Chrome üzerinde aranır; bulunamazsa kullanıcı grubu manuel açabilir.
- WhatsApp cevap modu #bot başlat# komutuyla aktif olur.
- #bot durdur# sorgu modunu durdurur.
- Aktif modda #?, #izmit kiralık 3+1#, #... link# gibi ilan sorguları yerel ilan havuzundan cevaplanır.
- Hem gelen hem de bot hesabından yazılan komutlar okunur. Bot yanıtları #...# biçiminde olmadığı için tekrar komut olarak işlenmez.
