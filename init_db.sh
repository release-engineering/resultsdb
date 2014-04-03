#!/usr/bin/bash
# this is a simple script to aid in the setup of a new db for F18

# init db
python run_cli.py init_db

# insert mock data
python run_cli.py mock_data
