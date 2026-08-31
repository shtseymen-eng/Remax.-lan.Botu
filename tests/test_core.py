from remax_bot.core import norm,source_key,source_label,source_site,split_listings_by_site,DB,Listing,search

def test_normalize():
    assert norm("İzmit Kiralık")=="izmit kiralik"

def test_source_key():
    assert source_key("https://X.sahibinden.com/?display=list")=="https://x.sahibinden.com/"

def test_labels():
    assert source_label("https://carsigayrimenkulkocaeli.sahibinden.com/")=="Sahibinden ÇARŞI"
    assert source_label("https://remaxcarsi2.sahibinden.com/")=="Sahibinden ÇARŞI 2"
    assert source_label("https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566")=="Emlakjet ÇARŞI"
    assert source_label("https://remax.com.tr/tr/ofis/detay/carsi")=="MyRE/MAX ÇARŞI"

def test_source_site_uses_source_and_falls_back_to_listing_link():
    assert source_site("https://remax.com.tr/tr/ofis/detay/carsi") == "MyRE/MAX"
    assert source_site("https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566") == "Emlakjet"
    assert source_site("https://carsigayrimenkulkocaeli.sahibinden.com/") == "Sahibinden"
    assert source_site("manual://entry", "https://www.emlakjet.com/ilan/test-19754937") == "Emlakjet"

def test_split_listings_keeps_unclassified_imports_visible():
    rows=[
        Listing("1","Site ilanı","https://www.emlakjet.com/ilan/test-19754937",source_url="excel://import"),
        Listing("2","Kaynağı belirsiz","",source_url="excel://import"),
    ]
    buckets=split_listings_by_site(rows)
    assert [x.listing_id for x in buckets["Emlakjet"]] == ["1"]
    assert [x.listing_id for x in buckets["Diğer"]] == ["2"]

def test_replace_source_keeps_other(tmp_path):
    db=DB(tmp_path/"x.sqlite")
    a="https://carsigayrimenkulkocaeli.sahibinden.com/"
    b="https://remaxcarsi2.sahibinden.com/"
    db.replace_source(a,[Listing("1","A","u1",advisor="Ayşe",phone="0532 111 22 33",source_url=a)])
    db.replace_source(b,[Listing("2","B","u2",source_url=b)])
    db.replace_source(a,[Listing("3","C","u3",source_url=a)])
    assert db.count()==2 and db.source_count(a)==1 and db.source_count(b)==1

def test_search_phone():
    assert len(search([Listing("1","A","u",phone="0532 111 22 33")],"0532"))==1
