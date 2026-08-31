from remax_bot.core import Listing
from remax_bot.importer import parse_command, command_response, command_help

def items():
    return [
        Listing('1','Yahya Kaptan 3+1 Kiralık Daire','https://x/1','Ayşe Şen','','45000 TL','Kocaeli İzmit Yahya Kaptan','3+1','Kiralık','Daire','120 m2','','https://remax.com.tr/tr/ofis/detay/carsi'),
        Listing('2','Yahya Kaptan 3+1 Kiralık Daire','https://x/2','Mert Öztürk','','55000 TL','Kocaeli İzmit Yahya Kaptan','3+1','Kiralık','Daire','130 m2','','https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566'),
        Listing('3','Çarşı Satılık Daire','https://x/3','AYŞE ŞEN','','3500000 TL','Kocaeli İzmit Çarşı','2+1','Satılık','Daire','95 m2','','https://carsigayrimenkulkocaeli.sahibinden.com/'),
        Listing('4','Çarşı Satılık Daire','https://x/4','Murat Şenoğlu','','4250000 TL','Kocaeli İzmit Çarşı','3+1','Satılık','Daire','120 m2','','https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566'),
    ]

def test_help():
    assert parse_command('#?')['type']=='help'
    assert '#danışmanlar#' in command_help()
    assert '#izmit kiralık 55 bin#' in command_help()
    assert '#izmit satılık daire 4 milyon#' in command_help()

def test_ignore_normal_chat():
    assert command_response(items(),'merhaba') is None

def test_summary():
    r=command_response(items(),'#yahya kaptan kiralık 3+1#')
    assert '2 uygun' in r and 'Ayşe Şen' in r and 'Mert Öztürk' in r

def test_links():
    r=command_response(items(),'#yahya kaptan kiralık 3+1 link#')
    assert 'https://x/1' in r and 'Danışman: Ayşe Şen' in r

def test_advisors_command_is_detected():
    assert parse_command('#danışmanlar#')['type']=='advisors'

def test_advisors_command_lists_counts_and_totals_with_turkish_chars():
    r=command_response(items(),'#danışmanlar#')
    assert 'DANIŞMAN İLAN DAĞILIMI' in r
    assert 'Ayşe Şen — Toplam 2 ilan' in r
    assert 'MyRE/MAX: 1 | Emlakjet: 0 | Sahibinden: 1' in r
    assert 'Mert Öztürk — Toplam 1 ilan' in r
    assert 'MyRE/MAX: 0 | Emlakjet: 1 | Sahibinden: 0' in r
    assert 'Toplam ilan: 4' in r
    assert 'Toplam danışman: 3' in r

def test_advisors_command_merges_short_and_full_middle_name_variants():
    rows=[
        Listing('1','A','https://x/1','Hatice Davarcı',source_url='https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566'),
        Listing('2','B','https://x/2','HATİCE AKPINAR DAVARCI',source_url='https://remax.com.tr/tr/ofis/detay/carsi'),
    ]
    r=command_response(rows,'#danışmanlar')
    assert 'Hatice Davarcı — Toplam 2 ilan' in r
    assert 'MyRE/MAX: 1 | Emlakjet: 1 | Sahibinden: 0' in r
    assert 'Toplam danışman: 1' in r

def test_advisors_command_deduplicates_within_site_but_not_across_sites():
    rows=[
        Listing('P1','A','https://remax.com.tr/tr/portfoy/P000001','RE/MAX ÇARŞI',source_url='https://remax.com.tr/tr/ofis/detay/carsi'),
        Listing('P1','A','https://remax.com.tr/tr/portfoy/P000001?office=2','AYŞE ŞEN',source_url='https://remax.com.tr/tr/ofis/detay/carsi-2'),
        Listing('99','A','https://www.emlakjet.com/ilan/a-99999999','Ayşe Şen',source_url='https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566'),
    ]
    r=command_response(rows,'#danışmanlar')
    assert 'Ayşe Şen — Toplam 2 ilan' in r
    assert 'MyRE/MAX: 1 | Emlakjet: 1 | Sahibinden: 0' in r
    assert 'Toplam ilan: 2' in r

def test_55_bin_is_parsed_as_55000_and_returns_links_automatically():
    cmd=parse_command('#yahya kaptan kiralık 55 bin#')
    assert cmd['target_price']==55000
    assert cmd['query']=='yahya kaptan kiralık'
    r=command_response(items(),'#yahya kaptan kiralık 55 bin#')
    assert '55.000 TL ve altında 2 uygun ilan bulundu:' in r
    assert 'https://x/1' in r and 'https://x/2' in r

def test_4_milyon_is_parsed_and_returns_only_at_or_below_limit():
    cmd=parse_command('#izmit satılık daire 4 milyon#')
    assert cmd['target_price']==4000000
    r=command_response(items(),'#izmit satılık daire 4 milyon#')
    assert '4.000.000 TL ve altında 1 uygun ilan bulundu:' in r
    assert 'https://x/3' in r
    assert 'https://x/4' not in r

def test_price_only_command_works():
    r=command_response(items(),'#55 bin#')
    assert 'https://x/1' in r and 'https://x/2' in r
    assert 'https://x/3' not in r

def test_plain_numeric_price_returns_links_without_link_keyword():
    r=command_response(items(),'#yahya kaptan kiralık 55000#')
    assert 'https://x/1' in r and 'https://x/2' in r

def test_grouped_numeric_price_is_supported():
    r=command_response(items(),'#izmit satılık 4.000.000#')
    assert 'https://x/3' in r and 'https://x/4' not in r

def test_no_listing_above_limit_is_substituted():
    r=command_response(items(),'#izmit satılık 3 milyon#')
    assert 'uygun ilan bulunamadı' in r
    assert 'https://x/3' not in r


def test_price_query_does_not_truncate_matching_links_to_default_limit():
    many=[Listing(str(i),f"Kiralık Daire {i}",f"https://x/{i}","Danışman","",f"{40000+i} TL","İzmit","2+1","Kiralık","Daire","90 m2","","manual://entry") for i in range(1,15)]
    r=command_response(many,"#izmit kiralık 55 bin#")
    assert "https://x/14" in r
    assert "14 uygun ilan bulundu" in r
