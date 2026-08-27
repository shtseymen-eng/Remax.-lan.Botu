from remax_bot.core import Listing, search
from remax_bot.importer import parse_command, command_response, command_help

def items():
 return [Listing('1','Yahya Kaptan 3+1 Kiralık Daire','https://x/1','Ayşe','','45000 TL','Kocaeli İzmit Yahya Kaptan','3+1','Kiralık','Daire','120 m2','','manual://entry'),Listing('2','Yahya Kaptan 3+1 Kiralık Daire','https://x/2','Mert','','55000 TL','Kocaeli İzmit Yahya Kaptan','3+1','Kiralık','Daire','130 m2','','manual://entry')]

def test_help():
 assert parse_command('#?')['type']=='help'
 assert '#yahya kaptan kiralık 3+1#' in command_help()

def test_ignore_normal_chat(): assert command_response(items(),'merhaba') is None
def test_summary():
 r=command_response(items(),'#yahya kaptan kiralık 3+1#'); assert '2 uygun' in r and 'Ayşe' in r and 'Mert' in r
def test_links():
 r=command_response(items(),'#yahya kaptan kiralık 3+1 link#'); assert 'https://x/1' in r and 'Danışman: Ayşe' in r
def test_price_nearest_under():
 r=command_response(items(),'#yahya kaptan kiralık 50000 link#'); assert '45000' in r and 'https://x/1' in r
