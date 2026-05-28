import datetime
import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client
from tests.mocks import Asset, PricingSource


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_page_with_no_assets(client):
    rv = client.get(f"/results", follow_redirects=True)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_page_with_no_assets_debug_on(client):
    rv = client.get(f"/results?debug=true", follow_redirects=True)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_unpriceable_asset_is_excluded_and_reported(client):
    # Pricing source without any quotes -> the period analyzer cannot price
    # the asset and flags it as errored.
    quoteId = PricingSource.createSimple().commit()
    Asset.createEquity() \
        .pricing(quoteId) \
        .operation('BUY', datetime.datetime(2020, 6, 1), 10, 10, 100) \
        .commit()

    rv = client.get("/results?timerange=2020", follow_redirects=True)
    assert rv.status_code == 200
    assert b"Could not price the following assets" in rv.data
    assert b"Test equity" in rv.data

