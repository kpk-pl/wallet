from flask import request, Blueprint


quotes = Blueprint('quotes', __name__, template_folder='templates', static_folder='static')

@quotes.route("/", methods=['GET', 'PUT'])
def index():
    if request.args.get('url'):
        from .index import indexOne
        return indexOne()
    else:
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
