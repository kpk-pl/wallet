from flask import Blueprint, request


pricing = Blueprint('pricing', __name__, template_folder='templates/pricing')

@pricing.route("/", methods=['GET'])
def index():
    if request.args.get('quoteId'):
        from .item import item
        return item()
    else:
        from .index import index
        return index()
