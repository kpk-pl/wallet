from flask import render_template
from flaskr import header
from flaskr.model.quote import QuoteUpdateFrequency


def add():
    data = dict(
        updateFrequencies = [f.name for f in QuoteUpdateFrequency],
    )
    return render_template("pricing/add.html", header=header.data(), data=data)
