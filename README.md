# ResultsDB

ResultsDB is a results store engine for (not only) Fedora QA tools. The API
documentation can be found at <http://docs.resultsdb20.apiary.io/>.

## Repositories

* ResultsDB Frontend - [Bitbucket GIT repo](https://bitbucket.org/fedoraqa/resultsdb_frontend)
* ResultsDB Client Library - [Bitbucket GIT repo](https://bitbucket.org/fedoraqa/resultsdb_api)

## Quick development setup

First, clone the repository.

Then, setup a virtual environment for development:

    $ sudo dnf install python-virtualenv
    $ virtualenv env_resultsdb
    $ source env_resultsdb/bin/activate
    $ pip install -r requirements.txt

Initialize your database:

    $ DEV=true ./init_db.sh

Run the server:

    $ DEV=true python runapp.py

The server is now running with a very simple frontend at <http://localhost:5001>.
API calls can be sent to <http://localhost:5001/api/v1.0>. All data is stored
inside `/var/tmp/resultsdb_db.sqlite`.

## Adjusting configuration

You can configure this app by copying `conf/settings.py.example` into
`conf/setting.py` and adjusting values as you see fit. It overrides default
values in `resultsdb/config.py`.

## Using with libtaskotron

You might want to use this tool together with libtaskotron. To use your own
*ResultsDB* server in libtaskotron, edit `/etc/taskotron/taskotron.yaml` and
set the following value::

    resultsdb_server: http://localhost:5001/api/v1.0

You might also need to adjust `reporting_enabled` and `report_to_resultsdb`,
depending on your local settings.

## Running test suite

You can run this test suite with the following command::

    $ py.test --functional testing/