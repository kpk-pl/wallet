#!/usr/bin/env bash
set -e

source venv/bin/activate
export FLASK_APP=flaskr
export FLASK_ENV=development
flask run --port=5001
