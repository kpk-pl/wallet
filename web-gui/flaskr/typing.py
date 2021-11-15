class Operation:
    class Type:
        buy = 'BUY'
        sell = 'SELL'

        @staticmethod
        def reverse(op):
            if op == Operation.Type.buy:
                return Operation.Type.sell
            if op == Operation.Type.sell:
                return Operation.Type.buy

            raise RuntimeError("Invalid operation code provided")

    @staticmethod
    def adjustQuantity(op, initial, adjustment):
        if op == Operation.Type.buy:
            return initial + adjustment
        if op == Operation.Type.sell:
            return initial - adjustment

        raise RuntimeError("Invalid operation code provided")


class Currency:
    main = 'PLN'
    decimals = 2
