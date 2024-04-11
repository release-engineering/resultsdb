#!/bin/bash
set -euo pipefail

podman_service_pid=""
cleanup() {
    podman ps --filter 'name=resultsdb-.*' --format '{{.Names}}' |
        xargs --no-run-if-empty podman rm --force
    if [[ -n "$podman_service_pid" ]]; then
        kill "$podman_service_pid"
    fi
}

cleanup
trap cleanup QUIT TERM INT HUP EXIT

export DOCKER_HOST=unix:///run/user/$UID/resultsdb-podman.sock
podman system service --time=0 "$DOCKER_HOST" &
podman_service_pid=$!
sleep 1

tox "$@"
