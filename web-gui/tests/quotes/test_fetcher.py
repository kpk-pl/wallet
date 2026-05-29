from flaskr.quotes.fetchers.stooq import Stooq
from flaskr.quotes.fetchers.justetf import JustETF


STOOQ_URL = "https://stooq.pl/q/g/?s=cpiypl.m"
JUSTETF_URL = "https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983"


# --- Stooq -------------------------------------------------------------

def test_stooq_validUrl():
    assert Stooq.validUrl(STOOQ_URL)
    assert not Stooq.validUrl(JUSTETF_URL)
    assert not Stooq.validUrl("")


def test_stooq_symbol_parsing():
    assert Stooq.symbol("https://stooq.pl/q/l/?s=sgln.uk&f=snd2t2c") == "sgln.uk"
    assert Stooq.symbol(STOOQ_URL) == "cpiypl.m"


def test_stooq_identify_from_symbol():
    assert Stooq.identify([], 'sgln.uk') == 'sgln.uk'


def test_stooq_identify_from_url():
    assert Stooq.identify([STOOQ_URL]) == 'cpiypl.m'


def test_stooq_symbol_takes_precedence_over_url():
    assert Stooq.identify([STOOQ_URL], 'sgln.uk') == 'sgln.uk'


def test_stooq_identify_none_when_absent():
    assert Stooq.identify([]) is None
    assert Stooq.identify(['']) is None


def test_stooq_does_not_identify_justetf_url():
    assert Stooq.identify([JUSTETF_URL]) is None


# --- JustETF -----------------------------------------------------------

def test_justetf_validUrl():
    assert JustETF.validUrl(JUSTETF_URL)
    assert not JustETF.validUrl("https://www.justetf.com/en/etf-profile.html")
    assert not JustETF.validUrl(STOOQ_URL)
    assert not JustETF.validUrl("")


def test_justetf_isin_extraction():
    assert JustETF.isin(JUSTETF_URL) == "IE00B4L5Y983"


def test_justetf_isin_none_when_missing():
    assert JustETF.isin("https://www.justetf.com/en/etf-profile.html") is None
    assert JustETF.isin("") is None
    assert JustETF.isin(None) is None


def test_justetf_identify_from_url():
    assert JustETF.identify([JUSTETF_URL]) == "IE00B4L5Y983"


def test_justetf_does_not_identify_stooq_url():
    assert JustETF.identify([STOOQ_URL]) is None
    assert JustETF.identify([]) is None


# --- multiple URLs -----------------------------------------------------

def test_identify_scans_all_urls_when_both_present():
    urls = [STOOQ_URL, JUSTETF_URL]
    assert Stooq.identify(urls) == 'cpiypl.m'
    assert JustETF.identify(urls) == 'IE00B4L5Y983'


def test_identify_order_independent():
    urls = [JUSTETF_URL, STOOQ_URL]
    assert Stooq.identify(urls) == 'cpiypl.m'
    assert JustETF.identify(urls) == 'IE00B4L5Y983'


def test_stooq_symbol_wins_over_urls():
    assert Stooq.identify([JUSTETF_URL], 'sgln.uk') == 'sgln.uk'
