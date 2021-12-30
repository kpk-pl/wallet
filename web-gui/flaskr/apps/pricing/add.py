from flask import render_template
from flaskr import header


def add():
    return render_template("pricing/add.html", header=header.data())
