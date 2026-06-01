import pytest
from flaskr.model import Asset, AssetType, AssetCurrency, PyObjectId, AssetOperation, AssetOperationType
from flaskr.analyzers import Profits
from decimal import Decimal as D
from datetime import datetime


def makeAsset(type:AssetType=AssetType.equity, currency_name:str="TST"):
    return Asset(
        _id = PyObjectId(),
        name = "Test asset",
        currency = AssetCurrency(
            name = currency_name
        ),
        institution = "Test",
        type = type,
        category = "Testing"
    )


def _op(type, date, price, quantity, finalQuantity, provision=None, currencyConversion=None, orderId=None):
    kwargs = dict(
        date=date,
        type=type,
        price=D(str(price)),
        finalQuantity=D(str(finalQuantity)),
    )
    if quantity is not None:
        kwargs["quantity"] = D(str(quantity))
    if provision is not None:
        kwargs["provision"] = D(str(provision))
    if currencyConversion is not None:
        kwargs["currencyConversion"] = D(str(currencyConversion))
    if orderId is not None:
        kwargs["orderId"] = orderId
    return AssetOperation(**kwargs)


def test_asset_with_no_operations():
    result = Profits()(makeAsset(AssetType.deposit))

    assert result.investmentStart is None
    assert result.holdingDays is None
    assert len(result.breakdown) == 0
    assert result.profit == D(0)
    assert result.netProfit == D(0)
    assert result.provisions == D(0)
    assert result.avgPrice is None
    assert result.avgNetPrice is None
    assert result.quantity == D(0)


def test_equity_default_currency():
    operations = [
        AssetOperation(
            date = datetime(2020, 1, 1),
            type = AssetOperationType.buy,
            price = D(50),
            quantity = D(25),
            finalQuantity = D(25)
        ),
        AssetOperation(
            date = datetime(2020, 1, 2),
            type = AssetOperationType.buy,
            price = D(100),
            quantity = D(25),
            finalQuantity = D(50),
            provision = D(1)
        ),
        AssetOperation(
            date = datetime(2020, 2, 1),
            type = AssetOperationType.sell,
            price = D(50),
            quantity = D(10),
            finalQuantity = D(40),
            provision = D("2.5")
        ),
        AssetOperation(
            date = datetime(2020, 2, 5),
            type = AssetOperationType.earning,  # this is equivalent to a distributed dividend
            price = D("5.5"),
            finalQuantity = D(40),
            provision = D("0.2")
        ),
        AssetOperation(
            date = datetime(2020, 3, 1),
            type = AssetOperationType.receive,  # this is equivalent to a being granted a free stocks
            price = D(160),
            quantity = D(40),
            finalQuantity = D(80),
            provision = D(40)
        ),
        AssetOperation(
            date = datetime(2020, 4, 1),
            type = AssetOperationType.sell,  # partial sell after RECEIVE and EARNING ops
            price = D(56),  # unit price will be 2.8
            quantity = D(20),
            finalQuantity = D(60),
            provision = D("1.2")
        )
    ]
    breakdowns = [
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(2),
            avgNetPrice = D(2),
            netInvestment = D(50),
            quantity = D(25),
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(3),
            avgNetPrice = D(3),
            netInvestment = D(150),
            quantity = D(50),
        ),
        Profits.Result.Breakdown(
            profit = D(30),  # FIFO: closes 10 of the oldest BUY (unit 2), 50 - 2*10 = 30
            netProfit = D(30),
            provisions = D("2.5"),  # only the SELL provision; the oldest BUY carried no provision
            avgPrice = D("3.25"),  # remaining 15@2 + 25@4 = 130 over 40
            avgNetPrice = D("3.25"),
            netInvestment = D(130),
            quantity = D(40),
        ),
        Profits.Result.Breakdown(
            profit = D("5.5"),
            netProfit = D("5.5"),
            provisions = D("0.2"),
            avgPrice = D("3.25"),
            avgNetPrice = D("3.25"),
            netInvestment = D(130),
            quantity = D(40),
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D("1.625"),  # RECEIVE adds 40 free units: 130 cost basis over 80
            avgNetPrice = D("1.625"),
            netInvestment = D(130),
            quantity = D(80),
        ),
        Profits.Result.Breakdown(
            profit = D(6),  # FIFO: 15 left of first BUY (unit 2) + 5 of second BUY (unit 4) = 50 cost; 56 - 50
            netProfit = D(6),
            provisions = D("1.4"),  # 1.2 from SELL + 0.2 drawn from the second BUY's provision (1 * 5/25)
            avgPrice = D(80) / D(60),  # remaining 20@4 + 40@0 = 80 over 60
            avgNetPrice = D(80) / D(60),
            netInvestment = D(80),
            quantity = D(60),
        )
    ]
    analyzer = Profits(currentDate = datetime(2020, 12, 31))
    asset = makeAsset(AssetType.equity)

    def checkToOperation(opNumber, profit, provisions, avgPrice, quantity):
        asset.operations = operations[:opNumber+1]
        result = analyzer(asset)
        assert result.investmentStart == datetime(2020, 1, 1)
        assert result.holdingDays == 365
        assert result.profit == profit
        assert result.netProfit == profit
        assert result.provisions == provisions
        assert result.avgPrice == avgPrice
        assert result.avgNetPrice is not None
        assert result.avgNetPrice == avgPrice
        assert result.quantity == quantity
        # netInvestment is the exact residual cost basis; avgNetPrice is derived from it, so a
        # non-terminating average (e.g. 80/60) only matches after quantizing both sides.
        _q = D("0.00000001")
        assert result.breakdown[-1].netInvestment.quantize(_q) == (result.quantity * result.avgNetPrice).quantize(_q)
        assert len(result.breakdown) == opNumber + 1

        # don't compare remainingOpenQuantity and matchingOpenPositions
        for resultBreakdown, breakdown in zip(result.breakdown, breakdowns[:opNumber+1]):
            resultBreakdown.remainingOpenQuantity = breakdown.remainingOpenQuantity
            resultBreakdown.matchingOpenPositions = []

        assert result.breakdown == breakdowns[:opNumber+1]

    checkToOperation(0, D(0), D(0), D(2), D(25))
    checkToOperation(1, D(0), D(1), D(3), D(50))

    # FIFO: selling 10 closes the oldest BUY (unit 2), so profit is 50 - 2*10 == 30
    checkToOperation(2, D(30), D("3.5"), D("3.25"), D(40))

    # profit is previous 30 + 5.5 distributed dividend now
    checkToOperation(3, D("35.5"), D("3.7"), D("3.25"), D(40))

    # average price is reduced because a RECEIVE operation is basically being given for free
    checkToOperation(4, D("35.5"), D("43.7"), D("1.625"), D(80))

    checkToOperation(5, D("41.5"), D("44.9"), D(80) / D(60), D(60))


def test_equity_with_conversion_rate():
    operations = [
        AssetOperation(
            date = datetime(2020, 1, 1),
            type = AssetOperationType.buy,
            price = D("12.5"),
            quantity = D(10),
            finalQuantity = D(10),
            currencyConversion = D(2)
        ),
        AssetOperation(
            date = datetime(2020, 2, 5),
            type = AssetOperationType.earning,  # this is equivalent to a distributed dividend
            price = D("7.5"),
            finalQuantity = D(10),
            provision = D("0.2"),
            currencyConversion = D("1.8")
        ),
        AssetOperation(
            date = datetime(2020, 3, 1),
            type = AssetOperationType.receive,  # this is equivalent to a being granted a free stocks
            price = D(4),
            quantity = D(10),
            finalQuantity = D(20),
            currencyConversion = D("2.0")
        ),
        AssetOperation(
            date = datetime(2020, 4, 1),
            type = AssetOperationType.sell,  # partial sell after RECEIVE and EARNING ops
            price = D(15),
            quantity = D(10),
            finalQuantity = D(10),
            provision = D("2.2"),
            currencyConversion = D("2.05")
        )
    ]
    breakdowns = [
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D("1.25"),
            avgNetPrice = D("2.5"),
            netInvestment = D(25),
            quantity = D(10)
        ),
        Profits.Result.Breakdown(
            profit = D("7.5"),
            netProfit = D("13.5"),
            provisions = D("0.2"),
            avgPrice = D("1.25"),
            avgNetPrice = D("2.5"),
            netInvestment = D(25),
            quantity = D(10)
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D("0.625"),
            avgNetPrice = D("1.25"),
            netInvestment = D(25),
            quantity = D(20)
        ),
        Profits.Result.Breakdown(
            profit = D("2.5"),  # FIFO closes the only priced lot (the BUY, native cost 12.5): 15 - 12.5
            netProfit = D("5.75"),  # 15*2.05 - 25 (BUY net cost)
            provisions = D("2.2"),
            avgPrice = D(0),  # only the free RECEIVE lot remains
            avgNetPrice = D(0),
            netInvestment = D(0),
            quantity = D(10)
        )
    ]
    analyzer = Profits(currentDate = datetime(2020, 12, 31))
    asset = makeAsset(AssetType.equity)

    def checkToOperation(opNumber, profit, netProfit, provisions, avgPrice, avgNetPrice, quantity):
        asset.operations = operations[:opNumber+1]
        result = analyzer(asset)
        assert result.investmentStart == datetime(2020, 1, 1)
        assert result.holdingDays == 365
        assert result.profit == profit
        assert result.netProfit == netProfit
        assert result.provisions == provisions
        assert result.avgPrice == avgPrice
        assert result.avgNetPrice is not None
        assert result.avgNetPrice == avgNetPrice
        assert result.quantity == quantity
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice
        assert len(result.breakdown) == opNumber + 1

        # don't compare remainingOpenQuantity and matchingOpenPositions
        for resultBreakdown, breakdown in zip(result.breakdown, breakdowns[:opNumber+1]):
            resultBreakdown.remainingOpenQuantity = breakdown.remainingOpenQuantity
            resultBreakdown.matchingOpenPositions = []

        assert result.breakdown == breakdowns[:opNumber+1]

    checkToOperation(0, D(0), D(0), D(0), D("1.25"), D("2.5"), D(10))
    checkToOperation(1, D("7.5"), D("13.5"), D("0.2"), D("1.25"), D("2.5"), D(10))
    checkToOperation(2, D("7.5"), D("13.5"), D("0.2"), D("0.625"), D("1.25"), D(20))
    # FIFO closes the priced BUY lot, leaving only the free RECEIVE lot -> residual cost basis 0
    checkToOperation(3, D(10), D("19.25"), D("2.4"), D(0), D(0), D(10))


def test_deposit_default_currency():
    operations = [
        AssetOperation(
            date = datetime(2020, 1, 1),
            type = AssetOperationType.buy,
            price = D(100),
            quantity = D(100),
            finalQuantity = D(100)
        ),
        AssetOperation(
            date = datetime(2020, 1, 2),
            type = AssetOperationType.buy,
            price = D(150),
            quantity = D(150),
            finalQuantity = D(250),
            provision = D(1)
        ),
        AssetOperation(
            date = datetime(2020, 2, 1),
            type = AssetOperationType.sell,
            price = D(50),
            quantity = D(50),
            finalQuantity = D(200),
            provision = D("0.5")
        ),
        AssetOperation(
            date = datetime(2020, 3, 1),
            type = AssetOperationType.earning,
            price = D(100),
            quantity = D(100),
            finalQuantity = D(300),
            provision = D("3.3")
        ),
        AssetOperation(
            date = datetime(2020, 3, 2),
            type = AssetOperationType.sell,
            price = D(200),
            quantity = D(200),
            finalQuantity = D(100)
        )

    ]
    breakdowns = [
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(1),
            avgNetPrice = D(1),
            netInvestment = D(100),
            quantity = D(100)
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(1),
            avgPrice = D(1),
            avgNetPrice = D(1),
            netInvestment = D(250),
            quantity = D(250)
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D("0.5"),
            avgPrice = D(1),
            avgNetPrice = D(1),
            netInvestment = D(200),
            quantity = D(200)
        ),
        Profits.Result.Breakdown(
            profit = D(100),
            netProfit = D(100),
            provisions = D("3.3"),
            avgPrice = D(1),
            avgNetPrice = D(1),
            netInvestment = D(300),  # An EARNING brings immediate profit and is put into the Deposit balance immediately, so increases netInvestment
            quantity = D(300)
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(1),
            avgNetPrice = D(1),
            netInvestment = D(100),
            quantity = D(100)
        )

    ]
    analyzer = Profits(currentDate = datetime(2020, 12, 31))
    asset = makeAsset(AssetType.deposit)

    def checkToOperation(opNumber, profit, provisions, quantity):
        asset.operations = operations[:opNumber+1]
        result = analyzer(asset)
        assert result.investmentStart == datetime(2020, 1, 1)
        assert result.holdingDays == 365
        assert result.profit == profit
        assert result.netProfit == profit
        assert result.provisions == provisions
        assert result.avgPrice == D(1)
        assert result.avgNetPrice is not None
        assert result.avgNetPrice == D(1)
        assert result.quantity == quantity
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice
        assert len(result.breakdown) == opNumber + 1

        # don't compare remainingOpenQuantity and matchingOpenPositions
        for resultBreakdown, breakdown in zip(result.breakdown, breakdowns[:opNumber+1]):
            resultBreakdown.remainingOpenQuantity = breakdown.remainingOpenQuantity
            resultBreakdown.matchingOpenPositions = []

        assert result.breakdown == breakdowns[:opNumber+1]

    checkToOperation(0, D(0), D(0), D(100))
    checkToOperation(1, D(0), D(1), D(250))
    checkToOperation(2, D(0), D("1.5"), D(200))  # SELL does not generate profits for Deposit
    checkToOperation(3, D(100), D("4.8"), D(300))
    checkToOperation(4, D(100), D("4.8"), D(100))


def test_deposit_foreign_currency():
    operations = [
        AssetOperation(
            date = datetime(2020, 1, 1),
            type = AssetOperationType.buy,
            price = D("12.5"),
            quantity = D("12.5"),
            finalQuantity = D("12.5"),
            currencyConversion = D(2)
        ),
        AssetOperation(
            date = datetime(2020, 2, 5),
            type = AssetOperationType.earning,
            price = D("7.5"),
            quantity = D("7.5"),
            finalQuantity = D(20),
            currencyConversion = D("1.8")
        ),
        AssetOperation(
            date = datetime(2020, 4, 1),
            type = AssetOperationType.sell,  # partial sell after EARNING op
            price = D(15),
            quantity = D(15),
            finalQuantity = D(5),
            currencyConversion = D("2.05")
        )
    ]
    breakdowns = [
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(1),
            avgNetPrice = D(2),
            netInvestment = D(25),
            quantity = D("12.5")
        ),
        Profits.Result.Breakdown(
            profit = D("7.5"),
            netProfit = D("13.5"),
            provisions = D(0),
            avgPrice = D(1),
            avgNetPrice = D("1.925"),
            netInvestment = D("38.5"),
            quantity = D(20)
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D("1.875"),
            provisions = D(0),
            avgPrice = D(1),
            avgNetPrice = D("1.925"),
            netInvestment = D("9.625"),
            quantity = D(5)
        )
    ]
    analyzer = Profits(currentDate = datetime(2020, 12, 31))
    asset = makeAsset(AssetType.deposit)

    def checkToOperation(opNumber, profit, netProfit, avgNetPrice, quantity):
        asset.operations = operations[:opNumber+1]
        result = analyzer(asset)
        assert result.investmentStart == datetime(2020, 1, 1)
        assert result.holdingDays == 365
        assert result.profit == profit
        assert result.netProfit == netProfit
        assert result.provisions == D(0)
        assert result.avgPrice == D(1)
        assert result.avgNetPrice is not None
        assert result.avgNetPrice == avgNetPrice
        assert result.quantity == quantity
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice
        assert len(result.breakdown) == opNumber + 1

        # don't compare remainingOpenQuantity and matchingOpenPositions
        for resultBreakdown, breakdown in zip(result.breakdown, breakdowns[:opNumber+1]):
            resultBreakdown.remainingOpenQuantity = breakdown.remainingOpenQuantity
            resultBreakdown.matchingOpenPositions = []

        assert result.breakdown == breakdowns[:opNumber+1]

    checkToOperation(0, D(0), D(0), D(2), D("12.5"))
    checkToOperation(1, D("7.5"), D("13.5"), D("1.925"), D(20))
    checkToOperation(2, D("7.5"), D("15.375"), D("1.925"), D(5))


def test_equity_selling_out_everything():
    operations = [
        AssetOperation(
            date = datetime(2020, 1, 1),
            type = AssetOperationType.buy,
            price = D(100),
            quantity = D(10),
            finalQuantity = D(10)
        ),
        AssetOperation(
            date = datetime(2020, 4, 1),
            type = AssetOperationType.sell,
            price = D(90),
            quantity = D(10),
            finalQuantity = D(0)
        )
    ]
    breakdowns = [
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(10),
            avgNetPrice = D(10),
            netInvestment = D(100),
            quantity = D(10),
            remainingOpenQuantity = D(0),
        ),
        Profits.Result.Breakdown(
            profit = D(-10),
            netProfit = D(-10),
            provisions = D(0),
            avgPrice = D(0),
            avgNetPrice = D(0),
            netInvestment = D(0),
            quantity = D(0),
            remainingOpenQuantity = None,
            matchingOpenPositions = [
                Profits.Result.Breakdown.MatchingOpenPosition(
                    operation = operations[0],
                    quantity = D(10),
                )
            ]
        )
    ]
    analyzer = Profits(currentDate = datetime(2020, 12, 31))
    asset = makeAsset(AssetType.equity)
    asset.operations = operations

    result = analyzer(asset)

    assert result.investmentStart is None
    assert result.holdingDays is None
    assert result.profit == D(-10)
    assert result.netProfit == D(-10)
    assert result.provisions == D(0)
    assert result.avgPrice == D(0)
    assert result.avgNetPrice == D(0)
    assert result.quantity == D(0)
    assert result.breakdown == breakdowns


def test_single_receive():
    operations = [
        AssetOperation(
            date = datetime(2020, 1, 1),
            type = AssetOperationType.receive,
            price = D(100),
            quantity = D(10),
            finalQuantity = D(10)
        )
    ]
    breakdowns = [
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(0),
            avgNetPrice = D(0),
            netInvestment = D(0),
            quantity = D(10),
            remainingOpenQuantity = D(10),
        )
    ]
    analyzer = Profits(currentDate = datetime(2020, 12, 31))
    asset = makeAsset(AssetType.equity)
    asset.operations = operations

    result = analyzer(asset)

    assert result.investmentStart == datetime(2020, 1, 1)
    assert result.holdingDays == 365
    assert result.profit == D(0)
    assert result.netProfit == D(0)
    assert result.provisions == D(0)
    assert result.avgPrice == D(0)
    assert result.avgNetPrice == D(0)
    assert result.quantity == D(10)
    assert result.breakdown == breakdowns


def test_investmentStart_set_on_first_buy_and_holdingDays_is_correct():
    asset = makeAsset()
    asset.operations = [_op(AssetOperationType.buy, datetime(2020, 1, 1), 100, 10, 10)]

    result = Profits(currentDate=datetime(2020, 4, 10))(asset)

    assert result.investmentStart == datetime(2020, 1, 1)
    assert result.holdingDays == 100  # Jan 1 → Apr 10, 2020 is 100 days


def test_investmentStart_cleared_after_full_liquidation():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.sell, datetime(2020, 6, 1), 100, 10, 0),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.investmentStart is None
    assert result.holdingDays is None


def test_investmentStart_reset_on_rebuy_after_full_liquidation():
    """After selling everything and buying again, the investmentStart must
    move to the new buy date — not stay anchored at the original buy."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.sell, datetime(2020, 6, 1), 100, 10, 0),
        _op(AssetOperationType.buy,  datetime(2020, 9, 1),  50,  5, 5),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.investmentStart == datetime(2020, 9, 1)
    assert result.holdingDays == 121  # Sep 1 → Dec 31


def test_investmentStart_unchanged_on_partial_sell():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.sell, datetime(2020, 6, 1),  50,  5, 5),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.investmentStart == datetime(2020, 1, 1)
    assert result.holdingDays == 365  # full year


def test_investmentStart_set_by_receive_when_first_operation():
    asset = makeAsset()
    asset.operations = [_op(AssetOperationType.receive, datetime(2020, 3, 1), 0, 10, 10)]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.investmentStart == datetime(2020, 3, 1)


def test_investmentStart_set_by_earning_when_first_operation_on_deposit():
    """EARNING on a deposit creates cash and is the only operation type that
    can be 'first' aside from BUY/RECEIVE.  Investment must start there."""
    asset = makeAsset(type=AssetType.deposit)
    asset.operations = [_op(AssetOperationType.earning, datetime(2020, 3, 1), 100, 100, 100)]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.investmentStart == datetime(2020, 3, 1)


def test_receive_then_sell_realises_full_proceeds_as_profit():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.receive, datetime(2020, 1, 1), 0, 10, 10),
        _op(AssetOperationType.sell,    datetime(2020, 6, 1), 50, 5,  5),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # avg cost was 0, so the full SELL price is profit
    assert result.profit == D(50)
    assert result.netProfit == D(50)
    # remaining 5 shares still at zero avg price
    assert result.avgPrice == D(0)
    assert result.quantity == D(5)


def test_sell_after_receive_plus_buy_uses_fifo_cost_basis():
    """RECEIVE 5@0 then BUY 5@100.  Under FIFO a SELL 3@40 closes the oldest lot
    first — the free RECEIVE shares — so its cost basis is 0 and profit=40."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.receive, datetime(2020, 1, 1),   0,  5, 5),
        _op(AssetOperationType.buy,     datetime(2020, 2, 1), 100,  5, 10),
        _op(AssetOperationType.sell,    datetime(2020, 3, 1),  40,  3, 7),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # FIFO closes 3 of the free RECEIVE lot (cost 0). profit = 40 - 0 = 40.
    assert result.profit == D(40)
    assert result.netProfit == D(40)


def test_sell_split_across_two_buys_records_FIFO_matching_positions():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.buy,  datetime(2020, 2, 1), 200, 10, 20),
        _op(AssetOperationType.sell, datetime(2020, 3, 1), 200, 15,  5),  # crosses the two BUYs
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell_breakdown = result.breakdown[2]
    assert len(sell_breakdown.matchingOpenPositions) == 2
    # First closed: all 10 from the first BUY
    assert sell_breakdown.matchingOpenPositions[0].operation.date == datetime(2020, 1, 1)
    assert sell_breakdown.matchingOpenPositions[0].quantity == D(10)
    # Then 5 from the second BUY
    assert sell_breakdown.matchingOpenPositions[1].operation.date == datetime(2020, 2, 1)
    assert sell_breakdown.matchingOpenPositions[1].quantity == D(5)

    # Verify remainingOpenQuantity got decremented on the prior buys
    assert result.breakdown[0].remainingOpenQuantity == D(0)
    assert result.breakdown[1].remainingOpenQuantity == D(5)


def test_two_consecutive_sells_after_one_buy():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.sell, datetime(2020, 2, 1),  60,  6,  4),
        _op(AssetOperationType.sell, datetime(2020, 3, 1),  50,  4,  0),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # avg cost = 10/share
    # SELL 1: 60 - 6*10 = 0
    # SELL 2: 50 - 4*10 = 10
    assert result.breakdown[1].profit == D(0)
    assert result.breakdown[2].profit == D(10)
    assert result.profit == D(10)
    # Final position cleared
    assert result.quantity == D(0)
    assert result.avgPrice == D(0)


def test_matchingOpenPositions_skips_non_position_breakdowns():
    """EARNING on a non-deposit creates a breakdown with
    remainingOpenQuantity=None.  Subsequent SELL matching should ignore it
    and only match against BUY / RECEIVE entries."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,     datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.earning, datetime(2020, 2, 1),   5, None, 10),
        _op(AssetOperationType.sell,    datetime(2020, 3, 1),  60,  6, 4),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell = result.breakdown[2]
    assert len(sell.matchingOpenPositions) == 1
    assert sell.matchingOpenPositions[0].operation.date == datetime(2020, 1, 1)
    assert sell.matchingOpenPositions[0].quantity == D(6)


def test_negative_finalQuantity_rejected_by_AssetOperation_validator():
    """An oversell would leave finalQuantity < 0.  The AssetOperation model
    rejects that at field level, so the bad data never reaches the analyzer."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AssetOperation(
            date=datetime(2020, 2, 1),
            type=AssetOperationType.sell,
            price=D(150),
            quantity=D(15),
            finalQuantity=D(-5),
            provision=D(0),
        )


def test_oversell_assert_is_defensive_backstop():
    """Defense-in-depth: if some path bypasses validation (e.g. .construct()
    or a hand-rolled dict), the Profits analyzer still asserts that a SELL
    is fully matched against open positions.  Pinned so the backstop isn't
    accidentally removed."""
    asset = makeAsset()
    asset.operations = [_op(AssetOperationType.buy, datetime(2020, 1, 1), 100, 10, 10)]
    bad_sell = AssetOperation.model_construct(
        date=datetime(2020, 2, 1),
        type=AssetOperationType.sell,
        price=D(150),
        quantity=D(15),       # 5 more than available
        finalQuantity=D(-5),
        provision=D(0),
    )
    asset.operations = list(asset.operations) + [bad_sell]

    with pytest.raises(AssertionError):
        Profits()(asset)


def test_earning_on_equity_records_profit_but_does_not_change_quantity():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,     datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.earning, datetime(2020, 6, 1),  15, None, 10),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # Quantity unchanged
    assert result.quantity == D(10)
    # avg price unchanged (dividend doesn't reduce cost basis)
    assert result.avgPrice == D(10)
    # Profit was 15
    assert result.profit == D(15)
    assert result.netProfit == D(15)
    # Earning breakdown has no remainingOpenQuantity (not a position)
    assert result.breakdown[1].remainingOpenQuantity is None


def test_earning_on_deposit_appears_as_remainingOpenQuantity_equal_to_price():
    """A bit of an oddity: for deposits, the EARNING breakdown's
    remainingOpenQuantity is set to operation.price (the cash inflow size).
    Locks in this current behaviour."""
    asset = makeAsset(type=AssetType.deposit)
    asset.operations = [
        _op(AssetOperationType.buy,     datetime(2020, 1, 1), 100, 100, 100),
        _op(AssetOperationType.earning, datetime(2020, 6, 1),  10,  10, 110),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.breakdown[1].remainingOpenQuantity == D(10)


def test_provisions_correctly_distributed_after_partial_sells():
    """Each SELL should consume a proportional slice of the running BUY
    provisions and report them in its breakdown.  After the asset is
    completely sold, every cent of provisions should appear in the total."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10, provision=10),
        _op(AssetOperationType.sell, datetime(2020, 2, 1),  60,  4,  6, provision=2),
        _op(AssetOperationType.sell, datetime(2020, 3, 1),  90,  6,  0, provision=3),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # BUY provision is 10; SELL 4/10 consumes 4 of it, SELL 6/6 consumes 6.
    # Plus the SELLs' own provisions 2 + 3 = 5.  Total = 15.
    assert result.provisions == D(15)
    assert result.breakdown[0].provisions == D(0)              # BUY defers
    assert result.breakdown[1].provisions == D(2) + D(4)       # SELL prov + 40% of 10
    assert result.breakdown[2].provisions == D(3) + D(6)       # SELL prov + remaining 6


def test_provisions_total_equals_sum_when_no_sells():
    """Without sells, BUY provisions stay in running.provision and are added
    only at the end."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy, datetime(2020, 1, 1), 100, 10, 10, provision=3),
        _op(AssetOperationType.buy, datetime(2020, 2, 1), 100, 10, 20, provision=5),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.provisions == D(8)
    # but the per-breakdown values are 0 (deferred to a future SELL)
    assert result.breakdown[0].provisions == D(0)
    assert result.breakdown[1].provisions == D(0)


def test_provisions_recorded_as_entered_regardless_of_currencyConversion():
    """Provisions and taxes are entered manually in the default (main)
    currency — even when the asset itself is denominated in a foreign
    currency.  The Profits analyzer therefore sums operation.provision
    AS-IS without applying currencyConversion.

    This test pins down that convention so a future "let's convert
    provisions" patch doesn't get reintroduced."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10,
            provision=10, currencyConversion=2),   # provision already in PLN
        _op(AssetOperationType.sell, datetime(2020, 6, 1),  60,  5,  5,
            provision=2, currencyConversion=3),    # provision already in PLN
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # In PLN throughout: BUY 10 + SELL 2 = 12.
    # currencyConversion does NOT touch provisions.
    assert result.provisions == D(12)


def test_loss_making_sell_records_negative_profit():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.sell, datetime(2020, 6, 1),  30,  5,  5),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # cost basis for 5 shares is 50; sold for 30 → -20
    assert result.profit == D(-20)
    assert result.netProfit == D(-20)


def test_currency_conversion_none_treated_as_one():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.sell, datetime(2020, 6, 1), 150, 10,  0),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.profit == D(50)
    assert result.netProfit == D(50)  # equal because conv == 1


def test_avg_price_stays_constant_after_partial_sells():
    """A SELL must reduce running totals proportionally so that the average
    price stays the same when no new BUY happens."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10),
        _op(AssetOperationType.sell, datetime(2020, 2, 1),  30,  3,  7),
        _op(AssetOperationType.sell, datetime(2020, 3, 1),  20,  2,  5),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    assert result.avgPrice == D(10)  # all the way through
    for b in result.breakdown:
        assert b.avgPrice == D(10)


def test_sell_with_orderId_uses_only_its_own_order_cost_basis():
    """When operations carry orderIds, a SELL must draw its cost basis (FIFO) from
    *its own order* — not across all orders — and must report only that order's BUYs
    as the matched open positions. (Order B is a single lot, so FIFO == its own cost.)"""
    asset = makeAsset()
    asset.hasOrderIds = True
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10, orderId="A"),  # unit 10
        _op(AssetOperationType.buy,  datetime(2020, 2, 1), 300, 10, 20, orderId="B"),  # unit 30
        _op(AssetOperationType.sell, datetime(2020, 3, 1), 400, 10, 10, orderId="B"),  # unit 40
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell = result.breakdown[2]
    # cost basis is order B's avg (30/share), NOT the blended 20/share:
    # 400 - 30*10 = 100   (blended would have been 400 - 20*10 = 200)
    assert sell.profit == D(100)
    assert result.profit == D(100)

    # only order B's BUY is closed; order A is untouched
    assert len(sell.matchingOpenPositions) == 1
    assert sell.matchingOpenPositions[0].operation.orderId == "B"
    assert sell.matchingOpenPositions[0].quantity == D(10)
    assert result.breakdown[0].remainingOpenQuantity == D(10)  # order A still fully open
    assert result.breakdown[1].remainingOpenQuantity == D(0)   # order B fully closed

    # asset-level running totals are still the aggregate across orders:
    # 10 shares of order A left at unit 10
    assert result.quantity == D(10)
    assert result.avgPrice == D(10)


def test_sell_matches_oldest_buy_within_same_order_fifo():
    """Within a single order, matching is still chronological/FIFO across that
    order's BUYs."""
    asset = makeAsset()
    asset.hasOrderIds = True
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10, orderId="A"),
        _op(AssetOperationType.buy,  datetime(2020, 2, 1), 200, 10, 20, orderId="A"),
        _op(AssetOperationType.sell, datetime(2020, 3, 1), 300, 15,  5, orderId="A"),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell = result.breakdown[2]
    assert len(sell.matchingOpenPositions) == 2
    assert sell.matchingOpenPositions[0].operation.date == datetime(2020, 1, 1)
    assert sell.matchingOpenPositions[0].quantity == D(10)
    assert sell.matchingOpenPositions[1].operation.date == datetime(2020, 2, 1)
    assert sell.matchingOpenPositions[1].quantity == D(5)


def test_netInvestment_equals_quantity_times_avgNetPrice_after_each_op():
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,     datetime(2020, 1, 1), 100, 10, 10, currencyConversion=2),
        _op(AssetOperationType.buy,     datetime(2020, 2, 1), 200, 10, 20, currencyConversion=3),
        _op(AssetOperationType.sell,    datetime(2020, 3, 1), 120,  5, 15, currencyConversion=4),
        _op(AssetOperationType.earning, datetime(2020, 4, 1),  10, None, 15, currencyConversion=2),
        _op(AssetOperationType.sell,    datetime(2020, 5, 1), 200,  5, 10, currencyConversion=3),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    for i, b in enumerate(result.breakdown):
        assert b.netInvestment == b.quantity * b.avgNetPrice, (
            f"netInvestment invariant broken at op {i}: "
            f"{b.netInvestment} != {b.quantity} * {b.avgNetPrice}"
        )


# --- FIFO cost-basis tests: profit must be FIFO, consistent with matchingOpenPositions ---

def test_fifo_worked_example():
    """Profit and matched lots come from the same FIFO drawdown. Prices are TOTALS:
    BUY 10 @ unit 100 (total 1000), BUY 5 @ unit 150 (total 750), SELL 8 (total 960).
    FIFO closes 8 of the first lot: 960 - 100*8 = +160 (average cost would give +26.67)."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 1000, 10, 10),
        _op(AssetOperationType.buy,  datetime(2020, 2, 1),  750,  5, 15),
        _op(AssetOperationType.sell, datetime(2020, 3, 1),  960,  8,  7),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell = result.breakdown[2]
    assert sell.profit == D(160)
    assert result.profit == D(160)

    # the matched lot and the profit are derived from the same FIFO drawdown
    assert len(sell.matchingOpenPositions) == 1
    assert sell.matchingOpenPositions[0].operation.date == datetime(2020, 1, 1)
    assert sell.matchingOpenPositions[0].quantity == D(8)
    assert result.breakdown[0].remainingOpenQuantity == D(2)
    assert result.breakdown[1].remainingOpenQuantity == D(5)


def test_fifo_multi_lot_sell_spans_lots():
    """A SELL larger than the oldest lot draws the remainder from the next one."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 1000, 10, 10),
        _op(AssetOperationType.buy,  datetime(2020, 2, 1),  750,  5, 15),
        _op(AssetOperationType.sell, datetime(2020, 3, 1), 1560, 12,  3),  # unit 130
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell = result.breakdown[2]
    # cost = all of lot1 (1000) + 2 of lot2 (750*2/5 = 300) = 1300
    assert sell.profit == D(1560) - D(1300)
    assert [(m.operation.date, m.quantity) for m in sell.matchingOpenPositions] == [
        (datetime(2020, 1, 1), D(10)),
        (datetime(2020, 2, 1), D(2)),
    ]
    assert result.breakdown[0].remainingOpenQuantity == D(0)
    assert result.breakdown[1].remainingOpenQuantity == D(3)


def test_fifo_cross_order_isolation():
    """FIFO is chronological within an order and never crosses orders."""
    asset = makeAsset()
    asset.hasOrderIds = True
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10, orderId="A"),  # unit 10
        _op(AssetOperationType.buy,  datetime(2020, 1, 2), 200, 10, 20, orderId="A"),  # unit 20
        _op(AssetOperationType.buy,  datetime(2020, 1, 3), 1000, 10, 30, orderId="B"),  # unit 100
        _op(AssetOperationType.sell, datetime(2020, 2, 1), 450, 15, 15, orderId="A"),  # within A
        _op(AssetOperationType.sell, datetime(2020, 3, 1), 600,  5, 10, orderId="B"),  # within B
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # SELL A closes all of A1 (cost 100) + 5 of A2 (200*5/10 = 100) = 200 -> 450 - 200 = 250
    sellA = result.breakdown[3]
    assert sellA.profit == D(250)
    assert [(m.operation.orderId, m.quantity) for m in sellA.matchingOpenPositions] == [("A", D(10)), ("A", D(5))]

    # SELL B closes 5 of B1 (1000*5/10 = 500) -> 600 - 500 = 100, untouched by order A
    sellB = result.breakdown[4]
    assert sellB.profit == D(100)
    assert [(m.operation.orderId, m.quantity) for m in sellB.matchingOpenPositions] == [("B", D(5))]


def test_fifo_currency_conversion_uses_lot_and_sell_rates():
    """netProfit draws cost at the matched lot's conversion rate and proceeds at the sell's."""
    asset = makeAsset(currency_name="USD")
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10, currencyConversion=2),  # net 200
        _op(AssetOperationType.buy,  datetime(2020, 2, 1), 100, 10, 20, currencyConversion=3),  # net 300
        _op(AssetOperationType.sell, datetime(2020, 3, 1),  75,  5, 15, currencyConversion=4),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell = result.breakdown[2]
    # FIFO closes 5 of the first lot: native cost 100*5/10 = 50, net cost 200*5/10 = 100
    assert sell.profit == D(75) - D(50)
    assert sell.netProfit == D(75) * D(4) - D(100)  # proceeds at sell rate 4, cost at lot rate 2


def test_fifo_provisions_drawn_from_matched_lots():
    """Provisions are drawn from the specific FIFO-matched lot, not blended across lots."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.buy,  datetime(2020, 1, 1), 100, 10, 10, provision=10),
        _op(AssetOperationType.buy,  datetime(2020, 2, 1), 100, 10, 20, provision=20),
        _op(AssetOperationType.sell, datetime(2020, 3, 1), 100,  5, 15, provision=1),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    sell = result.breakdown[2]
    # 5 drawn from the first lot only: 1 (SELL) + 10*5/10 = 6  (blended avg would give 8.5)
    assert sell.provisions == D(6)
