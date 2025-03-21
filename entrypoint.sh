#!/bin/bash
# ENTRYPOINT for the container.
# Activates virtualenv before running any commands.
set -e

# shellcheck disable=SC1091
. /venv/bin/activate

if [[ $# == 0 ]]; then
    exec mod_wsgi-express \
        start-server \
        /usr/share/resultsdb/resultsdb.wsgi \
        --user=apache \
        --group=apache \
        --processes="${MOD_WSGI_PROCESSES:-1}" \
        --threads="${MOD_WSGI_THREADS:-5}" \
        --port="${MOD_WSGI_PORT:-5001}" \
        --include-file=/etc/httpd/conf.d/resultsdb.conf \
        --log-level="${MOD_WSGI_LOG_LEVEL:-info}" \
        --log-to-terminal \
        --access-log \
        --startup-log
else
    exec "$@"
fi
