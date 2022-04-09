from collections import defaultdict


class Categories(object):
    def __init__(self):
        super(Categories, self).__init__()
        self.allocation = defaultdict(lambda: defaultdict(int))

    def __call__(self, assets):
        for asset in assets:
            category = asset['category']
            subcategory = asset['subcategory'] if 'subcategory' in asset else None

            if '_netValue' not in asset or asset['_netValue'] is None:
                raise RuntimeError(f"Could not determine '{asset['name']}' asset value for categories allocation engine")
            self.allocation[category][subcategory] += asset['_netValue']

        return self.allocation

    def fillStrategy(self, strategy):
        strategyAllocation = {}
        for category, subcategories in self.allocation.items():
            for subcategory, value in subcategories.items():
                name = (subcategory + ' ' if subcategory else '') + category
                strategyAllocation[name] = {'value': value, 'remainingShare': 100.0}

        for assetType in strategy['assetTypes']:
            assetType['_totalNetValue'] = 0.0
            for category in assetType['categories']:
                if isinstance(category, str):
                    if category in strategyAllocation:
                        assetType['_totalNetValue'] += strategyAllocation[category]['value']
                        strategyAllocation[category]['remainingShare'] -= 100.0
                else:
                    if category['name'] in strategyAllocation:
                        assetType['_totalNetValue'] += strategyAllocation[category['name']]['value'] * category['percentage'] / 100
                        strategyAllocation[category['name']]['remainingShare'] -= category['percentage']

        othersValue = sum(s['remainingShare'] * s['value'] / 100 for _, s in strategyAllocation.items() if isinstance(s, dict))
        if othersValue != 0:
            strategy['assetTypes'].append({'name': 'Others', 'percentage': 0, '_totalNetValue': othersValue})
