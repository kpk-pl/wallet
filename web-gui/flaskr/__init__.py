import os
from flask import Flask


def _filter_toJson(data):
    from bson.json_util import dumps
    content = dumps(data, indent=2)
    return content


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    #app.config.from_mapping(
    #    SECRET_KEY='dev'
    #)

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from flaskr import db
    db.init_app(app)

    from flaskr.handlers import assets, asset, wallet, quotes, quote, results

    app.add_url_rule('/wallet', 'wallet', wallet.wallet, methods=['GET'])

    app.add_url_rule('/assets', 'assets', assets.assets, methods=['GET'])

    app.add_url_rule('/asset', 'asset', asset.asset, methods=['GET', 'POST'])
    app.add_url_rule('/asset/add', 'asset.add', asset.asset_add, methods=['GET'])
    app.add_url_rule('/asset/receipt', 'asset.receipt', asset.asset_receipt, methods=['GET', 'POST'])
    app.add_url_rule('/asset/historicalValue', 'asset.historicalValue', asset.asset_historicalValue, methods=['GET'])
    app.add_url_rule('/asset/importQuotes', 'asset.importQuotes', asset.asset_importQuotes, methods=['GET', 'POST'])

    app.add_url_rule('/quotes', 'quotes', quotes.quotes, methods=['GET', 'PUT'])

    app.add_url_rule('/quote', 'quote', quote.quote, methods=['GET', 'POST'])
    app.add_url_rule('/quote/add', 'quote.add', quote.quote_add, methods=['GET'])
    app.add_url_rule('/quote/import', 'quote.import', quote.quote_import, methods=['GET'])

    app.add_url_rule('/results/<int:year>', 'results', results.results, methods=['GET'])

    app.jinja_env.filters['withSign'] = lambda x: '+'+str(x) if x > 0 else x
    app.jinja_env.filters['toJson'] = _filter_toJson

    return app
