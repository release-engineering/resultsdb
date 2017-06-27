#!/bin/bash
set -x
set -e

# initialize db (in a non-destructive manner)
env resultsdb init_db
# run ResultsDB
env gunicorn --bind 0.0.0.0:5001 --access-logfile=- resultsdb.wsgi
