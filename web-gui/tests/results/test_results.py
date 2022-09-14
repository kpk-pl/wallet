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

