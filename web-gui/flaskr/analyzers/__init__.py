def _valueOr(dictionary, key, default):
    return dictionary[key] if key in dictionary else default

def _operationNetValue(operation):
    return operation['price'] * _valueOr(operation, 'currencyConversion', 1.0)

def _printJson(data):
    from bson.json_util import dumps
    print(dumps(data, indent=2))


from .operations import Operations
from .profits import Profits
from .period import Period
from .categories import Categories
