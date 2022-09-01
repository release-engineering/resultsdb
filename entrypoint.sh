#!/bin/bash
# ENTRYPOINT for the container.
# Activates virtualenv before running any commands.
set -e

# shellcheck disable=SC1091
. /venv/bin/activate
exec "$@"
