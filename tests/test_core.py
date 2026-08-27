from remax_bot.core import norm,source_key,source_label,DB,Listing,search

def test_normalize(): assert norm("İzmit Kiralık")=="izmit kiralik"
def test_source_key(): assert source_key("https://X.sahibinden.com/?display=list")=="https://x.sahibinden.com/"
def test_labels():
    assert source_label("https://carsigayrimenkulkocaeli.sahibinden.com/")=="RE/MAX ÇARŞI"
    assert source_label("https://remaxcarsi2.sahibinden.com/")=="RE/MAX ÇARŞI 2"
def test_replace_source_keeps_other(tmp_path):
    db=DB(tmp_path/"x.sqlite");a="https://carsigayrimenkulkocaeli.sahibinden.com/";b="https://remaxcarsi2.sahibinden.com/"
    db.replace_source(a,[Listing("1","A","u1",advisor="Ayşe",phone="0532 111 22 33",source_url=a)]);db.replace_source(b,[Listing("2","B","u2",source_url=b)])
    db.replace_source(a,[Listing("3","C","u3",source_url=a)])
    assert db.count()==2 and db.source_count(a)==1 and db.source_count(b)==1
def test_search_phone():
    assert len(search([Listing("1","A","u",phone="0532 111 22 33")],"0532"))==1
