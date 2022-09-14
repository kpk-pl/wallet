from flask import render_template, request
from flaskr import db, header, utils
from flaskr.session import Session
from flaskr.analyzers import Profits, Period, Operations
from flaskr.model import Asset
import time
from datetime import datetime, date
from bson.objectid import ObjectId
import itertools


def _getPipeline(startDate, finalDate, label = None):
    pipeline = []

    # include only those assets that were created up to finalDate
    match = {
        "operations": { "$exists": True, "$not": { "$size": 0 } },
        "operations.0.date": { '$lte': finalDate }
    }

    if label is not None:
        match['labels'] = label

    pipeline.append({ "$match" : match })
    pipeline.append({ "$addFields" : {
        "finalOperation": { "$last": "$operations" },
    }})

    # remove assets with last operation happening before startDate
    # and resulting in finalQuantity == 0
    pipeline.append({ "$match" : {
        "$or" : [
            {"finalOperation.finalQuantity" : { "$gt": 0 }},
            {"finalOperation.date" : { "$gte": startDate }}
        ]
    }})

    pipeline.append({ '$addFields': {
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
            rangeName = str(date.today().year)

        timerange = {
            'name': rangeName,
            'periodStart': datetime(int(rangeName), 1, 1),
            'periodEnd': min(datetime(int(rangeName) + 1, 1, 1), datetime.now())
        }

        weakAssets = list(db.get_db().assets.aggregate(
            _getPipeline(timerange['periodStart'], timerange['periodEnd'], session.label())))
        assets = [Asset(**a) for a in weakAssets]

        breakdown = sum([Operations(asset.currency.name)(asset.operations, asset) for asset in assets], [])
        breakdown = [op for op in breakdown if op.date >= timerange['periodStart'] and op.date <= timerange['periodEnd'] and (op.closedPositionInfo or op.earningInfo)]
        breakdown.sort(key=lambda op: op.date)

        profits = Profits()
        period = Period(timerange['periodStart'], timerange['periodEnd'])

        assetData = []
        for asset in assets:
            data = dict()

            data['asset'] = asset

            if session.isDebug():
                data['debug'] = dict(profits=dict(), period=dict())

            data['profits'] = profits(asset, debug=data['debug']['profits'] if session.isDebug() else None)
            data['period'] = period(asset, data['profits'], debug=data['debug']['period'] if session.isDebug() else None)

            if not data['period'].profits.isZero():
                assetData.append(data)

        return render_template("results/index.html",
                               assetData=assetData,
                               operationBreakdown=breakdown,
                               timerange=timerange,
                               header=header.data(showLabels=True)
                               )
