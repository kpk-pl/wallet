from flaskr.quotes.fetchers.stooq import Stooq
from flaskr.quotes.fetchers.justetf import JustETF


# --- Stooq -------------------------------------------------------------

def test_stooq_validUrl():
    assert Stooq.validUrl("https://stooq.pl/q/g/?s=cpiypl.m")
    assert not Stooq.validUrl("https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983")
    assert not Stooq.validUrl("")


def test_stooq_symbol_parsing():
    assert Stooq.symbol("https://stooq.pl/q/l/?s=sgln.uk&f=snd2t2c") == "sgln.uk"
    assert Stooq.symbol("https://stooq.pl/q/g/?s=cpiypl.m") == "cpiypl.m"


def test_stooq_identify_from_symbol_field():
    assert Stooq.identify({'stooqSymbol': 'sgln.uk'}) == 'sgln.uk'


def test_stooq_identify_from_url():
    assert Stooq.identify({'url': "https://stooq.pl/q/g/?s=cpiypl.m"}) == 'cpiypl.m'


def test_stooq_symbol_field_takes_precedence_over_url():
    quote = {'stooqSymbol': 'sgln.uk', 'url': "https://stooq.pl/q/g/?s=cpiypl.m"}
    assert Stooq.identify(quote) == 'sgln.uk'


def test_stooq_identify_none_when_absent():
    assert Stooq.identify({}) is None
    assert Stooq.identify({'url': ''}) is None


def test_stooq_does_not_identify_justetf_url():
    quote = {'url': "https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983"}
    assert Stooq.identify(quote) is None


# --- JustETF -----------------------------------------------------------

def test_justetf_validUrl():
    assert JustETF.validUrl("https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983")
    assert not JustETF.validUrl("https://www.justetf.com/en/etf-profile.html")
    assert not JustETF.validUrl("https://stooq.pl/q/g/?s=cpiypl.m")
    assert not JustETF.validUrl("")


def test_justetf_isin_extraction():
    url = "https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983"
    assert JustETF.isin(url) == "IE00B4L5Y983"


def test_justetf_isin_none_when_missing():
    assert JustETF.isin("https://www.justetf.com/en/etf-profile.html") is None
    assert JustETF.isin("") is None
    assert JustETF.isin(None) is None


def test_justetf_identify_from_url():
    quote = {'url': "https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983"}
    assert JustETF.identify(quote) == "IE00B4L5Y983"


def test_justetf_does_not_identify_stooq_url():
    assert JustETF.identify({'url': "https://stooq.pl/q/g/?s=cpiypl.m"}) is None
    assert JustETF.identify({}) is None
