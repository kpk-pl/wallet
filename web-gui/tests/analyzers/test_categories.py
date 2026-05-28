import pytest
from decimal import Decimal as D

from flaskr.analyzers import Categories, CategoryEntry


def test_groups_by_category_and_subcategory():
    entries = [
        CategoryEntry(name="A", category="Equities", subcategory="EU", netValue=D(100)),
        CategoryEntry(name="B", category="Equities", subcategory="EU", netValue=D(50)),
        CategoryEntry(name="C", category="Equities", subcategory="US", netValue=D(200)),
        CategoryEntry(name="D", category="Cash", subcategory=None, netValue=D(10)),
    ]

    allocation = Categories()(entries)

    assert allocation["Equities"]["EU"] == D(150)
    assert allocation["Equities"]["US"] == D(200)
    assert allocation["Cash"][None] == D(10)


def test_raises_when_netvalue_missing():
    entries = [
        CategoryEntry(name="Broken", category="Equities", subcategory=None, netValue=None),
    ]

    with pytest.raises(RuntimeError, match="Broken"):
        Categories()(entries)


def test_fill_strategy_raises_when_allocations_overlap():
    categories = Categories()
    categories([
        CategoryEntry(name="A", category="Equities", subcategory="US", netValue=D(100)),
    ])

    strategy = {'assetTypes': [
        {'name': 'Bucket 1', 'categories': ['US Equities']},
        {'name': 'Bucket 2', 'categories': ['US Equities']},
    ]}

    with pytest.raises(RuntimeError, match="US Equities"):
        categories.fillStrategy(strategy)


def test_fill_strategy_raises_when_partial_allocations_exceed_full():
    categories = Categories()
    categories([
        CategoryEntry(name="A", category="Equities", subcategory="US", netValue=D(100)),
    ])

    strategy = {'assetTypes': [
        {'name': 'Bucket 1', 'categories': [{'name': 'US Equities', 'percentage': 70}]},
        {'name': 'Bucket 2', 'categories': [{'name': 'US Equities', 'percentage': 40}]},
    ]}

    with pytest.raises(RuntimeError, match="US Equities"):
        categories.fillStrategy(strategy)


def test_fill_strategy_others_bucket_for_partially_unallocated_category():
    categories = Categories()
    categories([
        CategoryEntry(name="A", category="Equities", subcategory="US", netValue=D(100)),
    ])

    strategy = {'assetTypes': [
        {'name': 'Bucket 1', 'categories': [{'name': 'US Equities', 'percentage': 60}]},
    ]}

    categories.fillStrategy(strategy)

    others = [a for a in strategy['assetTypes'] if a['name'] == 'Others']
    assert len(others) == 1
    assert others[0]['_totalNetValue'] == D(40)
