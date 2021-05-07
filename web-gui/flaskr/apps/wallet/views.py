from flask import Blueprint


wallet = Blueprint('wallet', __name__, template_folder='templates/wallet')

@wallet.route("/", methods=['GET'])
def index():
    from .index import index
    return index()
