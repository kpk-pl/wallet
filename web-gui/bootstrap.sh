#!/usr/bin/env bash
set -e

python3.7 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
