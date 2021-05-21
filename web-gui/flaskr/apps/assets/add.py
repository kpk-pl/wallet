from flask import render_template, request
from flaskr import db
from datetime import datetime


def _quotesListPipeline():
    return [
        {'$project': {
            '_id': 1,
            'name': 1,
            'unit': 1
        }}
    ]


def add():
    if request.method == 'GET':
        quotesList = list(db.get_db().quotes.aggregate(_quotesListPipeline()))

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("add.html", quotesList=quotesList, misc=misc)
