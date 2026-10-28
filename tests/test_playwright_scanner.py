from remax_bot.playwright_scanner import (
    extract_sahibinden_listing_links,
    extract_total_count,
    parse_listing_detail,
    is_human_verification,
    normalize_listing_url,
    is_valid_detail_listing,
    validate_scan_completeness,
    normalize_detail_pairs,
    PlaywrightScanner,
)
import pytest
from remax_bot.core import Listing


def test_extract_sahibinden_listing_links_keeps_only_classified_details():
    hrefs = [
        "/ilan/emlak-konut-satilik-yahya-kaptan-1234567890/detay",
        "https://www.sahibinden.com/ilan/emlak-konut-kiralik-carsi-1234567891/detay?x=1",
        "/ilan/emlak-konut-satilik-yahya-kaptan-1234567890/detay#foto",
        "/emlak-ofisleri/",
    ]
    assert extract_sahibinden_listing_links(hrefs, "https://carsigayrimenkulkocaeli.sahibinden.com/") == [
        "https://carsigayrimenkulkocaeli.sahibinden.com/ilan/emlak-konut-satilik-yahya-kaptan-1234567890/detay",
        "https://www.sahibinden.com/ilan/emlak-konut-kiralik-carsi-1234567891/detay",
    ]


def test_extract_total_count_from_store_text():
    text = 'Seçimlerinize uygun 188 ilan listeleniyor'
    assert extract_total_count(text) == 188


def test_normalize_listing_url_strips_query_and_fragment():
    url = 'https://www.sahibinden.com/ilan/emlak-konut-satilik-test-1234567890/detay?x=1#foo'
    assert normalize_listing_url(url) == 'https://www.sahibinden.com/ilan/emlak-konut-satilik-test-1234567890/detay'


def test_parse_listing_detail_extracts_core_fields():
    text = '''
    Yahya Kaptan 3+1 Satılık Daire
    5.750.000 TL
    İlan No: 1234567890
    Kocaeli / İzmit / Yahya Kaptan
    3+1
    145 m²
    İlan Tarihi 26 Ağustos 2026
    Danışman: Ayşe Yılmaz
    0532 111 22 33
    '''
    item = parse_listing_detail(
        text=text,
        url='https://www.sahibinden.com/ilan/x-1234567890/detay',
        source_url='https://carsigayrimenkulkocaeli.sahibinden.com/',
        title='Yahya Kaptan 3+1 Satılık Daire',
        price='5.750.000 TL',
        advisor='',
        phone='',
    )
    assert item.listing_id == '1234567890'
    assert item.rooms == '3+1'
    assert item.sqm == '145 m²'
    assert item.transaction_type == 'Satılık'
    assert item.property_type == 'Daire'
    assert item.advisor == 'Ayşe Yılmaz'
    assert '0532' in item.phone
    assert item.url.endswith('/detay')
    assert (item.province,item.district,item.neighborhood) == (
        'Kocaeli','İzmit','Yahya Kaptan'
    )


def test_parse_listing_detail_replaces_store_name_with_named_advisor():
    item = parse_listing_detail(
        text='İlan No: 1234567890\nYetkili Gayrimenkul Danışmanı:\nAyşe Yılmaz',
        url='https://www.sahibinden.com/ilan/x-1234567890/detay',
        source_url='https://carsigayrimenkulkocaeli.sahibinden.com/',
        title='Satılık Daire',
        advisor='RE/MAX ÇARŞI',
    )
    assert item.advisor == 'Ayşe Yılmaz'


def test_parse_listing_detail_replaces_portfolio_label_with_named_advisor():
    item = parse_listing_detail(
        text='İlan No: 1234567890\nYetkili Gayrimenkul Danışmanı:\nAyşe Yılmaz',
        url='https://www.sahibinden.com/ilan/x-1234567890/detay',
        source_url='https://carsigayrimenkulkocaeli.sahibinden.com/',
        title='Satılık Daire',
        advisor='Portföy No',
    )

    assert item.advisor == 'Ayşe Yılmaz'


def test_detects_human_verification():
    assert is_human_verification('Lütfen robot olmadığınızı doğrulayın')
    assert is_human_verification('CAPTCHA güvenlik kontrolü')
    assert not is_human_verification('188 ilan listeleniyor')


def test_browser_launch_options_match_visible_successful_probe():
    from remax_bot.playwright_scanner import browser_launch_options
    assert browser_launch_options() == {
        'headless': False,
        'channel': 'chrome',
        'args': ['--start-maximized'],
    }


def test_listing_row_text_recognizes_sahibinden_list_row():
    from remax_bot.playwright_scanner import is_listing_row_text
    row = 'ASFALT YOLA CEPHELİ 3765M2 MÜSTAKİL PARSEL\n3.600.000 TL\n24 Ağustos 2026\nKocaeli / İzmit'
    assert is_listing_row_text(row)
    assert not is_listing_row_text('Tüm İlanlar\nÖne Çıkanlar\nEkibimiz\nHakkımızda')


def test_candidate_title_from_row_text_prefers_listing_title():
    from remax_bot.playwright_scanner import candidate_title_from_row_text
    row = '''
    ASFALT YOLA CEPHELİ 3765M2 MÜSTAKİL PARSEL
    3.600.000 TL
    24 Ağustos 2026
    Kocaeli / İzmit
    '''
    assert candidate_title_from_row_text(row) == 'ASFALT YOLA CEPHELİ 3765M2 MÜSTAKİL PARSEL'


def test_blank_or_redirected_detail_is_rejected_before_replacing_data():
    placeholder=Listing(
        '19754937','İlan 19754937',
        'https://www.emlakjet.com/ilan/test-19754937',
        source_url='https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566',
    )
    assert not is_valid_detail_listing(
        'emlakjet','',placeholder,'https://www.emlakjet.com/ilan/test-19754937'
    )
    assert not is_valid_detail_listing(
        'emlakjet','İlan Numarası 19754937\nKategori Satılık Daire',placeholder,
        'https://www.emlakjet.com/ilan/other-19754938'
    )
    complete=Listing(
        '19754937','Yahya Kaptan 2+1 Satılık Daire',
        'https://www.emlakjet.com/ilan/test-19754937',
        price='4.000.000 ₺',source_url=placeholder.source_url,
    )
    assert is_valid_detail_listing(
        'emlakjet','İlan Numarası 19754937\nKategori Satılık Daire',complete,
        'https://www.emlakjet.com/ilan/test-19754937'
    )
    remax_placeholder=Listing(
        'P87625078','Portföy P87625078','https://remax.com.tr/tr/portfoy/P87625078',
        source_url='https://remax.com.tr/tr/ofis/detay/carsi',
    )
    assert not is_valid_detail_listing(
        'remax','Portföy No\nP87625078\nEmlak Tipi',remax_placeholder,remax_placeholder.url
    )


def test_scan_completeness_requires_known_total_all_links_and_all_details():
    with pytest.raises(RuntimeError,match='toplam ilan sayısı'):
        validate_scan_completeness(total=0,discovered=3,parsed=3)
    with pytest.raises(RuntimeError,match='3 ilan görünüyor; 2 ilan linki'):
        validate_scan_completeness(total=3,discovered=2,parsed=2)
    with pytest.raises(RuntimeError,match='2 ilan linki bulundu; 1 ilan'):
        validate_scan_completeness(total=2,discovered=2,parsed=1)
    validate_scan_completeness(total=2,discovered=2,parsed=2)


def test_sahibinden_detail_keeps_explicit_address_description_and_features():
    item=parse_listing_detail(
        text='İlan No: 1234567892\nKocaeli / İzmit / Yahya Kaptan\nSatılık Daire',
        url='https://www.sahibinden.com/ilan/x-1234567892/detay',
        source_url='https://carsigayrimenkulkocaeli.sahibinden.com/',
        title='Site İçinde Satılık Daire',
        details={
            'Cadde':'Akasyalar Caddesi','Site Adı':'Zeray Sitesi',
            'Adres':'Yahya Kaptan Mah. Akasyalar Cad. No: 10',
            'Brüt m²':'145 m²','Net m²':'130 m²',
            'Açıklama':'Ara kat, kapalı otoparklı daire','Isıtma':'Yerden Isıtma',
        },
    )

    assert item.street == 'Akasyalar Caddesi'
    assert item.complex_name == 'Zeray Sitesi'
    assert item.full_address == 'Yahya Kaptan Mah. Akasyalar Cad. No: 10'
    assert item.sqm == '145 m²'
    assert item.net_sqm == '130 m²'
    assert item.description == 'Ara kat, kapalı otoparklı daire'
    assert item.details['Isıtma'] == 'Yerden Isıtma'


def test_missing_address_components_stay_empty():
    item=parse_listing_detail(
        text='İlan No: 1234567893\nKocaeli / İzmit\nSatılık Daire',
        url='https://www.sahibinden.com/ilan/x-1234567893/detay',
        source_url='https://carsigayrimenkulkocaeli.sahibinden.com/',
        title='Satılık Daire',
    )

    assert item.province == 'Kocaeli'
    assert item.district == 'İzmit'
    assert item.neighborhood == ''
    assert item.street == ''
    assert item.complex_name == ''
    assert item.full_address == ''


def test_property_taxonomy_is_not_invented_as_an_address():
    item=parse_listing_detail(
        text='İlan No: 1234567894\nEmlak / Konut / Satılık\nSatılık Daire',
        url='https://www.sahibinden.com/ilan/x-1234567894/detay',
        source_url='https://carsigayrimenkulkocaeli.sahibinden.com/',
        title='Satılık Daire',
    )

    assert item.province == ''
    assert item.district == ''
    assert item.neighborhood == ''
    assert item.location == ''


def test_detail_pair_normalization_keeps_first_meaningful_value():
    pairs=[
        {'label':' Isıtma ','value':' Doğalgaz  Kombi '},
        {'label':'Isıtma','value':'Soba'},
        {'label':'','value':'değer'},
        {'label':'Balkon','value':''},
        ['Bulunduğu Kat','3'],
    ]
    assert normalize_detail_pairs(pairs) == {
        'Isıtma':'Doğalgaz Kombi','Bulunduğu Kat':'3'
    }


def test_scanner_reads_structured_detail_pairs_from_page(tmp_path):
    class Page:
        def evaluate(self, _script):
            return [
                {'label':'Isıtma','value':'Doğalgaz Kombi'},
                {'label':'Bina Yaşı','value':'5'},
            ]

    scanner=PlaywrightScanner(tmp_path)
    assert scanner._read_detail_attributes(Page()) == {
        'Isıtma':'Doğalgaz Kombi','Bina Yaşı':'5'
    }
