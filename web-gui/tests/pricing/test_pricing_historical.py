import pytest
import mongomock
import pymongo
import tests
from datetime import datetime
from tests import mocks
from flaskr import model
from flaskr.analyzers import Profits
from flaskr.pricing import HistoryPricing, Context
from decimal import Decimal as D
from bson import Decimal128, ObjectId


PRICING_SOURCE_ALPHA=dict(
    name = 'Alpha',
    unit = 'PLN',
    quotes = [
        (datetime(2022, 3, 9, 17), Decimal128("30")),
        (datetime(2022, 3, 10, 17), Decimal128("32")),
        (datetime(2022, 3, 11, 17), Decimal128("33")),
        (datetime(2022, 3, 14, 17), Decimal128("42"))
    ]
)


PRICING_SOURCE_USD=dict(
    name = 'USDPLN',
    quotes = [
        (datetime(2022, 3, 9, 17), Decimal128("4.1")),
        (datetime(2022, 3, 12, 17), Decimal128("4.4")),
        (datetime(2022, 3, 13, 17), Decimal128("4.2"))
    ]
)


def setup_alpha_pricing():
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


EXPECTED_8_15_TIMESCALE = [
    datetime(2022, 3, 8, 17),
    datetime(2022, 3, 9, 17),
    datetime(2022, 3, 10, 17),
    datetime(2022, 3, 11, 17),
    datetime(2022, 3, 12, 17),
    datetime(2022, 3, 13, 17),
    datetime(2022, 3, 14, 17),
    datetime(2022, 3, 15, 17)
]

@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_no_operations():
    asset = mocks.Asset(name="Test Asset", institution="Test", category="Directly quoted", type="ETF")
    asset.main_currency("PLN")
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        assert result.timescale == EXPECTED_8_15_TIMESCALE
        assert result.value == [D(0)]*8
        assert result.quantity == [D(0)]*8
        assert result.investedValue is None
        assert result.profit is None


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_default_currency_with_no_features():
    asset = mocks.Asset(name="Test Asset", institution="Test", category="Directly quoted", type="ETF")
    asset.pricing(setup_alpha_pricing())
    asset.main_currency("PLN")
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 1)
    asset.operation('BUY', datetime(2022, 3, 11, 17), 5, 10, 1)
    asset.operation('EARNING', datetime(2022, 3, 11, 18), None, 10, 5)
    asset.operation('RECEIVE', datetime(2022, 3, 12, 17), 1, 11, 1)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx)
        result = pricing(asset)

        assert result.timescale == EXPECTED_8_15_TIMESCALE
        assert result.value == [D(0), D(0), D(160), D(330), D(396), D(429), D(462), D(462)]
        assert result.quantity == [D(0), D(0), D(5), D(10), D(11), D(11), D(11), D(11)]
        assert result.investedValue is None
        assert result.profit is None


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_foreign_currency_with_no_features():
    asset = mocks.Asset(name="Test Asset", institution="Test", category="Directly quoted", type="ETF")
    asset.pricing(setup_alpha_pricing())
    asset.currency("USD", setup_usd())
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 1)
    asset.operation('BUY', datetime(2022, 3, 11, 17), 5, 10, 1)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx)
        result = pricing(asset)

        assert result.timescale == EXPECTED_8_15_TIMESCALE
        assert result.value == [D(0), D(0), D(160)*D("4.2"), D(330)*D("4.3"), D(360)*D("4.4"), D(390)*D("4.2"), \
                                D(420)*D("4.2"), D(420)*D("4.2")]
        assert result.quantity == [D(0), D(0), D(5), D(10), D(10), D(10), D(10), D(10)]
        assert result.investedValue is None
        assert result.profit is None


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_foreign_currency_deposit_with_no_features():
    asset = mocks.Asset(name="Test Asset", institution="Test", category="Directly quoted", type="Deposit")
    asset.currency("USD", setup_usd())
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 5, D(3.5))
    asset.operation('BUY', datetime(2022, 3, 11, 17), 5, 10, 5, D(3.5))
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx)
        result = pricing(asset)

        assert result.timescale == EXPECTED_8_15_TIMESCALE
        assert result.value == [D(0), D(0), D(5)*D("4.2"), D(10)*D("4.3"), D(10)*D("4.4"), D(10)*D("4.2"), \
                                D(10)*D("4.2"), D(10)*D("4.2")]
        assert result.quantity == [D(0), D(0), D(5), D(10), D(10), D(10), D(10), D(10)]
        assert result.investedValue is None
        assert result.profit is None


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_foreign_currency_with_all_features():
    asset = mocks.Asset(name="Test Asset", institution="Test", category="Directly quoted", type="ETF")
    asset.pricing(setup_alpha_pricing())
    asset.currency("USD", setup_usd())
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 140)
    asset.operation('BUY', datetime(2022, 3, 11, 17), 5, 10, 150)
    asset.operation('SELL', datetime(2022, 3, 13, 17), 4, 6, 140)
    asset.operation('SELL', datetime(2022, 3, 13, 18), 2, 4, 80)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx, features={"investedValue": True, "profit": True})
        result = pricing(asset, profitsInfo = Profits()(asset))

        assert result.timescale == EXPECTED_8_15_TIMESCALE
        assert result.value == [D(0), D(0), D(32*5)*D("4.2"), D(33*10)*D("4.3"), D(36*10)*D("4.4"), D(39*6)*D("4.2"), \
                                D(42*4)*D("4.2"), D(42*4)*D("4.2")]
        assert result.quantity == [D(0), D(0), D(5), D(10), D(10), D(6), D(4), D(4)]
        assert result.investedValue == [D(0), D(0), D(140), D(290), D(290), D(174), D(116), D(116)]
        assert result.profit == [D(0), D(0), D(0), D(0), D(0), D(24), D(46), D(46)]
