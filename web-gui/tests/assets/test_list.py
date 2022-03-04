import pytest
import mongomock
import tests
from tests.fixtures import client


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_can_get_asset_list_with_empty_database(client):
    rv = client.get(f"/assets", follow_redirects=True)
    assert rv.status_code == 200
