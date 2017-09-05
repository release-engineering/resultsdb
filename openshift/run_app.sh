#!/bin/bash
set -x
set -e

# initialize db (in a non-destructive manner)
env resultsdb init_db

exec mod_wsgi-express start-server /usr/share/resultsdb/resultsdb.wsgi \
    --user apache --group apache \
    --port 5001 --threads 5 \
    --include-file /etc/httpd/conf.d/resultsdb.conf \
    --log-level info \
    --log-to-terminal \
    --access-log \
    --startup-log
