from pathlib import Path

SRC=Path(__file__).parents[1]/'src'/'remax_bot'/'remax_web_scanner.py'

def scanner_text():
    return SRC.read_text(encoding='utf-8')

def test_scanner_enters_shadow_dom():
    s=scanner_text()
    assert 'shadowRoot' in s
    assert 'deepRoots' in s
    assert 'deepAll' in s

def test_scanner_marks_and_clicks_cards():
    s=scanner_text()
    assert 'data-remax-card-index' in s
    assert 'CLICK_CARD_JS' in s
    assert '_card_clicked' in s

def test_scanner_paginates_after_cards():
    s=scanner_text()
    assert 'CLICK_PAGE_JS' in s
    assert '_next_page' in s
    assert 'Sayfa {self.page_no} tamamlandı' in s


def test_embedded_detail_payload_includes_address_and_extra_details():
    s=scanner_text()
    for token in ['province','district','neighborhood','street','complexName','fullAddress','description','netSqm','details']:
        assert token in s


def test_embedded_detail_payload_does_not_duplicate_square_meter_units():
    s=scanner_text()

    assert 'const withSqm=' in s
    assert "sqm:withSqm(gross)" in s
    assert "netSqm:withSqm(netSqm)" in s


def test_embedded_remax_address_fallback_requires_a_real_province():
    s=scanner_text()

    assert "provinces.has" in s
