import pytest
from flaskr.model import Asset, PyObjectId
from pydantic import ValidationError
from decimal import Decimal
from datetime import datetime
import copy


PROTO_DEPOSIT = dict(
    _id = PyObjectId(),
    name = "Test asset",
    currency = dict(
        name = "TST"
    ),
    institution = "Test",
    type = "Deposit",
    category = "Testing",
    operations = [
        dict(
            date = datetime(2020, 1, 1),
            type = "BUY",
            price = Decimal(25),
            quantity = Decimal(25),
            finalQuantity = Decimal(25)
        )
    ]
)

def test_model_cannot_create_asset_deposit_with_receive_operations():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['operations'][0]['type'] = 'RECEIVE'

    with pytest.raises(ValidationError):
        asset = Asset(**data)

    data['operations'][0]['type'] = 'BUY'
    Asset(**data)


def test_model_currency_conversion_required_in_foreign_currency():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['type'] = 'ETF'
    data['currency'] = dict(
            name = "EUR",
            quoteId = PyObjectId()
        )

    with pytest.raises(ValidationError):
        asset = Asset(**data)

    data['operations'][0]['currencyConversion'] = Decimal(2)
    Asset(**data)


def test_model_cannot_create_asset_deposit_with_pricing():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['pricing'] = dict(
            quoteId = PyObjectId()
        )
    data['operations'][0]['currencyConversion'] = Decimal(1)

    with pytest.raises(ValidationError):
        asset = Asset(**data)

    del data['pricing']
    Asset(**data)


def test_model_enforces_order_ids():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['hasOrderIds'] = True

    with pytest.raises(ValidationError):
        asset = Asset(**data)

    data['operations'][0]['orderId'] = '1'
    Asset(**data)


def test_model_price_equals_quantity_for_deposits():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['operations'][0]['price'] = Decimal(50)

    with pytest.raises(ValidationError):
        asset = Asset(**data)

    data['operations'][0]['price'] = Decimal(25)
    Asset(**data)


# ---------------------------------------------------------------------------
# Operation date-ordering invariant
# ---------------------------------------------------------------------------
# Every consumer of `Asset.operations` iterates the list in storage order and
# treats it as date-ascending order.  The model validator below guarantees
# that, so out-of-order data cannot reach the analyzers / pricing engines.


def _op(date, price=10, quantity=10, finalQuantity=10, type='BUY'):
    return dict(date=date, type=type,
                price=Decimal(price),
                quantity=Decimal(quantity),
                finalQuantity=Decimal(finalQuantity))


def test_model_rejects_operations_with_descending_dates():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['operations'] = [
        _op(datetime(2022, 1, 2), price=10, quantity=10, finalQuantity=10),
        _op(datetime(2022, 1, 1), price=5,  quantity=5,  finalQuantity=15),  # earlier
    ]
    with pytest.raises(ValidationError) as exc_info:
        Asset(**data)
    assert "ascending" in str(exc_info.value)


def test_model_allows_operations_on_equal_timestamps():
    """Two operations at the same instant (e.g. settlement batch) are valid."""
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['operations'] = [
        _op(datetime(2022, 1, 1), price=10, quantity=10, finalQuantity=10),
        _op(datetime(2022, 1, 1), price=5,  quantity=5,  finalQuantity=15),
    ]
    Asset(**data)


def test_model_accepts_single_operation():
    data = copy.deepcopy(PROTO_DEPOSIT)
    Asset(**data)  # PROTO_DEPOSIT has exactly one op — must pass


def test_model_accepts_empty_operations_list():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['operations'] = []
    Asset(**data)


def test_model_accepts_long_ascending_chain():
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['operations'] = [
        _op(datetime(2022, 1, d), price=1, quantity=1, finalQuantity=d)
        for d in range(1, 11)
    ]
    Asset(**data)


def test_model_rejects_when_only_last_pair_out_of_order():
    """A single descending step anywhere in the list is enough to reject."""
    data = copy.deepcopy(PROTO_DEPOSIT)
    data['operations'] = [
        _op(datetime(2022, 1, 1), price=1, quantity=1, finalQuantity=1),
        _op(datetime(2022, 1, 2), price=1, quantity=1, finalQuantity=2),
        _op(datetime(2022, 1, 3), price=1, quantity=1, finalQuantity=3),
        _op(datetime(2022, 1, 2, 23), price=1, quantity=1, finalQuantity=4),  # 1h earlier
    ]
    with pytest.raises(ValidationError):
        Asset(**data)

