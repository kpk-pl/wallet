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

            raise RuntimeError(f"Cannot reverse operation {op}")

    @staticmethod
    def adjustQuantity(op, initial, adjustment):
        if op == Operation.Type.buy:
            return initial + adjustment
        if op == Operation.Type.sell:
            return initial - adjustment
        if op == Operation.Type.receive:
            return initial + adjustment
        if op == Operation.Type.earning:
            return initial

        raise RuntimeError(f"Cannot adjust operation {op}")

    @staticmethod
    def displayString(op, assetType):
        if assetType == 'Deposit':
            if op == Operation.Type.buy:
                return 'DEPOSIT'
            if op == Operation.Type.sell:
                return 'WITHDRAW'
        elif assetType == 'Equity':
            if op == Operation.Type.earning:
                return 'DIVIDEND'

        return op


class Currency:
    main = 'PLN'
    decimals = 2


class Results:
    firstYear = 2019

    @staticmethod
    def timeranges():
        import datetime
        return [str(y) for y in range(Results.firstYear, datetime.date.today().year +1)]
