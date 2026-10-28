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
    assert '#emlakjet izmit kiralık' in command_help()
    assert '#sahibinden izmit satılık' in command_help()
    assert '#myremax yahya kaptan kiralık' in command_help()
    assert '#izmit kiralık dükkan-ofis' in command_help()
    assert 'İlan aramalarında link kelimesi yazmanız gerekmez' in command_help()
    assert 'Ayarlar bölümünde seçilen kaynaklar kullanılır' in command_help()

def test_ignore_normal_chat():
    assert command_response(items(),'merhaba') is None

def test_summary():
    r=command_response(items(),'#yahya kaptan kiralık 3+1#')
    assert '2 uygun' in r and 'Ayşe Şen' in r and 'Mert Öztürk' in r


def test_normal_search_returns_listing_links_without_requiring_the_link_word():
    response=command_response(items(),'#yahya kaptan kiralık 3+1')

    assert 'https://x/1' in response
    assert 'https://x/2' in response

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

def test_advisors_command_keeps_unconfigured_middle_name_variants_separate():
    rows=[
        Listing('1','A','https://x/1','Hatice Davarcı',source_url='https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566'),
        Listing('2','B','https://x/2','HATİCE AKPINAR DAVARCI',source_url='https://remax.com.tr/tr/ofis/detay/carsi'),
    ]
    r=command_response(rows,'#danışmanlar')
    assert 'Hatice Davarcı — Toplam 1 ilan' in r
    assert 'HATİCE AKPINAR DAVARCI — Toplam 1 ilan' in r
    assert 'Toplam danışman: 2' in r

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


def test_link_response_never_displays_listing_label_as_advisor():
    rows=[
        Listing(
            '1','İzmit Satılık Daire','https://x/1','Portföy No','',
            '4.000.000 TL','Kocaeli İzmit','2+1','Satılık','Daire','90 m2','',
            'https://remax.com.tr/tr/ofis/detay/carsi',
        )
    ]

    response=command_response(rows,'#izmit satılık link')

    assert 'Danışman: Belirtilmemiş' in response
    assert 'Portföy No' not in response


def test_automatic_link_response_uses_same_placeholder_for_invalid_advisor():
    rows=[
        Listing(
            '1','İzmit Satılık Daire','https://x/1','İlan Numarası','',
            '4.000.000 TL','Kocaeli İzmit','2+1','Satılık','Daire','90 m2','',
            'https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566',
        )
    ]

    response=command_response(rows,'#izmit satılık')

    assert 'Danışman: Belirtilmemiş' in response
    assert 'Danışman belirtilmemiş' not in response
    assert 'İlan Numarası' not in response


def test_saved_link_source_filters_normal_link_commands():
    response=command_response(
        items(),
        '#yahya kaptan kiralık 3+1 link',
        link_source='Emlakjet',
    )

    assert 'https://x/2' in response
    assert 'https://x/1' not in response


def test_saved_link_source_filters_normal_commands_and_returns_the_link():
    response=command_response(
        items(),
        '#yahya kaptan kiralık 3+1',
        link_source='Emlakjet',
    )

    assert '1 uygun ilan bulundu' in response
    assert 'Danışman: Mert Öztürk' in response
    assert 'https://x/2' in response
    assert 'Ayşe Şen' not in response


def test_command_source_prefix_overrides_saved_source_and_returns_links():
    response=command_response(
        items(),
        '#emlakjet izmit kiralık',
        link_source='Sahibinden',
    )

    assert 'https://x/2' in response
    assert 'https://x/1' not in response
    assert 'Mert Öztürk' in response


def test_all_command_source_prefixes_are_parsed_as_link_searches():
    examples={
        '#emlakjet izmit kiralık':('Emlakjet','izmit kiralık'),
        '#sahibinden izmit satılık':('Sahibinden','izmit satılık'),
        '#myremax yahya kaptan kiralık':('MyRE/MAX','yahya kaptan kiralık'),
    }

    for text,(source,query) in examples.items():
        command=parse_command(text)
        assert command['type']=='search'
        assert command['source']==source
        assert command['query']==query
        assert command['links'] is True


def test_selected_source_never_falls_back_to_another_site():
    response=command_response(
        items(),
        '#yahya kaptan kiralık 3+1 link',
        link_source='Sahibinden',
    )

    assert response=='Sahibinden listesinde aramanıza uygun ilan bulunamadı.'


def test_advisors_command_always_counts_all_sites():
    response=command_response(items(),'#danışmanlar',link_source='Emlakjet')

    assert 'MyRE/MAX: 1 | Emlakjet: 0 | Sahibinden: 1' in response
    assert 'Toplam ilan: 4' in response


def test_invalid_saved_source_uses_safe_myremax_default():
    response=command_response(
        items(),
        '#yahya kaptan kiralık 3+1 link',
        link_source='eski-gecersiz-deger',
    )

    assert 'https://x/1' in response
    assert 'https://x/2' not in response


def test_custom_command_prefix_accepts_only_the_saved_prefix():
    assert parse_command("!izmit kiralık",prefix="!")["type"] == "search"
    assert parse_command("#izmit kiralık",prefix="!")["type"] == "ignore"
    help_text=command_help(prefix="!")
    assert "!?" in help_text
    assert "!danışmanlar" in help_text
    assert "#danışmanlar" not in help_text


def test_search_sources_and_fields_limit_normal_search_but_not_advisor_counts():
    rows=[
        Listing(
            "S1","Sahibinden Daire","https://www.sahibinden.com/ilan/s-12345678/detay",
            advisor="Ayşe Yılmaz",description="deniz manzaralı",
            source_url="https://carsigayrimenkulkocaeli.sahibinden.com/",
        ),
        Listing(
            "R1","MyREMAX Daire","https://remax.com.tr/tr/portfoy/P12345678",
            advisor="Ayşe Yılmaz",description="deniz manzaralı",
            source_url="https://remax.com.tr/tr/ofis/detay/carsi",
        ),
    ]

    sahibinden=command_response(
        rows,"!deniz",prefix="!",search_sources=["Sahibinden"],search_fields=["description"]
    )
    assert "Sahibinden Daire" in sahibinden
    assert "MyREMAX Daire" not in sahibinden
    assert "uygun ilan bulunamadı" in command_response(
        rows,"!deniz",prefix="!",search_sources=["Sahibinden"],search_fields=["title"]
    )
    advisor_response=command_response(
        rows,"!danışmanlar",prefix="!",search_sources=["Sahibinden"],search_fields=["title"]
    )
    assert "MyRE/MAX: 1" in advisor_response
    assert "Sahibinden: 1" in advisor_response


def test_relevance_prefers_title_and_address_over_description_matches():
    rows=[
        Listing("1","Başka Bölge","https://x/1",description="yahya kaptan yakınında",source_url="manual://one"),
        Listing("2","Yahya Kaptan Satılık Daire","https://x/2",source_url="manual://two"),
        Listing("3","Satılık Daire","https://x/3",province="Kocaeli",district="İzmit",neighborhood="Yahya Kaptan",source_url="manual://three"),
    ]

    response=command_response(rows,"#yahya kaptan",search_fields=["title","location","description"])

    assert response.index("Yahya Kaptan Satılık Daire") < response.index("Başka Bölge")
    assert response.index("https://x/3") < response.index("https://x/1")


def test_search_result_always_contains_the_link_without_link_or_ilan_words():
    row=Listing("1","Kiralık Daire","https://example.test/ilan/1",location="İzmit")
    response=command_response([row],"#izmit kiralık")
    assert "https://example.test/ilan/1" in response
