import pytest
import mongomock
import pymongo
import tests
from bson.objectid import ObjectId
from tests.fixtures import client


MAXIMAL_ASSET_ADD_DATA_QUOTE_ID = ObjectId()
MAXIMAL_ASSET_ADD_DATA = dict(
    link = "http://stooq.pl/q/?s=test",
    name = "Test asset",
    ticker = "TST",
    currency = "PLN",
    priceQuoteId = str(MAXIMAL_ASSET_ADD_DATA_QUOTE_ID),
    institution = "Test Bank",
    type = "Equity",
    labels = "longterm,notsmart",
    category = "Equities",
    subcategory = "Emerging Markets",
    region = "World",
)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_add_with_all_possible_info(client):
    rv = client.post(f"/assets", data=MAXIMAL_ASSET_ADD_DATA, follow_redirects=True)
    assert rv.status_code == 200
    assert 'id' in rv.json

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        dbAsset = db.wallet.assets.find_one({'_id': ObjectId(rv.json['id'])})

        expected = {k:v for (k,v) in MAXIMAL_ASSET_ADD_DATA.items()}
        expected['_id'] = ObjectId(rv.json['id'])
        expected['currency'] = {"name": expected['currency']}
        expected['labels'] = expected['labels'].split(',')
        expected['pricing'] = {"quoteId": MAXIMAL_ASSET_ADD_DATA_QUOTE_ID}
        del expected['priceQuoteId']

        assert dbAsset == expected
