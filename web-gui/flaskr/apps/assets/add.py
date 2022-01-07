from flask import render_template, request
from flaskr import db, header


def _quotesListPipeline():
    return [
        {'$project': {
            '_id': 1,
            'name': 1,
            'unit': 1
        }},
        {
         '$sort': {
            'name': 1,
            'unit': 1
         }
        }
    ]


def add():
    if request.method == 'GET':
        quotesList = list(db.get_db().quotes.aggregate(_quotesListPipeline()))
        return render_template("assets/add.html", quotesList=quotesList, header=header.data())
