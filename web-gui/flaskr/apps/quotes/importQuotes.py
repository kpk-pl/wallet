from flask import render_template, request, Response, json
from bson.objectid import ObjectId
from flaskr import db, header
from datetime import datetime
import dateutil.parser


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

        return render_template("import.html", quote=quoteItems[0], header=header.data())

    elif request.method == 'POST':
        quoteId = request.form.get('id')
        method = request.form.get('method')
        data = json.loads(request.form.get('data'))

        if not data:
            return ({"error": "The request has empty data"}, 500)

        for entry in data:
            entry['timestamp'] = datetime.utcfromtimestamp(entry['timestamp'] / 1e3)

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
        if len(fields) != 2:
            return ({}, 500)

        result.append({
            'timestamp': dateutil.parser.parse(fields[0]),
            'quote': float(fields[1])
        })

    return Response(json.dumps(result), mimetype="application/json")
