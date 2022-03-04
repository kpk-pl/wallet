import pymongo
from flask import current_app, g


def get_db():
    if 'db' not in g:
        url = 'mongodb://{}:{}@{}:{}'.format(current_app.config["MONGO_USER"],
                                             current_app.config["MONGO_PASS"],
                                             current_app.config["MONGO_HOST"],
                                             current_app.config["MONGO_PORT"])
        mongo = pymongo.MongoClient(url)
        g.db = mongo.wallet

    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.client.close()


def init_app(app):
    app.teardown_appcontext(close_db)
