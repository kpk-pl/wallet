#!/usr/bin/env bash
set -e

source venv/bin/activate
export FLASK_APP=flaskr
export FLASK_ENV=development
export MONGO_HOST=192.168.101.132
flask run --port=5001
