from flask import request, Response
from flaskr import db
from bson.objectid import ObjectId


def trash():
    if request.method == 'POST':
        quoteId = request.args.get('quoteId')
        if not quoteId:
            return ('', 400)

        query = {'_id': ObjectId(quoteId)}
        update = {'$set': {'trashed': True}}
        db.get_db().quotes.update(query, update)

        return Response()
