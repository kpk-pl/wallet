import pytest
import mongomock
import pymongo
import tests
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
@pytest.mark.parametrize("url", ["/assets/?id={}", "/assets/receipt?id={}"])
def test_hidden_asset_pages_are_not_found(client, url):
    ids = _commitThree()

    if url != "/assets/?id={}":  # the details page uses a $lookup mongomock lacks
        assert client.get(url.format(ids['kids'])).status_code == 200
    assert client.get(url.format(ids['private'])).status_code == 404
    assert client.get(url.format(ids['unlabelled'])).status_code == 404


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_operation_can_be_recorded_only_for_visible_asset(client):
    ids = _commitThree()
    form = dict(date="2020-01-01", type="BUY", quantity="1", price="1")

    rv = client.post(f"/assets/receipt?id={ids['private']}", data=form)
    assert rv.status_code == 400
    assert len(_storedAsset(ids['private'])['operations']) == 1

    rv = client.post(f"/assets/receipt?id={ids['kids']}", data=form)
    assert rv.status_code == 200
    assert len(_storedAsset(ids['kids'])['operations']) == 2


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_assets_cannot_be_added_edited_or_trashed(client):
    ids = _commitThree()
    form = dict(name="X", type="Equity", institution="X", category="Equities", region="World",
                currency="PLN", labels="kids")

    for method, url in [("get", "/assets/add"),
                        ("post", "/assets/"),
                        ("get", f"/assets/edit?id={ids['kids']}"),
                        ("post", f"/assets/edit?id={ids['kids']}"),
                        ("post", f"/assets/trash?id={ids['kids']}"),
                        ("get", f"/assets/receipt/edit?id={ids['kids']}&index=0"),
                        ("post", f"/assets/receipt/edit?id={ids['kids']}&index=0")]:
        rv = getattr(client, method)(url, data=form if method == "post" else None)
        assert rv.status_code == 403, (method, url)

    stored = _storedAsset(ids['kids'])
    assert stored['name'] == "Kids fund"
    assert 'trashed' not in stored
    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        assert db.wallet.assets.count_documents({}) == 4


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_edit_controls_are_hidden(client):
    _commitThree()

    rv = client.get("/assets/")
    assert b'/assets/add' not in rv.data

    rv = client.get("/wallet/strategy")
    assert b'/wallet/strategy/edit' not in rv.data

    rv = client.get("/wallet/strategy?label=kids")
    assert b'/wallet/strategy/edit' in rv.data


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
@pytest.mark.parametrize("method,url", [("get", "/pricing/"), ("get", "/pricing/add"), ("get", "/quotes/"),
                                        ("put", "/quotes/"), ("get", "/quotes/import"),
                                        ("get", "/pricing/static/pricing/add.js")])
def test_pricing_and_quotes_are_hidden(client, method, url):
    rv = getattr(client, method)(url)
    assert rv.status_code == 404


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_pricing_tab_and_feed_errors_are_hidden(client):
    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        import datetime
        db.wallet.price_feed_errors.insert_one(dict(name="Feed", timestamp=datetime.datetime.now(), error="boom"))

    rv = client.get("/wallet/")
    assert rv.status_code == 200
    assert b'/pricing/' not in rv.data
    assert b'id="priceFeedErrorIndicator"' not in rv.data


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

    # The unlabelled strategy and strategies of hidden tags stay untouchable.
    for url in ["/wallet/strategy", "/wallet/strategy?label=secret"]:
        assert client.post(url, data="[]").status_code == 403, url
    for url in ["/wallet/strategy/edit", "/wallet/strategy/edit?label=secret"]:
        assert client.get(url).status_code == 403, url

    assert client.get("/wallet/strategy/edit?label=kids").status_code == 200
    assert client.post("/wallet/strategy?label=kids", data="[]").status_code == 201

    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        assert db.wallet.strategy.count_documents({'label': None}) == 1
        assert db.wallet.strategy.count_documents({'label': 'kids'}) == 2


@mongomock.patch(servers=[tests.MONGO_TEST_SERVER])
def test_single_allowed_label_is_always_selected(singleLabelClient):
    _commitThree()
    with pymongo.MongoClient(tests.MONGO_TEST_SERVER) as db:
        db.wallet.strategy.insert_one(dict(creationDate=1, label='kids', assetTypes=[{'name': 'kidsStrategy'}]))

    rv = singleLabelClient.get("/wallet/strategy", headers={"Accept": "application/json"})
    assert rv.status_code == 200
    assert rv.get_json()['strategy']['assetTypes'] == [{'name': 'kidsStrategy'}]

    assert singleLabelClient.post("/wallet/strategy", data="[]").status_code == 201

    rv = singleLabelClient.get("/assets/")
    assert rv.status_code == 200
    assert b'badge-success mr-1">kids' in rv.data
