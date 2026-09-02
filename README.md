# RE/MAX ÇARŞI İlan Botu

Windows ve macOS üzerinde çalışan ilan yönetimi ve WhatsApp yanıt uygulaması.

## Özellikler

- İki MyRE/MAX ofisini, Emlakjet ÇARŞI ofisini ve iki Sahibinden mağazasını ayrı kaynaklar olarak tarar.
- İlanlar sayfasını Sahibinden, Emlakjet ve MyRE/MAX sekmelerinde ayrı listeler.
- Aktif site sekmesindeki tüm ilanları Excel'e aktarır; MyRE/MAX ve Sahibinden sekmeleri kendi iki ofis/mağaza kaynaklarını birlikte içerir.
- Tabloda seçilen bir ilanın hatalı alanlarını uygulama içinde düzenleyip günceller.
- `#danışmanlar` komutunda her danışmanın üç sitedeki ilan adetlerini ayrı ayrı gösterir.
- Excel/CSV dosyalarından veya manuel girişten ilan ekler.
- İlanları danışman, konum, tür ve fiyata göre filtreler.
- `dükkan-ofis` ve `ev-daire` gibi birleşik sorgularda türlerden herhangi biriyle eşleşir.
- İlan arama komutlarında ayrıca `link` yazılmasa da sonuçları doğrudan ilan linkleriyle gönderir.
- Danışman isimlerinin farklı yazımlarını Ayarlar bölümünde seçerek kalıcı biçimde tek isim altında birleştirir; gerektiğinde birleştirmeyi kaldırır.
- Kalıcı oturum profiliyle ayrı bir Google Chrome penceresindeki WhatsApp Web mesajlarını okur ve yanıtlar.
- Ayarlardaki grup/sohbet adını otomatik bulup açar.
- Aynı mesajı yalnızca bir kez işler ve yanıtı gerçek Gönder düğmesiyle yollar.
- WhatsApp ve tarayıcı profillerini bilgisayarda kalıcı olarak saklar.

## Kurulum

Python 3.11 veya daha yeni bir sürüm gerekir.

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m remax_bot.app
```

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m remax_bot.app
```

İlk WhatsApp kullanımında otomatik açılan Google Chrome penceresindeki QR kodunu okutun. Bu pencerenin oturumu sonraki açılışlarda korunur.

## Botu kullanma

1. Sabit bir grup isterseniz **Ayarlar** bölümüne WhatsApp grup/sohbet adını eksiksiz yazıp kaydedin; Chrome otomatik olarak bu gruba geçer.
2. **BOTU BAŞLAT** düğmesine basın.
3. Max, ayrı Google Chrome penceresindeki WhatsApp Web'de belirtilen sohbeti bulur.
4. Durum satırında grubun açıldığı görüldükten sonra sohbete `#Max başla` veya `#Max başlat` yazın.
5. `#?` ile komut yardımını veya örneğin `#izmit kiralık 3+1#` sorgusunu gönderin.
6. `#Max durdur` ile cevap modunu kapatın.

Komutları WhatsApp'a göndermeden denemek için soldaki **Bot Testi** sayfasını kullanabilirsiniz. Ana Sayfa WhatsApp bağlantı durumunu ve Chrome penceresini öne getiren düğmeyi gösterir.

Normal ilan sorguları, Ayarlar bölümünde seçili sitedeki sonuçları linkleriyle döndürür. Komutun başına `#emlakjet`, `#sahibinden` veya `#myremax` yazarak o sorgu için site seçimini geçersiz kılabilirsiniz. Örnek: `#emlakjet izmit kiralık dükkan-ofis`.

## İlan kaynaklarını güncelleme

1. **İlanlar** sayfasındaki kaynak listesinden MyRE/MAX, Emlakjet veya Sahibinden kaynağını seçin.
2. **TARA / GÜNCELLE** düğmesine basın.
3. Site güvenlik doğrulaması isterse açılan tarama penceresinde doğrulamayı tamamlayın.
4. Tarama eksik kalırsa o kaynağın önceki ilanları korunur; başarılı olursa yalnızca seçilen kaynak yenilenir.

Aktif Sahibinden, Emlakjet veya MyRE/MAX sekmesindeki tüm ilanları almak için **EXCEL'E AKTAR** düğmesini kullanın. Bir satırı düzeltmek için satırı seçip **SEÇİLİ İLANI DÜZENLE** düğmesine basın. Kaynak sütunu dışa aktarılan dosyada korunduğu için dosya yeniden yüklendiğinde ilanlar doğru site sekmesine döner.

Danışman yazım farklılıklarını düzeltmek için **Ayarlar > Danışman İsimlerini Birleştir** alanında isimleri işaretleyin, kullanılacak ana ismi seçin veya yazın ve **BİRLEŞTİR VE GÜNCELLE** düğmesine basın. Sadece işaretlenen isimler birleşir; kural sonraki tarama ve yüklemelere de uygulanır. Aynı alandan birleştirmeyi kaldırabilirsiniz.

Grup adı boş bırakılırsa Max, `#Max başla` veya `#Max başlat` komutunun görüldüğü açık sohbete kilitlenir. Ayarlarda grup adı varsa o grup önceliklidir ve diğer sohbetlerdeki komutlar yok sayılır.

## Test

```bash
python -m pytest -q
```

## Hazır paketler

`.github/workflows/main.yml` her ana dal güncellemesinde testleri çalıştırır. Testler başarılı olursa Windows EXE ve macOS APP paketleri GitHub Actions çıktısı olarak hazırlanır.
