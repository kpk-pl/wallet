import pytest
import mongomock
import pymongo
import tests
from datetime import datetime
from tests import mocks
from flaskr import model
from flaskr.pricing import Pricing, Context
from decimal import Decimal
from bson import Decimal128, ObjectId


DATE_NOW=datetime(2022, 3, 15, 12, 0, 0)
DATE_YESTERDAY=datetime(2022, 3, 14, 12, 0, 0)
DATE_BEFORE_CURRENCIES=datetime(2022, 3, 2, 12, 0, 0)
DATE_PAST=datetime(2022, 1, 1, 12, 0, 0)
DATE_FUTURE=datetime(2023, 1, 1, 12, 0, 0)


PRICING_SOURCE_ALPHA=dict(
    name = 'Alpha',
    unit = 'PLN',
    quotes = [
        (datetime(2022, 3, 9, 17), Decimal128("30")),
        (datetime(2022, 3, 10, 17, 20), Decimal128("31.5")),
        (datetime(2022, 3, 11, 17, 13), Decimal128("32")),
        (datetime(2022, 3, 14, 17, 5), Decimal128("31"))
    ]
)


PRICING_SOURCE_USD=dict(
    name = 'USDPLN',
    quotes = [
        (datetime(2022, 3, 9, 17), Decimal128("4.1")),
        (datetime(2022, 3, 10, 17, 20), Decimal128("4.13")),
        (datetime(2022, 3, 11, 17, 13), Decimal128("4.15")),
        (datetime(2022, 3, 12, 17, 10), Decimal128("4.21")),
        (datetime(2022, 3, 13, 17, 0), Decimal128("4.17")),
        (datetime(2022, 3, 14, 17, 5), Decimal128("4.15"))
    ]
)


def setup_alpha():
    source = mocks.PricingSource()
    source.name(PRICING_SOURCE_ALPHA['name'])
    source.unit(PRICING_SOURCE_ALPHA['unit'])
    for ts, q in PRICING_SOURCE_ALPHA['quotes']:
        source.quote(ts, q)
    return source.commit()


def setup_usd():
    source = mocks.PricingSource.createCurrencyPair("USD")
    source.name(PRICING_SOURCE_USD['name'])
    for ts, q in PRICING_SOURCE_USD['quotes']:
        source.quote(ts, q)
    return source.commit()


def setup_asset(quoteId, currency=None):
    asset = mocks.Asset(name="Asset1", institution="Test", category="Directly quoted", type="ETF")
    asset.pricing(quoteId)

    if currency is None:
        asset.main_currency("PLN")
    else:
        asset.currency(currency[0], currency[1])

    asset.operation('BUY', datetime(2022, 3, 1, 15), 5, 5, 1)
    asset.operation('BUY', datetime(2022, 3, 14, 15), 5, 10, 1)
    return asset.commit()


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote():
    assetId = setup_asset(setup_alpha())

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        # Both operations are in scope
        pricing = Pricing(ctx=Context(DATE_NOW, db=db.wallet))
        assert (Decimal(310), Decimal(10)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote_includes_only_operations_up_to_final_date():
    assetId = setup_asset(setup_alpha())

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        # Only first operation is in scope
        pricing = Pricing(ctx=Context(DATE_YESTERDAY, db=db.wallet))
        assert (Decimal(160), Decimal(5)) ==  pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote_zeros_when_no_operations_in_scope():
    assetId = setup_asset(setup_alpha())

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        # None of the operations are in scope
        pricing = Pricing(ctx=Context(DATE_PAST, db=db.wallet))
        assert (Decimal(0), Decimal(0)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote_asset_without_any_quotes():
    currencyId = mocks.PricingSource().name("Empty").unit("PLN").commit()
    assetId = setup_asset(currencyId)

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(DATE_NOW, db=db.wallet))
        assert (None, Decimal(10)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote_in_foreign_currency():
    assetId = setup_asset(setup_alpha(), currency=("USD", setup_usd()))

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(DATE_YESTERDAY, db=db.wallet))
        value, quantity = pricing(asset)
        assert value == Decimal(160)*Decimal("4.17")
        assert quantity == Decimal(5)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote_in_foreign_currency_when_missing_currency():
    assetId = setup_asset(setup_alpha(), currency=("USD", ObjectId()))

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(DATE_NOW, db=db.wallet))
        assert (None, Decimal(10)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote_in_foreign_currency_when_too_far_back_in_the_past():
    assetId = setup_asset(setup_alpha(), currency=("USD", setup_usd()))

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(DATE_BEFORE_CURRENCIES, db=db.wallet))
        assert (None, Decimal(5)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_by_quote_various_operation_types():
    source = mocks.PricingSource()
    source.name("Simple pricing").unit("PLN")
    for dom in range(1, 8):
        source.quote(datetime(2022, 3, dom), 1.0 + float(dom))

    pricingId = source.commit()

    asset = mocks.Asset(name="Asset1", institution="Test", category="Directly quoted", type="ETF")
    asset.pricing(pricingId).main_currency("PLN")

    asset.operation('BUY', datetime(2022, 3, 1, 15), 5, 5, 1)
    asset.operation('RECEIVE', datetime(2022, 3, 2), 3, 8, 1)
    asset.operation('BUY', datetime(2022, 3, 3, 15), 5, 13, 1)
    asset.operation('EARNING', datetime(2022, 3, 4), None, 13, 2)
    asset.operation('SELL', datetime(2022, 3, 5, 12), 6, 7, 1)
    asset.operation('BUY', datetime(2022, 3, 6, 15), 5, 12, 1)

    assetId = asset.commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(datetime(2022, 2, 20), db=db.wallet))
        assert (0, Decimal(0)) == pricing(asset)

        pricing = Pricing(ctx=Context(datetime(2022, 3, 1, 16), db=db.wallet))
        assert (5 * 2.0, Decimal(5)) == pricing(asset)

        pricing = Pricing(ctx=Context(datetime(2022, 3, 2, 16), db=db.wallet))
        assert (8 * 3.0, Decimal(8)) == pricing(asset)

        pricing = Pricing(ctx=Context(datetime(2022, 3, 3, 16), db=db.wallet))
        assert (13 * 4.0, Decimal(13)) == pricing(asset)

        pricing = Pricing(ctx=Context(datetime(2022, 3, 4, 16), db=db.wallet))
        assert (13 * 5.0, Decimal(13)) == pricing(asset)

        pricing = Pricing(ctx=Context(datetime(2022, 3, 5, 16), db=db.wallet))
        assert (7 * 6.0, Decimal(7)) == pricing(asset)

        pricing = Pricing(ctx=Context(datetime(2022, 3, 6, 16), db=db.wallet))
        assert (12 * 7.0, Decimal(12)) == pricing(asset)
