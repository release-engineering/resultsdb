#!/bin/bash
set -e
uv run resultsdb init_alembic
uv run resultsdb init_db
uv run resultsdb mock_data
