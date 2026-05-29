from flask import render_template, request, Response, json
from flaskr import db, header
from flaskr.apps.quotes.list import listIds as listActiveQuoteIds
from flaskr.model import Quote
from bson.objectid import ObjectId


def _getPipeline(quoteId, trimmedDown):
    pipeline = []
    pipeline.append({'$match' : { '_id' : ObjectId(quoteId) }})

    # Project a full Quote-shaped document so the result can be wrapped in the
    # Quote model. The JSON listing only needs the last quote, so trim history
    # to its last entry there; the detail page renders the full chart.
    projection = {
        '_id': 1,
        'name': 1,
        'urls': 1,
        'url': 1,
        'unit': 1,
        'ticker': 1,
        'trashed': 1,
        'updateFrequency': 1,
        'currencyPair': 1,
        'quoteHistory': {'$slice': ['$quoteHistory', -1]} if trimmedDown else '$quoteHistory',
    }

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

        doc = quotes[0]
        model = Quote(**doc)

        if type == "json":
            last = model.lastQuote
            payload = {
                'name': model.name,
                'url': model.url,
                'unit': model.unit,
                'lastQuote': float(last.quote) if last else 0,
            }
            return Response(json.dumps(payload), mimetype="application/json")
        else:
            # `quoteHistory` is forwarded verbatim to the chart JS as a raw
            # list of {timestamp, quote: float} dicts so ApexCharts gets
            # native numbers through |tojson. The Quote model supplies what
            # the rest of the template reads (item.lastQuote, item.currencyPair, …).
            return render_template("pricing/item.html",
                                   item=model,
                                   active=ObjectId(quoteId) in listActiveQuoteIds(used=True),
                                   quoteHistory=doc.get('quoteHistory', []),
                                   header=header.data())
    else:
        return '', 405
