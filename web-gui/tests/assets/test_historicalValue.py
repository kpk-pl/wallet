import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client
from tests.mocks import Asset, PricingSource


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_historical_data_with_no_assets(client):
    rv = client.get(f"/assets/historicalValue?daysBack=180&investedValue=True", follow_redirects=True)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_historical_data_with_assets_without_quotes(client):
    Asset().createEquity().pricing().quantity(1).commit()

    rv = client.get(f"/assets/historicalValue?daysBack=180&investedValue=True", follow_redirects=True)
    assert rv.status_code == 200
