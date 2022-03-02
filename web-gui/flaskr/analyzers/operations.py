from flaskr.model import AssetOperation, AssetOperationType
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal


class DecoratedAssetOperation(AssetOperation):
    unitPrice: Optional[Decimal]


class Operations(object):
    def __init__(self, currency):
        super(Operations, self).__init__();
        self.currency = currency

    def __call__(self, operations):
        result = []

        for operation in operations:
            result.append(self._next(operation))

        return result

    def _next(self, operation):
        thisOp = DecoratedAssetOperation(**operation)

        self._commonFields(thisOp)

        if thisOp.type == AssetOperationType.buy:
            self._buy(thisOp)
        elif thisOp.type == AssetOperationType.sell:
            self._sell(thisOp)
        elif thisOp.type == AssetOperationType.receive:
            self._receive(thisOp)
        elif thisOp.type == AssetOperationType.earning:
            self._earning(thisOp)
        else:
            raise NotImplementedError("Did not implement Operation for type {}" % (thisOp.type))

        return thisOp

    def _commonFields(self, operation):
        if operation.quantity:
            operation.unitPrice = operation.price / operation.quantity

    def _buy(self, operation):
        pass

    def _sell(self, operation):
        pass

    def _receive(self, operation):
        pass

    def _earning(self, operation):
        pass
