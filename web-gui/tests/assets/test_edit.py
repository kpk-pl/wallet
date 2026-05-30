import pytest
import mongomock
import pymongo
import tests
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from tests.fixtures import client
from tests.mocks import Asset, PricingSource


def _parametrizedAsset():
    asset = Asset(name="EDO", institution="PKO", type="Polish Individual Bonds", category="Bonds")
    asset['subcategory'] = "Inflation Linked"
    asset.main_currency("PLN")
    asset._data['pricing'] = dict(
        length = dict(count=10, name="year"),
        profitDistribution = "accumulating",
        interest = [dict(fixed={'percentage': Decimal128("0.017")})],
    )
    return asset


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_get_renders_form(client):
    assetId = Asset.createEquity().commit()

    rv = client.get(f"/assets/edit?id={assetId}")
    assert rv.status_code == 200
    assert b'Edit asset' in rv.data
    # Existing values are pre-filled into the form.
    assert b'Test equity' in rv.data


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_get_without_id_is_bad_request(client):
    rv = client.get("/assets/edit")
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_get_not_found(client):
    rv = client.get(f"/assets/edit?id={ObjectId()}")
    assert rv.status_code == 404


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_updates_fields(client):
    assetId = Asset.createEquity().commit()

    data = dict(
        name="Renamed equity",
        ticker="NEW",
        type="ETF",
        institution="New Bank",
        category="Bonds",
        subcategory="Domestic",
        region="Europe",
        link="http://example.com",
        labels="longterm,fixed",
    )

    rv = client.post(f"/assets/edit?id={assetId}", data=data)
    assert rv.status_code == 200
    assert rv.json['id'] == str(assetId)

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert dbAsset['name'] == "Renamed equity"
        assert dbAsset['ticker'] == "NEW"
        assert dbAsset['type'] == "ETF"
        assert dbAsset['institution'] == "New Bank"
        assert dbAsset['category'] == "Bonds"
        assert dbAsset['subcategory'] == "Domestic"
        assert dbAsset['region'] == "Europe"
        assert dbAsset['link'] == "http://example.com"
        assert dbAsset['labels'] == ['longterm', 'fixed']
        # The currency / pricing source is never touched by an edit.
        assert dbAsset['currency'] == {'name': 'PLN'}


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_clears_optional_fields(client):
    assetId = Asset.createEquity().commit()

    data = dict(
        name="Test equity",
        ticker="",
        type="Equity",
        institution="Bank of Mocks",
        category="Equities",
        subcategory="",
        region="World",
        link="",
        labels="",
    )

    rv = client.post(f"/assets/edit?id={assetId}", data=data)
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert 'ticker' not in dbAsset
        assert 'subcategory' not in dbAsset
        assert 'link' not in dbAsset
        assert 'labels' not in dbAsset


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_preserves_operations(client):
    assetId = Asset.createEquity().pricing().quantity(10).commit()

    data = dict(
        name="Still here",
        type="Equity",
        institution="Bank of Mocks",
        category="Equities",
        region="World",
    )

    rv = client.post(f"/assets/edit?id={assetId}", data=data)
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert dbAsset['name'] == "Still here"
        assert len(dbAsset['operations']) == 1


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_get_renders_form_for_parametrized(client):
    assetId = _parametrizedAsset().commit()

    rv = client.get(f"/assets/edit?id={assetId}")
    assert rv.status_code == 200
    assert b'Edit asset' in rv.data
    assert b'EDO' in rv.data


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_preserves_parametrized_pricing(client):
    assetId = _parametrizedAsset().commit()

    data = dict(
        name="EDO renamed",
        type="Polish Individual Bonds",
        institution="PKO",
        category="Bonds",
        subcategory="Inflation Linked",
        region="",
    )

    rv = client.post(f"/assets/edit?id={assetId}", data=data)
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert dbAsset['name'] == "EDO renamed"
        # The parametrized pricing block is left untouched by an edit.
        assert dbAsset['pricing']['profitDistribution'] == "accumulating"
        assert dbAsset['pricing']['interest'][0]['fixed']['percentage'] == Decimal128("0.017")


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_parametrized_updates_pricing(client):
    quoteId = PricingSource.createSimple().unit("%").commit()
    assetId = _parametrizedAsset().commit()

    payload = dict(
        name="EDO updated",
        institution="PKO",
        type="Polish Individual Bonds",
        category="Bonds",
        subcategory="Inflation Linked",
        region="Poland",
        labels="longterm",
        pricing=dict(
            length=dict(count=12, name="month", multiplier=1),
            profitDistribution="distributing",
            interest=[
                dict(fixed=dict(percentage="0.02")),
                dict(derived=dict(
                    quoteId=str(quoteId),
                    sample=dict(interval="month", intervalOffset=-1, choose="last",
                                multiplier="0.01", usePreviousWhenMissing=True),
                )),
            ],
        ),
    )

    rv = client.post(f"/assets/edit?id={assetId}", json=payload)
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert dbAsset['name'] == "EDO updated"
        assert dbAsset['region'] == "Poland"
        # The currency is never touched by an edit.
        assert dbAsset['currency'] == {'name': 'PLN'}
        # Pricing parameters are fully replaced by the edited values.
        assert dbAsset['pricing']['length'] == {'count': 12, 'name': 'month'}
        assert dbAsset['pricing']['profitDistribution'] == "distributing"
        assert len(dbAsset['pricing']['interest']) == 2
        assert dbAsset['pricing']['interest'][0]['fixed']['percentage'] == Decimal128("0.02")
        assert dbAsset['pricing']['interest'][1]['derived']['quoteId'] == quoteId


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_parametrized_rejects_empty_interest_period(client):
    assetId = _parametrizedAsset().commit()

    payload = dict(
        name="EDO",
        institution="PKO",
        type="Polish Individual Bonds",
        category="Bonds",
        pricing=dict(
            length=dict(count=10, name="year"),
            profitDistribution="accumulating",
            interest=[{}],
        ),
    )

    rv = client.post(f"/assets/edit?id={assetId}", json=payload)
    assert rv.status_code == 400
    assert rv.json['code'] == 12


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_edit_post_not_found(client):
    data = dict(
        name="Whatever",
        type="Equity",
        institution="Bank",
        category="Equities",
        region="World",
    )

    rv = client.post(f"/assets/edit?id={ObjectId()}", data=data)
    assert rv.status_code == 404
