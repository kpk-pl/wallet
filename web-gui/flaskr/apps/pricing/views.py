from flask import Blueprint, request
from flask_accept import accept, accept_fallback


pricing = Blueprint('pricing', __name__, template_folder='templates', static_folder="static")


@pricing.route("/", methods=['GET', 'POST'])
@accept_fallback
def index():
    if request.args.get('quoteId'):
        from .item import item
        return item("text")
    else:
        from .listAll import listAll
        return listAll()


@pricing.route("/trash", methods=['POST'])
def trash():
    from .trash import trash
    return trash()


@index.support('application/json')
def index_json():
    from .item import item
    return item("json")


@pricing.route("/add", methods=['GET'])
def add():
    from .add import add
    return add()
