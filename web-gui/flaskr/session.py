from flask import request, session


class Session:
    def __init__(self, fields):
        for field in fields:
            self._readField(field)

    def isDebug(self):
        return self._getField('debug')

    def label(self):
        return self._getField('label')

    def _readField(self, name):
        value = request.args.get(name)
        if value:
            session[name] = value
        else:
            if name in session:
                session.pop(name)

    def _getField(self, name):
        return session.get(name)

