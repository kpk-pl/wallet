from flask import render_template, request, Response, json
from flaskr import db, header
from flaskr.apps.quotes.list import listIds as listActiveQuoteIds
from flaskr.model import Quote
from bson.objectid import ObjectId


def _getPipeline(quoteId, trimmedDown):
    pipeline = []
    pipeline.append({'$match' : { '_id' : ObjectId(quoteId) }})

    projection = {
        '_id': 0,
        'name': 1,
        'url': 1,
        'unit': 1,
        'lastQuote': { '$ifNull': [{ '$last': '$quoteHistory.quote' }, 0] },
    }
    if not trimmedDown:
        projection.update({
            '_id': 1,
            'ticker': 1,
            'stooqSymbol': 1,
            'trashed': 1,
            'quoteHistory': 1,
            'updateFrequency': 1,
            'currencyPair': 1
        })

    pipeline.append({'$project' : projection})
    return pipeline


def item(type):
    if request.method == 'GET':
        quoteId = request.args.get('quoteId')
        if not quoteId:
            return ('', 400)

        quotes = list(db.get_db().quotes.aggregate(_getPipeline(quoteId, type == "json")))
        if not quotes:
            return ('', 404)

        if type == "json":
            return Response(json.dumps(quotes[0]), mimetype="application/json")
        else:
            doc = quotes[0]
            # `quoteHistory` is forwarded verbatim to the chart JS as a raw
            # list of {timestamp, quote: float} dicts so ApexCharts gets
            # native numbers through |tojson. The Quote-wrapped copy is what
            # the rest of the template reads (item.lastQuote, item.currencyPair, …).
            return render_template("pricing/item.html",
                                   item=Quote(**doc),
                                   active=ObjectId(quoteId) in listActiveQuoteIds(used=True),
                                   quoteHistory=doc.get('quoteHistory', []),
                                   header=header.data())
    else:
        return '', 405
