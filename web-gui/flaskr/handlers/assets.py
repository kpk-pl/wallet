from flask import render_template, request
from flaskr import db
from datetime import datetime


def assets():
    if request.method == 'GET':
        pipeline = [
            {
                "$addFields" : {
                    "finalQuantity": { "$last": "$operations.finalQuantity" }
                }
            },
            { "$unset" : ["quoteHistory", "operations"] }
        ]
        assets = list(db.get_db().assets.aggregate(pipeline))

        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }
        return render_template("assets.html", assets=assets, misc=misc)
