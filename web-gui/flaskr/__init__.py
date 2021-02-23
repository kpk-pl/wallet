import os
from flask import Flask


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

    from flaskr.handlers import assets, asset, wallet, quotes, quote
    app.add_url_rule('/wallet', 'wallet', wallet.wallet, methods=['GET'])
    app.add_url_rule('/assets', 'assets', assets.assets, methods=['GET'])
    app.add_url_rule('/asset', 'asset', asset.asset, methods=['POST'])
    app.add_url_rule('/asset/add', 'asset.add', asset.asset_add, methods=['GET'])
    app.add_url_rule('/asset/receipt', 'asset.receipt', asset.asset_receipt, methods=['GET', 'POST'])
    app.add_url_rule('/quotes', 'quotes', quotes.quotes, methods=['GET', 'PUT'])
    app.add_url_rule('/quote', 'quote', quote.quote, methods=['GET'])

    return app
