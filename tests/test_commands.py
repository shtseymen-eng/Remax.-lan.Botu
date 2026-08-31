from remax_bot.core import Listing
from remax_bot.importer import parse_command, command_response, command_help

def items():
    return [
        Listing('1','Yahya Kaptan 3+1 Kiralık Daire','https://x/1','Ayşe Şen','','45000 TL','Kocaeli İzmit Yahya Kaptan','3+1','Kiralık','Daire','120 m2','','manual://entry'),
        Listing('2','Yahya Kaptan 3+1 Kiralık Daire','https://x/2','Mert Öztürk','','55000 TL','Kocaeli İzmit Yahya Kaptan','3+1','Kiralık','Daire','130 m2','','manual://entry'),
        Listing('3','Çarşı Satılık Daire','https://x/3','Ayşe Şen','','3500000 TL','Kocaeli İzmit Çarşı','2+1','Satılık','Daire','95 m2','','manual://entry'),
    ]

def test_help():
    assert parse_command('#?')['type']=='help'
    assert '#danışmanlar#' in command_help()

def test_ignore_normal_chat():
    assert command_response(items(),'merhaba') is None

def test_summary():
    r=command_response(items(),'#yahya kaptan kiralık 3+1#')
    assert '2 uygun' in r and 'Ayşe Şen' in r and 'Mert Öztürk' in r

def test_links():
    r=command_response(items(),'#yahya kaptan kiralık 3+1 link#')
    assert 'https://x/1' in r and 'Danışman: Ayşe Şen' in r

def test_price_nearest_under():
    r=command_response(items(),'#yahya kaptan kiralık 50000 link#')
    assert '45000' in r and 'https://x/1' in r

def test_advisors_command_is_detected():
    assert parse_command('#danışmanlar#')['type']=='advisors'

def test_advisors_command_lists_counts_and_totals_with_turkish_chars():
    r=command_response(items(),'#danışmanlar#')
    assert 'DANIŞMAN İLAN DAĞILIMI' in r
    assert 'Ayşe Şen: 2 ilan' in r
    assert 'Mert Öztürk: 1 ilan' in r
    assert 'Toplam ilan: 3' in r
    assert 'Toplam danışman: 2' in r
