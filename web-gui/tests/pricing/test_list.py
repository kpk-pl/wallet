import pytest
import mongomock
import pymongo
import tests
from tests.fixtures import client
from bson.objectid import ObjectId
from datetime import datetime
from flaskr.model.quote import QuoteUpdateFrequency


MINIMAL_PRICING_SOURCE_DATA = dict(
    name = "Test source",
    url = "http://test.source.com",
    updateFrequency = "daily",
    unit = "EUR",
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
            updateFrequency = MINIMAL_PRICING_SOURCE_DATA['updateFrequency'],
            unit = MINIMAL_PRICING_SOURCE_DATA['unit'],
        )

@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_pulls_the_latest_quote_from_url(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}
    data['url'] = "http://mocking.com?quote=10.1&timestamp=2022-01-12T14:30:00"

    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbPricing = db.wallet.quotes.find_one({'_id': ObjectId(rv.json['id'])})

        assert dbPricing == dict(
            _id = ObjectId(rv.json['id']),
            name = data['name'],
            url = data['url'],
            updateFrequency = data['updateFrequency'],
            unit = data['unit'],
            quoteHistory = [dict(quote=10.1, timestamp=datetime(2022, 1, 12, 14, 30))]
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_supports_predefined_update_frequencies(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}

    for freq in QuoteUpdateFrequency:
        data['updateFrequency'] = freq.name
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
        currencyPairFrom = "PLN",
        currencyPairCheck = True
    )

    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbPricing = db.wallet.quotes.find_one({'_id': ObjectId(rv.json['id'])})

        assert 'currencyPair' in dbPricing
        assert dbPricing['currencyPair'] == {'from': MINIMAL_PRICING_SOURCE_DATA['unit'], 'to': "PLN"}


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_add_source_fails_with_incorrect_url(client):
    data = {**MINIMAL_PRICING_SOURCE_DATA}
    data['url'] = "mock://invalid.com"

    rv = client.post(f"/pricing", data=data, follow_redirects=True)
    assert rv.status_code == 400


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
