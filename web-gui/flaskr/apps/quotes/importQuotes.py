from flask import render_template, request, Response, json
from bson.objectid import ObjectId
from pymongo.errors import OperationFailure
from flaskr import db, header
from flaskr.model import Quote
from flaskr.quotes.fetchers.justetf import JustETF
from flaskr.quotes.fetchers.base import FetchError
from datetime import datetime
import dateutil.parser


def _onlineSources(quote):
    sources = []
    if JustETF.identify(quote.urls):
        sources.append('justetf')
    return sources


def _getPipeline(quoteId):
    pipeline = []
    pipeline.append({ "$match" : { "_id" : ObjectId(quoteId) } })
    pipeline.append({ "$project": {
        '_id': 1,
        'name': 1,
        'urls': 1,
        'url': 1,
        'unit': 1,
        'updateFrequency': 1,
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

        quote = Quote(**quoteItems[0])
        # `quoteHistory` is forwarded as the raw list of {timestamp, quote}
        # dicts so the chart JS gets native values through |tojson; the Quote
        # model supplies everything else (name, url, id, unit).
        return render_template("quotes/import.html", quote=quote,
                               quoteHistory=quoteItems[0].get('quoteHistory', []),
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

        def callback(session=None):
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


        try:
            with db.get_db().client.start_session() as session:
                session.with_transaction(callback)
        except OperationFailure as e:
            # Standalone MongoDB deployments don't support multi-document
            # transactions; fall back to sequential (non-atomic) updates.
            if e.code != 20:  # IllegalOperation: "Transaction numbers are only allowed..."
                raise
            callback()

        return ({"ok": True}, 200)


def csvUpload():
    if 'file' not in request.files:
        return ({}, 500)

    lines = [line.decode().strip() for line in request.files.get('file')]
    lines = [line for line in lines if line]
    if not lines:
        return ({}, 500)

    header = lines[0].split(',')
    # Stooq daily-history CSV: "Data,Otwarcie,Najwyzszy,Najnizszy,Zamkniecie,Wolumen".
    # Recognise it by its header and import the close price ("Zamkniecie").
    if 'Data' in header and 'Zamkniecie' in header:
        dateIdx, quoteIdx = header.index('Data'), header.index('Zamkniecie')
        rows = lines[1:]
    else:
        # Plain headerless two-column CSV: "<timestamp-or-date>,<quote>".
        dateIdx, quoteIdx = 0, 1
        rows = lines

    result = []
    for line in rows:
        fields = line.split(',')
        if len(fields) <= max(dateIdx, quoteIdx):
            return ({}, 500)

        dateField = fields[dateIdx]
        timestamp = datetime.utcfromtimestamp(int(dateField)) if dateField.isdigit() else dateutil.parser.parse(dateField)
        result.append({
            'timestamp': timestamp,
            'quote': float(fields[quoteIdx])
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

    doc = db.get_db().quotes.find_one({'_id': ObjectId(quoteId)}, {'quoteHistory': 0})
    if not doc:
        return ({"error": "Quote not found"}, 404)
    quote = Quote(**doc)

    if source == 'justetf':
        isin = JustETF.identify(quote.urls)
        if not isin:
            return ({"error": "No justETF ISIN available for this quote"}, 400)
        fetcher = JustETF("https://www.justetf.com/en/etf-profile.html?isin={}".format(isin))
    else:
        return ({"error": "Unknown import source"}, 400)

    try:
        history = fetcher.fetchHistory(fromDate, toDate, unit=quote.unit)
    except FetchError as e:
        return ({"error": e.msg}, 502)

    result = [{'timestamp': item.timestamp, 'quote': float(item.quote)} for item in history]
    return Response(json.dumps(result), mimetype="application/json")
