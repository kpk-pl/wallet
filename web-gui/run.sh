#!/usr/bin/env bash
set -e

source venv/bin/activate
export FLASK_APP=src/main.py
flask run
