#!/bin/bash
set -euo pipefail

export DOCKER_HOST=unix:///run/user/$UID/resultsdb-podman.sock
podman system service --time=0 "$DOCKER_HOST" &
trap "kill $!" QUIT TERM INT HUP EXIT
sleep 1

tox "$@"
