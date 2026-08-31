# RE/MAX ÇARŞI İlan Botu

Windows ve macOS üzerinde çalışan ilan yönetimi ve WhatsApp yanıt uygulaması.

## Özellikler

- RE/MAX ÇARŞI ve RE/MAX ÇARŞI 2 portföylerini tarar.
- Excel/CSV dosyalarından veya manuel girişten ilan ekler.
- İlanları danışman, konum, tür ve fiyata göre filtreler.
- Uygulamanın içindeki WhatsApp Web panelinden mesajları okur ve yanıtlar.
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

İlk WhatsApp kullanımında uygulamanın içindeki WhatsApp panelinde görünen QR kodunu okutun. Oturum sonraki açılışlarda korunur.

## Botu kullanma

1. Sabit bir grup isterseniz **Ayarlar** bölümüne WhatsApp grup/sohbet adını eksiksiz yazıp kaydedin; panel otomatik olarak bu gruba geçer.
2. **BOTU BAŞLAT** düğmesine basın.
3. Max uygulamanın içindeki WhatsApp panelinde belirtilen sohbeti bulur.
4. Durum satırında grubun açıldığı görüldükten sonra sohbete `#Max başla` veya `#Max başlat` yazın.
5. `#?` ile komut yardımını veya örneğin `#izmit kiralık 3+1#` sorgusunu gönderin.
6. `#Max durdur` ile cevap modunu kapatın.

Grup adı boş bırakılırsa Max, `#Max başla` veya `#Max başlat` komutunun görüldüğü açık sohbete kilitlenir. Ayarlarda grup adı varsa o grup önceliklidir ve diğer sohbetlerdeki komutlar yok sayılır.

## Test

```bash
python -m pytest -q
```

## Hazır paketler

`.github/workflows/main.yml` her ana dal güncellemesinde testleri çalıştırır. Testler başarılı olursa Windows EXE ve macOS APP paketleri GitHub Actions çıktısı olarak hazırlanır.
