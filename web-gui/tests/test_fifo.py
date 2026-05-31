import pytest
from datetime import datetime
from decimal import Decimal as D

from flaskr import fifo
from flaskr.model import AssetOperation, AssetOperationType


def _op(type, date, quantity, finalQuantity, price=0, orderId=None):
    return AssetOperation(
        date=date,
        type=type,
        price=D(str(price)),
        quantity=D(str(quantity)),
        finalQuantity=D(str(finalQuantity)),
        orderId=orderId,
    )


def _buy(date, quantity, finalQuantity, orderId=None):
    return _op(AssetOperationType.buy, date, quantity, finalQuantity, orderId=orderId)


def _sell(date, quantity, finalQuantity, orderId=None):
    return _op(AssetOperationType.sell, date, quantity, finalQuantity, orderId=orderId)


def _receive(date, quantity, finalQuantity, orderId=None):
    return _op(AssetOperationType.receive, date, quantity, finalQuantity, orderId=orderId)


def _earning(date, finalQuantity, orderId=None):
    return _op(AssetOperationType.earning, date, 0, finalQuantity, orderId=orderId)


def test_single_lot_partial_sell():
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10),
        _sell(datetime(2020, 2, 1), 4, 6),
    ]
    res = fifo.match(ops)

    assert res.remainingByIndex == [D(6), None]
    sell = res.sellByIndex[1]
    assert len(sell.matches) == 1
    assert sell.matches[0].lot is res.lots[0]
    assert sell.matches[0].quantity == D(4)
    assert res.openLotsByOrder[None][0].remaining == D(6)


def test_sell_spans_multiple_lots_fifo():
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10),
        _buy(datetime(2020, 2, 1), 5, 15),
        _sell(datetime(2020, 3, 1), 12, 3),
    ]
    res = fifo.match(ops)

    sell = res.sellByIndex[2]
    assert [(m.lot.openIndex, m.quantity) for m in sell.matches] == [(0, D(10)), (1, D(2))]
    assert res.remainingByIndex == [D(0), D(3), None]
    # first lot fully closed -> dropped from open bucket
    assert [lot.openIndex for lot in res.openLotsByOrder[None]] == [1]


def test_per_order_isolation():
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10, orderId="A"),
        _buy(datetime(2020, 2, 1), 10, 20, orderId="B"),
        _sell(datetime(2020, 3, 1), 10, 10, orderId="B"),
    ]
    res = fifo.match(ops)

    sell = res.sellByIndex[2]
    assert len(sell.matches) == 1
    assert sell.matches[0].lot.operation.orderId == "B"
    assert res.remainingByIndex == [D(10), D(0), None]  # order A untouched


def test_strict_oversell_raises():
    ops = [
        _buy(datetime(2020, 1, 1), 5, 5),
        _sell(datetime(2020, 2, 1), 8, 0),
    ]
    with pytest.raises(AssertionError):
        fifo.match(ops, strict=True)


def test_non_strict_oversell_tolerated():
    ops = [
        _buy(datetime(2020, 1, 1), 5, 5),
        _sell(datetime(2020, 2, 1), 8, 0),
    ]
    res = fifo.match(ops, strict=False)
    sell = res.sellByIndex[1]
    assert sum(m.quantity for m in sell.matches) == D(5)  # only what was open


def test_zero_quantity_lot_skipped():
    ops = [
        _buy(datetime(2020, 1, 1), 0, 0),
        _buy(datetime(2020, 1, 2), 10, 10),
        _sell(datetime(2020, 2, 1), 4, 6),
    ]
    res = fifo.match(ops)

    assert len(res.lots) == 1
    assert res.lots[0].openIndex == 1
    assert res.remainingByIndex == [None, D(6), None]


def test_receive_opens_lot_like_buy():
    ops = [
        _receive(datetime(2020, 1, 1), 10, 10),
        _sell(datetime(2020, 2, 1), 4, 6),
    ]
    res = fifo.match(ops)

    assert len(res.lots) == 1
    assert res.lots[0].operation.type is AssetOperationType.receive
    assert res.remainingByIndex == [D(6), None]
    sell = res.sellByIndex[1]
    assert sell.matches[0].lot is res.lots[0]
    assert sell.matches[0].quantity == D(4)


def test_ignored_types_skipped():
    # earning is neither an opening op nor a sell; it must not create a lot or shift indices
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10),
        _earning(datetime(2020, 1, 15), 10),
        _sell(datetime(2020, 2, 1), 4, 6),
    ]
    res = fifo.match(ops)

    assert len(res.lots) == 1
    assert res.lots[0].openIndex == 0
    assert res.remainingByIndex == [D(6), None, None]
    assert res.sellByIndex[1] is None
    sell = res.sellByIndex[2]
    assert sell.matches[0].lot is res.lots[0]


def test_non_strict_sell_with_no_open_lot():
    # the buy lives outside the loaded window: the sell has nothing to draw from
    ops = [
        _sell(datetime(2020, 2, 1), 8, 0),
    ]
    res = fifo.match(ops, strict=False)

    assert res.lots == []
    sell = res.sellByIndex[0]
    assert sell.matches == []
    # a sell-only orderId must not leak an open-lot bucket
    assert all(lots for lots in res.openLotsByOrder.values())


def test_open_quantity_over_time():
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10),
        _sell(datetime(2020, 3, 15), 4, 6),
    ]
    res = fifo.match(ops)
    lot = res.lots[0]

    timescale = [datetime(2020, m, 1) for m in range(1, 6)]  # Jan..May
    series = fifo.openQuantityOverTime(res, lot, timescale)

    # Sell on Mar 15 -> reduced from the first point strictly after it (Apr 1)
    assert series == [D(10), D(10), D(10), D(6), D(6)]


def test_open_quantity_over_time_future_sell_ignored():
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10),
        _sell(datetime(2020, 12, 1), 4, 6),
    ]
    res = fifo.match(ops)
    lot = res.lots[0]

    timescale = [datetime(2020, m, 1) for m in range(1, 6)]  # ends in May, before the sell
    series = fifo.openQuantityOverTime(res, lot, timescale)

    assert series == [D(10)] * 5


def test_open_quantity_over_time_zero_before_open():
    # lot opened mid-timescale: it holds nothing before the purchase date
    ops = [
        _buy(datetime(2020, 3, 1), 10, 10),
        _sell(datetime(2020, 4, 15), 4, 6),
    ]
    res = fifo.match(ops)
    lot = res.lots[0]

    timescale = [datetime(2020, m, 1) for m in range(1, 7)]  # Jan..Jun
    series = fifo.openQuantityOverTime(res, lot, timescale)

    # 0 before Mar 1, 10 from Mar/Apr, 6 from the first point after the Apr 15 sell (May)
    assert series == [D(0), D(0), D(10), D(10), D(6), D(6)]


def test_open_quantity_over_time_multiple_sells_one_lot():
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10),
        _sell(datetime(2020, 2, 15), 3, 7),
        _sell(datetime(2020, 4, 15), 2, 5),
    ]
    res = fifo.match(ops)
    lot = res.lots[0]

    timescale = [datetime(2020, m, 1) for m in range(1, 7)]  # Jan..Jun
    series = fifo.openQuantityOverTime(res, lot, timescale)

    # 10 until after Feb sell (Mar -> 7), then after Apr sell (May -> 5)
    assert series == [D(10), D(10), D(7), D(7), D(5), D(5)]


def test_open_quantity_over_time_isolated_per_lot():
    ops = [
        _buy(datetime(2020, 1, 1), 10, 10),
        _buy(datetime(2020, 2, 1), 5, 15),
        _sell(datetime(2020, 3, 15), 12, 3),  # closes lot0 fully, draws 2 from lot1
    ]
    res = fifo.match(ops)
    timescale = [datetime(2020, m, 1) for m in range(1, 6)]  # Jan..May

    lot0 = fifo.openQuantityOverTime(res, res.lots[0], timescale)
    lot1 = fifo.openQuantityOverTime(res, res.lots[1], timescale)

    # lot0: full until after the Mar 15 sell (Apr -> 0)
    assert lot0 == [D(10), D(10), D(10), D(0), D(0)]
    # lot1: zero before Feb 1, then 5, dropping to 3 after the sell (Apr)
    assert lot1 == [D(0), D(5), D(5), D(3), D(3)]
