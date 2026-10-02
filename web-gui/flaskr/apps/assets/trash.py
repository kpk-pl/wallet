from flask import render_template, request, Response
from flaskr import db
from flaskr import labels as access
from bson.objectid import ObjectId


def trash():
    if request.method == 'POST':
        assetId = request.args.get('id')
        if not assetId:
            return ('', 400)

        query = {'_id': ObjectId(assetId)}
        access.requireAssetVisible(db.get_db().assets.find_one(query, {'labels': 1}))
        update = {'$set': {'trashed': True}}
        db.get_db().assets.update_one(query, update)

        return Response()
