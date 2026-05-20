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
