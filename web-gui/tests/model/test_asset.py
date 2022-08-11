import pytest
from flaskr.model import Asset, PyObjectId
from pydantic import ValidationError
from decimal import Decimal
from datetime import datetime


def test_model_cannot_create_asset_deposit_with_receive_operations():
    data = dict(
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
                type = "RECEIVE",
                price = Decimal(50),
                quantity = Decimal(25),
                finalQuantity = Decimal(25)
            )
        ]
    )

    with pytest.raises(ValidationError):
        asset = Asset(**data)

    data['operations'][0]['type'] = 'BUY'
    Asset(**data)


def test_model_enforces_order_ids():
    data = dict(
        _id = PyObjectId(),
        name = "Test asset",
        currency = dict(
            name = "TST"
        ),
        institution = "Test",
        type = "Deposit",
        category = "Testing",
        hasOrderIds = True,
        operations = [
            dict(
                date = datetime(2020, 1, 1),
                type = "BUY",
                price = Decimal(50),
                quantity = Decimal(25),
                finalQuantity = Decimal(25)
            )
        ]
    )

    with pytest.raises(ValidationError):
        asset = Asset(**data)

    data['operations'][0]['orderId'] = '1'
    Asset(**data)