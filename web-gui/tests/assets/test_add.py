import pytest
import mongomock
import pymongo
import tests
from bson.objectid import ObjectId
from tests.fixtures import client
from tests.mocks import PricingSource


ASSET_ADD_DATA_QUOTE_ID = ObjectId()
MINIMAL_ASSET_ADD_DATA = dict(
    name = "Test asset",
    priceQuoteId = str(ASSET_ADD_DATA_QUOTE_ID),
    institution = "Test Bank",
    type = "Equity",
    category = "Equities",
    region = "World",
)

@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_minimal_listed(client):
    PricingSource.createSimple(ASSET_ADD_DATA_QUOTE_ID).commit()

    rv = client.post(f"/assets", data=MINIMAL_ASSET_ADD_DATA, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': ObjectId(rv.json['id'])})

        assert dbAsset == dict(
            _id = ObjectId(rv.json['id']),
            name = MINIMAL_ASSET_ADD_DATA['name'],
            institution = MINIMAL_ASSET_ADD_DATA['institution'],
            type = MINIMAL_ASSET_ADD_DATA['type'],
            category = MINIMAL_ASSET_ADD_DATA['category'],
            region = MINIMAL_ASSET_ADD_DATA['region'],
            pricing = { 'quoteId': ObjectId(ASSET_ADD_DATA_QUOTE_ID) },
            currency = { 'name': 'PLN' }
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_maximal_listed(client):
    PricingSource.createSimple(ASSET_ADD_DATA_QUOTE_ID).commit()

    data = {k: v for (k,v) in MINIMAL_ASSET_ADD_DATA.items()}
    data.update(dict(
        ticker = "MAX",
        subcategory = "Domestic",
        link = "http://link.com",
        labels = "longterm,fixed",
    ))

    rv = client.post(f"/assets", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': ObjectId(rv.json['id'])})

        assert dbAsset == dict(
            _id = ObjectId(rv.json['id']),
            name = MINIMAL_ASSET_ADD_DATA['name'],
            ticker = "MAX",
            institution = MINIMAL_ASSET_ADD_DATA['institution'],
            type = MINIMAL_ASSET_ADD_DATA['type'],
            category = MINIMAL_ASSET_ADD_DATA['category'],
            subcategory = "Domestic",
            region = MINIMAL_ASSET_ADD_DATA['region'],
            link = "http://link.com",
            labels = ['longterm', 'fixed'],
            pricing = { 'quoteId': ObjectId(ASSET_ADD_DATA_QUOTE_ID) },
            currency = { 'name': 'PLN' }
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_failure_invalid_pricing_data(client):
    rv = client.post(f"/assets", data=MINIMAL_ASSET_ADD_DATA, follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 2


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_currency_taken_from_quoteid_by_default(client):
    PricingSource.createSimple(ASSET_ADD_DATA_QUOTE_ID).unit("EUR").commit()
    currencyId = PricingSource.createCurrencyPair("EUR").commit()

    data = {k: v for (k,v) in MINIMAL_ASSET_ADD_DATA.items()}
    data['currency'] = "USD"

    rv = client.post(f"/assets", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': ObjectId(rv.json['id'])})
        assert dbAsset['currency'] == dict(
            name = "EUR",
            quoteId = currencyId,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_failure_when_no_currency_pair_found(client):
    PricingSource.createSimple(ASSET_ADD_DATA_QUOTE_ID).unit("EUR").commit()

    rv = client.post(f"/assets", data=MINIMAL_ASSET_ADD_DATA, follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 3


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_failure_when_no_currency_info(client):
    data = {k: v for (k,v) in MINIMAL_ASSET_ADD_DATA.items()}
    del data['priceQuoteId']

    rv = client.post(f"/assets", data=data, follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 1


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_explicit_currency(client):
    data = {k: v for (k,v) in MINIMAL_ASSET_ADD_DATA.items()}
    data['currency'] = 'PLN'
    del data['priceQuoteId']

    rv = client.post(f"/assets", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': ObjectId(rv.json['id'])})
        assert dbAsset['currency'] == {'name': "PLN"}


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_failure_explicit_foreign_currency_not_found(client):
    data = {k: v for (k,v) in MINIMAL_ASSET_ADD_DATA.items()}
    data['currency'] = 'USD'
    del data['priceQuoteId']

    rv = client.post(f"/assets", data=data, follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 3




