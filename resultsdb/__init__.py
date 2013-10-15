# Copyright 2013, Red Hat, Inc
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors:
#   Josef Skladanka <jskladan@redhat.com>

from flask import Flask
from flask.ext.login import LoginManager
from flask.ext.sqlalchemy import SQLAlchemy

import logging
import os


# the version as used in setup.py
__version__ = "0.0.1"


# Flask App
app = Flask(__name__)
app.secret_key = 'not-really-a-secret'

# load default configuration
if os.getenv('DEV') == 'true':
    app.config.from_object('resultsdb.config.DevelopmentConfig')
elif os.getenv('TEST') == 'true':
    app.config.from_object('resultsdb.config.TestingConfig')
else:
    if app.secret_key == 'not-really-a-secret':
        raise Warning("You need to change the app.secret_key value for production")
    app.config.from_object('resultsdb.config.ProductionConfig')


# load real configuration values to override defaults
config_file = '/etc/resultsdb/settings.py'
if not app.testing:
    if os.path.exists(config_file):
        app.logger.info('Loading configuration from %s' % config_file)
        app.config.from_pyfile(config_file)
    else:
        config_file = os.path.abspath('conf/settings.py')
        if os.path.exists(config_file):
            app.logger.info('Loading configuration from %s' % config_file)
            app.config.from_pyfile(config_file)
        else:
            app.logger.info('No extra config found, using defaults')

# setup logging

# setup logging
fmt = '[%(filename)s:%(lineno)d] ' if app.debug else '%(module)-12s '
fmt += '%(asctime)s %(levelname)-7s %(message)s'
datefmt = '%Y-%m-%d %H:%M:%S'
loglevel = logging.DEBUG if app.debug else logging.INFO
formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

def setup_logging():
    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.DEBUG)

    if app.config['STREAM_LOGGING']:
        print "doing stream logging"
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(loglevel)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        app.logger.addHandler(stream_handler)

    if app.config['SYSLOG_LOGGING']:
        print "doing syslog logging"
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log',
                            facility=logging.handlers.SysLogHandler.LOG_LOCAL4)
        syslog_handler.setLevel(loglevel)
        syslog_handler.setFormatter(formatter)
        root_logger.addHandler(syslog_handler)
        app.logger.addHandler(syslog_handler)

    if app.config['FILE_LOGGING'] and app.config['LOGFILE']:
        print "doing file logging to %s" % app.config['LOGFILE']
        file_handler = logging.handlers.RotatingFileHandler(app.config['LOGFILE'], maxBytes=500000, backupCount=5)
        file_handler.setLevel(loglevel)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        app.logger.addHandler(file_handler)

setup_logging()

app.logger.debug('using DBURI: %s' % app.config['SQLALCHEMY_DATABASE_URI'])


# database
db = SQLAlchemy(app)

# setup login manager
login_manager = LoginManager()
login_manager.setup_app(app)
login_manager.login_view = 'login_page.login'

# register blueprints
from resultsdb.controllers.main import main
app.register_blueprint(main)

from resultsdb.controllers.login_page import login_page
app.register_blueprint(login_page)

from resultsdb.controllers.admin import admin
app.register_blueprint(admin)

from resultsdb.controllers.api_v1 import api as api_v1
app.register_blueprint(api_v1, url_prefix = "/api")

