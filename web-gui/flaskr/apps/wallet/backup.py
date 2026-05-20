import io
import zipfile
from datetime import datetime

from bson.json_util import dumps, JSONOptions, JSONMode
from flask import send_file

from flaskr import db


def backup():
    database = db.get_db()
    jsonOptions = JSONOptions(json_mode=JSONMode.CANONICAL)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in db.COLLECTIONS:
            lines = (dumps(document, json_options=jsonOptions)
                     for document in database[name].find({}))
            archive.writestr('{}.json'.format(name), '\n'.join(lines))

    buffer.seek(0)
    filename = 'wallet_backup_{}.zip'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))

    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename,
    )
