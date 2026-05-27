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


def _op(type, date, price, quantity, finalQuantity, provision=None, currencyConversion=None):
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
            profit = D(20),
            netProfit = D(20),
            provisions = D("2.5") + D("0.2"),  # previous total BUY provisions were 1 for 50 quantity. Selling 20% of total quantity
            avgPrice = D(3),
            avgNetPrice = D(3),
            netInvestment = D(120),  # sold 20% (10 out of 50) of everything out of 150 previous netInvestment
            quantity = D(40),
        ),
        Profits.Result.Breakdown(
            profit = D("5.5"),
            netProfit = D("5.5"),
            provisions = D("0.2"),
            avgPrice = D(3),
            avgNetPrice = D(3),
            netInvestment = D(120),
            quantity = D(40),
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D("1.5"),
            avgNetPrice = D("1.5"),
            netInvestment = D(120),
            quantity = D(80),
        ),
        Profits.Result.Breakdown(
            profit = D(26),  # average price was 1.5 (1.5*20 = 30) and selling for 56
            netProfit = D(26),
            provisions = D("11.4"),  # 1.2 from SELL operation and 25% out of all remaining provisions (40 from RECEIVE and 0.8 remaining from BUY)
            avgPrice = D("1.5"),
            avgNetPrice = D("1.5"),
            netInvestment = D(90),  # sold 20 out of 80 which is 25% (25% of 120 is 30)
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
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice
        assert len(result.breakdown) == opNumber + 1

        # don't compare remainingOpenQuantity and matchingOpenPositions
        for resultBreakdown, breakdown in zip(result.breakdown, breakdowns[:opNumber+1]):
            resultBreakdown.remainingOpenQuantity = breakdown.remainingOpenQuantity
            resultBreakdown.matchingOpenPositions = []

        assert result.breakdown == breakdowns[:opNumber+1]

    checkToOperation(0, D(0), D(0), D(2), D(25))
    checkToOperation(1, D(0), D(1), D(3), D(50))

    # average BUY price is 3, selling 10 pieces for 50, so profit is 50-3*10 == 20
    checkToOperation(2, D(20), D("3.5"), D(3), D(40))

    # profit is previous 20 + 5.5 distributed dividend now
    checkToOperation(3, D("25.5"), D("3.7"), D(3), D(40))

    # average price is reduced because a RECEIVE operation is basically being given for free
    checkToOperation(4, D("25.5"), D("43.7"), D("1.5"), D(80))

    checkToOperation(5, D("51.5"), D("44.9"), D("1.5"), D(60))


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
            profit = D("8.75"),
            netProfit = D("18.25"),
            provisions = D("2.2"),
            avgPrice = D("0.625"),
            avgNetPrice = D("1.25"),
            netInvestment = D("12.5"),
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
    checkToOperation(3, D("16.25"), D("31.75"), D("2.4"), D("0.625"), D("1.25"), D(10))


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


def test_sell_after_receive_plus_buy_uses_running_average_cost():
    """RECEIVE 5@0 then BUY 5@100 → avg cost 10/share.  SELL 3@40 takes a
    cost basis of 3*10=30 (avg), so profit=10."""
    asset = makeAsset()
    asset.operations = [
        _op(AssetOperationType.receive, datetime(2020, 1, 1),   0,  5, 5),
        _op(AssetOperationType.buy,     datetime(2020, 2, 1), 100,  5, 10),
        _op(AssetOperationType.sell,    datetime(2020, 3, 1),  40,  3, 7),
    ]

    result = Profits(currentDate=datetime(2020, 12, 31))(asset)

    # avg = (0 + 100) / 10 = 10. SELL 3 → cost basis = 30. profit = 40-30 = 10.
    assert result.profit == D(10)
    assert result.netProfit == D(10)


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
    bad_sell = AssetOperation.construct(
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
