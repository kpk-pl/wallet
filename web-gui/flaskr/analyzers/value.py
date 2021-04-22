from . import _valueOr
from flaskr.pricing import Pricing

class Value(object):
    def __init__(self, assetData, currencyQuotes):
        super(Value, self).__init__()
        self.data = assetData
        self.currencyQuotes = currencyQuotes

    def __call__(self):
        if 'pricing' in self.data:
            self.data['_netValue'] = Pricing(self.data['pricing']).priceAsset(self.data['operations'])
        elif 'lastQuote' in self.data and self.data['lastQuote'] is not None:
            self.data['_netValue'] = self.data['finalQuantity'] * self.data['lastQuote']['quote']
        else:
            self.data['_netValue'] = self.data['_stillInvestedNetValue']

        if self.data['currency'] != 'PLN':
            currencyConv = self.currencyQuotes[self.data['currency']]['quote']
            self.data['_netValue'] *= currencyConv

        return self.data
