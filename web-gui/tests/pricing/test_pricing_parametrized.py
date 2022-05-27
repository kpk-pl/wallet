import pytest
import mongomock
import pymongo
import tests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from tests import mocks
from flaskr import model
from flaskr.pricing import Pricing, Context, ParametrizedQuoting
from decimal import Decimal
from bson import Decimal128, ObjectId


PRICING_SOURCE_CPI=dict(
    name = 'CPI',
    unit = '%',
    quotes = [
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


ASSET_INITIAL_PRICE = Decimal("1000")
ASSET_INITIAL_FIXED_INTEREST = Decimal("0.017")
ASSET_COMPOUND_FIXED_INTEREST = Decimal("0.01")
ASSET_COMPOUND_DERIVED_INTEREST = Decimal("0.052") # from 2021-10-05
ASSET_OPERATION_DATE = datetime(2020, 11, 1)


def setup_asset(operationDate = ASSET_OPERATION_DATE):
    asset = mocks.Asset(name="EDO", institution="Bank", category="Inflation Bonds", type="Bonds")

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
    return asset.commit()


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_before_first_operation():
    assetId = setup_asset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE - timedelta(days=1), db=db.wallet))
        assert (Decimal(0), Decimal(0)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_price_first_day():
    assetId = setup_asset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE, db=db.wallet))
        assert (ASSET_INITIAL_PRICE, Decimal(10)) == pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("daysIn", [1, 30, 365])
def test_price_fixed_pricing_linearly(daysIn):
    assetId = setup_asset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + timedelta(days=daysIn), db=db.wallet))
        value, quantity = pricing(asset)
        expectedPrice = ASSET_INITIAL_PRICE * (Decimal(1) + Decimal(daysIn) / Decimal(365) * ASSET_INITIAL_FIXED_INTEREST)
        assert value == expectedPrice
        assert quantity == Decimal(10)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_context_logic():
    assetId = setup_asset()

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
        assert pctx.partialMultiplier() == Decimal(1)
        assert pctx.timePoint == ASSET_OPERATION_DATE
        assert pctx.nextTimePoint == ASSET_OPERATION_DATE + relativedelta(years=1)
        assert pctx.interestIdx == 0
        assert pctx.fixedGrowth() == ASSET_INITIAL_FIXED_INTEREST
        assert pctx.derivedGrowth() is None

        pctx.advance()

        assert pctx.isPartial()
        assert pctx.partialMultiplier() == Decimal(1) / Decimal(365)
        assert pctx.timePoint == ASSET_OPERATION_DATE + relativedelta(years=1)
        assert pctx.interestIdx == 1
        assert pctx.fixedGrowth() == ASSET_COMPOUND_FIXED_INTEREST * Decimal(1) / Decimal(365)
        assert pctx.derivedQuoteTimestamp() == datetime(2021, 10, 1)
        assert pctx.derivedPercentageForTimestamp(datetime(2021, 10, 1)) == ASSET_COMPOUND_DERIVED_INTEREST
        assert pctx.derivedGrowth() == ASSET_COMPOUND_DERIVED_INTEREST * Decimal(1) / Decimal(365)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_key_points_beginning_of_next_period():
    assetId = setup_asset()

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

        totalGrowth = Decimal(1)
        assert keyPoints[0] == ParametrizedQuoting.KeyPoint(ASSET_OPERATION_DATE, totalGrowth)

        totalGrowth *= (Decimal(1) + ASSET_INITIAL_FIXED_INTEREST)
        assert keyPoints[1] == ParametrizedQuoting.KeyPoint(ASSET_OPERATION_DATE + relativedelta(years=1), totalGrowth)

        totalGrowth *= (Decimal(1) + (ASSET_COMPOUND_FIXED_INTEREST + ASSET_COMPOUND_DERIVED_INTEREST) / Decimal(365))
        assert keyPoints[2] == ParametrizedQuoting.KeyPoint(ASSET_OPERATION_DATE + relativedelta(years=1, days=1), totalGrowth)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("daysInCompound", [1, 30, 365])
def test_price_derived_pricing_linearily(daysInCompound):
    assetId = setup_asset()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        pricing = Pricing(ctx=Context(ASSET_OPERATION_DATE + relativedelta(years=1, days=daysInCompound), db=db.wallet))
        value, quantity = pricing(asset)

        priceAfterFirstYear = ASSET_INITIAL_PRICE * (Decimal(1) + ASSET_INITIAL_FIXED_INTEREST)
        periodPercent = (ASSET_COMPOUND_FIXED_INTEREST + ASSET_COMPOUND_DERIVED_INTEREST) * Decimal(daysInCompound) / Decimal(365)
        expectedPrice = priceAfterFirstYear * (Decimal(1) + periodPercent)

        assert value == expectedPrice
        assert quantity == Decimal(10)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_context_logic_when_missing_quoting_data():
    assetId = setup_asset()

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
        assert pctx.partialMultiplier() == Decimal(1) / Decimal(365)
        assert pctx.timePoint == ASSET_OPERATION_DATE + relativedelta(years=2)
        assert pctx.interestIdx == 1  # This does not increase because it's the last one
        assert pctx.derivedQuoteTimestamp() == datetime(2022, 10, 1)

        # There is not quote data for this timestamp
        assert pctx.derivedPercentageForTimestamp(datetime(2022, 10, 1)) is None


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_quoting_context_logic_when_quoting_data_was_not_updated_very_recently():
    operationDate = datetime(2021, 6, 1)
    assetId = setup_asset(operationDate)

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
        assert pctx.partialMultiplier() == Decimal(1) / Decimal(365)
        assert pctx.timePoint == operationDate + relativedelta(years=1)
        assert pctx.interestIdx == 1
        assert pctx.derivedQuoteTimestamp() == datetime(2022, 5, 1)

        # There is not quote data for 2022-05-01 but 2022-04-05 is close enough to be considered
        assert pctx.derivedPercentageForTimestamp(datetime(2022, 5, 1)) == Decimal("0.052")
