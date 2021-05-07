from flask import render_template, request, Response
from flaskr import db
from bson.objectid import ObjectId


def trash():
    if request.method == 'POST':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        query = {'_id': ObjectId(assetId)}
        update = {'$set': {'trashed': True}}
        db.get_db().assets.update(query, update)

        return Response()
