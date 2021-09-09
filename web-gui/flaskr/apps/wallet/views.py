from flask import Blueprint
from flask_accept import accept, accept_fallback


wallet = Blueprint('wallet', __name__, template_folder='templates/wallet')

@wallet.route("/", methods=['GET'])
def index():
    from .index import index
    return index()


@wallet.route('/strategy', methods=['GET'])
@accept_fallback
def strategy():
    from .strategy import strategy
    return strategy()


@strategy.support('application/json')
def strategy_json():
    from .strategy import strategy_json
    return strategy_json()
