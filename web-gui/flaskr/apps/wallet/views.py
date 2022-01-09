from flask import Blueprint
from flask_accept import accept, accept_fallback


wallet = Blueprint('wallet', __name__, template_folder='templates', static_folder='static')

@wallet.route("/", methods=['GET'])
def index():
    from .wallet import wallet
    return wallet()


@wallet.route('/strategy', methods=['GET', 'POST'])
@accept_fallback
def strategy():
    from .strategy import strategy
    return strategy()


@strategy.support('application/json')
def strategy_json():
    from .strategy import strategy_json
    return strategy_json()


@wallet.route('/strategy/edit', methods=['GET'])
def strategy_edit():
    from .strategy_edit import strategy_edit
    return strategy_edit()
