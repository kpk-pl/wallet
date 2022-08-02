import pytest
from flaskr.model import Asset, AssetType, AssetCurrency, PyObjectId, AssetOperation, AssetOperationType
from flaskr.analyzers import Profits
from decimal import Decimal as D
from datetime import datetime


def makeAsset(type:AssetType):
    return Asset(
        _id = PyObjectId(),
        name = "Test asset",
        currency = AssetCurrency(
            name = "TST"
        ),
        institution = "Test",
        type = type,
        category = "Testing"
    )


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
            quantity = D(25)
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D(3),
            avgNetPrice = D(3),
            netInvestment = D(150),
            quantity = D(50)
        ),
        Profits.Result.Breakdown(
            profit = D(20),
            netProfit = D(20),
            provisions = D("2.5") + D("0.2"),  # previous total BUY provisions were 1 for 50 quantity. Selling 20% of total quantity
            avgPrice = D(3),
            avgNetPrice = D(3),
            netInvestment = D(120),  # sold 20% (10 out of 50) of everything out of 150 previous netInvestment
            quantity = D(40)
        ),
        Profits.Result.Breakdown(
            profit = D("5.5"),
            netProfit = D("5.5"),
            provisions = D("0.2"),
            avgPrice = D(3),
            avgNetPrice = D(3),
            netInvestment = D(120),
            quantity = D(40)
        ),
        Profits.Result.Breakdown(
            profit = D(0),
            netProfit = D(0),
            provisions = D(0),
            avgPrice = D("1.5"),
            avgNetPrice = D("1.5"),
            netInvestment = D(120),
            quantity = D(80)
        ),
        Profits.Result.Breakdown(
            profit = D(26),  # average price was 1.5 (1.5*20 = 30) and selling for 56
            netProfit = D(26),
            provisions = D("11.4"),  # 1.2 from SELL operation and 25% out of all remaining provisions (40 from RECEIVE and 0.8 remaining from BUY)
            avgPrice = D("1.5"),
            avgNetPrice = D("1.5"),
            netInvestment = D(90),  # sold 20 out of 80 which is 25% (25% of 120 is 30)
            quantity = D(60)
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
        assert result.avgNetPrice == avgPrice
        assert result.quantity == quantity
        assert result.breakdown == breakdowns[:opNumber+1]
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice

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
        assert result.avgNetPrice == avgNetPrice
        assert result.quantity == quantity
        assert result.breakdown == breakdowns[:opNumber+1]
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice

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
        assert result.avgNetPrice == D(1)
        assert result.quantity == quantity
        assert result.breakdown == breakdowns[:opNumber+1]
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice

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
        assert result.avgNetPrice == avgNetPrice
        assert result.quantity == quantity
        assert result.breakdown == breakdowns[:opNumber+1]
        assert result.breakdown[-1].netInvestment == result.quantity * result.avgNetPrice

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
            quantity = D(10)
        ),
        Profits.Result.Breakdown(
            profit = D(-10),
            netProfit = D(-10),
            provisions = D(0),
            avgPrice = D(0),
            avgNetPrice = D(0),
            netInvestment = D(0),
            quantity = D(0)
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
            quantity = D(10)
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

