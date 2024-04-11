# ResultsDB

![logo of ResultsDB](https://pagure.io/taskotron/resultsdb/raw/develop/f/logo.png)

## What is ResultsDB

ResultsDB is a results store engine for (not only) Fedora QA tools.

The API v2 documentation can be found at
<http://docs.resultsdb20.apiary.io/>.

## Repositories

* ResultsDB Frontend - [GIT repo](https://pagure.io/taskotron/resultsdb_frontend)
* ResultsDB Client Library - [GIT repo](https://pagure.io/taskotron/resultsdb_api)

## Quick development setup

If you encounter any installation issues, it's possible that you don't have
`gcc` and necessary C development headers installed to compile C extensions
from PyPI. Either install those based on the error messages, or install
the necessary packages directly to your system. See `requirements.txt` to
learn how.

Install the project:

    $ poetry run python -m ensurepip --upgrade
    $ poetry install

Initialize your database:

    $ DEV=true poetry run ./init_db.sh

Run the server:

    $ DEV=true poetry run python runapp.py

The server is now running with a very simple frontend at <http://localhost:5001>.
API calls can be sent to <http://localhost:5001/api/v2.0>. All data is stored
inside `/var/tmp/resultsdb_db.sqlite`.

## Adjusting configuration

You can configure this app by copying `conf/settings.py.example` into
`conf/setting.py` and adjusting values as you see fit. It overrides default
values in `resultsdb/config.py`.

## Using with libtaskotron

You might want to use this tool together with libtaskotron. To use your own
*ResultsDB* server in libtaskotron, edit `/etc/taskotron/taskotron.yaml` and
set the following value:

    resultsdb_server: http://localhost:5001/api/v2.0

You might also need to adjust `reporting_enabled` and `report_to_resultsdb`,
depending on your local settings.

## Using real-life data from Fedora Infra dumps

Sometimes, you might want to check some performance tweaks with real-life data.
The easy solution might be using our daily dumps and a Postgres instance in Docker:

    docker run --name postgres_resultsdb -e POSTGRES_USER=resultsdb -e POSTGRES_PASSWORD=resultsdb -d -p 65432:5432 postgres
    wget https://infrastructure.fedoraproject.org/infra/db-dumps/resultsdb.dump.xz
    xzcat resultsdb.dump.xz | docker exec -i postgres_resultsdb psql -Uresultsdb

Then just change your config (for DEV environment, you can use `conf/settings.py` file)
to contain this db connector:

    SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://resultsdb:resultsdb@localhost:65432/resultsdb'

And run as usual.

## Running test suite

After making changes run `tox -e black-format` to reformat the code.

You can run the test suite with the following command:

    $ tox

Note, that in order for some of the tests to work properly, tox is configured to spin-up PostgreSQL in a docker container using the
`tox-docker` plugin installed automatically by `tox` when needed.

To avoid using container and use SQLite database in tests instead, run:

    $ tox -e py3-nodocker

To use tox-docker with podman without requiring root, you can use
`tox-podman.sh` script that wraps `tox`:

    $ ./tox-podman.sh -e py311

## Deployment

If you're trying to deploy ResultsDB, you might find some helpful instructions
in the
[Fedora infra docs](https://pagure.io/infra-docs/blob/master/f/docs/sysadmin-guide/sops/resultsdb.rst).
