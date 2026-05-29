from bson.objectid import ObjectId
from flaskr.model import Quote


def _doc(**overrides):
    base = {
        '_id': ObjectId(),
        'name': 'Test',
        'unit': 'PLN',
        'updateFrequency': 'daily',
    }
    base.update(overrides)
    return base


def test_url_property_returns_first_of_urls():
    quote = Quote(**_doc(urls=[
        "https://stooq.pl/q/g/?s=cpiypl.m",
        "https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983",
    ]))
    assert str(quote.url) == "https://stooq.pl/q/g/?s=cpiypl.m"
    assert len(quote.urls) == 2


def test_legacy_scalar_url_is_coalesced_into_urls():
    # Pre-migration documents carry a scalar `url` and no `urls` array.
    quote = Quote(**_doc(url="https://stooq.pl/q/g/?s=cpiypl.m"))
    assert [str(u) for u in quote.urls] == ["https://stooq.pl/q/g/?s=cpiypl.m"]
    assert str(quote.url) == "https://stooq.pl/q/g/?s=cpiypl.m"


def test_urls_take_precedence_over_legacy_url():
    quote = Quote(**_doc(
        url="https://stooq.pl/q/g/?s=legacy.m",
        urls=["https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983"],
    ))
    assert str(quote.url) == "https://www.justetf.com/en/etf-profile.html?isin=IE00B4L5Y983"


def test_url_is_none_when_no_urls():
    quote = Quote(**_doc())
    assert quote.urls == []
    assert quote.url is None
