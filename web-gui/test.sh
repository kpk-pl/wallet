#!/usr/bin/env bash
set -e

source venv/bin/activate
pytest -s -W ignore::DeprecationWarning
