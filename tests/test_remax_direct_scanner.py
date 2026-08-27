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
