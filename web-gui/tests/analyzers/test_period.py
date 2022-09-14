import pytest
import mongomock
import pymongo
import tests
from datetime import datetime
from tests import mocks
from flaskr.model import Asset, AssetType, AssetCurrency, PyObjectId, AssetOperation, AssetOperationType, AssetPricingQuotes
from flaskr.analyzers import Profits, Period
from decimal import Decimal as D
from bson import Decimal128, ObjectId


DATE_INITIAL=datetime(2020, 1, 1)
DATE_FINAL=datetime(2021, 1, 1)
PRICING_QUOTE_ID=ObjectId()
PRICING_SOURCE_ALPHA=dict(
    name = 'Alpha',
    unit = 'PLN',
    quotes = [
        (datetime(2020, 1, 1), Decimal128("10")),
        (datetime(2020, 1, 10), Decimal128("10")),
        (datetime(2020, 1, 12), Decimal128("11")),
        (datetime(2020, 1, 13), Decimal128("12")),
        (datetime(2020, 2, 1), Decimal128("15")),
        (datetime(2020, 2, 2), Decimal128("15"))
    ]
)


def setup_pricing_alpha():
    source = mocks.PricingSource(PRICING_QUOTE_ID)
    source.name(PRICING_SOURCE_ALPHA['name'])
    source.unit(PRICING_SOURCE_ALPHA['unit'])
    for ts, q in PRICING_SOURCE_ALPHA['quotes']:
        source.quote(ts, q)
    return source.commit()


def makeAsset():
    return Asset(
        _id = PyObjectId(),
        name = "Test asset",
        currency = AssetCurrency(
            name = "TST"
        ),
        institution = "Test",
        type = AssetType.etf,
        category = "Testing",
        pricing = AssetPricingQuotes(
            quoteId = PRICING_QUOTE_ID
        ),
        operations = [
            AssetOperation(
                date = datetime(2020, 1, 10),
                type = AssetOperationType.buy,
                price = D(100),
                quantity = D(10),
                finalQuantity = D(10)
            ),
            AssetOperation(
                date = datetime(2020, 1, 12),
                type = AssetOperationType.buy,
                price = D(110),
                quantity = D(10),
                finalQuantity = D(20)
            ),
            AssetOperation(
                date = datetime(2020, 2, 1),
                type = AssetOperationType.sell,
                price = D(80),
                quantity = D(5),
                finalQuantity = D(15)
            )
        ]
    )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_without_operations():
    asset = makeAsset()
    asset.operations = []

    period = Period(DATE_INITIAL, DATE_FINAL)
    result = period(asset, Profits()(asset))

    assert not result.error
    assert result.initialNetValue == D(0)
    assert result.initialQuantity == D(0)
    assert result.finalNetValue == D(0)
    assert result.finalQuantity == D(0)
    assert result.profits.totalNetProfit == D(0)
    assert result.profits.netProfit == D(0)
    assert result.profits.provisions == D(0)
    assert result.profits.isZero()


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_timerange_not_covering_any_operation():
    asset = makeAsset()

    period = Period(DATE_INITIAL, datetime(2020, 1, 2))
    result = period(asset, Profits()(asset))

    assert not result.error
    assert result.initialNetValue == D(0)
    assert result.initialQuantity == D(0)
    assert result.finalNetValue == D(0)
    assert result.finalQuantity == D(0)
    assert result.profits.totalNetProfit == D(0)
    assert result.profits.netProfit == D(0)
    assert result.profits.provisions == D(0)
    assert result.profits.isZero()


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_no_pricing_data():
    asset = makeAsset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        period = Period(DATE_INITIAL, DATE_FINAL, db=db.wallet)
        result = period(asset, Profits()(asset))

    assert result.error


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_only_buys():
    setup_pricing_alpha()
    asset = makeAsset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        period = Period(DATE_INITIAL, datetime(2020, 1, 13), db=db.wallet)
        result = period(asset, Profits()(asset))

    assert not result.error
    assert result.initialNetValue == D(0)
    assert result.initialQuantity == D(0)
    assert result.finalNetValue == D(240)
    assert result.finalQuantity == D(20)
    assert result.profits.totalNetProfit == D(30)
    assert result.profits.netProfit == D(0)
    assert result.profits.provisions == D(0)
    assert not result.profits.isZero()


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_buys_and_sells():
    setup_pricing_alpha()
    asset = makeAsset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        period = Period(DATE_INITIAL, datetime(2020, 2, 2), db=db.wallet)
        result = period(asset, Profits()(asset))

    assert not result.error
    assert result.initialNetValue == D(0)
    assert result.initialQuantity == D(0)
    assert result.finalNetValue == D(15*15)
    assert result.finalQuantity == D(15)
    # 10.5 - average buy price
    assert result.profits.netProfit == D(80) - D("10.5") * D(5)
    assert result.profits.totalNetProfit == D(80) - D("10.5") * D(5) + (D(15)-D("10.5")) * D(15)
    assert result.profits.provisions == D(0)
    assert not result.profits.isZero()


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_provisions_are_all_in_the_requested_timerange():
    setup_pricing_alpha()
    asset = makeAsset()
    asset.operations = [
            AssetOperation(
                date = datetime(2019, 12, 10),
                type = AssetOperationType.buy,
                price = D(100),
                quantity = D(10),
                finalQuantity = D(10),
                provision = D(5)
            ),
            AssetOperation(
                date = datetime(2020, 1, 12),
                type = AssetOperationType.buy,
                price = D(110),
                quantity = D(10),
                finalQuantity = D(20),
                provision = D(7)
            ),
            AssetOperation(
                date = datetime(2020, 1, 15),
                type = AssetOperationType.sell,
                price = D(120),
                quantity = D(10),
                finalQuantity = D(10),
                provision = D(6)
            ),
            AssetOperation(
                date = datetime(2020, 2, 12),
                type = AssetOperationType.buy,
                price = D(100),
                quantity = D(10),
                finalQuantity = D(20),
                provision = D(10)
            )
        ]

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        period = Period(DATE_INITIAL, datetime(2020, 2, 1), db=db.wallet)
        result = period(asset, Profits()(asset))

    assert not result.error
    assert result.initialNetValue == D(100)
    assert result.initialQuantity == D(10)
    assert result.finalNetValue == D(150)
    assert result.finalQuantity == D(10)
    # 10.5 - average buy price, 12 - sell price, 15 - current price
    assert result.profits.netProfit == D("1.5") * D(10)
    assert result.profits.totalNetProfit == D("1.5") * D(10) + D("4.5") * D(10)
    assert result.profits.provisions == D(7) + D(6)
    assert not result.profits.isZero()
