from flask import render_template, request
from flaskr import db, header, utils
from flaskr.session import Session
from flaskr.analyzers import Profits, Period
from flaskr.model import Asset, AssetOperation
import time
from datetime import datetime, date
from bson.objectid import ObjectId
import itertools
from dataclasses import dataclass


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


@dataclass
class AssetData:
    asset: Asset
    profits: Profits.Result
    period: Period.Result
    debug: dict


@dataclass
class BreakdownElement:
    asset: Asset
    operation: AssetOperation
    breakdown: Profits.Result.Breakdown


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

        pipeline = _getPipeline(timerange['periodStart'], timerange['periodEnd'], session.label())
        assets = [Asset(**a) for a in db.get_db().assets.aggregate(pipeline)]

        profitsAnalyzer = Profits()
        periodAnalyzer = Period(timerange['periodStart'], timerange['periodEnd'])

        assetData = []
        for asset in assets:
            debug = None
            if session.isDebug():
                debug = dict(profits=dict(), period=dict())

            profits = profitsAnalyzer(asset, debug=debug['profits'] if session.isDebug() else None)
            period = periodAnalyzer(asset, profits, debug=debug['period'] if session.isDebug() else None)

            if not period.profits.isZero():
                assetData.append(AssetData(asset, profits, period, debug))

        operationsBreakdown = []
        for data in assetData:
            for op, bdown in zip(data.asset.operations, data.profits.breakdown):
                if op.date >= timerange['periodStart'] and op.date <= timerange['periodEnd'] and bdown.profit > 0:
                    operationsBreakdown.append(BreakdownElement(data.asset, op, bdown))


        return render_template("results/index.html",
                               assetData=assetData,
                               operationsBreakdown=operationsBreakdown,
                               timerange=timerange,
                               header=header.data(showLabels=True)
                               )
