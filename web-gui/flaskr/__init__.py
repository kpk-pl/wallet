import os
from flask import Flask, request, url_for, json


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY = 'dev',
        SESSION_COOKIE_SAMESITE = "Strict",
        # EXPLAIN_TEMPLATE_LOADING = True,
        MONGO_USER = os.environ.get("MONGO_USER", ""),
        MONGO_PASS = os.environ.get("MONGO_PASS", ""),
        MONGO_HOST = os.environ.get("MONGO_HOST", "127.0.0.1"),
        MONGO_PORT = os.environ.get("MONGO_PORT", "27017"),
        MONGO_SESSIONS = True,
    )

    app.config.from_file('config.json', load=json.load)
    if test_config is not None:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from flaskr import db, typing
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

    @app.template_filter()
    def withSign(value):
        return '+' + str(value) if value > 0 else str(value)

    @app.template_filter()
    def toJson(data, indent=2):
        from bson.json_util import dumps, JSONOptions
        opts = JSONOptions(datetime_representation=2, json_mode=1)
        return dumps(data, indent=indent, json_options=opts)

    @app.template_filter()
    def nthField(iterable, n):
        return map(lambda e: e[n], iterable)

    @app.template_filter()
    def roundFixed(value, precision=2):
        return '{0:.{1}f}'.format(round(value, precision), precision)

    @app.template_filter()
    def asCurrency(value, currency, withSymbol=True):
        from babel.numbers import format_currency
        return format_currency(float(value), currency, format=u'#.##0.00 ¤¤' if withSymbol else u'#.##0.00')

    @app.template_filter()
    def operationDisplayString(operation, assetType):
        return typing.Operation.displayString(operation, assetType)

    @app.template_filter()
    def simplify(model):
        from flaskr.utils import simplifyModel
        return simplifyModel(model)

    @app.template_filter()
    def valueOr(optValue, default):
        if optValue is not None:
            return optValue
        return default

    @app.template_filter('zip')
    def zipFilter(a, b):
        return zip(a, b)

    @app.context_processor
    def urlProcessor():
        def url_for_self(**args):
            return url_for(request.endpoint, **dict(request.args, **args))
        return dict(url_for_self=url_for_self);

    @app.template_test(name='list')
    def isList(o):
        return isinstance(o, list)

    @app.context_processor
    def constants():
        return dict(
            resultsTimeranges = typing.Results.timeranges,
        )

    return app
