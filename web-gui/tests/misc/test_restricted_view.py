import pytest
import mongomock
import pymongo
import tests
from bson.objectid import ObjectId
from flaskr import create_app, labels
from tests.mocks import Asset


def _makeClient(allowedLabels):
    app = create_app({"TESTING": True,
                      "MONGO_HOST": tests.MONGO_TEST_HOST,
                      "MONGO_PORT": str(tests.MONGO_TEST_PORT),
                      "MONGO_SESSIONS": False,
                      "ALLOWED_LABELS": allowedLabels,
                      })
    return app.test_client()


@pytest.fixture
def client():
    with _makeClient("kids, retirement") as client:
        yield client


@pytest.fixture
def singleLabelClient():
    with _makeClient("kids") as client:
        yield client


def _equity(name, assetLabels):
    asset = Asset.createEquity()
    asset['name'] = name
    if assetLabels:
        asset['labels'] = assetLabels
    return asset.pricing().quantity(1).commit()


def _deposit(name, assetLabels):
    asset = Asset.createDeposit()
    asset['name'] = name
    if assetLabels:
        asset['labels'] = assetLabels
    return asset.quantity(100).commit()


def _commitThree():
    return dict(
        kids=_equity("Kids fund", ["kids"]),
        mixed=_equity("Shared fund", ["kids", "secret"]),
        private=_equity("Private fund", ["secret"]),
        unlabelled=_equity("Unlabelled fund", None),
    )


def _storedAsset(assetId):
    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        return db.wallet.assets.find_one({'_id': assetId})


def test_parse_allowed_labels():
    assert labels.parseAllowedLabels(None) is None
    assert labels.parseAllowedLabels("") is None
    assert labels.parseAllowedLabels(" , ") is None
    assert labels.parseAllowedLabels("b, a,,b ") == ["a", "b"]
    assert labels.parseAllowedLabels(["x"]) == ["x"]


def test_allowed_labels_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_LABELS", "kids")
    app = create_app({"TESTING": True})
    assert app.config['ALLOWED_LABELS'] == ["kids"]
    assert app.config['SESSION_COOKIE_NAME'] != 'session'


def test_unrestricted_by_default(monkeypatch):
    monkeypatch.delenv("ALLOWED_LABELS", raising=False)
    app = create_app({"TESTING": True})
    assert app.config['ALLOWED_LABELS'] is None
    assert app.config['SESSION_COOKIE_NAME'] == 'session'


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("url", ["/wallet/", "/assets/", "/results/"])
def test_lists_show_only_allowed_assets(client, url):
    _commitThree()

    rv = client.get(url, follow_redirects=True)
    assert rv.status_code == 200
    assert b'Kids fund' in rv.data or url == "/results/"
    assert b'Private fund' not in rv.data
    assert b'Unlabelled fund' not in rv.data
    # The tag picker in the header only offers allowed tags.
    assert b'secret' not in rv.data


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_asset_list_hides_other_tags_of_visible_asset(client):
    _commitThree()

    rv = client.get("/assets/")
    assert rv.status_code == 200
    assert b'Shared fund' in rv.data
    assert b'secret' not in rv.data


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_disallowed_label_in_url_is_forbidden(client):
    _commitThree()

    for url in ["/wallet/?label=secret", "/assets/?label=secret", "/results/?label=secret",
                "/wallet/strategy?label=secret", "/assets/historicalValue?label=secret"]:
        rv = client.get(url)
        assert rv.status_code == 403, url


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_allowed_label_filter_still_works(client):
    _commitThree()
    _equity("Retirement fund", ["retirement"])

    rv = client.get("/assets/?label=retirement")
    assert rv.status_code == 200
    assert b'Retirement fund' in rv.data
    assert b'Kids fund' not in rv.data


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_historical_value_covers_only_allowed_assets(client):
    ids = _commitThree()

    rv = client.get("/assets/historicalValue?daysBack=5&investedValue=True")
    assert rv.status_code == 200
    names = {asset['name'] for asset in rv.get_json()['assets']}
    assert names == {"Kids fund", "Shared fund"}

    # Asking for a hidden asset by id does not reveal it either.
    rv = client.get(f"/assets/historicalValue?daysBack=5&investedValue=True&id={ids['private']}")
    assert rv.get_json()['assets'] == []


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
@pytest.mark.parametrize("url", ["/assets/?id={}", "/assets/edit?id={}", "/assets/receipt?id={}",
                                 "/assets/receipt/edit?id={}&index=0"])
def test_hidden_asset_pages_are_not_found(client, url):
    ids = _commitThree()

    if url != "/assets/?id={}":  # the details page uses a $lookup mongomock lacks
        assert client.get(url.format(ids['kids'])).status_code == 200
    assert client.get(url.format(ids['private'])).status_code in (400, 404)
    assert client.get(url.format(ids['unlabelled'])).status_code in (400, 404)


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_hidden_asset_cannot_be_modified(client):
    ids = _commitThree()

    rv = client.post(f"/assets/trash?id={ids['private']}")
    assert rv.status_code == 404
    assert 'trashed' not in _storedAsset(ids['private'])

    rv = client.post(f"/assets/receipt?id={ids['private']}",
                     data=dict(date="2020-01-01", type="BUY", quantity="1", price="1"))
    assert rv.status_code == 400
    assert len(_storedAsset(ids['private'])['operations']) == 1

    rv = client.post(f"/assets/edit?id={ids['private']}",
                     data=dict(name="X", type="Equity", institution="X", category="Equities", labels="kids"))
    assert rv.status_code == 404
    assert _storedAsset(ids['private'])['name'] == "Private fund"


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_visible_asset_can_be_trashed(client):
    ids = _commitThree()

    rv = client.post(f"/assets/trash?id={ids['kids']}")
    assert rv.status_code == 200
    assert _storedAsset(ids['kids'])['trashed'] is True


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_receipt_offers_and_accepts_only_allowed_billing_deposits(client):
    ids = _commitThree()
    visibleCash = _deposit("Kids cash", ["kids"])
    hiddenCash = _deposit("Secret cash", ["secret"])

    rv = client.get(f"/assets/receipt?id={ids['kids']}")
    assert rv.status_code == 200
    assert b'Kids cash' in rv.data
    assert b'Secret cash' not in rv.data

    form = dict(date="2020-01-01", type="BUY", quantity="1", price="10")
    rv = client.post(f"/assets/receipt?id={ids['kids']}", data=dict(form, billingAsset=str(hiddenCash)))
    assert rv.status_code == 400
    assert rv.get_json()['code'] == 203

    rv = client.post(f"/assets/receipt?id={ids['kids']}", data=dict(form, billingAsset=str(visibleCash)))
    assert rv.status_code == 200


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_keeps_hidden_tags_and_rejects_disallowed_ones(client):
    ids = _commitThree()
    form = dict(name="Shared fund", type="Equity", institution="Bank of Mocks", category="Equities", region="World")

    rv = client.get(f"/assets/edit?id={ids['mixed']}")
    assert rv.status_code == 200
    assert b'secret' not in rv.data

    rv = client.post(f"/assets/edit?id={ids['mixed']}", data=dict(form, labels="kids,retirement"))
    assert rv.status_code == 200
    assert _storedAsset(ids['mixed'])['labels'] == ["kids", "retirement", "secret"]

    rv = client.post(f"/assets/edit?id={ids['mixed']}", data=dict(form, labels="kids,other"))
    assert rv.status_code == 400
    assert rv.get_json()['code'] == 13

    # Removing every allowed tag would make the asset disappear from this view.
    rv = client.post(f"/assets/edit?id={ids['mixed']}", data=dict(form, labels=""))
    assert rv.status_code == 400
    assert rv.get_json()['code'] == 13
    assert _storedAsset(ids['mixed'])['labels'] == ["kids", "retirement", "secret"]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_add_requires_allowed_tag(client):
    form = dict(name="New", type="Equity", institution="Bank", category="Equities", currency="PLN")

    rv = client.post("/assets/", data=form)
    assert rv.status_code == 400
    assert rv.get_json()['code'] == 13

    rv = client.post("/assets/", data=dict(form, labels="kids,secret"))
    assert rv.status_code == 400
    assert rv.get_json()['code'] == 13

    rv = client.post("/assets/", data=dict(form, labels="kids"))
    assert rv.status_code == 200
    assert _storedAsset(ObjectId(rv.get_json()['id']))['labels'] == ["kids"]


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_backup_is_forbidden(client):
    rv = client.get("/wallet/backup")
    assert rv.status_code == 403

    rv = client.get("/wallet/")
    assert b'/wallet/backup' not in rv.data


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_strategy_scoped_to_labels(client):
    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        db.wallet.strategy.insert_one(dict(creationDate=1, label=None, assetTypes=[{'name': 'global'}]))
        db.wallet.strategy.insert_one(dict(creationDate=1, label='kids', assetTypes=[{'name': 'kidsStrategy'}]))

    json = {"Accept": "application/json"}

    rv = client.get("/wallet/strategy", headers=json)
    assert rv.status_code == 200
    assert 'strategy' not in rv.get_json()

    rv = client.get("/wallet/strategy?label=kids", headers=json)
    assert rv.get_json()['strategy']['assetTypes'] == [{'name': 'kidsStrategy'}]

    rv = client.post("/wallet/strategy", data="[]")
    assert rv.status_code == 403

    rv = client.post("/wallet/strategy?label=secret", data="[]")
    assert rv.status_code == 403

    rv = client.post("/wallet/strategy?label=kids", data="[]")
    assert rv.status_code == 201


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_single_allowed_label_is_always_selected(singleLabelClient):
    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        db.wallet.strategy.insert_one(dict(creationDate=1, label='kids', assetTypes=[{'name': 'kidsStrategy'}]))

    rv = singleLabelClient.get("/wallet/strategy", headers={"Accept": "application/json"})
    assert rv.status_code == 200
    assert rv.get_json()['strategy']['assetTypes'] == [{'name': 'kidsStrategy'}]

    rv = singleLabelClient.post("/wallet/strategy", data="[]")
    assert rv.status_code == 201
