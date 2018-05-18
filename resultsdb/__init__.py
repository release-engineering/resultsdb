# Copyright 2013-2014, Red Hat, Inc
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
#   Ralph Bean <rbean@redhat.com>

from resultsdb import proxy

import flask
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import logging
import logging.handlers
import os


# the version as used in setup.py
__version__ = "2.1.1"

try:
    basestring
except NameError:
    basestring = (str, bytes)


# Flask App
app = Flask(__name__)
app.secret_key = 'replace-me-with-something-random'

# make sure app behaves when behind a proxy
app.wsgi_app = proxy.ReverseProxied(app.wsgi_app)

# Monkey patch Flask's "jsonify" to also handle JSONP
original_jsonify = flask.jsonify

# Expose the __version__ variable in templates
app.jinja_env.globals['app_version'] = __version__


def jsonify_with_jsonp(*args, **kwargs):
    response = original_jsonify(*args, **kwargs)

    callback = flask.request.args.get('callback', None)

    if callback:
        if not isinstance(callback, basestring):
            callback = callback[0]
        response.mimetype = 'application/javascript'
        response.set_data('%s(%s);' % (callback, response.get_data()))

    return response

flask.jsonify = jsonify_with_jsonp

# Load default config, then override that with a config file
if os.getenv('DEV') == 'true':
    default_config_obj = 'resultsdb.config.DevelopmentConfig'
    default_config_file = os.getcwd() + '/conf/settings.py'
elif os.getenv('TEST') == 'true':
    default_config_obj = 'resultsdb.config.TestingConfig'
    default_config_file = os.getcwd() + '/conf/settings.py'
else:
    default_config_obj = 'resultsdb.config.ProductionConfig'
    default_config_file = '/etc/resultsdb/settings.py'

app.config.from_object(default_config_obj)

config_file = os.environ.get('RESULTSDB_CONFIG', default_config_file)

if os.path.exists(config_file):
    app.config.from_pyfile(config_file)

if app.config['PRODUCTION']:
    if app.secret_key == 'replace-me-with-something-random':
        raise Warning("You need to change the app.secret_key value for production")

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
        print("doing stream logging")
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(loglevel)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        app.logger.addHandler(stream_handler)

    if app.config['SYSLOG_LOGGING']:
        print("doing syslog logging")
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log',
                                                        facility=logging.handlers.SysLogHandler.LOG_LOCAL4)
        syslog_handler.setLevel(loglevel)
        syslog_handler.setFormatter(formatter)
        root_logger.addHandler(syslog_handler)
        app.logger.addHandler(syslog_handler)

    if app.config['FILE_LOGGING'] and app.config['LOGFILE']:
        print("doing file logging to %s" % app.config['LOGFILE'])
        file_handler = logging.handlers.RotatingFileHandler(
            app.config['LOGFILE'], maxBytes=500000, backupCount=5)
        file_handler.setLevel(loglevel)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        app.logger.addHandler(file_handler)

setup_logging()

if app.config['SHOW_DB_URI']:
    app.logger.debug('using DBURI: %s' % app.config['SQLALCHEMY_DATABASE_URI'])


# database
db = SQLAlchemy(app)

# Register auth
if app.config['AUTH_MODULE'] == 'oidc':
    from flask_oidc import OpenIDConnect
    oidc = OpenIDConnect(app)

    def _check():
        if flask.request.method == 'POST':
            # We don't need to do auth for any non-POST
            # Prefer POSTed access token: they don't get into the httpd logs
            token = flask.request.form.get('_auth_token')
            if token is None:
                token = flask.request.args.get('_auth_token')
            if token is None:
                token = flask.request.json.get('_auth_token')
            if not token:
                app.logger.error('No token submitted')
                return False
            validity = oidc.validate_token(token, [app.config['OIDC_SCOPE']])
            if validity is not True:
                app.logger.error('Token validation error: %s', validity)
                return False
            try:
                token_info = oidc._get_token_info(token)
            except Exception as ex:
                app.logger.error('get_token failed: %s' % ex)
                return False
            if token_info.get('sub') not in app.config['OIDC_ADMINS']:
                app.logger.error('Subject %s is not admin' %
                                 token_info.get('sub'))
                return False
            return True
        elif flask.request.method == 'GET':
            return True

    def check_token():
        result = _check()
        if result is None:
            return flask.jsonify({'error': 'server_error'})
        elif result is False:
            return flask.jsonify({'error': 'invalid_token',
                                  'error_description': 'Invalid or no token'})
        # If the check passed, we fall through. This returns None, telling
        # Flask that it can proceed further with the request

    app.before_request(check_token)

# register blueprints
from resultsdb.controllers.main import main
app.register_blueprint(main)

from resultsdb.controllers.api_v1 import api as api_v1
app.register_blueprint(api_v1, url_prefix="/api/v1.0")

from resultsdb.controllers.api_v2 import api as api_v2
app.register_blueprint(api_v2, url_prefix="/api/v2.0")

app.logger.debug("Finished ResultsDB initialization")
