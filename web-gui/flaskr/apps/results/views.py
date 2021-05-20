from flask import Blueprint


results = Blueprint('results', __name__, template_folder='templates/results')

@results.route("/", methods=['GET'])
def index():
    from .index import index
    return index()
