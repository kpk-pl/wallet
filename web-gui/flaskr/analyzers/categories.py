from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass
class CategoryEntry:
    name: str
    category: str
    subcategory: Optional[str]
    netValue: Optional[Decimal]


class Categories(object):
    def __init__(self):
        super(Categories, self).__init__()
        self.allocation = defaultdict(lambda: defaultdict(int))

    def __call__(self, entries: List[CategoryEntry]):
        for entry in entries:
            if entry.netValue is None:
                raise RuntimeError(f"Could not determine '{entry.name}' asset value for categories allocation engine")
            self.allocation[entry.category][entry.subcategory] += entry.netValue

        return self.allocation

    def fillStrategy(self, strategy):
        strategyAllocation = {}
        for category, subcategories in self.allocation.items():
            for subcategory, value in subcategories.items():
                name = (subcategory + ' ' if subcategory else '') + category
                strategyAllocation[name] = {'value': value, 'remainingShare': Decimal(100)}

        for assetType in strategy['assetTypes']:
            assetType['_totalNetValue'] = Decimal(0)
            for category in assetType['categories']:
                if isinstance(category, str):
                    name, share = category, Decimal(100)
                else:
                    name, share = category['name'], Decimal(str(category['percentage']))

                if name not in strategyAllocation:
                    continue

                bucket = strategyAllocation[name]
                if share > bucket['remainingShare']:
                    raise RuntimeError(
                        f"Strategy over-allocates '{name}': cumulative share exceeds 100%"
                    )
                assetType['_totalNetValue'] += bucket['value'] * share / 100
                bucket['remainingShare'] -= share

        othersValue = sum((s['remainingShare'] * s['value'] / 100 for s in strategyAllocation.values()), Decimal(0))
        if othersValue != 0:
            strategy['assetTypes'].append({'name': 'Others', 'percentage': 0, '_totalNetValue': othersValue})
