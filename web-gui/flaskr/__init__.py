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

    from flaskr.apps.assets.views import assets
    app.register_blueprint(assets, url_prefix="/assets")

    from flaskr.apps.wallet.views import wallet
    app.register_blueprint(wallet, url_prefix="/wallet")

    from flaskr.apps.quotes.views import quotes
    app.register_blueprint(quotes, url_prefix="/quotes")

    from flaskr.handlers import quote, results

    app.add_url_rule('/quote', 'quote', quote.quote, methods=['GET', 'POST'])
    app.add_url_rule('/quote/add', 'quote.add', quote.quote_add, methods=['GET'])
    app.add_url_rule('/quote/import', 'quote.import', quote.quote_import, methods=['GET'])

    app.add_url_rule('/results/<int:year>', 'results', results.results, methods=['GET'])

    app.jinja_env.filters['withSign'] = lambda x: '+'+str(x) if x > 0 else x
    app.jinja_env.filters['toJson'] = _filter_toJson

    print(app.url_map)

    return app
