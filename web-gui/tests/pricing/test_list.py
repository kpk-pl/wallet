import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client
from bson.objectid import ObjectId


MINIMAL_PRICING_SOURCE_DATA = dict(
    name = "Test source",
    url = "http://test.source.com",
    updateFrequency = "daily"
)

@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source(client):
    rv = client.post(f"/pricing", data=MINIMAL_PRICING_SOURCE_DATA, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbPricing = db.wallet.quotes.find_one({'_id': ObjectId(rv.json['id'])})

        assert dbPricing == dict(
            _id = ObjectId(rv.json['id']),
            name = MINIMAL_PRICING_SOURCE_DATA['name'],
            url = MINIMAL_PRICING_SOURCE_DATA['url'],
            updateFrequency = MINIMAL_PRICING_SOURCE_DATA['updateFrequency']
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_supports_predefined_update_frequencies(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}

    for freq in ['daily', 'weekly', 'monthly']:
        data['updateFrequency'] = freq
        rv = client.post(f"/pricing", data=data, follow_redirects=True)
        assert rv.status_code == 200

    data['updateFrequency'] = 'invalid'
    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 400

@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_maximal_data(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}
    data.update(
        ticker = "PS",
        unit = "USD"
    )

    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbPricing = db.wallet.quotes.find_one({'_id': ObjectId(rv.json['id'])})

        assert dbPricing == dict(
            _id = ObjectId(rv.json['id']),
            name = data['name'],
            ticker = data['ticker'],
            unit = data['unit'],
            url = data['url'],
            updateFrequency = data['updateFrequency']
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_maximal_data(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}
    data.update(
        ticker = "PS",
        unit = "USD"
    )

    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbPricing = db.wallet.quotes.find_one({'_id': ObjectId(rv.json['id'])})

        assert dbPricing == dict(
            _id = ObjectId(rv.json['id']),
            name = data['name'],
            ticker = data['ticker'],
            unit = data['unit'],
            url = data['url'],
            updateFrequency = data['updateFrequency']
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_as_currency_pair(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}
    data.update(
        unit = "USD",
        currencyPairFrom = "PLN",
        currencyPairCheck = True
    )

    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbPricing = db.wallet.quotes.find_one({'_id': ObjectId(rv.json['id'])})

        assert 'currencyPair' in dbPricing
        assert dbPricing['currencyPair'] == {'from': "USD", 'to': "PLN"}


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_as_currency_pair_fails_without_required_data(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}
    data['currencyPairCheck'] = True

    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 400

    data['unit'] = 'PLN'
    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 400
    del data['unit']

    data['currencyPairFrom'] = 'USD'
    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 400
