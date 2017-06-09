#!/bin/bash
set -x
set -e

# initialize db (in a non-destructive manner)
env resultsdb init_db
# run ResultsDB
env run_resultsdb
