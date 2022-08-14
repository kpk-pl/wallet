import pytest
from decimal import Decimal
from datetime import datetime
from flaskr.pricing.interp import interp
from flaskr.model import QuoteHistoryItem


def test_supports_empty_input():
    result = interp([], [])
    assert len(result) == 0


def test_performs_linear_interpolation_correctly():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 12), quote=Decimal(10))
    ]

    timerange = [
        datetime(2020, 1, 1, 12),
        datetime(2020, 1, 2),
        datetime(2020, 1, 2, 12),
    ]

    result = interp(data, timerange)
    assert result == [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2), quote=Decimal("7.5")),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 12), quote=Decimal(10))
    ]


def test_skips_quotes_when_needed():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 13), quote=Decimal(6)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 18), quote=Decimal(7)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 12), quote=Decimal(10))
    ]

    timerange = [
        datetime(2020, 1, 1, 12),
        datetime(2020, 1, 2, 12),
    ]

    result = interp(data, timerange)
    assert result == [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 12), quote=Decimal(10))
    ]


def test_interpolates_multiple_points_between_quotes():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 0), quote=Decimal(11))
    ]

    timerange = [
        datetime(2020, 1, 1, 12),
        datetime(2020, 1, 1, 13),
        datetime(2020, 1, 1, 14),
        datetime(2020, 1, 1, 18),
        datetime(2020, 1, 1, 21),
    ]

    result = interp(data, timerange)
    assert result == [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 13), quote=Decimal("5.5")),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 14), quote=Decimal(6)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 18), quote=Decimal(8)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 21), quote=Decimal("9.5"))
    ]


def test_fills_with_edge_value():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 0), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 12), quote=Decimal(15))
    ]

    timerange = [
        datetime(2020, 1, 1),
        datetime(2020, 1, 2),
        datetime(2020, 1, 3),
    ]

    result = interp(data, timerange)
    assert result == [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 3), quote=Decimal(15)),
    ]


def test_fills_with_defined_value():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 12), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 0), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2, 12), quote=Decimal(15))
    ]

    timerange = [
        datetime(2020, 1, 1),
        datetime(2020, 1, 2),
        datetime(2020, 1, 3),
    ]

    result = interp(data, timerange, leftFill = 0, rightFill = 1)
    assert result == [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1), quote=Decimal(0)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 3), quote=Decimal(1)),
    ]
