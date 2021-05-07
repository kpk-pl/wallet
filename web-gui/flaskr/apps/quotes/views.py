from flask import Blueprint


quotes = Blueprint('quotes', __name__, template_folder='templates/quotes')

@quotes.route("/", methods=['GET', 'PUT'])
def index():
    from .index import index
    return index()
