from enum import Enum
from decimal import Decimal
from bson.decimal128 import Decimal128


class Operation:
    class Type:
        buy = 'BUY'
        sell = 'SELL'
        receive = 'RECEIVE'
        earning = 'EARNING'

        @staticmethod
        def reverse(op):
            if op == Operation.Type.buy:
                return Operation.Type.sell
            if op == Operation.Type.sell:
                return Operation.Type.buy
            if op == Operation.Type.earning:
                return Operation.Type.buy  # cash earnings can be deposited

            raise RuntimeError(f"Cannot reverse operation {op}")

    @staticmethod
    def _simplifyDecimal(val:int|Decimal|Decimal128):
        # float is intentionally not accepted: Decimal(0.1) materializes the binary
        # float's exact representation (0.1000000000000000055...) and silently
        # corrupts any money calculation downstream. Route floats through
        # Decimal(str(v)) at the call site if you really must.
        if isinstance(val, Decimal128):
            return val.to_decimal()
        if isinstance(val, int):
            return val
        return Decimal(val)

    @staticmethod
    def adjustQuantity(op:str,
                       initial:int|Decimal|Decimal128,
                       adjustment:int|Decimal|Decimal128):
        def add(initial:int|Decimal, adjustment:int|Decimal):
            if op == Operation.Type.buy:
                return initial + adjustment
            if op == Operation.Type.sell:
                return initial - adjustment
            if op == Operation.Type.receive:
                return initial + adjustment
            if op == Operation.Type.earning:
                return initial
            raise RuntimeError(f"Cannot adjust operation {op}")

        return add(Operation._simplifyDecimal(initial), Operation._simplifyDecimal(adjustment))

    @staticmethod
    def adjustBillingQuantity(op:str,
                              initial:int|Decimal|Decimal128,
                              provision:int|Decimal|Decimal128):
        # Mirrors adjustQuantity but answers a different question: how a provision
        # on the original op shifts the cash flow posted to the billing deposit.
        # The EARNING branch is the only real divergence — on the asset side a
        # dividend doesn't change the share count, but on the billing side the
        # provision is withholding tax and reduces the net cash arriving.
        initial = Operation._simplifyDecimal(initial)
        provision = Operation._simplifyDecimal(provision)

        if op == Operation.Type.buy:
            return initial + provision
        if op == Operation.Type.sell:
            return initial - provision
        if op == Operation.Type.earning:
            return initial - provision
        raise RuntimeError(f"Cannot adjust billing for operation {op}")

    @staticmethod
    def displayString(op, assetType):
        if isinstance(op, Enum):
            op = op.value

        if assetType == 'Deposit':
            if op == Operation.Type.buy:
                return 'DEPOSIT'
            if op == Operation.Type.sell:
                return 'WITHDRAW'
        elif assetType == 'Equity':
            if op == Operation.Type.earning:
                return 'DIVIDEND'

        return op


class Results:
    firstYear = 2019

    @staticmethod
    def timeranges():
        import datetime
        return [str(y) for y in range(Results.firstYear, datetime.date.today().year +1)]


class CurrencyConversion:
    @staticmethod
    def staticRate(ffrom:str, to:str):
        from decimal import Decimal
        if ffrom == to:
            return Decimal(1)
        if ffrom == 'GBP' and to == 'GBX':
            return Decimal(100)
        if ffrom == 'GBX' and to == 'GBP':
            return Decimal("0.01")
        raise NotImplementedError(f"Static conversion rate from {ffrom} to {to} is not implemented")

    @staticmethod
    def staticConvert(ffrom:str, to:str, value):
        if ffrom == to:
            return value
        value = Operation._simplifyDecimal(value)
        if ffrom == 'GBP' and to == 'GBX':
            return value * 100
        if ffrom == 'GBX' and to == 'GBP':
            return value / 100
        raise NotImplementedError(f"Static conversion rate from {ffrom} to {to} is not implemented")
