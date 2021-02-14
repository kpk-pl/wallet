class AssetGroup(object):
    def __init__(self, op):
        super(AssetGroup, self).__init__()
        self.operation = op

        self.quantity = self.operation['quantity']
        self.pricePerOne = self.operation['price'] / float(self.quantity)
        self._provision = self.operation['provision'] if 'provision' in self.operation else 0.0
        self._provisionPerOne = self._provision / float(self.quantity)

    def provision(self, quantity):
        return quantity * self._provisionPerOne

    def netPrice(self, quantity):
        result = quantity * self.pricePerOne
        if 'currencyConversion' in self.operation:
            result *= self.operation['currencyConversion']
        return result


class Analyzer(object):
    def __init__(self, assetData):
        super(Analyzer, self).__init__()
        self.data = assetData

        self.data['_investmentStart'] = self.data['operations'][0]['date']
        self.data['_investmentEnd'] = self.data['operations'][-1]['date'] if self.data['finalQuantity'] != 0 else ""

        self._realisedGains = []
        self._calculateRealisedGain()

    def addQuoteInfo(self, currencies):
        if 'lastQuote' in self.data and self.data['lastQuote'] is not None:
            self.data['_netValue'] = self.data['finalQuantity'] * self.data['lastQuote']['quote']
        else:
            self.data['_netValue'] = self.data['_unrealisedInvestment']

        if self.data['currency'] != 'PLN':
            currencyConv = currencies[self.data['currency']]['quote']
            self.data['_netValue'] *= currencyConv

    def _calculateRealisedGain(self):
        buyGroups = []

        for op in self.data['operations']:
            if op['type'] == 'BUY':
                buyGroups.append(AssetGroup(op))
            elif op['type'] == 'SELL':
                self._realiseGain(op, buyGroups)
                op['_realisedGain'] = self._realisedGains[-1]

        self.data['_unrealisedProvision'] = sum([g.provision(g.quantity) for g in buyGroups])
        self.data['_unrealisedInvestment'] = sum([g.netPrice(g.quantity) for g in buyGroups])

        self.data['_realisedGain'] = sum([rg['netGain'] for rg in self._realisedGains])
        self.data['_realisedProvision'] = sum([rg['provisions'] for rg in self._realisedGains])

        assert(abs(self.data['finalQuantity'] - sum([g.quantity for g in buyGroups]) < 1e-6))

    def _realiseGain(self, operation, buyGroups):
        opGroup = AssetGroup(operation)

        self._realisedGains.append({
            "date": operation["date"],
            "netGain": 0.0,
            "provisions": opGroup.provision(opGroup.quantity)
        })

        while opGroup.quantity > 0:
            quantity = min(opGroup.quantity, buyGroups[0].quantity)
            self._realisedGains[-1]['netGain'] += opGroup.netPrice(quantity) - buyGroups[0].netPrice(quantity)
            self._realisedGains[-1]['provisions'] += buyGroups[0].provision(quantity)

            if quantity >= buyGroups[0].quantity:
                opGroup.quantity -= buyGroups[0].quantity
                del buyGroups[0]
            else:
                buyGroups[0].quantity -= quantity
                return

