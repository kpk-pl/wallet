from flask import request, json, Response
from flaskr import db
from flaskr.quotes import getQuote
from bson.objectid import ObjectId


def quote():
    if request.method == 'GET':
        quoteUrl = request.args.get('url')
        response = getQuote(quoteUrl)
        return Response(json.dumps(response), mimetype="application/json")
