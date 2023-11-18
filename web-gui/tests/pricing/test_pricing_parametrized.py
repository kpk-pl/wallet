import pytest
import mongomock
import pymongo
import tests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from tests import mocks
from flaskr import model
from flaskr.pricing import Pricing, Context, ParametrizedQuoting
from decimal import Decimal as D, localcontext
from bson import Decimal128, ObjectId


PRICING_SOURCE_CPI=dict(
    name = 'CPI',
    unit = '%',
    quotes = [
        (datetime(2020, 10, 5), Decimal128("0.02")),
        (datetime(2020, 11, 5), Decimal128("0.04")),
        (datetime(2020, 12, 5), Decimal128("0.05")),
        (datetime(2021, 1, 5), Decimal128("0.1")),
        (datetime(2021, 2, 5), Decimal128("0.25")),
        (datetime(2021, 3, 5), Decimal128("0.3")),
        (datetime(2021, 4, 5), Decimal128("0.7")),
        (datetime(2021, 5, 5), Decimal128("1.2")),
        (datetime(2021, 6, 5), Decimal128("1.8")),
        (datetime(2021, 7, 5), Decimal128("2.7")),
        (datetime(2021, 8, 5), Decimal128("3.5")),
        (datetime(2021, 9, 5), Decimal128("3.8")),
        (datetime(2021, 10, 5), Decimal128("5.2")),
        (datetime(2021, 11, 5), Decimal128("9.4")),
        (datetime(2021, 12, 5), Decimal128("9.5")),
        (datetime(2022, 1, 5), Decimal128("10.2")),
        (datetime(2022, 2, 5), Decimal128("6.5")),
        (datetime(2022, 3, 5), Decimal128("5.5")),
        (datetime(2022, 4, 5), Decimal128("5.2")),
    ]
)

def setup_cpi():
    source = mocks.PricingSource()
    source.name(PRICING_SOURCE_CPI['name'])
    source.unit(PRICING_SOURCE_CPI['unit'])
    for ts, q in PRICING_SOURCE_CPI['quotes']:
        source.quote(ts, q)
    return source.commit()


ASSET_INITIAL_PRICE = D("1000")
ASSET_INITIAL_FIXED_INTEREST = D("0.017")
ASSET_COMPOUND_FIXED_INTEREST = D("0.01")
ASSET_COMPOUND_DERIVED_INTEREST = D("0.052") # from 2021-10-05
ASSET_OPERATION_DATE = datetime(2020, 11, 1)


def setup_asset(operationDate = ASSET_OPERATION_DATE):
    asset = mocks.Asset(name="EDO", institution="Bank", category="Inflation Bonds", type="Bond")

    asset.main_currency("PLN")
    asset._data['pricing'] = dict(
        length = dict(count = 10, name = "year"),
        profitDistribution = "accumulating",
        interest = [
            dict(
                fixed = {'percentage': Decimal128(str(ASSET_INITIAL_FIXED_INTEREST))}
            ),
            dict(
                fixed = {'percentage': Decimal128(str(ASSET_COMPOUND_FIXED_INTEREST))},
                derived = dict(
                    quoteId = setup_cpi(),
                    sample = dict(
                        interval = "month",
                        intervalOffset = -1,
                        choose = "last",
                        clampBelow = Decimal128("0"),
                        multiplier = Decimal128("0.01")
                    )
                )
            )
        ]
    )

    asset.operation('BUY', operationDate, 10, 10, float(ASSET_INITIAL_PRICE))
    return asset


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_before_first_operation():
    assetId = setup_asset().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE - timedelta(days=1), db=db.wallet))
        assert (D(0), D(0)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_first_day():
    assetId = setup_asset().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE, db=db.wallet))
        assert (ASSET_INITIAL_PRICE, D(10)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("daysIn", [1, 30, 365])
def test_price_fixed_pricing_linearly(daysIn):
    assetId = setup_asset().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + timedelta(days=daysIn), db=db.wallet))
        value, quantity = pricing(asset)
        expectedPrice = ASSET_INITIAL_PRICE * (D(1) + D(daysIn) / D(365) * ASSET_INITIAL_FIXED_INTEREST)
        assert value == expectedPrice
        assert quantity == D(10)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_fixed_future_sell_does_not_influence_current_price():
    sellDate = ASSET_OPERATION_DATE + timedelta(days=31)
    assetId = setup_asset().operation('SELL', sellDate, 10, 0, float(ASSET_INITIAL_PRICE)).commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + timedelta(days=30), db=db.wallet))
        value, quantity = pricing(asset)
        expectedPrice = ASSET_INITIAL_PRICE * (D(1) + D(30) / D(365) * ASSET_INITIAL_FIXED_INTEREST)
        assert value == expectedPrice
        assert quantity == D(10)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("sellQuantity", [1, 5, 10])
def test_price_fixed_after_sell_operation(sellQuantity):
    sellDate = ASSET_OPERATION_DATE + timedelta(days=15)
    assetId = setup_asset().operation('SELL', sellDate, sellQuantity, 10-sellQuantity, float(ASSET_INITIAL_PRICE)).commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + timedelta(days=30), db=db.wallet))
        value, quantity = pricing(asset)
        expectedPrice = ASSET_INITIAL_PRICE * (D(1) + D(30) / D(365) * ASSET_INITIAL_FIXED_INTEREST) * D(10 - sellQuantity) / D(10)
        assert value == expectedPrice
        assert quantity == D(10 - sellQuantity)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_context_logic():
    assetId = setup_asset().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(finalDate=ASSET_OPERATION_DATE + relativedelta(years=1, days=1),
                      db=db.wallet,
                      interpolate=False,
                      keepOnlyFinalQuote=False)

        quoting = ParametrizedQuoting(asset.pricing, asset.operations[0].date, ctx)
        pctx = ParametrizedQuoting.Context(quoting)

        assert not pctx.isPartial()
        assert pctx.partialMultiplier() == D(1)
        assert pctx.timePoint == ASSET_OPERATION_DATE
        assert pctx.nextTimePoint == ASSET_OPERATION_DATE + relativedelta(years=1)
        assert pctx.interestIdx == 0
        assert pctx.fixedGrowth() == ASSET_INITIAL_FIXED_INTEREST
        assert pctx.derivedGrowth() is None

        pctx.advance()

        assert pctx.isPartial()
        assert pctx.partialMultiplier() == D(1) / D(365)
        assert pctx.timePoint == ASSET_OPERATION_DATE + relativedelta(years=1)
        assert pctx.interestIdx == 1
        assert pctx.fixedGrowth() == ASSET_COMPOUND_FIXED_INTEREST * D(1) / D(365)
        assert pctx.derivedQuoteTimestamp() == datetime(2021, 10, 1)
        assert pctx.derivedPercentageForTimestamp(datetime(2021, 10, 1)) == ASSET_COMPOUND_DERIVED_INTEREST
        assert pctx.derivedGrowth() == ASSET_COMPOUND_DERIVED_INTEREST * D(1) / D(365)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_key_points_beginning_of_next_period():
    assetId = setup_asset().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(finalDate=ASSET_OPERATION_DATE + relativedelta(years=1, days=1),
                      db=db.wallet,
                      interpolate=False,
                      keepOnlyFinalQuote=False)

        quoting = ParametrizedQuoting(asset.pricing, asset.operations[0].date, ctx)
        keyPoints = quoting.getKeyPoints()
        assert len(keyPoints) == 3

        totalGrowth = D(1)
        assert keyPoints[0] == ParametrizedQuoting.KeyPoint(ASSET_OPERATION_DATE, totalGrowth)

        totalGrowth *= (D(1) + ASSET_INITIAL_FIXED_INTEREST)
        assert keyPoints[1] == ParametrizedQuoting.KeyPoint(ASSET_OPERATION_DATE + relativedelta(years=1), totalGrowth)

        totalGrowth *= (D(1) + (ASSET_COMPOUND_FIXED_INTEREST + ASSET_COMPOUND_DERIVED_INTEREST) / D(365))
        assert keyPoints[2] == ParametrizedQuoting.KeyPoint(ASSET_OPERATION_DATE + relativedelta(years=1, days=1), totalGrowth)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("daysInCompound", [1, 30, 365])
def test_price_derived_pricing_linearily(daysInCompound):
    assetId = setup_asset().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + relativedelta(years=1, days=daysInCompound), db=db.wallet))
        value, quantity = pricing(asset)

        priceAfterFirstYear = ASSET_INITIAL_PRICE * (D(1) + ASSET_INITIAL_FIXED_INTEREST)
        periodPercent = (ASSET_COMPOUND_FIXED_INTEREST + ASSET_COMPOUND_DERIVED_INTEREST) * D(daysInCompound) / D(365)
        expectedPrice = priceAfterFirstYear * (D(1) + periodPercent)

        assert value == expectedPrice
        assert quantity == D(10)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_context_logic_when_missing_quoting_data():
    assetId = setup_asset().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(finalDate=ASSET_OPERATION_DATE + relativedelta(years=2, days=1),
                      db=db.wallet,
                      interpolate=False,
                      keepOnlyFinalQuote=False)

        quoting = ParametrizedQuoting(asset.pricing, asset.operations[0].date, ctx)
        pctx = ParametrizedQuoting.Context(quoting)

        # Skip first 2 years for which we do have proper data
        pctx.advance()
        pctx.advance()

        assert pctx.isPartial()
        assert pctx.partialMultiplier() == D(1) / D(365)
        assert pctx.timePoint == ASSET_OPERATION_DATE + relativedelta(years=2)
        assert pctx.interestIdx == 1  # This does not increase because it's the last one
        assert pctx.derivedQuoteTimestamp() == datetime(2022, 10, 1)

        # There is not quote data for this timestamp
        assert pctx.derivedPercentageForTimestamp(datetime(2022, 10, 1)) is None


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_context_logic_when_quoting_data_was_not_updated_very_recently():
    operationDate = datetime(2021, 6, 1)
    assetId = setup_asset(operationDate).commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(finalDate=operationDate + relativedelta(years=1, days=1),
                      db=db.wallet,
                      interpolate=False,
                      keepOnlyFinalQuote=False)

        quoting = ParametrizedQuoting(asset.pricing, asset.operations[0].date, ctx)
        pctx = ParametrizedQuoting.Context(quoting)

        # Skip first year for which we do have proper data
        pctx.advance()

        assert pctx.isPartial()
        assert pctx.partialMultiplier() == D(1) / D(365)
        assert pctx.timePoint == operationDate + relativedelta(years=1)
        assert pctx.interestIdx == 1
        assert pctx.derivedQuoteTimestamp() == datetime(2022, 5, 1)

        # There is not quote data for 2022-05-01 but 2022-04-05 is close enough to be considered
        assert pctx.derivedPercentageForTimestamp(datetime(2022, 5, 1)) == D("0.052")


def setup_distributing_asset(operationDate = ASSET_OPERATION_DATE):
    asset = mocks.Asset(name="ROR", institution="Bank", category="Inflation Bonds", type="Bond")

    asset.main_currency("PLN")
    asset._data['pricing'] = dict(
        length = dict(count = 12, name = "month"),
        profitDistribution = "distributing",
        interest = [
            dict(
                derived = dict(
                    quoteId = setup_cpi(),
                    sample = dict(
                        interval = "month",
                        intervalOffset = -1,
                        choose = "last",
                        multiplier = Decimal128("0.01")
                    )
                )
            )
        ]
    )

    asset.operation('BUY', operationDate, 10, 10, float(ASSET_INITIAL_PRICE))
    return asset.commit()


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("params", [
    (0, D(0)), # The day of creation there is no profit
    (1, D("0.02") / 100 / 365), # First day, 1/365 of yield, CPI date 2020-10-05, yield 0.02
    (29, D("0.02") * 29 / 100 / 365), # 29th day, still should be the same month so the same yield 0.02, last day of the month in the first period
    (30, D(0)), # 30th day which is the end of the month. Profit should be distributed and not reflected with the price
    (45, D("0.04") * 15 / 100 / 365), # 15 days of December at 0.04 yield from 2020-11-05 in the current period
    (70, D("0.05") * 9 / 100 / 365), # January yield is 0.05 from 2020-12-05 and this is third pricing period
])
def test_price_distributing(params):
    daysIn, expectedMultiplier = params
    assetId = setup_distributing_asset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + timedelta(days=daysIn), db=db.wallet))
        value, quantity = pricing(asset)
        expectedPrice = ASSET_INITIAL_PRICE * (D(1) + expectedMultiplier)

        with localcontext() as ctx:
            assert value is not None
            ctx.prec = 20
            assert +value == +expectedPrice

        assert quantity == D(10)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_stops_after_investment_period():
    assetId = setup_distributing_asset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + relativedelta(years=1), db=db.wallet))
        finalValue, _ = pricing(asset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + relativedelta(years=1, days=1), db=db.wallet))
        valueAfter, _ = pricing(asset)

        assert finalValue == valueAfter
