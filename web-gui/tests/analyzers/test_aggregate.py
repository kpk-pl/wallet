import pytest
from datetime import datetime
from decimal import Decimal as D

from flaskr.model import (
    Asset, AggregatedAsset, AssetType, AssetCurrency, AssetOperation,
    AssetOperationType, AssetPricingQuotes, PyObjectId,
)
from flaskr.analyzers.aggregate import aggregate, AggregationType


def _equity(institution="Bank", name="Eq", ticker="TST", pricingId=None,
            operations=(), hasOrderIds=False):
    return Asset(
        _id=PyObjectId(),
        name=name,
        ticker=ticker,
        currency=AssetCurrency(name="PLN"),
        institution=institution,
        type=AssetType.equity,
        category="Equities",
        pricing=AssetPricingQuotes(quoteId=pricingId) if pricingId else None,
        operations=list(operations),
        hasOrderIds=hasOrderIds,
    )


def _deposit(institution="Bank", name="Cash", operations=()):
    return Asset(
        _id=PyObjectId(),
        name=name,
        ticker=None,
        currency=AssetCurrency(name="PLN"),
        institution=institution,
        type=AssetType.deposit,
        category="Cash",
        pricing=None,
        operations=list(operations),
    )


def _buy(date, quantity, finalQuantity, orderId=None):
    return AssetOperation(
        date=date,
        type=AssetOperationType.buy,
        price=D(quantity),
        quantity=D(quantity),
        finalQuantity=D(finalQuantity),
        orderId=orderId,
    )


def _depositBuy(date, amount, finalAmount):
    return AssetOperation(
        date=date,
        type=AssetOperationType.buy,
        price=D(amount),
        quantity=D(amount),
        finalQuantity=D(finalAmount),
    )


def test_two_equities_same_pricing_different_institutions_merge():
    pid = PyObjectId()
    a = _equity(institution="A", pricingId=pid,
                operations=[_buy(datetime(2020, 1, 1), 10, 10)])
    b = _equity(institution="B", pricingId=pid,
                operations=[_buy(datetime(2020, 2, 1), 5, 5)])

    result = aggregate([a, b], AggregationType.pricing)

    assert len(result) == 1
    merged = result[0]
    assert isinstance(merged, AggregatedAsset)
    assert merged.institutions == ["A", "B"]
    assert len(merged.ids) == 2
    assert merged.name == "Eq"
    assert merged.currency.name == "PLN"
    assert len(merged.operations) == 2
    assert merged.operations[0].date < merged.operations[1].date
    assert merged.operations[-1].finalQuantity == D(15)
    assert merged.finalQuantity == D(15)


def test_different_pricing_does_not_merge():
    a = _equity(institution="A", pricingId=PyObjectId(),
                operations=[_buy(datetime(2020, 1, 1), 10, 10)])
    b = _equity(institution="B", pricingId=PyObjectId(),
                operations=[_buy(datetime(2020, 2, 1), 5, 5)])

    result = aggregate([a, b], AggregationType.pricing)

    assert len(result) == 2
    assert all(isinstance(r, Asset) for r in result)


def test_orderid_namespaced_on_merge():
    pid = PyObjectId()
    a = _equity(institution="A", pricingId=pid, hasOrderIds=True,
                operations=[_buy(datetime(2020, 1, 1), 10, 10, orderId="1")])
    b = _equity(institution="B", pricingId=pid, hasOrderIds=True,
                operations=[_buy(datetime(2020, 2, 1), 5, 5, orderId="1")])

    result = aggregate([a, b], AggregationType.pricing)

    assert len(result) == 1
    orderIds = sorted(op.orderId for op in result[0].operations)
    assert orderIds == ["A:1", "B:1"]


def test_original_assets_untouched_after_merge():
    pid = PyObjectId()
    a = _equity(institution="A", pricingId=pid, hasOrderIds=True,
                operations=[_buy(datetime(2020, 1, 1), 10, 10, orderId="1")])
    b = _equity(institution="B", pricingId=pid, hasOrderIds=True,
                operations=[_buy(datetime(2020, 2, 1), 5, 5, orderId="1")])

    aggregate([a, b], AggregationType.pricing)

    assert a.operations[0].orderId == "1"
    assert b.operations[0].orderId == "1"
    assert a.operations[0].finalQuantity == D(10)
    assert b.operations[0].finalQuantity == D(5)


def test_three_way_merge_produces_single_aggregated_asset():
    pid = PyObjectId()
    a = _equity(institution="A", pricingId=pid,
                operations=[_buy(datetime(2020, 1, 1), 10, 10)])
    b = _equity(institution="B", pricingId=pid,
                operations=[_buy(datetime(2020, 2, 1), 5, 5)])
    c = _equity(institution="C", pricingId=pid,
                operations=[_buy(datetime(2020, 3, 1), 3, 3)])

    result = aggregate([a, b, c], AggregationType.pricing)

    assert len(result) == 1
    merged = result[0]
    assert isinstance(merged, AggregatedAsset)
    assert merged.institutions == ["A", "B", "C"]
    assert len(merged.ids) == 3
    assert merged.operations[-1].finalQuantity == D(18)


def test_name_aggregation_skips_priced_entries():
    pid = PyObjectId()
    d1 = _deposit(institution="A",
                  operations=[_depositBuy(datetime(2020, 1, 1), 100, 100)])
    d2 = _deposit(institution="B",
                  operations=[_depositBuy(datetime(2020, 2, 1), 50, 50)])
    e = _equity(institution="C", pricingId=pid,
                operations=[_buy(datetime(2020, 1, 1), 10, 10)])

    result = aggregate([d1, d2, e], AggregationType.name)

    aggregateds = [r for r in result if isinstance(r, AggregatedAsset)]
    singles = [r for r in result if isinstance(r, Asset)]
    assert len(aggregateds) == 1
    assert aggregateds[0].institutions == ["A", "B"]
    assert aggregateds[0].operations[-1].finalQuantity == D(150)
    assert len(singles) == 1
    assert singles[0].name == "Eq"


def test_pn_aggregation_combines_steps():
    pid = PyObjectId()
    # Two equities with same pricing — merge under 'p'
    e1 = _equity(institution="A", pricingId=pid,
                 operations=[_buy(datetime(2020, 1, 1), 10, 10)])
    e2 = _equity(institution="B", pricingId=pid,
                 operations=[_buy(datetime(2020, 2, 1), 5, 5)])
    # Two deposits — merge under 'n'
    d1 = _deposit(institution="A",
                  operations=[_depositBuy(datetime(2020, 1, 1), 100, 100)])
    d2 = _deposit(institution="B",
                  operations=[_depositBuy(datetime(2020, 2, 1), 50, 50)])

    entries = [e1, e2, d1, d2]
    for step in "pn":
        entries = aggregate(entries, AggregationType(step))

    assert len(entries) == 2
    assert all(isinstance(e, AggregatedAsset) for e in entries)


def test_aggregating_aggregated_with_fresh_asset_keeps_one_aggregated():
    pid = PyObjectId()
    a = _equity(institution="A", pricingId=pid,
                operations=[_buy(datetime(2020, 1, 1), 10, 10)])
    b = _equity(institution="B", pricingId=pid,
                operations=[_buy(datetime(2020, 2, 1), 5, 5)])
    first = aggregate([a, b], AggregationType.pricing)
    assert len(first) == 1 and isinstance(first[0], AggregatedAsset)

    c = _equity(institution="C", pricingId=pid,
                operations=[_buy(datetime(2020, 3, 1), 3, 3)])
    second = aggregate(first + [c], AggregationType.pricing)

    assert len(second) == 1
    merged = second[0]
    assert isinstance(merged, AggregatedAsset)
    assert merged.institutions == ["A", "B", "C"]
    assert len(merged.ids) == 3
