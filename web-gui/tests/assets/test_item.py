import mongomock
import tests
from bson.objectid import ObjectId
from flaskr.apps.assets import item
from tests.fixtures import client
from tests.mocks import Asset


def _pipelineWithoutQuotes(assetId):
    # mongomock does not implement $lookup with 'let', so skip joining quotes
    return [
        { "$match" : { "_id" : ObjectId(assetId) } },
        { "$addFields" : { "quoteInfo" : [] } },
    ]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_foreign_currency_deposit_without_operations_renders(client, monkeypatch):
    monkeypatch.setattr(item, "_getPipelineForAssetDetails", _pipelineWithoutQuotes)
    assetId = Asset.createDeposit().currency("USD").commit()

    rv = client.get(f"/assets/?id={assetId}")
    assert rv.status_code == 200
    assert b'Average conversion rate' in rv.data
