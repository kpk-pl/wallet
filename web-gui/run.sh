#!/usr/bin/env bash
set -e

source venv/bin/activate
export FLASK_APP=src/main.py
export FLASK_ENV=development
flask run
