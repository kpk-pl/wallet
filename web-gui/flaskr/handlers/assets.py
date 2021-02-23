from flask import render_template, request
from flaskr import db


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
        return render_template("assets.html", assets=assets)
