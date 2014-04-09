# ResultsDB

ResultsDB is a results store engine for (not only) FedoraQA tools.

## Repositories

* ResultsDB Frontend - [Bitbucket GIT repo](https://bitbucket.org/fedoraqa/resultsdb_frontend)
* ResultsDB Client Library - [Bitbucket GIT repo](https://bitbucket.org/fedoraqa/resultsdb_api)

## Hacking

First, clone the repository.

Then, setup a virtual environment for development.

    $ sudo yum install python-virtualenv
    $ virtualenv resultsdb
    $ source resultsdb/bin/activate
    $ pip install -r requirements.txt
    $ python setup.py install

Setup a config file:

    $ cp conf/settings.py.example conf/settings.py
    $ # edit conf/settings.py accordingly

Initialize your database:

    $ ./init_db.sh

Run the server

    $ python runapp.py
