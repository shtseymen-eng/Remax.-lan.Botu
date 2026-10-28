# İlan Ayrıntıları, Excel Akışı ve Max Arama Ayarları Tasarımı

## Amaç

Sahibinden ilanları, dışarıdaki bir yapay zekânın doldurduğu standart Excel/CSV dosyasından alınacak; Emlakjet ve iki MyRE/MAX kaynağı dosya içe aktarıldıktan sonra uygulama tarafından taranacak. Bütün ilanlar tek kalıcı havuzda birleşecek ve Max, Ayarlar bölümünde seçilen kaynaklar ile veri alanlarını kullanarak WhatsApp komutlarına her zaman ilan linkleriyle cevap verecek.

## Hedefler

- Sahibinden için ilan detaylarını ve adres bileşenlerini kayıpsız içe aktarmak.
- Emlakjet ile iki MyRE/MAX kaynağını Excel/CSV yüklemesinden sonra sırayla güncellemek.
- İl, ilçe, mahalle, sokak/cadde, site ve açık adresi yalnızca kaynakta mevcutsa saklamak.
- Kategoriye göre değişen bütün ilan özelliklerini kaybetmeden korumak ve Max aramasına açmak.
- Max'in komut işaretini, arama kaynaklarını, arama alanlarını ve yükleme sonrası tarama davranışını Ayarlar bölümünden yönetmek.
- `danışmanlar` komutunda danışmanların Sahibinden, Emlakjet ve MyRE/MAX adetlerini ayrı ve toplam göstermek.
- Normal aramalarda `ilan` veya `link` kelimesi aranmadan sonuç linklerini her zaman göndermek.
- Mevcut uygulama düzenini, marka görünümünü ve WhatsApp okuma/gönderme akışını korumak.

## Hedef Dışı Konular

- Sahibinden linklerini uygulamanın kendisinin yapay zekâyla yorumlaması bu çalışmanın parçası değildir; Excel/CSV dosyasını dışarıdaki yapay zekâ doldurur.
- Eksik adres veya ilan özelliği tahmin edilmeyecek ve başka alanlardan uydurulmayacaktır.
- WhatsApp Web DOM okuyucusu, gönderim kuyruğu, oturum profili ve pencere çalışma şekli yeniden tasarlanmayacaktır.
- Uygulamanın görsel tasarımı veya sayfa yapısı değiştirilmeyecektir; yalnızca mevcut Ayarlar, İlanlar ve Veri Ekle sayfalarına gerekli kontroller/alanlar eklenecektir.

## Mevcut Durum

- `Listing` modeli 13 alan saklıyor; adres yalnızca tek `location` metnidir.
- SQLite tablosu bu 13 alanı kalıcı tutuyor ve eski şemayı bir defalık tablo taşımasıyla dönüştürebiliyor.
- Excel ve CSV okunabiliyor, fakat dışa aktarma yalnızca XLSX'tir ve kategoriye özgü ek özellikleri korumaz.
- Sahibinden detay ayrıştırıcısı ilan numarası, başlık, link, danışman, telefon, fiyat, genel konum, oda, ilk m² değeri, tarih, işlem türü ve sınırlı bir emlak türü listesi alıyor.
- Max araması başlık, danışman, telefon, fiyat, genel konum, oda, işlem türü, emlak türü, m², tarih ve kaynak etiketinde çalışıyor.
- `danışmanlar` ve normal sonuçlarda link gönderme davranışı zaten vardır; bunlar korunup yeni modele bağlanacaktır.

## Değerlendirilen Yaklaşımlar

### 1. Merkezî ilan havuzu ve esnek ayrıntı sözlüğü — seçilen yaklaşım

Sabit, karşılaştırılabilir alanlar `Listing` ve SQLite şemasında tutulur. Kategoriye göre değişen etiket-değer çiftleri ayrıca JSON ayrıntı sözlüğünde saklanır. Excel/CSV, sabit alanların yanında dinamik ayrıntı sütunlarını da kayıpsız taşır. Max tek birleşik havuzda, Ayarlar'da seçilen alanlarda arama yapar.

Bu yaklaşım veri kaybını önler, üç platformu karşılaştırılabilir tutar ve Sahibinden yeni bir özellik etiketi eklediğinde şema değişikliği gerektirmez.

### 2. Excel'i ana veri deposu yapmak — reddedildi

Kurulumu daha basit görünür; ancak eşzamanlı taramalar, tekrar kayıtları, danışman birleştirmeleri ve kaynak bazlı güvenli yenileme kırılganlaşır.

### 3. Her emlak kategorisine ayrı tablo/şablon yapmak — reddedildi

Daire, arsa, ticari ve bina ilanlarını ayrıntılı temsil eder; fakat kullanıcıya birden çok dosya yükü getirir ve platformlar arası aramayı karmaşıklaştırır.

## Veri Modeli

Mevcut alanlar geriye uyumluluk için korunur. Aşağıdaki sabit alanlar eklenir:

- `province`: il
- `district`: ilçe
- `neighborhood`: mahalle
- `street`: sokak veya cadde
- `complex_name`: site/proje adı
- `full_address`: kaynakta açıkça gösterilen açık adres
- `description`: temizlenmiş ilan açıklaması
- `net_sqm`: net metrekare; mevcut `sqm` brüt/genel metrekare olarak kalır
- `details`: kategoriye özgü, normalize edilmiş etiket-değer sözlüğü

`details` içinde örneğin bina yaşı, kat, toplam kat, ısıtma, banyo, balkon, eşyalı, kullanım durumu, site içerisinde, aidat, tapu, kredi, takas, cephe, otopark ve asansör tutulabilir. Kaynakta olmayan anahtar oluşturulmaz; boş değerler boş kalır.

SQLite şema yükseltmesi mevcut kayıtları koruyarak yeni sütunları boş varsayılanlarla ekler. Ayrıntı sözlüğü UTF-8 JSON olarak saklanır. Okuma sırasında bozuk JSON güvenli biçimde boş sözlük kabul edilir ve diğer ilan alanları kaybedilmez.

## Excel ve CSV Sözleşmesi

Hazırlanacak örnek dosyada tek zorunlu alan `İlan Linki` olacaktır. Dış yapay zekâ mümkün olan alanları doldurur. Önerilen sabit sütunlar:

- İlan No, Başlık, İlan Linki, Kaynak
- Danışman, Telefon, Fiyat
- Satılık/Kiralık, Emlak Türü, Oda, Brüt m², Net m², İlan Tarihi
- İl, İlçe, Mahalle, Sokak/Cadde, Site/Proje, Açık Adres
- İlan Açıklaması

Bu sabit sütunlardan sonra bina yaşı, bulunduğu kat, ısıtma gibi ek sütunlar yer alabilir. Tanınmayan fakat değeri olan sütunlar `details` sözlüğüne alınır; sonraki Excel/CSV dışa aktarımında yeniden ayrı sütunlar olarak yazılır. Böylece yapay zekânın doldurduğu hiçbir ilan ayrıntısı sessizce atılmaz.

Hem `.xlsx` hem `.csv` için aynı başlık eşleştirmesi kullanılır. Dışa aktarım iki biçimi de destekler ve Türkçe karakterleri korur. Eski şablondaki `Bölge` sütunu okunmaya devam eder.

## İçe Aktarma ve Otomatik Tarama Akışı

1. Kullanıcı Veri Ekle sayfasından Excel/CSV dosyasını yükler.
2. Satırlar doğrulanır, Sahibinden linkleri Sahibinden kaynağına sınıflandırılır ve mevcut tekrar önleme kurallarıyla ilan havuzuna eklenir/güncellenir.
3. Başarılı içe aktarmadan sonra Ayarlar'da etkinleştirilen otomatik kaynaklar sıraya alınır. Varsayılan sıra MyRE/MAX ÇARŞI, MyRE/MAX ÇARŞI 2 ve Emlakjet ÇARŞI'dır.
4. Her kaynak mevcut Playwright tarayıcısıyla tamamlanır; kaynak yalnızca tam ve doğrulanmış tarama sonunda değiştirilir.
5. Bir kaynağın taraması başarısız olursa o kaynağın eski kayıtları ve içe aktarılan Sahibinden kayıtları korunur. Hata kullanıcıya gösterilir; ayara bağlı kuyruk kalan bağımsız kaynağa devam eder.
6. İlerleme mevcut tarama durum alanında gösterilir; yeni pencere veya yeni ana sayfa oluşturulmaz.

## Max Ayarları

Mevcut Ayarlar sayfasına `Max Arama Ayarları` grubu eklenir:

- **Komut işareti:** varsayılan `#`; tek, görünür ve boşluk olmayan karakter. Yardım metni ve bütün Max komutları seçilen işareti gösterir.
- **Aranacak kaynaklar:** Sahibinden, Emlakjet ve MyRE/MAX için çoklu seçim; yeni kurulumda üçü de seçilidir.
- **Aranacak veri alanları:** başlık, danışman, telefon, fiyat, adres/konum, oda, işlem türü, emlak türü, m², ilan tarihi, açıklama ve ek özellikler için çoklu seçim; yeni kurulumda hepsi seçilidir.
- **Yükleme sonrası otomatik tarama:** aç/kapat.
- **Otomatik taranacak kaynaklar:** iki MyRE/MAX ofisi ve Emlakjet ofisi için çoklu seçim; varsayılan olarak üçü de seçilidir.

Seçilmeyen alanlar veya kaynaklar silinmez; yalnızca Max'in normal aramasına katılmaz. `danışmanlar` komutu, kullanıcı isteği gereği arama alanı seçimlerinden bağımsız olarak ilan havuzundaki üç platformun tamamını karşılaştırır.

## Komut Davranışı

- Varsayılan örnekler `#danışmanlar`, `#sahibinden izmit kiralık`, `#ayşe yılmaz başiskele satılık` biçimindedir.
- Komut işareti `!` yapılırsa aynı komutlar `!danışmanlar` ve `!sahibinden ...` olur.
- Başlatma/durdurma ve yardım komutları da aynı ayarlanmış işareti kullanır; varsayılan `#` eski davranışı aynen korur.
- Normal aramada bütün sorgu kelimeleri Ayarlar'da seçilen alanlarda aranır. Adres, başlık ve danışman eşleşmeleri daha yüksek ağırlıkla sıralanır; açıklama ve ek özellikler sonuç bulmayı genişletir.
- Fiyat ifadeleri mevcut `55 bin`, `4 milyon` ve doğrudan TL biçimlerini desteklemeye devam eder.
- Sonuçlar, kullanıcı `ilan` veya `link` yazmasa da başlık, fiyat, konum/adres, danışman ve ilan linkini içerir.
- `danışmanlar` her danışman için MyRE/MAX, Emlakjet, Sahibinden ve toplam sayıyı verir; danışman birleştirme kuralları uygulanmaya devam eder.

## WhatsApp Güvenliği ve Geriye Uyumluluk

WhatsApp Web'i okuyan DOM betikleri, sohbet kilidi, geçmişi tekrar işlememe, gönderim kuyruğu, kalıcı Chrome profili ve gönder düğmesi davranışı değişmeyecektir. Yalnızca komut sınıflandırıcısına kaydedilmiş komut işareti verilecektir. Varsayılan ayar `#` olduğundan mevcut kurulum ve komutlar değişmeden çalışır.

Eski ayar dosyalarında yeni anahtarlar yoksa güvenli varsayılanlar kullanılır. Eski Excel/CSV dosyaları, mevcut SQLite verileri ve manuel ilan girişleri çalışmaya devam eder.

## Arayüz Etkisi

- İlan listesinde mevcut sütunlar korunur; `Adres` sütunu eklenir ve bilinen adres bileşenleriyle gösterilir.
- Ayrıntılı ayrı adres alanları ve ek özellikler ilan düzenleme penceresinde bulunur.
- Veri Ekle sayfasındaki mevcut yükleme/dışa aktarma düzeni korunur; dışa aktarma dosya türüne Excel ve CSV eklenir ve örnek şablon indirme düğmesi eklenir.
- Ayarlar sayfasında yukarıdaki Max ve otomatik tarama seçenekleri tek bir yeni grup içinde yer alır.

## Doğrulama

- Her üç platformun adres ve ayrıntı ayrıştırıcıları gerçekçi sayfa metni örnekleriyle test edilir.
- Eksik adres bileşenlerinin boş kaldığı ve uydurulmadığı test edilir.
- Eski SQLite şemasının veri kaybetmeden yükseldiği test edilir.
- Excel ve CSV gidiş-dönüş testleri sabit alanları, dinamik ayrıntıları ve Türkçe karakterleri doğrular.
- Excel yükleme sonrası kaynak kuyruğunun sırası, hata halinde eski veriyi koruması ve kalan kaynaklara devamı test edilir.
- Ayarlanmış komut işareti, kaynak/alan seçimleri, bütün-alan araması, fiyat araması ve koşulsuz link çıktısı test edilir.
- `danışmanlar` komutunun platform bazlı ve toplam sayıları danışman birleştirmeleriyle birlikte doğrulanır.
- Mevcut WhatsApp uyumluluk ve arayüz sözleşmesi testlerinin tamamı çalıştırılır.
