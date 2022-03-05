import pytest
import mongomock
import pymongo
import tests
from datetime import datetime
from tests.fixtures import client
from tests.mocks import PricingSource
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
    PricingSource.createSimple().quote(datetime(2022, 3, 1, 12), 12.3) \
                          .quote(datetime(2022, 3, 1, 14), 12.4).commit()
    PricingSource.createSimple().quote(datetime(2022, 3, 1, 11), 2.3) \
                          .quote(datetime(2022, 3, 1, 12), 2.4).commit()

    with client.application.app_context():
        hd = HeaderData()

        assert hd.lastQuoteUpdate.timestamp == datetime(2022, 3, 1, 14)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_header_last_quote_update_with_asset_without_history(client):
    PricingSource.createSimple().quote(datetime(2022, 3, 1, 12), 12.3).commit()
    PricingSource.createSimple().commit()

    with client.application.app_context():
        hd = HeaderData()

        assert hd.lastQuoteUpdate.timestamp == datetime(2022, 3, 1, 12)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_header_last_quote_update_with_asset_without_any_history(client):
    PricingSource.createSimple().commit()

    with client.application.app_context():
        hd = HeaderData()

        assert hd.lastQuoteUpdate == None
