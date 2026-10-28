from remax_bot.playwright_scanner import extract_remax_portfolio_links, parse_remax_detail


def test_extract_remax_portfolio_links_deduplicates_and_normalizes():
    hrefs = [
        '/tr/portfoy/P87625078',
        'https://remax.com.tr/tr/portfoy/P03303834?x=1',
        '/tr/portfoy/P87625078#top',
        '/tr/ofis/detay/carsi',
    ]
    assert extract_remax_portfolio_links(hrefs, 'https://remax.com.tr/tr/ofis/detay/carsi') == [
        'https://remax.com.tr/tr/portfoy/P87625078',
        'https://remax.com.tr/tr/portfoy/P03303834',
    ]


def test_parse_remax_detail_reads_real_remax_labels():
    text = '''İlan Detayı\nSATILIK 3+1 ZERAY GÜNEŞİ MÜSTAKİL BAHÇELİ DAİRE\n6.250.000 ₺\nKocaeli\nBaşiskele\nFatih Mah.\nPortföy No\nP87625078\nEmlak Tipi\nVilla / Satılık\nYayınlanma Tarihi\n27.08.2026\nm2 (Brüt)\n148\nm2 (Net)\n128\nOda Sayısı\n3+1\nBerkan Aslan Çarşı\nKocaeli / İzmit\n+90 532 386 25 47\n'''
    x = parse_remax_detail(text=text, url='https://remax.com.tr/tr/portfoy/P87625078', source_url='https://remax.com.tr/tr/ofis/detay/carsi')
    assert x.listing_id == 'P87625078'
    assert x.title == 'SATILIK 3+1 ZERAY GÜNEŞİ MÜSTAKİL BAHÇELİ DAİRE'
    assert x.price == '6.250.000 ₺'
    assert x.property_type == 'Villa'
    assert x.transaction_type == 'Satılık'
    assert x.rooms == '3+1'
    assert x.sqm == '148 m²'
    assert x.listing_date == '27.08.2026'
    assert x.phone == '0532 386 25 47'
    assert x.advisor == 'Berkan Aslan'


def test_parse_remax_detail_prefers_labeled_advisor_over_portfolio_noise():
    text='''İlan Detayı
SATILIK DAİRE
Portföy No
P87625078
Emlak Tipi
Daire / Satılık
Gayrimenkul Danışmanı
Hatice Akpınar Davarcı
Telefon
0532 111 22 33
'''

    item=parse_remax_detail(
        text=text,
        url='https://remax.com.tr/tr/portfoy/P87625078',
        source_url='https://remax.com.tr/tr/ofis/detay/carsi',
    )

    assert item.advisor == 'Hatice Akpınar Davarcı'


def test_parse_remax_detail_keeps_explicit_address_description_and_extra_features():
    text='''İlan Detayı
SATILIK SİTE İÇİNDE DAİRE
6.250.000 ₺
Kocaeli
Başiskele
Fatih Mah.
Portföy No
P87625079
Emlak Tipi
Daire / Satılık
m2 (Brüt)
148
m2 (Net)
128
'''
    details={
        'İl':'Kocaeli','İlçe':'Başiskele','Mahalle':'Fatih Mah.',
        'Cadde':'Gülümser Caddesi','Site Adı':'Zeray Güneşi',
        'Açık Adres':'Fatih Mah. Gülümser Cad. No: 4',
        'm2 (Net)':'128','Bina Yaşı':'0','İlan Açıklaması':'Bahçeli ara kat daire',
    }

    item=parse_remax_detail(
        text=text,
        url='https://remax.com.tr/tr/portfoy/P87625079',
        source_url='https://remax.com.tr/tr/ofis/detay/carsi',
        details=details,
    )

    assert (item.province,item.district,item.neighborhood) == ('Kocaeli','Başiskele','Fatih Mah.')
    assert item.street == 'Gülümser Caddesi'
    assert item.complex_name == 'Zeray Güneşi'
    assert item.full_address == 'Fatih Mah. Gülümser Cad. No: 4'
    assert item.net_sqm == '128 m²'
    assert item.description == 'Bahçeli ara kat daire'
    assert item.details['Bina Yaşı'] == '0'


def test_remax_buttons_before_portfolio_number_are_not_invented_as_address():
    item=parse_remax_detail(
        text='''İlan Detayı
SATILIK DAİRE
Favorilere Ekle
Teklif Ver
Portföy No
P87625080
Emlak Tipi
Daire / Satılık
''',
        url='https://remax.com.tr/tr/portfoy/P87625080',
        source_url='https://remax.com.tr/tr/ofis/detay/carsi',
    )

    assert item.province == ''
    assert item.district == ''
    assert item.neighborhood == ''
