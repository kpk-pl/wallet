import pytest
import mongomock
import pymongo
import tests
from datetime import datetime
from tests.fixtures import client
from tests.mocks import Quote
from flaskr.header import HeaderData


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_header_from_empty_database(client):
    with client.application.app_context():
        hd = HeaderData(showLabels=True)

        assert hd.showLabels == True
        assert hd.allLabels == []
        assert hd.lastQuoteUpdate == None


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_header_last_quote_update(client):
    Quote("Quote 1", "PLN").quote(datetime(2022, 3, 1, 12), 12.3) \
                          .quote(datetime(2022, 3, 1, 14), 12.4).commit()
    Quote("Quote 2", "PLN").quote(datetime(2022, 3, 1, 11), 2.3) \
                          .quote(datetime(2022, 3, 1, 12), 2.4).commit()

    with client.application.app_context():
        hd = HeaderData()

        assert hd.lastQuoteUpdate.timestamp == datetime(2022, 3, 1, 14)
