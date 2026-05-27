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


def test_single_point_data_repeats_on_every_timescale_entry():
    """One data point should be reused for every timescale entry that follows."""
    data = [QuoteHistoryItem(timestamp=datetime(2020, 1, 1), quote=Decimal(5))]
    timerange = [
        datetime(2020, 1, 1),  # exact match
        datetime(2020, 1, 2),  # after
        datetime(2020, 1, 5),  # later still
    ]

    result = interp(data, timerange)

    assert [r.quote for r in result] == [Decimal(5), Decimal(5), Decimal(5)]
    assert [r.timestamp for r in result] == timerange


def test_single_point_data_with_timescale_before_data_uses_data_point():
    """leftFill=None on timescale points before data → use the only data point."""
    data = [QuoteHistoryItem(timestamp=datetime(2020, 6, 1), quote=Decimal(7))]
    timerange = [datetime(2020, 1, 1), datetime(2020, 3, 1), datetime(2020, 6, 1)]

    result = interp(data, timerange)

    assert [r.quote for r in result] == [Decimal(7), Decimal(7), Decimal(7)]


def test_leftFill_zero_int_is_promoted_to_decimal():
    """leftFill given as int should be coerced into Decimal in the result."""
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 6, 1), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 6, 2), quote=Decimal(20)),
    ]
    timerange = [datetime(2020, 5, 30)]

    result = interp(data, timerange, leftFill=0)

    assert result[0].quote == Decimal(0)
    assert isinstance(result[0].quote, Decimal)


def test_leftFill_float_is_promoted_to_decimal():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 6, 1), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 6, 2), quote=Decimal(20)),
    ]
    timerange = [datetime(2020, 5, 30)]

    result = interp(data, timerange, leftFill=0.0)

    assert result[0].quote == Decimal(0)
    assert isinstance(result[0].quote, Decimal)


def test_rightFill_used_only_when_timescale_exceeds_last_data_point():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2), quote=Decimal(20)),
    ]
    timerange = [
        datetime(2020, 1, 1),   # at first
        datetime(2020, 1, 2),   # at last
        datetime(2020, 1, 3),   # past last  → rightFill kicks in
    ]

    result = interp(data, timerange, rightFill=999)

    assert [r.quote for r in result] == [Decimal(10), Decimal(20), Decimal(999)]


def test_timescale_entirely_before_data_with_leftFill():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 6, 1), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 6, 2), quote=Decimal(20)),
    ]
    timerange = [datetime(2020, 1, 1), datetime(2020, 3, 1)]

    result = interp(data, timerange, leftFill=Decimal("99"))

    assert [r.quote for r in result] == [Decimal(99), Decimal(99)]


def test_timescale_entirely_after_data_with_rightFill():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2), quote=Decimal(20)),
    ]
    timerange = [datetime(2020, 5, 1), datetime(2020, 6, 1)]

    result = interp(data, timerange, rightFill=Decimal("99"))

    assert [r.quote for r in result] == [Decimal(99), Decimal(99)]


def test_quote_exactly_on_subsequent_timescale_point():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1), quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 5), quote=Decimal(50)),
    ]
    timerange = [
        datetime(2020, 1, 1),
        datetime(2020, 1, 3),  # half-way
        datetime(2020, 1, 5),
    ]

    result = interp(data, timerange)

    assert result[0].quote == Decimal(10)
    assert result[1].quote == Decimal(30)  # halfway, linear
    assert result[2].quote == Decimal(50)  # exact match


def test_multiple_data_points_before_first_timescale_entry():
    """Several quotes before the first timescale point: the most recent
    relevant pair must be used for interpolation."""
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1),  quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2),  quote=Decimal(20)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 3),  quote=Decimal(30)),  # last point before timescale
        QuoteHistoryItem(timestamp=datetime(2020, 1, 10), quote=Decimal(100)),
    ]
    timerange = [datetime(2020, 1, 5)]  # 2 days into the [3..10] segment

    result = interp(data, timerange)

    # linear between (1/3, 30) and (1/10, 100):  30 + (100-30) * 2/7 = 50
    assert result[0].quote == Decimal(30) + (Decimal(100) - Decimal(30)) * Decimal(2) / Decimal(7)


def test_empty_data_with_non_empty_timescale_asserts():
    """The current implementation asserts on empty data — lock that in."""
    with pytest.raises(AssertionError):
        interp([], [datetime(2020, 1, 1)])


def test_negative_slope_interpolation():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1),  quote=Decimal(100)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 11), quote=Decimal(0)),
    ]
    timerange = [datetime(2020, 1, 6)]  # half-way

    result = interp(data, timerange)

    assert result[0].quote == Decimal(50)


def test_constant_data_yields_constant_output():
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1),  quote=Decimal(50)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 10), quote=Decimal(50)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 20), quote=Decimal(50)),
    ]
    timerange = [datetime(2020, 1, d) for d in (1, 5, 10, 15, 20)]

    result = interp(data, timerange)

    assert all(r.quote == Decimal(50) for r in result)


def test_sub_second_precision_does_not_zero_divide():
    """timestamps differing by a microsecond should not blow up the divisor."""
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 0, 0, 0),    quote=Decimal(10)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1, 0, 0, 0, 1), quote=Decimal(20)),  # 1µs later
    ]
    timerange = [datetime(2020, 1, 1, 0, 0, 0, 1)]  # exact match on data[1]

    result = interp(data, timerange)
    assert result[0].quote == Decimal(20)


def test_leftFill_does_not_override_data_point_on_exact_match():
    """Regression: `leftFill` used to be returned even when the first
    timescale point coincided exactly with the first data point.  The fix
    in `interp` distinguishes "strictly before any data" (use `leftFill`)
    from "exactly on the first data point" (use that point's quote — there
    is no previous point to interpolate from)."""
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 1), quote=Decimal(5)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 2), quote=Decimal(10)),
    ]
    timerange = [datetime(2020, 1, 1), datetime(2020, 1, 2)]

    result = interp(data, timerange, leftFill=0)

    assert [r.quote for r in result] == [Decimal(5), Decimal(10)]


def test_leftFill_used_only_when_strictly_before_first_data_point():
    """leftFill should kick in for timescale points BEFORE data[0], not at
    or after."""
    data = [
        QuoteHistoryItem(timestamp=datetime(2020, 1, 5),  quote=Decimal(100)),
        QuoteHistoryItem(timestamp=datetime(2020, 1, 10), quote=Decimal(200)),
    ]
    timerange = [
        datetime(2020, 1, 1),  # before  → leftFill
        datetime(2020, 1, 3),  # before  → leftFill
        datetime(2020, 1, 5),  # exact   → 100 (the data point)
        datetime(2020, 1, 10), # exact   → 200
    ]

    result = interp(data, timerange, leftFill=Decimal(0))

    assert [r.quote for r in result] == [Decimal(0), Decimal(0), Decimal(100), Decimal(200)]
