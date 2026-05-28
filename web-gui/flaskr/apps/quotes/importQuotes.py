from flask import render_template, request, Response, json
from bson.objectid import ObjectId
from flaskr import db, header
from flaskr.quotes.fetchers.stooq import Stooq
from flaskr.quotes.fetchers.justetf import JustETF
from flaskr.quotes.fetchers.base import FetchError
from datetime import datetime
import dateutil.parser


def _onlineSources(quote):
    sources = []
    if Stooq.identify(quote):
        sources.append('stooq')
    if JustETF.identify(quote):
        sources.append('justetf')
    return sources


def _getPipeline(quoteId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(quoteId) } })
    pipeline.append({ "$project": {
        '_id': 1,
        'name': 1,
        'stooqSymbol': 1,
        'url': 1,
        'unit': 1,
        'quoteHistory': 1
    }})
    return pipeline


def importQuotes():
    if request.method == 'GET':
        quoteId = request.args.get('id')
        if not quoteId:
            return ('', 400)

        quoteItems = list(db.get_db().quotes.aggregate(_getPipeline(quoteId)))
        if not quoteItems:
            return ('', 404)

        quote = quoteItems[0]
        return render_template("quotes/import.html", quote=quote,
                               onlineSources=_onlineSources(quote), header=header.data())

    elif request.method == 'POST':
        quoteId = request.form.get('id')
        method = request.form.get('method')
        rawData = json.loads(request.form.get('data'))

        if not rawData:
            return ({"error": "The request has empty data"}, 500)

        data = [dict(
            timestamp = datetime.utcfromtimestamp(entry['x'] / 1e3),
            quote = entry['y'],
        ) for entry in rawData]

        data.sort(key=lambda e: e['timestamp'])

        def callback(session):
            query = {'_id': ObjectId(quoteId)}

            if method == 'replace':
                update = {'$pull': {'quoteHistory': {
                    '$and': [
                        {'timestamp': {'$gte': data[0]['timestamp']}},
                        {'timestamp': {'$lte': data[-1]['timestamp']}}
                    ]
                }}}
                db.get_db().quotes.update_one(query, update, session=session);

            update = {'$push': { 'quoteHistory': {
                    '$each': data,
                    '$sort': {'timestamp': 1}
            }}}
            db.get_db().quotes.update_one(query, update, session=session);


        with db.get_db().client.start_session() as session:
            session.with_transaction(callback)

        return ({"ok": True}, 200)


def csvUpload():
    if 'file' not in request.files:
        return ({}, 500)

    result = []
    for csvLine in request.files.get('file'):
        fields = csvLine.decode().strip().split(',')
        if len(fields) < 2:
            return ({}, 500)

        timestamp = datetime.utcfromtimestamp(int(fields[0])) if fields[0].isdigit() else dateutil.parser.parse(fields[0])
        result.append({
            'timestamp': timestamp,
            'quote': float(fields[1])
        })

    return Response(json.dumps(result), mimetype="application/json")


def historyImport():
    quoteId = request.args.get('id')
    source = request.args.get('source')
    if not quoteId:
        return ({"error": "Missing quote id"}, 400)

    try:
        fromDate = dateutil.parser.parse(request.args.get('from'))
        toDate = dateutil.parser.parse(request.args.get('to'))
    except (TypeError, ValueError):
        return ({"error": "Invalid or missing date range"}, 400)

    quote = db.get_db().quotes.find_one({'_id': ObjectId(quoteId)}, {'stooqSymbol': 1, 'url': 1})
    if not quote:
        return ({"error": "Quote not found"}, 404)

    if source == 'stooq':
        symbol = Stooq.identify(quote)
        if not symbol:
            return ({"error": "No Stooq symbol available for this quote"}, 400)
        fetcher = Stooq("https://stooq.pl/q/l/?s={}".format(symbol))
    elif source == 'justetf':
        isin = JustETF.identify(quote)
        if not isin:
            return ({"error": "No justETF ISIN available for this quote"}, 400)
        fetcher = JustETF("https://www.justetf.com/en/etf-profile.html?isin={}".format(isin))
    else:
        return ({"error": "Unknown import source"}, 400)

    try:
        history = fetcher.fetchHistory(fromDate, toDate)
    except FetchError as e:
        return ({"error": e.msg}, 502)

    result = [{'timestamp': item.timestamp, 'quote': float(item.quote)} for item in history]
    return Response(json.dumps(result), mimetype="application/json")
