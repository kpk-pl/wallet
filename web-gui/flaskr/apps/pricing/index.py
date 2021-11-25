from flask import request, render_template
from flaskr import db, header


def _getPipeline():
    return [
        {'$project': {
            '_id': 1,
            'name': 1,
            'url': 1,
            'unit': 1,
            'lastQuote': {'$last': '$quoteHistory'}
        }}
    ]

def index():
    if request.method == 'GET':
        sources = list(db.get_db().quotes.aggregate(_getPipeline()))

        return render_template("pricing_index.html", sources=sources, header=header.data())
