from flask import render_template, request
from flaskr import db
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
            'cond': {'$lte': ['$$op.date', finalDate]}
        }}
    }})

    return pipeline


def index():
    finalDate = datetime(2021, 1, 1)
    startDate = datetime(2020, 1, 1)
    trueEnd = min(finalDate, datetime.now())

    if request.method == 'GET':
        debug = bool(request.args.get('debug'))

        assets = list(db.get_db().assets.aggregate(_getPipeline(startDate, finalDate)))
        assets = [Profits(asset)() for asset in assets]

        periodAnalyzer = Period(startDate, trueEnd)
        for asset in assets:
            periodAnalyzer(asset)

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'showData': debug,
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }
        return render_template("indexx.html", assets=assets, misc=misc)
