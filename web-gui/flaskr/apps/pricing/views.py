from flask import Blueprint, request


pricing = Blueprint('pricing', __name__, template_folder='templates', static_folder="static")

@pricing.route("/", methods=['GET', 'POST'])
def index():
    if request.args.get('quoteId'):
        from .item import item
        return item()
    else:
        from .listAll import listAll
        return listAll()

@pricing.route("/add", methods=['GET'])
def add():
    from .add import add
    return add()
