import pytest
import mongomock
import pymongo
import tests
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from flaskr import model
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


def _parametrizedPayload(quoteId):
    return dict(
        kind = "parametrized",
        name = "EDO Test",
        institution = "PKO",
        type = "Polish Individual Bonds",
        category = "Bonds",
        subcategory = "Inflation Linked",
        currency = "PLN",
        labels = "longterm,safety",
        pricing = dict(
            length = dict(count=10, name="year", multiplier=1),
            profitDistribution = "accumulating",
            interest = [
                dict(fixed=dict(percentage="0.017")),
                dict(
                    fixed = dict(percentage="0.01"),
                    derived = dict(
                        quoteId = str(quoteId),
                        sample = dict(interval="month", intervalOffset=-2, choose="last",
                                      multiplier="0.01", clampBelow="0", usePreviousWhenMissing=True),
                    ),
                ),
            ],
        ),
    )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_parametrized(client):
    quoteId = PricingSource.createSimple().unit("%").commit()

    rv = client.post("/assets", json=_parametrizedPayload(quoteId), follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': ObjectId(rv.json['id'])})

        assert dbAsset['type'] == "Polish Individual Bonds"
        assert dbAsset['category'] == "Bonds"
        assert dbAsset['subcategory'] == "Inflation Linked"
        assert dbAsset['currency'] == {'name': 'PLN'}
        assert dbAsset['labels'] == ['longterm', 'safety']

        # The default unit multiplier is dropped to match existing documents.
        assert dbAsset['pricing']['length'] == {'count': 10, 'name': 'year'}
        assert dbAsset['pricing']['profitDistribution'] == 'accumulating'

        interest = dbAsset['pricing']['interest']
        assert interest[0] == {'fixed': {'percentage': Decimal128("0.017")}}
        derived = interest[1]['derived']
        assert derived['quoteId'] == quoteId
        assert derived['sample']['intervalOffset'] == -2
        assert derived['sample']['clampBelow'] == Decimal128("0")
        assert derived['sample']['usePreviousWhenMissing'] is True

        # The stored document round-trips back through the typed model.
        asset = model.Asset(**dbAsset)
        assert isinstance(asset.pricing, model.AssetPricingParametrized)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_parametrized_rejects_empty_interest_period(client):
    payload = _parametrizedPayload(ObjectId())
    payload['pricing']['interest'].append({})

    rv = client.post("/assets", json=payload, follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 12
