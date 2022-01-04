import pytest
import mongomock
import pymongo
import tests
import datetime
from tests.fixtures import client
from tests.mocks import PricingSource, Asset


MINIMAL_WORKING_RECEIPT_DATA = dict(
    type = 'BUY',
    date = '2021-07-12T12:01:08',
    quantity = 1,
    price = 100
)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_bad_request_when_no_id(client):
    rv = client.post(f"/assets/receipt", follow_redirects=True)
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_bad_request_when_invalid(client):
    rv = client.post(f"/assets/receipt?id=12", follow_redirects=True)
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_minimal_working_data(client):
    assetId = Asset.createEquity().pricing().commit()
    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=MINIMAL_WORKING_RECEIPT_DATA)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,field', [
    (pytest.lazy_fixture('client'), "type"),
    (pytest.lazy_fixture('client'), "date"),
    (pytest.lazy_fixture('client'), "quantity"),
    (pytest.lazy_fixture('client'), "price"),
])
def test_receipt_failure_when_required_field_missing(clientApp, field):
    assetId = Asset.createEquity().pricing().commit()

    baseData = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items() if k != field}
    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=baseData)
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


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,type', [
    (pytest.lazy_fixture('client'), "BUY"),
    (pytest.lazy_fixture('client'), "SELL"),
])
def test_receipt_supports_conversion_rate_for_foreign_currency(clientApp, type):
    pricingId = PricingSource.createSimple().unit("USD").commit()
    assetId = Asset.createEquity().pricing(pricingId).currency("USD").quantity(10).commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = type
    data['currencyConversion'] = 1.02

    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1]['type'] == type
        assert dbAsset['operations'][1]['currencyConversion'] == 1.02


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,type', [
    (pytest.lazy_fixture('client'), "BUY"),
    (pytest.lazy_fixture('client'), "SELL"),
])
def test_receipt_failure_no_conversion_rate_for_foreign_currency(clientApp, type):
    pricingId = PricingSource.createSimple().unit("USD").commit()
    assetId = Asset.createEquity().pricing(pricingId).currency("USD").quantity(10).commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = type

    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,type', [
    (pytest.lazy_fixture('client'), "BUY"),
    (pytest.lazy_fixture('client'), "SELL"),
])
def test_receipt_failure_no_code_for_coded(clientApp, type):
    assetId = Asset.createEquity().pricing().quantity(10).coded().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = type

    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)
    assert rv.status_code == 400


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,type', [
    (pytest.lazy_fixture('client'), "BUY"),
    (pytest.lazy_fixture('client'), "SELL"),
])
def test_receipt_successfull_for_coded(clientApp, type):
    assetId = Asset.createEquity().pricing().quantity(10).coded().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = type
    data['code'] = "CD"

    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)
    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1]['type'] == type
        assert dbAsset['operations'][1]['code'] == "CD"
