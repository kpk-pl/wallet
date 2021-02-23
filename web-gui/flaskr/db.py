from pymongo import MongoClient
from flask import current_app, g
import os


def get_db():
    if 'db' not in g:
        mongo = MongoClient('mongodb://{}:{}@{}:{}'.format(os.environ.get("MONGO_USER", "investing"),
                                                           os.environ.get("MONGO_PASS", "investing"),
                                                           os.environ.get("MONGO_HOST", "127.0.0.1"),
                                                           os.environ.get("MONGO_PORT", "27017")))
        g.db = mongo.wallet

    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.client.close()


def init_app(app):
    app.teardown_appcontext(close_db)
