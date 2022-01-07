from flask import Blueprint, request


assets = Blueprint('assets', __name__, template_folder='templates', static_folder='static')


@assets.route("/", methods=['GET'])
def index():
    if request.args.get('id'):
        from .item import item
        return item()
    else:
        from .list import listAll
        return listAll()


@assets.route("/", methods=["POST"])
def index_post():
    from .list import post
    return post()


@assets.route("/add", methods=['GET'])
def add():
    from .add import add
    return add()


@assets.route("/receipt", methods=['GET', 'POST'])
def receipt():
    from .receipt import receipt
    return receipt()


@assets.route("/trash", methods=['POST'])
def trash():
    from .trash import trash
    return trash()


@assets.route("/historicalValue", methods=['GET'])
def historicalValue():
    from .historicalValue import historicalValue
    return historicalValue()
