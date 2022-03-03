from flaskr.model import PyObjectId, AssetOperation, AssetOperationType, Asset
from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal


class DecoratedAssetOperationAssetInfo(BaseModel):
    id: PyObjectId
    name: str
    type: str
    institution: str
    currency: str


class ClosedPositionInfo(BaseModel):
    openingOperations: List[AssetOperation] = Field(default_factory=list)
    matchingOpenPrice: Decimal = Decimal(0)
    matchingOpenNetPrice: Decimal = Decimal(0)
    matchingOpenProvision: Decimal = Decimal(0)


class EarningInfo(BaseModel):
    earning: Decimal = Decimal(0)
    netEarning: Decimal = Decimal(0)


class DecoratedAssetOperation(AssetOperation):
    asset: Optional[DecoratedAssetOperationAssetInfo]

    netPrice: Decimal
    unitPrice: Optional[Decimal]

    openQuantity: Optional[Decimal]  # still open quantity part (0 means position is closed)
    profit: Optional[Decimal]
    netProfit: Optional[Decimal]
    totalNetProfit: Optional[Decimal]

    closedPositionInfo: Optional[ClosedPositionInfo]
    earningInfo: Optional[EarningInfo]

    @classmethod
    def make(cls, operation: AssetOperation):
        fields = operation.dict()
        fields['netPrice'] = operation.price
        if operation.currencyConversion:
            fields['netPrice'] *= operation.currencyConversion

        if operation.quantity:
            fields['unitPrice'] = operation.price / operation.quantity

        return cls(**fields)


class Operations(object):
    def __init__(self, currency:str):
        super(Operations, self).__init__();
        self.currency = currency

        self.results = []

    def __call__(self, operations:List[AssetOperation], asset=None):
        self.results = []

        for operation in operations:
            self.results.append(self._next(operation))

        if asset is not None:
            self._assetInfo(asset)

        return self.results

    def _next(self, operation):
        thisOp = DecoratedAssetOperation.make(operation)

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

    def _buy(self, operation):
        operation.openQuantity = operation.quantity

    # a RECEIVE is a BUY with a price 0, so just changing quantity
    def _receive(self, operation):
        operation.openQuantity = operation.quantity

    def _sell(self, operation):
        matchingPositions = [op for op in self.results if op.openQuantity and op.orderId == operation.orderId]

        closedPosInfo = ClosedPositionInfo()
        remainingQuantity = operation.quantity
        while remainingQuantity > 0 and matchingPositions:
            matchingPos = matchingPositions[0]
            closingQuantity = min(remainingQuantity, matchingPos.openQuantity)

            closedPosInfo.openingOperations.append(matchingPos)

            openPrice = matchingPos.price * (closingQuantity / matchingPos.quantity)
            closedPosInfo.matchingOpenPrice += openPrice
            closedPosInfo.matchingOpenNetPrice += (openPrice * matchingPos.currencyConversion if matchingPos.currencyConversion else openPrice)
            if matchingPos.provision:
                closedPosInfo.matchingOpenProvision += matchingPos.provision * (closingQuantity / matchingPos.quantity)

            matchingPos.openQuantity -= closingQuantity

            remainingQuantity -= closingQuantity
            matchingPositions = matchingPositions[1:]

        if remainingQuantity > 0:
            raise RuntimeError("SELL operation could not match orders")

        operation.closedPositionInfo = closedPosInfo

        operation.profit = operation.price - operation.closedPositionInfo.matchingOpenPrice
        operation.netProfit = operation.netPrice - operation.closedPositionInfo.matchingOpenNetPrice
        operation.totalNetProfit = operation.netProfit - operation.provision - operation.closedPositionInfo.matchingOpenProvision

    def _earning(self, operation):
        earning = EarningInfo()
        earning.earning = operation.price
        earning.netEarning = (operation.price * operation.currencyConversion if operation.currencyConversion else operation.price)
        operation.earningInfo = earning

        operation.profit = operation.earningInfo.earning
        operation.netProfit = operation.earningInfo.netEarning
        operation.totalNetProfit = operation.netProfit - operation.provision

    def _assetInfo(self, asset:Asset):
        assetData = {
            'id': asset.id,
            'name': asset.name,
            'type': asset.type,
            'institution': asset.institution,
            'currency': self.currency
        }

        assetInfo = DecoratedAssetOperationAssetInfo(**assetData)
        for operation in self.results:
            operation.asset = assetInfo
