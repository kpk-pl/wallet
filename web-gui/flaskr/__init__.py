from flask import Flask, request, url_for
import os
from flaskr import typing


def _filter_toJson(data, indent=2):
    from bson.json_util import dumps, JSONOptions
    opts = JSONOptions(datetime_representation=2, json_mode=1)
    content = dumps(data, indent=indent, json_options=opts)
    return content


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY = 'dev',
        SESSION_COOKIE_SAMESITE = "Strict",
        # EXPLAIN_TEMPLATE_LOADING = True
    )

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

    from flaskr.apps.results.views import results
    app.register_blueprint(results, url_prefix="/results")

    from flaskr.apps.pricing.views import pricing
    app.register_blueprint(pricing, url_prefix="/pricing")

    app.jinja_env.filters['withSign'] = lambda x: '+'+str(x) if x > 0 else x
    app.jinja_env.filters['toJson'] = _filter_toJson

    def url_for_self(**args):
        return url_for(request.endpoint, **dict(request.args, **args))

    app.jinja_env.globals['url_for_self'] = url_for_self

    @app.context_processor
    def constants():
        return dict(
            currencyMain = typing.Currency.main,
            currencyMainDecimals = typing.Currency.decimals
        )

    print(app.url_map)

    return app
