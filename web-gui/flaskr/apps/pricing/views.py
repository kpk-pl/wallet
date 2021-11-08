from flask import Blueprint


pricing = Blueprint('pricing', __name__, template_folder='templates/pricing')

@pricing.route("/", methods=['GET'])
def index():
    from .index import index
    return index()


@pricing.route("/importQuotes", methods=['GET', 'POST'])
def importQuotes():
    from .importQuotes import importQuotes
    return importQuotes()
