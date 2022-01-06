import pytest
import mongomock
import pymongo
import tests
import datetime
from bson.objectid import ObjectId
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
    assert rv.json['code'] == 1


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_bad_request_when_invalid(client):
    rv = client.post(f"/assets/receipt?id=12", follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 2


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_minimal_working_data(client):
    assetId = Asset.createEquity().pricing().commit()
    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=MINIMAL_WORKING_RECEIPT_DATA)
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,field,errorCode', [
    (pytest.lazy_fixture('client'), "type", 101),
    (pytest.lazy_fixture('client'), "date", 100),
    (pytest.lazy_fixture('client'), "quantity", 102),
    (pytest.lazy_fixture('client'), "price", 103),
])
def test_receipt_failure_when_required_field_missing(clientApp, field, errorCode):
    assetId = Asset.createEquity().pricing().commit()

    baseData = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items() if k != field}
    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=baseData)
    assert rv.status_code == 400
    assert rv.json['code'] == errorCode


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
    assert rv.json['code'] == 11


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,type', [
    (pytest.lazy_fixture('client'), "BUY"),
    (pytest.lazy_fixture('client'), "SELL"),
    (pytest.lazy_fixture('client'), "RECEIVE"),
    (pytest.lazy_fixture('client'), "EARNING"),
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
    (pytest.lazy_fixture('client'), "RECEIVE"),
    (pytest.lazy_fixture('client'), "EARNING"),
])
def test_receipt_failure_no_conversion_rate_for_foreign_currency(clientApp, type):
    pricingId = PricingSource.createSimple().unit("USD").commit()
    assetId = Asset.createEquity().pricing(pricingId).currency("USD").quantity(10).commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = type

    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 104


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,type', [
    (pytest.lazy_fixture('client'), "BUY"),
    (pytest.lazy_fixture('client'), "SELL"),
    (pytest.lazy_fixture('client'), "RECEIVE"),
    (pytest.lazy_fixture('client'), "EARNING"),
])
def test_receipt_failure_no_code_for_coded(clientApp, type):
    assetId = Asset.createEquity().pricing().quantity(10).coded().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = type

    rv = clientApp.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)
    assert rv.status_code == 400
    assert rv.json['code'] == 105


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize('clientApp,type', [
    (pytest.lazy_fixture('client'), "BUY"),
    (pytest.lazy_fixture('client'), "SELL"),
    (pytest.lazy_fixture('client'), "RECEIVE"),
    (pytest.lazy_fixture('client'), "EARNING"),
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


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_deposit_handling(client):
    assetId = Asset.createDeposit().commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'BUY',
        date = '2020-01-04T12:13:14',
        quantity = 1000,
        provision = 12.5
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1
        assert dbAsset['operations'][0] == dict(
            type = 'BUY',
            quantity = 1000,
            finalQuantity = 1000,
            price = 1000,
            date = datetime.datetime(2020, 1, 4, 12, 13, 14),
            provision = 12.5
        )

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'SELL',
        date = '2020-01-04T13:00:00',
        quantity = 999,
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1] == dict(
            type = 'SELL',
            quantity = 999,
            finalQuantity = 1,
            price = 999,
            date = datetime.datetime(2020, 1, 4, 13, 0, 0),
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_receive(client):
    assetId = Asset.createEquity().pricing().quantity(10).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'RECEIVE',
        date = '2021-12-02T17:45:22',
        quantity = 22,
        price = 27.2
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1] == dict(
            type = "RECEIVE",
            date = datetime.datetime(2021, 12, 2, 17, 45, 22),
            quantity = 22,
            finalQuantity = 32,
            price = 27.2,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_receive_does_not_support_provision(client):
    assetId = Asset.createEquity().pricing().commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'RECEIVE',
        date = '2021-12-02T17:45:22',
        quantity = 22,
        price = 27.2,
        provision = 1000,
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1
        assert 'provision' not in dbAsset['operations'][0]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_failure_receive_not_supported_for_deposit(client):
    assetId = Asset.createDeposit().commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'RECEIVE',
        date = '2021-12-02T17:45:22',
        quantity = 22,
        price = 27.2,
    ), follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 10


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_successfull_earning(client):
    assetId = Asset.createEquity().pricing().quantity(10).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'EARNING',
        date = '2021-12-02T17:45:22',
        price = 12.5,
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1] == dict(
            type = "EARNING",
            date = datetime.datetime(2021, 12, 2, 17, 45, 22),
            finalQuantity = 10,
            price = 12.5,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_earning_does_not_contain_quantity(client):
    assetId = Asset.createEquity().pricing().commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'EARNING',
        date = '2021-12-02T17:45:22',
        price = 12.5,
        quantity = 13,
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1
        assert 'quantity' not in dbAsset['operations'][0]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_earning_for_deposit_needs_quantity(client):
    assetId = Asset.createDeposit().quantity(12).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'EARNING',
        date = '2021-12-02T17:45:22',
        quantity = 13,
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2
        assert dbAsset['operations'][1] == dict(
            type = "EARNING",
            date = datetime.datetime(2021, 12, 2, 17, 45, 22),
            quantity = 13,
            price = 13,
            finalQuantity = 25,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_for_buy(client):
    assetId = Asset.createEquity().commit()
    billingId = Asset.createDeposit().quantity(1000).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'BUY',
        date = '2021-12-03T12:00:00',
        quantity = 2,
        price = 560,
        billingAsset = str(billingId),
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1

        billingAsset = db.wallet.assets.find_one({'_id': billingId})
        assert len(billingAsset['operations']) == 2
        assert billingAsset['operations'][1] == dict(
            type = 'SELL',
            date = datetime.datetime(2021, 12, 3, 12),
            quantity = 560,
            finalQuantity = 440,
            price = 560,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_for_sell_currency_conversion(client):
    assetId = Asset.createEquity().currency("USD").quantity(20).commit()
    billingId = Asset.createDeposit().quantity(100).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'SELL',
        date = '2021-12-03T12:00:00',
        quantity = 5,
        price = 100,
        currencyConversion = 3.5,
        billingAsset = str(billingId),
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2

        billingAsset = db.wallet.assets.find_one({'_id': billingId})
        assert len(billingAsset['operations']) == 2
        assert billingAsset['operations'][1] == dict(
            type = 'BUY',
            date = datetime.datetime(2021, 12, 3, 12),
            quantity = 350,
            finalQuantity = 450,
            price = 350,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_failure_not_enough(client):
    assetId = Asset.createEquity().quantity(20).commit()
    billingId = Asset.createDeposit().quantity(100).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'BUY',
        date = '2021-12-03T12:00:00',
        quantity = 5,
        price = 101,
        billingAsset = str(billingId),
    ), follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 206


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_for_earning(client):
    assetId = Asset.createEquity().commit()
    billingId = Asset.createDeposit().commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'EARNING',
        date = '2021-12-03T12:00:00',
        price = 100,
        billingAsset = str(billingId),
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1

        billingAsset = db.wallet.assets.find_one({'_id': billingId})
        assert len(billingAsset['operations']) == 1
        assert billingAsset['operations'][0] == dict(
            type = 'BUY',
            date = datetime.datetime(2021, 12, 3, 12),
            quantity = 100,
            finalQuantity = 100,
            price = 100,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_does_not_work_for_receive(client):
    assetId = Asset.createEquity().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = 'RECEIVE'
    data['billingAsset'] = str(ObjectId())

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_does_not_work_for_earning_on_deposit(client):
    assetId = Asset.createDeposit().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['type'] = 'EARNING'
    data['billingAsset'] = str(ObjectId())

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 201


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_failure_when_invalid_id(client):
    assetId = Asset.createEquity().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['billingAsset'] = 13

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 202


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_failure_when_unknown_id(client):
    assetId = Asset.createEquity().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['billingAsset'] = str(ObjectId())

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 203


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_failure_not_deposit(client):
    assetId = Asset.createEquity().commit()
    billingId = Asset.createEquity().commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['billingAsset'] = str(billingId)

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 204


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_failure_two_different_currencies(client):
    assetId = Asset.createEquity().currency("USD").commit()
    billingId = Asset.createDeposit().currency("EUR").commit()

    data = {k:v for (k,v) in MINIMAL_WORKING_RECEIPT_DATA.items()}
    data['currencyConversion'] = 4.5
    data['billingAsset'] = str(billingId)

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=data, follow_redirects=True)

    assert rv.status_code == 400
    assert rv.json['code'] == 205


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_buy_with_provision(client):
    assetId = Asset.createEquity().commit()
    billingId = Asset.createDeposit().quantity(1000).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'BUY',
        date = '2021-12-03T12:00:00',
        quantity = 2,
        price = 560,
        billingAsset = str(billingId),
        provision = 25,
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1

        billingAsset = db.wallet.assets.find_one({'_id': billingId})
        assert len(billingAsset['operations']) == 2
        assert billingAsset['operations'][1] == dict(
            type = 'SELL',
            date = datetime.datetime(2021, 12, 3, 12),
            quantity = 585,
            finalQuantity = 415,
            price = 585,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_sell_with_provision(client):
    assetId = Asset.createEquity().quantity(10).commit()
    billingId = Asset.createDeposit().quantity(1000).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'SELL',
        date = '2021-12-03T12:00:00',
        quantity = 2,
        price = 560,
        billingAsset = str(billingId),
        provision = 25,
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 2

        billingAsset = db.wallet.assets.find_one({'_id': billingId})
        assert len(billingAsset['operations']) == 2
        assert billingAsset['operations'][1] == dict(
            type = 'BUY',
            date = datetime.datetime(2021, 12, 3, 12),
            quantity = 535,
            finalQuantity = 1535,
            price = 535,
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_billing_asset_foreign_currencies(client):
    assetId = Asset.createEquity().currency("USD").commit()
    billingId = Asset.createDeposit().quantity(1000).commit()

    rv = client.post(f"/assets/receipt?id={str(assetId)}", data=dict(
        type = 'BUY',
        date = '2021-12-03T12:00:00',
        quantity = 2,
        price = 100,
        billingAsset = str(billingId),
        provision = 25,
        currencyConversion = 4.5
    ), follow_redirects=True)

    assert rv.status_code == 200

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        assert len(dbAsset['operations']) == 1
        assert dbAsset['operations'][0] == dict(
            type = "BUY",
            date = datetime.datetime(2021, 12, 3, 12),
            quantity = 2,
            finalQuantity = 2,
            price = 100,
            currencyConversion = 4.5,
            provision = 25,
        )

        billingAsset = db.wallet.assets.find_one({'_id': billingId})
        assert len(billingAsset['operations']) == 2
        assert billingAsset['operations'][1] == dict(
            type = 'SELL',
            date = datetime.datetime(2021, 12, 3, 12),
            quantity = 475,
            finalQuantity = 525,
            price = 475,
        )
