import pytest
from flaskr.quotes import Fetcher, FetchError
from flaskr.quotes.fetchers import Mock as MockFetcher
from datetime import datetime
from decimal import Decimal


def test_generic_fetcher_create():
    fetcher = Fetcher.getInstance("mock://samplemock.com")
    assert isinstance(fetcher, MockFetcher)


def test_can_set_values_from_url():
    url = "mock://mocking.com?quote=12.1&timestamp=2022-01-12T14:30:00"
    quote = MockFetcher(url).fetch()

    assert quote.quote == Decimal('12.1')
    assert quote.timestamp == datetime(2022, 1, 12, 14, 30)


def test_invalid_parameters_cause_gracefull_error():
    url = "mock://mocking.com?quote=12.1&timestamp=bad"
    with pytest.raises(Exception) as e:
        assert isinstance(e, FetchError)
