import pytest
from datetime import datetime
from decimal import Decimal
from flaskr.model import AssetOperation, AssetOperationType
from flaskr.analyzers import Operations


def test_matches_closing_position():
    buy = AssetOperation(date=datetime(2020, 10, 1), type=AssetOperationType.buy, price="1000.0", quantity="10", finalQuantity="10")
    sell = AssetOperation(date=datetime(2020, 10, 2), type=AssetOperationType.sell, price="1100.0", quantity="10", finalQuantity="0")

    result = Operations("PLN")([buy, sell])
    assert len(result) == 2

    assert result[0].openQuantity == 0
    assert result[0].netPrice == 1000
    assert result[0].unitPrice == 100
    assert not result[0].closedPositionInfo
    assert not result[0].earningInfo

    assert not result[1].openQuantity
    assert result[1].netPrice == 1100
    assert result[1].unitPrice == 110
    assert result[1].profit == 100
    assert result[1].netProfit == 100
    assert result[1].totalNetProfit == 100
    assert result[1].closedPositionInfo
    assert result[1].closedPositionInfo.openingOperations[0].date == buy.date
    assert result[1].closedPositionInfo.matchingOpenPrice == 1000
    assert result[1].closedPositionInfo.matchingOpenNetPrice == 1000
    assert result[1].closedPositionInfo.matchingOpenProvision == 0
    assert not result[1].earningInfo


def test_matches_closing_position_by_orderId():
    buy1 = AssetOperation(date=datetime(2020, 10, 1), type=AssetOperationType.buy, orderId="1", price="1000.0", quantity="10", finalQuantity="10")
    buy2 = AssetOperation(date=datetime(2020, 10, 2), type=AssetOperationType.buy, orderId="2", price="2000.0", quantity="10", finalQuantity="10")
    buyn = AssetOperation(date=datetime(2020, 10, 3), type=AssetOperationType.buy, price="3000.0", quantity="10", finalQuantity="10")
    sell = AssetOperation(date=datetime(2020, 10, 4), type=AssetOperationType.sell, orderId="2", price="2200.0", quantity="10", finalQuantity="0")

    result = Operations("PLN")([buy1, buy2, buyn, sell])
    assert len(result) == 4

    assert len(result[3].closedPositionInfo.openingOperations) == 1
    assert result[3].closedPositionInfo.openingOperations[0].date == buy2.date


def test_matches_partial_sell():
    buy = AssetOperation(date=datetime(2020, 10, 1), type=AssetOperationType.buy, price="1000.0", quantity="10", finalQuantity="10")
    sell1 = AssetOperation(date=datetime(2020, 10, 2), type=AssetOperationType.sell, price="600", quantity="5", finalQuantity="5")
    sell2 = AssetOperation(date=datetime(2020, 10, 3), type=AssetOperationType.sell, price="300", quantity="2", finalQuantity="3")

    result = Operations("PLN")([buy, sell1, sell2])
    assert len(result) == 3

    assert result[0].openQuantity == 3

    assert result[1].unitPrice == 120
    assert result[1].profit == 100
    assert result[1].netProfit == 100
    assert result[1].totalNetProfit == 100
    assert result[1].closedPositionInfo.openingOperations[0].date == buy.date
    assert result[1].closedPositionInfo.matchingOpenPrice == 500
    assert result[1].closedPositionInfo.matchingOpenNetPrice == 500

    assert result[2].unitPrice == 150
    assert result[2].profit == 100
    assert result[2].netProfit == 100
    assert result[2].totalNetProfit == 100
    assert result[2].closedPositionInfo.openingOperations[0].date == buy.date
    assert result[2].closedPositionInfo.matchingOpenPrice == 200
    assert result[2].closedPositionInfo.matchingOpenNetPrice == 200


def test_matches_joins_multiple_buys():
    buy1 = AssetOperation(date=datetime(2020, 10, 1), type=AssetOperationType.buy, price="1000.0", quantity="10", finalQuantity="10")
    buy2 = AssetOperation(date=datetime(2020, 10, 2), type=AssetOperationType.buy, price="1100.0", quantity="10", finalQuantity="20")
    sell = AssetOperation(date=datetime(2020, 10, 3), type=AssetOperationType.sell, price="2400", quantity="20", finalQuantity="0")

    result = Operations("PLN")([buy1, buy2, sell])
    assert len(result) == 3

    assert result[0].openQuantity == 0
    assert result[1].openQuantity == 0

    assert result[2].unitPrice == 120
    assert result[2].profit == 300
    assert result[2].netProfit == 300
    assert result[2].totalNetProfit == 300
    assert len(result[2].closedPositionInfo.openingOperations) == 2
    assert result[2].closedPositionInfo.openingOperations[0].date == buy1.date
    assert result[2].closedPositionInfo.openingOperations[1].date == buy2.date
    assert result[2].closedPositionInfo.matchingOpenPrice == 2100
    assert result[2].closedPositionInfo.matchingOpenNetPrice == 2100


def test_matches_closing_position_in_foreign_currency_with_provision():
    buy = AssetOperation(date=datetime(2020, 10, 1), type=AssetOperationType.buy, price="1000.0", quantity="10", finalQuantity="10", currencyConversion="1.5", provision="10")
    sell = AssetOperation(date=datetime(2020, 10, 2), type=AssetOperationType.sell, price="1100.0", quantity="10", finalQuantity="0", currencyConversion="2", provision="15")

    result = Operations("EUR")([buy, sell])
    assert len(result) == 2

    assert result[0].openQuantity == 0
    assert result[0].netPrice == 1500
    assert result[0].unitPrice == 100

    assert result[1].netPrice == 2200
    assert result[1].unitPrice == 110
    assert result[1].profit == 100
    assert result[1].netProfit == 700
    assert result[1].totalNetProfit == 675
    assert result[1].closedPositionInfo.matchingOpenPrice == 1000
    assert result[1].closedPositionInfo.matchingOpenNetPrice == 1500
    assert result[1].closedPositionInfo.matchingOpenProvision == 10


def test_decorates_earning():
    earning = AssetOperation(date=datetime(2020, 11, 2), type=AssetOperationType.earning, price="50", currencyConversion="1.5", provision="2", finalQuantity="0")

    result = Operations("EUR")([earning])
    assert len(result) == 1

    assert not result[0].openQuantity
    assert not result[0].unitPrice
    assert not result[0].closedPositionInfo
    assert result[0].earningInfo
    assert result[0].profit == 50
    assert result[0].netProfit == 75
    assert result[0].totalNetProfit == 73
    assert result[0].earningInfo.earning == 50
    assert result[0].earningInfo.netEarning == 75
