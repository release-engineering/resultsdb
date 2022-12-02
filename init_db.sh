#!/bin/bash
set -e
poetry run resultsdb init_alembic
poetry run resultsdb init_db
poetry run resultsdb mock_data
