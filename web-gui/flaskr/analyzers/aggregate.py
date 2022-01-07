from itertools import groupby
from enum import Enum
import copy
from flaskr import typing


class AggregationType(str, Enum):
    pricing = 'p'
    name = 'n'


# https://stackoverflow.com/questions/5884066/hashing-a-dictionary
def make_hash(o):
    """
    makes a hash out of anything that contains only list,dict and hashable types including string and numeric types
    """
    def _freeze(o):
        if isinstance(o, dict):
            return frozenset({ k:_freeze(v) for k,v in o.items()}.items())
        if isinstance(o, (list)):
            return tuple([_freeze(v) for v in o])

        return str(o)
    return hash(_freeze(o))


def _key(aggregationType: AggregationType):
    if aggregationType == AggregationType.pricing:
        return lambda a: make_hash([a['pricing'] if 'pricing' in a else None, a['currency']])
    if aggregationType == AggregationType.name:
        return lambda a: make_hash([a['name'], a['currency']])


def _filter(aggregationType: AggregationType):
    if aggregationType == AggregationType.pricing:
        return None
    if aggregationType == AggregationType.name:
        return lambda a: 'pricing' not in a


def _asList(o, key=None):
    if isinstance(o, dict):
        if key in o:
            return _asList(o[key])
        return []
    if isinstance(o, list):
        return o
    return [o]


def _merge(lhs, rhs):
    assert 'pricing' not in lhs or 'pricing' not in rhs or lhs['pricing'] == rhs['pricing']
    assert lhs['currency'] == rhs['currency']

    result = copy.deepcopy(lhs)

    result['_id'] = list(set(_asList(lhs, '_id') + _asList(rhs, '_id')))
    result['institution'] = list(set(_asList(lhs, 'institution') + _asList(rhs, 'institution')))

    result['operations'] = sorted(_asList(lhs, 'operations') + _asList(rhs, 'operations'), key=lambda op: op['date'])
    finalQuantity = 0
    for operation in result['operations']:
        if 'quantity' in operation:
            finalQuantity = typing.Operation.adjustQuantity(operation['type'], finalQuantity, operation['quantity'])
        operation['finalQuantity'] = finalQuantity

    result['finalQuantity'] = finalQuantity

    return result


def aggregate(assets, type: AggregationType):
    filt = _filter(type)
    ignored = []
    if filt:
        assetsSorted = sorted(assets, key=filt)
        for key, group in groupby(assetsSorted, filt):
            if key:
                assets = list(group)
            else:
                ignored = list(group)

    key = _key(type)
    assets = sorted(assets, key=key)

    pos = 0
    while pos < len(assets)-1:
        if key(assets[pos]) != key(assets[pos+1]):
            pos += 1
            continue

        assets[pos] = _merge(assets[pos], assets[pos+1])
        del assets[pos+1]

    return ignored + assets
