import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_wallet_load_without_db_data(client):
    rv = client.get(f"/wallet", follow_redirects=True)
    assert rv.status_code == 200
