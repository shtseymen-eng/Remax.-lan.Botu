# İlan Silme ve Kaynak Uzlaştırma Tasarımı

## Amaç

İlanlar ekranında kullanıcıya kalıcı veritabanındaki bütün ilanları, gerçek bir kaynağın bütün ilanlarını veya tabloda seçtiği ilanları güvenle silme imkânı vermek; başarılı tam tarama sonrasında yayından kalkmış ilanları kaldırırken başarısız, yarım ya da şüpheli biçimde boş taramada eski kayıtları korumak.

## Hedefler

- Her silme öncesinde etkilenecek kesin kayıt sayısını göstermek ve açık kullanıcı onayı almak.
- Tüm ilan, kaynak ve seçili satır silmelerini tek işlem içinde kalıcı SQLite veritabanına uygulamak.
- Kaynak seçicisinde sabit bir tahmin listesi yerine veritabanındaki gerçek kaynakları ve sayımlarını göstermek; RE/MAX ÇARŞI, ÇARŞI 2, Sahibinden mağazaları, Emlakjet, Excel/CSV ve manuel kaynaklar bu yolla doğal olarak kapsanır.
- Silme sonrasında tabloları, sekme ve toplam sayaçlarını, filtre seçeneklerini ve danışman listelerini tek `refresh()` akışıyla yenilemek.
- Max motorunu değiştirmeden, mevcut her-komutta-DB-okuma davranışı sayesinde sonraki arama sonuçlarının güncel kayıtları kullanmasını sağlamak.
- Tam ve doğrulanmış tarama sonucunu kaynak için atomik olarak değiştirerek yayından kalkmış ilanları kaldırmak; boş sonuç veya herhangi bir tarama doğrulama hatasında eski veriyi korumak.

## Kapsam Dışı

- WhatsApp Max komutları, arama algoritması veya Chrome çalışma biçimi değiştirilmeyecek.
- Danışman isim birleştirme kuralları silinmeyecek; bunlar gelecekteki taramalar için kalıcı ayardır, ilan kaydı değildir.
- Arayüzün sayfa düzeni ve görsel dili yeniden tasarlanmayacak; mevcut düğme, seçim kutusu ve mesaj kutusu bileşenleri kullanılacak.
- Kaynağın gerçekten sıfır ilana düştüğünü otomatik olarak kabul eden bir yol eklenmeyecek; sıfır sonuç güvenlik gereği şüpheli sayılacak ve veri korunacak.

## Yaklaşımlar

1. **Önerilen ve seçilen: DB merkezli küçük API + mevcut `refresh()` akışı.** Silme/sayım işlemleri `DB` üzerinde tutulur, arayüz sadece kimlikleri toplar, sayıyı gösterir, onay alır ve yeniler. En az değişiklikle atomiklik ve bütün tüketicilerde tutarlı veri sağlar.
2. **Arayüzde doğrudan SQL.** Daha az satır gibi görünür ancak veri mantığını pencereye bağlar, test etmeyi zorlaştırır ve farklı silme yollarında tutarsızlık riski yaratır; kullanılmayacak.
3. **Soft-delete/çöp kutusu.** Geri alma sağlayabilir fakat tüm sorgu ve sayaçların yeni bir durum alanını tanımasını, şema göçünü ve Max aramasının değişmesini gerektirir; kalıcı silme talebinin ve mevcut mimarinin ötesindedir.

## Tasarım

`DB`, kaynakları `(source_url, count)` olarak listeleyen ve silinen gerçek satır sayısını döndüren `delete_all`, `delete_source` ve `delete_listings` işlemlerini sağlayacak. Seçili kimlikler `(source_url, listing_id)` çiftleri olacak ve yinelenen seçimler tekilleştirilecek. Kaynak URL'leri mevcut `source_key()` ile normalize edilecek.

İlanlar ekranındaki tablolar çoklu satır seçimine açılacak. Mevcut tarama/düzenleme alanına, veri tabanındaki gerçek kaynaklarla yenilenen bir kaynak seçicisi ve üç silme düğmesi eklenecek. Her işlem işlem anındaki DB sayısını kullanacak; sayı sıfırsa silme yapılmayacak. Onay iletişim kutusunun metni kesin kayıt sayısını içerecek ve varsayılan cevap “Hayır” olacak. Başarılı silmeden sonra seçim izi temizlenecek ve ortak yenileme akışı çalıştırılacak.

Tarayıcı katmanındaki mevcut toplam-link-ayrıntı eşitliği doğrulamaları korunacak. `replace_source` boş koleksiyonu kabul etmeyerek savunmayı veri katmanına da taşıyacak. Yalnızca doğrulamaları geçen, boş olmayan tam sonuç kaynağı atomik biçimde değiştirir; bu değişim aynı kaynakta artık bulunmayan kayıtları kaldırır ve diğer kaynaklara dokunmaz.

## Doğrulama

- DB testleri üç silme kapsamını, gerçek kaynak sayımlarını, kimlik tekilleştirmeyi ve kaynak izolasyonunu doğrulayacak.
- Tarama uzlaştırma testleri eski kaydın tam sonuçta kaldırıldığını, boş sonuçta korunduğunu ve işlem hatasında rollback yapıldığını doğrulayacak.
- UI sözleşme testleri üç kontrolü, çoklu seçim modunu, sayımlı onay çağrılarını ve silme sonrası ortak yenilemeyi sabitleyecek.
- Bütün pytest paketi çalıştırılacak; GitHub Actions dosyası ve bağımlılıkları platformlar arası paketleme uyumluluğunu koruyacak şekilde değişmeden bırakılacak.
