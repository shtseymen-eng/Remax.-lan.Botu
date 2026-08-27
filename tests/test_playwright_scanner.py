from remax_bot.playwright_scanner import (
    extract_total_count,
    parse_listing_detail,
    is_human_verification,
    normalize_listing_url,
)


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


def test_detects_human_verification():
    assert is_human_verification('Lütfen robot olmadığınızı doğrulayın')
    assert is_human_verification('CAPTCHA güvenlik kontrolü')
    assert not is_human_verification('188 ilan listeleniyor')


def test_browser_launch_options_match_visible_successful_probe():
    from remax_bot.playwright_scanner import browser_launch_options
    assert browser_launch_options() == {
        'headless': False,
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
