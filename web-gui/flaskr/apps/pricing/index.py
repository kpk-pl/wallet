from flask import request, render_template
from flaskr import db
from datetime import datetime


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

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("index_pricing.html", sources=sources, misc=misc)
