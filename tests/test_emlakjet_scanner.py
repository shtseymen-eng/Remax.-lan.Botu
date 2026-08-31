import remax_bot.playwright_scanner as scanner_module
from remax_bot.playwright_scanner import (
    PlaywrightScanner,
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


def test_emlakjet_advisor_comes_only_from_a_real_profile_link():
    extract=getattr(scanner_module,"extract_emlakjet_advisor",lambda _links:"")
    links=[
        {"href":"https://www.emlakjet.com/danismanlar","text":"Danışman Bul"},
        {"href":"https://www.emlakjet.com/danismanlar/hatice-davarci-2109741","text":"Hatice Davarcı"},
        {"href":"https://www.emlakjet.com/ilan/test-19754856","text":"İlan Numarası"},
    ]

    assert extract(links) == "Hatice Davarcı"


def test_emlakjet_pagination_advances_from_page_1_to_page_2(tmp_path):
    class Locator:
        def __init__(self, page, label="", present=False):
            self.page=page
            self.label=label
            self.present=present

        @property
        def first(self):
            return self

        def count(self):
            return int(self.present)

        def is_visible(self):
            return self.present

        def get_attribute(self, name):
            return self.label if name == "aria-label" else None

        def click(self, timeout=0, force=False):
            self.page.forced=force
            if force:
                self.page.force_clicks+=1
                if self.page.force_clicks >= 2:
                    self.page.clicked=self.label
                    self.page.ready_at=self.page.waits+2

    class Page:
        url="https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566"

        def __init__(self):
            self.clicked=""
            self.forced=False
            self.force_clicks=0
            self.current="Page 1"
            self.waits=0
            self.ready_at=0

        def locator(self, selector):
            if selector == 'button[aria-current="page"]':
                return Locator(self,self.current,True)
            if selector == 'button[aria-label="Page 2"]':
                return Locator(self,"Page 2",True)
            return Locator(self)

        def wait_for_load_state(self, *args, **kwargs):
            pass

        def wait_for_timeout(self, _milliseconds):
            self.waits+=1
            if self.ready_at and self.waits >= self.ready_at:
                self.current=self.clicked

    page=Page()
    scanner=PlaywrightScanner(tmp_path)

    assert scanner._next_page(page)
    assert page.forced
    assert page.force_clicks == 2
    assert page.clicked == "Page 2"
    assert page.current == "Page 2"


def test_pagination_uses_legacy_next_control_when_numbered_button_stalls(tmp_path):
    class Locator:
        def __init__(self, page, kind="", present=False):
            self.page=page
            self.kind=kind
            self.present=present

        @property
        def first(self):
            return self

        def count(self):
            return int(self.present)

        def is_visible(self):
            return self.present

        def get_attribute(self, name):
            if name == "aria-label" and self.kind == "current":
                return "Page 1"
            return None

        def click(self, **_kwargs):
            if self.kind == "legacy":
                self.page.legacy_clicked=True

    class Page:
        url="https://example.test/listings"

        def __init__(self):
            self.legacy_clicked=False

        def locator(self, selector):
            if selector == 'button[aria-current="page"]':
                return Locator(self,"current",True)
            if selector == 'button[aria-label="Page 2"]':
                return Locator(self,"numbered",True)
            if selector == 'a[rel="next"]':
                return Locator(self,"legacy",True)
            return Locator(self)

        def wait_for_timeout(self, _milliseconds):
            pass

        def wait_for_load_state(self, **_kwargs):
            pass

    page=Page()
    scanner=PlaywrightScanner(tmp_path)

    assert scanner._next_page(page)
    assert page.legacy_clicked


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


def test_emlakjet_detail_uses_current_advisor_card_and_rejects_listing_label():
    text="""Remax Çarşı Dan Kabaoğlunda Satılık Dükkan
8.250.000 ₺
İlan Numarası
19754856
Kategori
Satılık Dükkan & Mağaza
RE/MAX ÇARŞI
Hatice Davarcı
Tüm İlanları
Taşınmaz Ticareti Yetki Belgesi: 4106038
"""

    item=parse_emlakjet_detail(
        text=text,
        url="https://www.emlakjet.com/ilan/remax-carsi-dan-kabaoglunda-satilik-dukkan-19754856",
        source_url="https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566",
        advisor="İlan Numarası",
    )

    assert item.advisor == "Hatice Davarcı"


def test_scanner_dispatches_each_supported_site():
    assert source_platform("https://remax.com.tr/tr/ofis/detay/carsi") == "remax"
    assert source_platform("https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566") == "emlakjet"
    assert source_platform("https://carsigayrimenkulkocaeli.sahibinden.com/") == "sahibinden"
