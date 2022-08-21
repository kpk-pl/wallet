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
    data['pricing'] = dict(
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

