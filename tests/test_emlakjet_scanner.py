from remax_bot.playwright_scanner import (
    extract_emlakjet_listing_links,
    extract_emlakjet_total_count,
    parse_emlakjet_detail,
    source_platform,
)


def test_emlakjet_office_links_are_deduplicated_without_related_pages():
    hrefs = [
        "/ilan/60-evler-yavuz-sultan-selim-mahallesinde-21-kiralik-daire-19754937",
        "https://www.emlakjet.com/ilan/satilik-dukkan-19754938?ref=office",
        "/ilan/60-evler-yavuz-sultan-selim-mahallesinde-21-kiralik-daire-19754937#foto",
        "/emlak-ofisleri/remax-carsi-1662566",
        "/satilik-daire/",
    ]
    assert extract_emlakjet_listing_links(hrefs, "https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566") == [
        "https://www.emlakjet.com/ilan/60-evler-yavuz-sultan-selim-mahallesinde-21-kiralik-daire-19754937",
        "https://www.emlakjet.com/ilan/satilik-dukkan-19754938",
    ]


def test_emlakjet_total_count_reads_office_listing_count():
    assert extract_emlakjet_total_count("RE/MAX ÇARŞI\nİlan Sayısı:41\nTüm İlanlar") == 41


def test_emlakjet_detail_reads_listing_and_advisor_fields():
    text = """60 Evler Yavuz Sultan Selim Mahallesinde 2+1 Kiralık Daire
Yavuz Sultan Mahallesi, Derince, Kocaeli - Haritada Gör
18.000 ₺
İlan Bilgileri
2+1
Oda Sayısı
100 m²
Brüt
İlan Numarası 19754937
İlan Güncelleme Tarihi 21 Ağustos 2026
Kategori Kiralık Daire
Hatice Davarcı | RE/MAX ÇARŞI
"""
    item = parse_emlakjet_detail(
        text=text,
        url="https://www.emlakjet.com/ilan/60-evler-yavuz-sultan-selim-mahallesinde-21-kiralik-daire-19754937",
        source_url="https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566",
    )
    assert item.listing_id == "19754937"
    assert item.title == "60 Evler Yavuz Sultan Selim Mahallesinde 2+1 Kiralık Daire"
    assert item.price == "18.000 ₺"
    assert item.location == "Kocaeli / Derince / Yavuz Sultan Mahallesi"
    assert item.rooms == "2+1"
    assert item.sqm == "100 m²"
    assert item.transaction_type == "Kiralık"
    assert item.property_type == "Daire"
    assert item.listing_date == "21 Ağustos 2026"
    assert item.advisor == "Hatice Davarcı"


def test_scanner_dispatches_each_supported_site():
    assert source_platform("https://remax.com.tr/tr/ofis/detay/carsi") == "remax"
    assert source_platform("https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566") == "emlakjet"
    assert source_platform("https://carsigayrimenkulkocaeli.sahibinden.com/") == "sahibinden"
