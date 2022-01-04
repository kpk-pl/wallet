import pytest
import mongomock
import pymongo
import tests
import datetime
from tests.fixtures import client
from tests.mocks import PricingSource, Asset


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_bad_request_when_no_id(client):
    rv = client.post(f"/assets/receipt", follow_redirects=True)
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_bad_request_when_invalid(client):
    rv = client.post(f"/assets/receipt?id=12", follow_redirects=True)
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_first_buy(client):
    assetId = Asset.createEquity().pricing().commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'BUY',
        date = '2021-07-12T12:01:08',
        quantity = 10,
        price = 100
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1
        assert dbAsset['operations'][0] == dict(
            type = 'BUY',
            quantity = 10,
            finalQuantity = 10,
            price = 100,
            date = datetime.datetime(2021, 7, 12, 12, 1, 8)
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_next_buy(client):
    assetId = Asset.createEquity().pricing().quantity(10).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'BUY',
        date = '2021-07-12T12:01:08',
        quantity = 15,
        price = 100
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1]['finalQuantity'] == 25


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_sell(client):
    assetId = Asset.createEquity().pricing().quantity(10).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'SELL',
        date = '2021-07-12T12:01:08',
        quantity = 3,
        price = 100
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1] == dict(
            type = 'SELL',
            quantity = 3,
            finalQuantity = 7,
            price = 100,
            date = datetime.datetime(2021, 7, 12, 12, 1, 8)
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_failure_sell_more_than_have(client):
    assetId = Asset.createEquity().pricing().quantity(10).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'SELL',
        date = '2021-07-12T12:01:08',
        quantity = 15,
        price = 100
    ), follow_redirects=True)

    assert rv.status_code == 400
