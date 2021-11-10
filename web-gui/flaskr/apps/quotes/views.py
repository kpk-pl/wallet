from flask import Blueprint


quotes = Blueprint('quotes', __name__, template_folder='templates/quotes')

@quotes.route("/", methods=['GET', 'PUT'])
def index():
    from .index import index
    return index()


@quotes.route("/import", methods=['GET', 'POST'])
def importQuotes():
    from .importQuotes import importQuotes
    return importQuotes()


@quotes.route("/import/csvUpload", methods=['POST'])
def csvUpload():
    from .importQuotes import csvUpload
    return csvUpload()
