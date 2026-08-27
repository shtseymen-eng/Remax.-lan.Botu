from pathlib import Path

SRC=Path(__file__).parents[1]/'src'/'remax_bot'/'remax_web_scanner.py'
TEXT=SRC.read_text(encoding='utf-8')

def test_list_scanner_targets_remax_portfolios():
    assert 'portfoy' in TEXT.lower()
    assert 'P\\d{6,}' in TEXT

def test_pagination_detection_exists():
    assert 'CLICK_PAGE_JS' in TEXT
    assert 'deepAll' in TEXT
    assert '_next_page' in TEXT

def test_detail_labels_exist():
    for label in ['Portföy No','Emlak Tipi','Yayınlanma Tarihi','Oda Sayısı']:
        assert label in TEXT
