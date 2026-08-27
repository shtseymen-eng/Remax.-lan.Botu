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
