import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client
from urllib.parse import quote as urlQuote


def test_quotes_get_from_url(client):
    mockUrl = urlQuote("mock://test.com?quote=12.4&timestamp=2022-03-12T12:00:00")

    rv = client.get(f"/quotes?url={mockUrl}", follow_redirects=True)
    assert rv.status_code == 200

    assert rv.json == dict(quote = "12.4",
                           timestamp = "Sat, 12 Mar 2022 12:00:00 GMT")

