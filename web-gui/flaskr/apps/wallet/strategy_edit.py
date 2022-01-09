from flask import render_template, request, json

from flaskr import db, header
from flaskr.session import Session


def _lastStrategy(label = None):
    return [
        {'$match': {'label': label}},
        {'$sort': {'creationDate': -1}},
        {'$limit': 1},
        {'$project': {
            '_id': 0
        }}
    ]


def strategy_edit():
    if request.method == 'GET':
        session = Session(['label'])

        strategy = list(db.get_db().strategy.aggregate(_lastStrategy(session.label())))
        if not strategy:
            return '', 404

        return render_template("wallet/strategy_edit.html", strategy=json.dumps(strategy[0]), header=header.data(showLabels = True))
