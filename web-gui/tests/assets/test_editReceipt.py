import pytest
import mongomock
import pymongo
import tests
import datetime
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from tests.fixtures import client
from tests.mocks import Asset


def _twoOperationEquity():
    return (Asset.createEquity()
            .pricing()
            .operation('BUY', datetime.datetime(2021, 1, 1), 10, 10, 100)
            .operation('BUY', datetime.datetime(2021, 6, 1), 5, 15, 50)
            .commit())


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_get_renders_form(client):
    assetId = _twoOperationEquity()
    rv = client.get(f"/assets/receipt/edit?id={str(assetId)}&index=0")
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_get_renders_form_for_deposit(client):
    assetId = (Asset.createDeposit()
               .operation('BUY', datetime.datetime(2021, 1, 1), 100, 100, 100)
               .operation('BUY', datetime.datetime(2021, 6, 1), 50, 150, 50)
               .commit())
    rv = client.get(f"/assets/receipt/edit?id={str(assetId)}&index=1")
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_get_renders_form_for_earning_without_volume(client):
    assetId = (Asset.createEquity()
               .pricing()
               .operation('BUY', datetime.datetime(2021, 1, 1), 10, 10, 100)
               .operation('EARNING', datetime.datetime(2021, 6, 1), None, 10, 5)
               .commit())
    rv = client.get(f"/assets/receipt/edit?id={str(assetId)}&index=1")
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_bad_request_when_no_id(client):
    rv = client.post("/assets/receipt/edit?index=0", data={'date': '2021-01-01 00:00:00', 'price': 1})
    assert rv.status_code == 400
    assert rv.json['code'] == 1


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_bad_request_when_invalid_index(client):
    assetId = _twoOperationEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=abc", data={'date': '2021-01-01 00:00:00', 'price': 1})
    assert rv.status_code == 400
    assert rv.json['code'] == 3


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_bad_request_when_index_out_of_range(client):
    assetId = _twoOperationEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=9", data={'date': '2021-01-01 00:00:00', 'price': 1})
    assert rv.status_code == 400
    assert rv.json['code'] == 5


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_updates_price_and_provision(client):
    assetId = _twoOperationEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=0",
                     data={'date': '2021-01-01 00:00:00', 'price': 123, 'provision': 7})
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        operation = db.wallet.assets.find_one({'_id': assetId})['operations'][0]
        assert operation['price'] == 123
        assert operation['provision'] == 7
        # Volume / type / finalQuantity must be untouched.
        assert operation['quantity'] == 10
        assert operation['type'] == 'BUY'
        assert operation['finalQuantity'] == 10


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_rejects_date_later_than_following_operation(client):
    assetId = _twoOperationEquity()
    # Move the first operation past the second one — must keep ascending order.
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=0",
                     data={'date': '2021-12-01 00:00:00', 'price': 100})
    assert rv.status_code == 400
    assert rv.json['code'] == 106


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_rejects_date_earlier_than_preceding_operation(client):
    assetId = _twoOperationEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=1",
                     data={'date': '2020-01-01 00:00:00', 'price': 50})
    assert rv.status_code == 400
    assert rv.json['code'] == 106


def _foreignCurrencyEquity():
    return (Asset.createEquity()
            .currency('USD')
            .operation('BUY', datetime.datetime(2021, 1, 1), 10, 10, 100, currencyConversion=4)
            .operation('BUY', datetime.datetime(2021, 6, 1), 5, 15, 50, currencyConversion=4)
            .commit())


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_get_renders_form_for_foreign_currency(client):
    assetId = _foreignCurrencyEquity()
    rv = client.get(f"/assets/receipt/edit?id={str(assetId)}&index=0")
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_updates_conversion_rate_for_foreign_currency(client):
    assetId = _foreignCurrencyEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=0",
                     data={'date': '2021-01-01 00:00:00', 'price': 100, 'currencyConversion': 5, 'provision': 2})
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        operation = db.wallet.assets.find_one({'_id': assetId})['operations'][0]
        assert operation['currencyConversion'] == 5
        assert operation['provision'] == 2


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_requires_conversion_rate_for_foreign_currency(client):
    assetId = _foreignCurrencyEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=0",
                     data={'date': '2021-01-01 00:00:00', 'price': 100})
    assert rv.status_code == 400
    assert rv.json['code'] == 104


def _orderIdEquity():
    return (Asset.createEquity()
            .hasOrderIds()
            .pricing()
            .operation('BUY', datetime.datetime(2021, 1, 1), 10, 10, 100, orderId='A1')
            .operation('BUY', datetime.datetime(2021, 6, 1), 5, 15, 50, orderId='A2')
            .commit())


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_updates_order_id(client):
    assetId = _orderIdEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=0",
                     data={'date': '2021-01-01 00:00:00', 'price': 100, 'orderId': 'B7'})
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        operation = db.wallet.assets.find_one({'_id': assetId})['operations'][0]
        assert operation['orderId'] == 'B7'


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_requires_order_id_when_asset_has_them(client):
    assetId = _orderIdEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=0",
                     data={'date': '2021-01-01 00:00:00', 'price': 100})
    assert rv.status_code == 400
    assert rv.json['code'] == 105


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_allows_date_within_neighbours(client):
    assetId = _twoOperationEquity()
    rv = client.post(f"/assets/receipt/edit?id={str(assetId)}&index=0",
                     data={'date': '2021-03-15 10:00:00', 'price': 100})
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        operation = db.wallet.assets.find_one({'_id': assetId})['operations'][0]
        assert operation['date'] == datetime.datetime(2021, 3, 15, 10, 0, 0)
