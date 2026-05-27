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


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_provisions_accumulate_step_by_step():
    """Each provision should land on the day of its operation and persist
    forward for every subsequent timescale point."""
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 1)
    asset['operations'][-1]['provision'] = D("0.5")
    asset.operation('BUY', datetime(2022, 3, 12, 17), 5, 10, 1)
    asset['operations'][-1]['provision'] = D("0.7")
    asset.operation('SELL', datetime(2022, 3, 14, 17), 3, 7, 1)
    asset['operations'][-1]['provision'] = D("0.3")
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # Days: 3/8, 3/9, 3/10, 3/11, 3/12, 3/13, 3/14, 3/15
        assert result.provision == [
            D(0), D(0),
            D("0.5"),                 # 3/10 BUY
            D("0.5"),                 # 3/11 (no change)
            D("0.5") + D("0.7"),      # 3/12 BUY
            D("1.2"),                 # 3/13 (no change)
            D("1.2") + D("0.3"),      # 3/14 SELL
            D("1.5"),                 # 3/15
        ]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_history_provisions_are_summed_as_entered():
    """Provisions and taxes are entered manually in the default (main)
    currency — even when the asset itself is denominated in a foreign
    currency.  HistoryPricing._getProvision therefore sums them AS-IS
    without applying currencyConversion."""
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing())
    asset.currency("USD", setup_usd())
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 1)
    asset['operations'][-1]['provision'] = D(10)   # already in PLN by convention
    asset['operations'][-1]['currencyConversion'] = D("4.2")
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # On/after 3/10 the provision timeline is the raw 10 PLN.
        # currencyConversion (4.2) does NOT apply to provisions.
        assert result.provision[2] == D(10)
        assert result.provision[-1] == D(10)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_operation_exactly_on_first_timescale_point_is_included():
    """An operation timestamped at startDate counts toward day 0 quantity."""
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 3, 8, 17), 5, 5, 1)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        assert result.quantity[0] == D(5)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_operation_exactly_on_final_timescale_point_is_included():
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 3, 15, 17), 5, 5, 1)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # All days before should be 0, and the very last day should reflect
        # the BUY (because op.date <= dateIdx is true on the last point).
        assert result.quantity == [D(0)] * 7 + [D(5)]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_operation_strictly_after_finalDate_is_excluded():
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 4, 1, 17), 5, 5, 1)  # after finalDate
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        assert result.quantity == [D(0)] * 8


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_operation_before_startDate_carries_quantity_from_day_zero():
    """If we bought a position prior to the visible window, the chart should
    start from that pre-existing quantity on day 0."""
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 2, 1, 12), 5, 5, 1)  # pre-window
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        assert result.quantity == [D(5)] * 8


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_investedValue_reflects_each_buy_and_sell():
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY',  datetime(2022, 3, 10, 17), 5, 5, 20)   # invest 20
    asset.operation('BUY',  datetime(2022, 3, 11, 17), 5, 10, 30)  # invest 50
    asset.operation('SELL', datetime(2022, 3, 13, 17), 4, 6, 50)   # avg 5, 50% sold → 25
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx, features={"investedValue": True})
        result = pricing(asset, profitsInfo=Profits()(asset))

        # 8 days: 3/8 3/9 3/10 3/11 3/12 3/13 3/14 3/15
        assert result.investedValue == [
            D(0), D(0),
            D(20),                 # after BUY 1
            D(50),                 # after BUY 2
            D(50),                 # idle
            D(30),                 # after SELL: 60% of 50
            D(30), D(30),
        ]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_investedValue_feature_without_profitsInfo_raises():
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 1)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx, features={"investedValue": True})
        with pytest.raises(RuntimeError):
            pricing(asset)  # no profitsInfo


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_profit_accumulates_only_on_realising_operations():
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY',     datetime(2022, 3, 10, 17), 5, 5, 4)         # invest 4
    asset.operation('EARNING', datetime(2022, 3, 11, 17), None, 5, 1)      # +1 profit
    asset.operation('SELL',    datetime(2022, 3, 14, 17), 1, 4, 3)         # avg 0.8, 1 sold → +2.2
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx, features={"profit": True})
        result = pricing(asset, profitsInfo=Profits()(asset))

        # 3/8: 0  3/9: 0  3/10: 0 (BUY)  3/11: +1 (EARNING)
        # 3/12-3/13: 1   3/14: 1+2.2 = 3.2   3/15: 3.2
        assert result.profit == [
            D(0), D(0), D(0),
            D(1), D(1), D(1),
            D("3.2"), D("3.2"),
        ]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_profit_feature_without_profitsInfo_raises():
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 1)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        pricing = HistoryPricing(ctx=ctx, features={"profit": True})
        with pytest.raises(RuntimeError):
            pricing(asset)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_deposit_in_default_currency_value_equals_quantity():
    asset = mocks.Asset(name="A", institution="T", category="C", type="Deposit")
    asset.main_currency("PLN")
    asset.operation('BUY',     datetime(2022, 3, 10, 17), 100, 100, 100)
    asset.operation('BUY',     datetime(2022, 3, 12, 17), 50,  150, 50)
    asset.operation('EARNING', datetime(2022, 3, 14, 17), 10, 160, 10)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        ctx = Context(startDate=datetime(2022, 3, 8, 17),
                      finalDate=datetime(2022, 3, 15, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # Value == quantity for default-currency deposits.
        assert result.value == result.quantity
        assert result.value == [
            D(0), D(0), D(100), D(100), D(150), D(150), D(160), D(160),
        ]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_quote_source_with_no_data_before_first_op_uses_first_known_quote():
    """The Alpha source starts on 3/9 17:00.  An operation on 3/10 with a
    BUY price doesn't have a pre-op quote.  HistoryPricing should fall
    back to the first known quote (interp's leftFill=None behaviour)."""
    asset = mocks.Asset(name="A", institution="T", category="C", type="ETF")
    asset.pricing(setup_alpha_pricing()).main_currency("PLN")
    asset.operation('BUY', datetime(2022, 3, 10, 17), 5, 5, 1)
    asset = asset.model()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        # window starts before the first quote
        ctx = Context(startDate=datetime(2022, 3, 6, 17),
                      finalDate=datetime(2022, 3, 11, 17),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # The quote series is back-filled with the earliest known quote (30)
        # for any timescale point before the first quote (3/9 17:00).
        # Quantity drives value: 0 before 3/10, 5 on 3/10 and after.
        # On 3/10 17:00 the interpolated quote = 32, on 3/11 = 33.
        assert result.quantity == [D(0)] * 4 + [D(5), D(5)]
        assert result.value[4] == D(5) * D(32)   # 3/10
        assert result.value[5] == D(5) * D(33)   # 3/11


def _setup_simple_fixed_bond():
    """One-year bond, 10% fixed, accumulating, paid 1000 PLN on day 0."""
    asset = mocks.Asset(name="Bond", institution="Bank",
                        category="Inflation Bonds", type="Bond")
    asset.main_currency("PLN")
    asset._data['pricing'] = dict(
        length=dict(count=1, name="year"),
        profitDistribution="accumulating",
        interest=[dict(fixed={'percentage': Decimal128("0.10")})],
    )
    asset.operation('BUY', datetime(2022, 1, 1), 10, 10, 1000)
    return asset


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_bond_value_grows_linearly_first_year():
    """A fixed-rate accumulating bond should grow ~linearly within the
    first year."""
    assetId = _setup_simple_fixed_bond().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(startDate=datetime(2022, 1, 1),
                      finalDate=datetime(2022, 7, 1),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # Sanity: value strictly non-decreasing
        for prev, nxt in zip(result.value, result.value[1:]):
            assert nxt >= prev, f"Value decreased: {prev} → {nxt}"
        # End-of-period value: 1000 * (1 + 0.10 * 181/365); discretisation
        # makes it approximate, but must be in the 1000 .. 1100 band.
        assert D(1000) <= result.value[-1] <= D(1100)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_bond_value_zero_before_buy_date():
    """Days before the BUY date must show zero value."""
    assetId = _setup_simple_fixed_bond().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(startDate=datetime(2021, 11, 1),
                      finalDate=datetime(2022, 1, 5),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        for i, date in enumerate(result.timescale):
            if date < datetime(2022, 1, 1):
                assert result.value[i] == D(0), (
                    f"Bond had non-zero value {result.value[i]} on {date} "
                    f"before the BUY"
                )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_value_at_buy_date_equals_principal():
    """Regression: when the chart's startDate aligns with the BUY date, day
    0 used to show 0 instead of the bond principal because
    `_priceAssetByInterest` passes `leftFill=0.0` to `interp` and a bug in
    `interp` was overriding the exact-match data point with `leftFill`.  The
    `interp` fix resolves this — locked in here so a regression to either
    side reopens the issue."""
    assetId = _setup_simple_fixed_bond().commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        # startDate lands EXACTLY on the BUY date at the same time-of-day
        # so the timescale contains the BUY timestamp.
        ctx = Context(startDate=datetime(2022, 1, 1),
                      finalDate=datetime(2022, 1, 5),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # We bought a 1000 PLN bond on 2022-01-01 — the chart starts at 1000.
        assert result.value[0] == D(1000)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_bond_sell_reduces_position_value():
    """After a partial SELL, future value should reflect the remaining
    quantity only."""
    asset = _setup_simple_fixed_bond()
    asset.operation('SELL', datetime(2022, 4, 1), 4, 6, 400)
    assetId = asset.commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(startDate=datetime(2022, 1, 1),
                      finalDate=datetime(2022, 7, 1),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        post_sell_idx = next(
            i for i, d in enumerate(result.timescale) if d > datetime(2022, 4, 1)
        )
        post_sell_value = result.value[post_sell_idx]
        # 60% of position left → value ~60% of a no-sell baseline.
        asset_no_sell = _setup_simple_fixed_bond()
        no_sell_id = asset_no_sell.commit()
        dbAsset2 = db.wallet.assets.find_one({'_id': no_sell_id})
        asset2 = model.Asset(**dbAsset2)
        result2 = HistoryPricing(ctx=ctx)(asset2)

        baseline = result2.value[post_sell_idx]
        assert abs(post_sell_value - baseline * D("0.6")) < D("0.01")


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_sell_spans_multiple_open_positions():
    """A SELL whose quantity exceeds the first BUY's lot should consume
    FIFO from the next open position, leaving any later BUYs untouched.

    Regression for the SELL match loop in _priceAssetByInterest: after the
    early-break fix, behaviour for a SELL that fully satisfies within the
    first few positions must match what we'd get walking every one.

    All BUYs are placed on the same instant so each open position has the
    same multiplier on any future day — that lets us predict an exact ratio
    against a no-sell baseline (otherwise the lot-by-lot accumulation
    differences would muddy the comparison)."""
    sameDate = datetime(2022, 1, 1)
    asset = mocks.Asset(name="Bond", institution="Bank",
                        category="Inflation Bonds", type="Bond")
    asset.main_currency("PLN")
    asset._data['pricing'] = dict(
        length=dict(count=1, name="year"),
        profitDistribution="accumulating",
        interest=[dict(fixed={'percentage': Decimal128("0.10")})],
    )
    asset.operation('BUY',  sameDate, 10, 10, 1000)
    asset.operation('BUY',  sameDate, 10, 20, 1000)
    asset.operation('BUY',  sameDate, 10, 30, 1000)
    # SELL 15 — consumes all of position 1 (10) + 5 from position 2.
    # Position 3 must be left untouched (the early-break path).
    asset.operation('SELL', datetime(2022, 4, 1), 15, 15, 1500)
    assetId = asset.commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(startDate=datetime(2022, 1, 1),
                      finalDate=datetime(2022, 7, 1),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # Baseline: same three BUYs at the same instant, no SELL.
        asset_no_sell = mocks.Asset(name="Bond2", institution="Bank",
                                    category="Inflation Bonds", type="Bond")
        asset_no_sell.main_currency("PLN")
        asset_no_sell._data['pricing'] = dict(
            length=dict(count=1, name="year"),
            profitDistribution="accumulating",
            interest=[dict(fixed={'percentage': Decimal128("0.10")})],
        )
        asset_no_sell.operation('BUY', sameDate, 10, 10, 1000)
        asset_no_sell.operation('BUY', sameDate, 10, 20, 1000)
        asset_no_sell.operation('BUY', sameDate, 10, 30, 1000)
        no_sell_id = asset_no_sell.commit()
        dbAsset2 = db.wallet.assets.find_one({'_id': no_sell_id})
        asset2 = model.Asset(**dbAsset2)
        result_no_sell = HistoryPricing(ctx=ctx)(asset2)

        post_sell_idx = next(
            i for i, d in enumerate(result.timescale) if d > datetime(2022, 4, 1)
        )
        # Remaining qty 15 / total 30 → exactly 50 % of baseline.
        baseline = result_no_sell.value[post_sell_idx]
        post_sell_value = result.value[post_sell_idx]
        assert abs(post_sell_value - baseline * D("0.5")) < D("0.01"), (
            f"Expected ~50% of baseline ({baseline*D('0.5')}); got {post_sell_value}"
        )


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_parametrized_with_two_orderIds_sums_independently():
    """Two BUYs with distinct orderIds (separate batches) should each grow
    independently and the timeline value is the sum."""
    asset = mocks.Asset(name="Bond", institution="Bank",
                        category="Inflation Bonds", type="Bond")
    asset.main_currency("PLN")
    asset.hasOrderIds()
    asset._data['pricing'] = dict(
        length=dict(count=1, name="year"),
        profitDistribution="accumulating",
        interest=[dict(fixed={'percentage': Decimal128("0.10")})],
    )
    asset.operation('BUY', datetime(2022, 1, 1), 10, 10, 1000, orderId="A")
    asset.operation('BUY', datetime(2022, 1, 1), 5,  15, 500,  orderId="B")
    assetId = asset.commit()

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': assetId})
        asset = model.Asset(**dbAsset)

        ctx = Context(startDate=datetime(2022, 1, 1),
                      finalDate=datetime(2022, 6, 30),
                      db=db.wallet)
        result = HistoryPricing(ctx=ctx)(asset)

        # A few days after the BUY, both positions accruing ~the same %,
        # the value should be ≈ 1500 * (1 + small).
        idx = next(i for i, d in enumerate(result.timescale) if d > datetime(2022, 1, 5))
        assert D(1500) <= result.value[idx] <= D(1510)


def test_parametrized_sell_before_buy_is_rejected_by_model():
    """Storage order = date order is now an Asset-model invariant. A SELL
    stored before its matching BUY (the old Bug 4 state) cannot be loaded at
    all — Pydantic raises ValidationError before any pricing engine sees it.

    This replaces an earlier xfail test that bypassed validation and showed
    HistoryPricing silently dropping the out-of-order SELL."""
    from pydantic import ValidationError

    pricingDoc = dict(
        length=dict(count=1, name="year"),
        profitDistribution="accumulating",
        interest=[dict(fixed={'percentage': Decimal128("0.10")})],
    )
    operations = [
        dict(date=datetime(2022, 4, 1), type='SELL',
             price=D(400), quantity=D(4), finalQuantity=D(6),
             currencyConversion=D(1)),
        dict(date=datetime(2022, 1, 1), type='BUY',
             price=D(1000), quantity=D(10), finalQuantity=D(10),
             currencyConversion=D(1)),
    ]
    raw = dict(
        _id=model.PyObjectId(),
        name="Bond", institution="Bank", category="Inflation Bonds",
        type="Bond", currency=dict(name="PLN"),
        pricing=pricingDoc, operations=operations,
    )
    with pytest.raises(ValidationError) as exc_info:
        model.Asset(**raw)
    assert "ascending" in str(exc_info.value)
