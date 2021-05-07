from flask import render_template, request
from flaskr import db
from datetime import datetime


def listAll():
    if request.method == 'GET':
        pipeline = [
            { "$match" : { 'trashed': { '$ne' : True } } },
            { "$project" : {
                '_id': 1,
                'name': 1,
                'ticker': 1,
                'institution': 1,
                'type': 1,
                'category': 1,
                'subcategory': 1,
                'region': 1,
                'quantity': 1,
                'link': 1,
                'finalQuantity': { "$last": "$operations.finalQuantity" }
            }}
        ]
        assets = list(db.get_db().assets.aggregate(pipeline))

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }
        return render_template("list.html", assets=assets, misc=misc)
