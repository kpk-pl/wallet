import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client
from tests.mocks import Asset, PricingSource


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_wallet_load_without_db_data(client):
    rv = client.get(f"/wallet", follow_redirects=True)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_wallet_asset_without_quote_history_in_pricing(client):
    Asset().createEquity().pricing().quantity(1).commit()

    rv = client.get(f"/wallet", follow_redirects=True)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_stragety_get_without_assets(client):
    rv = client.get(f"/wallet/strategy?allocation=true", follow_redirects=True)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_strategy_json_get_without_assets(client):
    rv = client.get(f"/wallet/strategy?allocation=true", follow_redirects=True, headers={"Accept": "application/json"})
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_strategy_get_with_missing_quotes_for_pricing(client):
    Asset().createEquity().pricing().quantity(1).commit()

    rv = client.get(f"/wallet/strategy?allocation=true", follow_redirects=True)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_strategy_json_get_with_missing_quotes_for_pricing(client):
    Asset().createEquity().pricing().quantity(1).commit()

    rv = client.get(f"/wallet/strategy?allocation=true", follow_redirects=True, headers={"Accept": "application/json"})
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_wallet_aggregation_merges_assets_sharing_pricing(client):
    quoteId = PricingSource.createSimple().commit()

    a = Asset().createEquity().pricing(quoteId).quantity(1)
    a['institution'] = "Bank A"
    a.commit()

    b = Asset().createEquity().pricing(quoteId).quantity(2)
    b['institution'] = "Bank B"
    b.commit()

    rv = client.get(f"/wallet?aggregation=pn", follow_redirects=True)
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    assert "Bank A" in body
    assert "Bank B" in body


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_wallet_aggregation_with_mixed_priced_and_deposit(client):
    quoteId = PricingSource.createSimple().commit()

    a = Asset().createEquity().pricing(quoteId).quantity(1)
    a['institution'] = "Bank A"
    a.commit()
    b = Asset().createEquity().pricing(quoteId).quantity(2)
    b['institution'] = "Bank B"
    b.commit()

    d = Asset().createDeposit().quantity(100)
    d['institution'] = "Bank A"
    d.commit()

    rv = client.get(f"/wallet?aggregation=pn", follow_redirects=True)
    assert rv.status_code == 200
