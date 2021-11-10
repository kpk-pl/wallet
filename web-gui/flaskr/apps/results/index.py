from flask import render_template, request
from flaskr import db, header
from flaskr.session import Session
from flaskr.analyzers.profits import Profits
from flaskr.analyzers.period import Period
import time
from datetime import datetime, date
from bson.objectid import ObjectId


def _getPipeline(startDate, finalDate):
    pipeline = []

    # include only those assets that were created up to finalDate
    pipeline.append({ '$match': { "operations.0.date": {'$lte': finalDate}}})

    # TODO: maybe filter assets that ended before startDate, ie finalQuantity is 0 and/or is marked as trashed

    pipeline.append({ '$project': {
        '_id': 1,
        'name': 1,
        'ticker': 1,
        'institution': 1,
        'currency': 1,
        'link': 1,
        'category': 1,
        'subcategory': 1,
        'pricing': 1,
        'trashed': 1,
        'operations': { '$filter': {
            'input': '$operations',
            'as': 'op',
            'cond': {'$lt': ['$$op.date', finalDate]}
        }}
    }})

    return pipeline


def index():
    if request.method == 'GET':
        session = Session(['label', 'debug'])
        rangeName = request.args.get('timerange')
        if not rangeName:
            rangeName = date.today().year

        timerange = {
            'name': rangeName,
            'periodStart': datetime(int(rangeName), 1, 1),
            'periodEnd': min(datetime(int(rangeName) + 1, 1, 1), datetime.now())
        }

        assets = list(db.get_db().assets.aggregate(_getPipeline(timerange['periodStart'], timerange['periodEnd'])))
        assets = [Profits(asset)() for asset in assets]

        periodAnalyzer = Period(timerange['periodStart'], timerange['periodEnd'], debug=session.isDebug())
        for asset in assets:
            periodAnalyzer(asset)

        return render_template("indexx.html", assets=assets, timerange=timerange, header=header.data(showLabels = True))
