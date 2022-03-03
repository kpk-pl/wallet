from bson.objectid import ObjectId
import tests
import datetime
import pymongo


class _DictLike(object):
    def __init__(self):
        super(_DictLike, self).__init__()
        self._data = {}

    def asdict(self):
        return self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, val):
        self._data[key] = val


class PricingSource(_DictLike):
    def __init__(self, id=None):
        super(PricingSource, self).__init__()
        if isinstance(id, ObjectId):
            self._data['_id'] = id

    def unit(self, value):
        self._data['unit'] = value
        return self

    def commit(self):
        with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
            return db.wallet.quotes.insert_one(self.asdict()).inserted_id

    @classmethod
    def createSimple(cls, id=None):
        result = cls(id)

        result['name'] = "Simple price source"
        result['url'] = "http://te.st"
        result['unit'] = "PLN"

        return result

    @classmethod
    def createCurrencyPair(cls, currency="USD", id=None):
        result = cls(id)

        result['name'] = "Currency price source"
        result['url'] = "http://te.st"
        result['unit'] = "PLN"
        result['currencyPair'] = {"from": "PLN", "to": currency}

        return result


class Asset(_DictLike):
    def __init__(self, id=None):
        super(Asset, self).__init__()
        if isinstance(id, ObjectId):
            self._data['_id'] = id

    def pricing(self, quoteId = None):
        if not quoteId:
            quoteId = PricingSource.createSimple().commit()
        self.pricing = {"quoteId": quoteId}
        return self

    def quantity(self, quantity):
        self._data['operations'] = [dict(
            type = 'BUY',
            date = datetime.datetime(1970, 1, 1),
            quantity = quantity,
            finalQuantity = quantity,
            price = 1
        )]
        return self

    def currency(self, currency, quoteId = None):
        if not quoteId:
            quoteId = PricingSource.createCurrencyPair(currency).commit()
        self._data['currency'] = dict(
            name = currency,
            quoteId = quoteId,
        )
        return self

    def hasOrderIds(self):
        self._data['hasOrderIds'] = True
        return self

    def commit(self):
        with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
            return db.wallet.assets.insert_one(self.asdict()).inserted_id

    @classmethod
    def createEquity(cls, id=None):
        result = cls(id)

        result['name'] = "Test equity"
        result['ticker'] = "TEQ"
        result['type'] = "Equity"
        result['category'] = "Equities"
        result['region'] = "World"
        result['institution'] = "Bank of Mocks"
        result['currency'] = {"name": "PLN"}

        return result

    @classmethod
    def createDeposit(cls, id=None):
        result = cls(id)

        result['name'] = "Cash"
        result['type'] = "Deposit"
        result['category'] = "Cash"
        result['institution'] = "Bank of Mocks"
        result['currency'] = {"name": "PLN"}

        return result
