from flask import render_template, request
from flaskr import db
from datetime import datetime

def add():
    if request.method == 'GET':
        lastQuoteUpdateTime = db.last_quote_update_time()
        misc = {
            'lastQuoteUpdate': {
                'timestamp': lastQuoteUpdateTime,
                'daysPast': (datetime.now() - lastQuoteUpdateTime).days
            }
        }

        return render_template("add.html", misc=misc)
