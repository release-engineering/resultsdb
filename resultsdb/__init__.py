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

import json
import logging
import logging.config as logging_config
import logging.handlers
import os

from flask import Flask, current_app, jsonify, send_from_directory, session
from flask_pydantic.exceptions import ValidationError
from flask_pyoidc import OIDCAuthentication
from flask_pyoidc.provider_configuration import (
    ClientMetadata,
    ProviderConfiguration,
    ProviderMetadata,
)
from flask_pyoidc.user_session import UserSession
from flask_session import Session

from resultsdb.controllers.api_v2 import api as api_v2
from resultsdb.controllers.api_v3 import api as api_v3
from resultsdb.controllers.api_v3 import create_endpoints
from resultsdb.controllers.main import main
from resultsdb.messaging import load_messaging_plugin
from resultsdb.models import db
from resultsdb.proxy import ReverseProxied
from resultsdb.tracing import setup_tracing

from . import config

# the version as used in setup.py
__version__ = "2.2.0"

VALIDATION_KEYS = frozenset({"input", "loc", "msg", "type", "url"})


def create_app(config_obj=None):
    app = Flask(__name__)
    app.secret_key = "replace-me-with-something-random"  # nosec

    # make sure app behaves when behind a proxy
    app.wsgi_app = ReverseProxied(app.wsgi_app)

    # Expose the __version__ variable in templates
    app.jinja_env.globals["app_version"] = __version__

    # Checks for env variable OPENSHIFT_PROD to trigger OpenShift codepath on init
    # The main difference is that settings will be queried from env
    # (check config.openshift_config())
    # Possible values are:
    # "1" - OpenShift production deployment
    # "0" - OpenShift testing deployment
    openshift = os.getenv("OPENSHIFT_PROD")

    # Load default config, then override that with a config file
    if not config_obj:
        if os.getenv("DEV") == "true":
            config_obj = "resultsdb.config.DevelopmentConfig"
        elif os.getenv("TEST") == "true" or openshift == "0":
            config_obj = "resultsdb.config.TestingConfig"
        else:
            config_obj = "resultsdb.config.ProductionConfig"

    app.config.from_object(config_obj)

    if openshift:
        config.openshift_config(app.config, openshift)

    default_config_file = app.config["DEFAULT_CONFIG_FILE"]
    config_file = os.environ.get("RESULTSDB_CONFIG", default_config_file)
    if config_file and os.path.exists(config_file):
        app.config.from_pyfile(config_file)

    if app.config["PRODUCTION"]:
        if app.secret_key == "replace-me-with-something-random":  # nosec
            raise Warning("You need to change the app.secret_key value for production")

    setup_logging(app)

    app.logger.info("Using configuration object: %s", config_obj)
    if openshift:
        app.logger.info("Using OpenShift configuration")
    app.logger.info("Using configuration file: %s", config_file)

    if app.config["SHOW_DB_URI"]:
        app.logger.debug("Using DBURI: %s", app.config["SQLALCHEMY_DATABASE_URI"])

    db.init_app(app)

    with app.app_context():
        setup_tracing(app, db.engine)

    init_session(app)

    register_handlers(app)

    app.register_blueprint(main)
    app.register_blueprint(api_v2, url_prefix="/api/v2.0")
    app.add_url_rule("/favicon.png", view_func=favicon)

    if app.config["AUTH_MODULE"] == "oidc":
        app.logger.info("OpenIDConnect authentication is enabled")
        enable_oidc(app)
        app.register_blueprint(api_v3, url_prefix="/api/v3")
    else:
        app.logger.info("OpenIDConnect authentication is disabled")

    setup_messaging(app)

    app.logger.debug("Finished ResultsDB initialization")
    return app


def setup_logging(app):
    # Use LOGGING if defined instead of the old options
    log_config = app.config.get("LOGGING")
    if log_config:
        logging_config.dictConfig(log_config)
        return

    fmt = "[%(filename)s:%(lineno)d] " if app.debug else "%(module)-12s "
    fmt += "%(asctime)s %(levelname)-7s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    loglevel = logging.DEBUG if app.debug else logging.INFO
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    root_logger = logging.getLogger("")
    root_logger.setLevel(logging.DEBUG)

    # Keep the old way to setup logging in settings.py or config.py, example:
    # LOGFILE = '/var/log/resultsdb/resultsdb.log'
    # FILE_LOGGING = False
    # SYSLOG_LOGGING = False
    # STREAM_LOGGING = True
    if app.config["STREAM_LOGGING"]:
        print("doing stream logging")
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(loglevel)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        app.logger.addHandler(stream_handler)

    if app.config["SYSLOG_LOGGING"]:
        print("doing syslog logging")
        syslog_handler = logging.handlers.SysLogHandler(
            address="/dev/log", facility=logging.handlers.SysLogHandler.LOG_LOCAL4
        )
        syslog_handler.setLevel(loglevel)
        syslog_handler.setFormatter(formatter)
        root_logger.addHandler(syslog_handler)
        app.logger.addHandler(syslog_handler)

    if app.config["FILE_LOGGING"] and app.config["LOGFILE"]:
        print(f"doing file logging to {app.config['LOGFILE']}")
        file_handler = logging.handlers.RotatingFileHandler(
            app.config["LOGFILE"], maxBytes=500000, backupCount=5
        )
        file_handler.setLevel(loglevel)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        app.logger.addHandler(file_handler)


def setup_messaging(app):
    app.messaging_plugin = None
    if not app.config["MESSAGE_BUS_PUBLISH"]:
        app.logger.info("No messaging plugin selected")
        return

    plugin_name = app.config["MESSAGE_BUS_PLUGIN"]
    app.logger.info("Using messaging plugin %s", plugin_name)
    plugin_args = app.config["MESSAGE_BUS_KWARGS"]
    app.messaging_plugin = load_messaging_plugin(
        name=plugin_name,
        plugin_args=plugin_args,
    )


def register_handlers(app):
    # TODO: find out why error handler works for 404 but not for 400
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"message": "Bad request"}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        app.logger.warning("Unauthorized access: %s", error)
        return jsonify({"message": str(error)}), 401

    @app.errorhandler(403)
    def forbidden(error):
        app.logger.warning("Permission denied: %s", error)
        return jsonify({"message": str(error)}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"message": "Not found"}), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error("Internal error: %s", error)
        return jsonify({"message": "Internal Server Error"}), 500

    @app.errorhandler(502)
    def bad_gateway(error):
        app.logger.error("External error received: %s", error)
        return jsonify({"message": "Bad Gateway"}), 502

    app.register_error_handler(ValidationError, handle_validation_error)


def handle_validation_error(error: ValidationError):
    errors = (
        error.body_params
        or error.form_params
        or error.path_params
        or error.query_params
    )
    # Keep only interesting stuff and remove objects potentially
    # unserializable in JSON.
    err = [{k: v for k, v in e.items() if k in VALIDATION_KEYS} for e in errors]
    response = jsonify({"validation_error": err})
    response.status_code = 400
    return response


def init_session(app):
    app.config["SESSION_SQLALCHEMY"] = db
    app.server_session = Session(app)
    if app.config["SESSION_TYPE"] == "sqlalchemy":
        import sqlalchemy

        with app.app_context():
            inspect = sqlalchemy.inspect(db.engine)
            table = app.config["SESSION_SQLALCHEMY_TABLE"]
            if not inspect.has_table(table):
                db.create_all()


def enable_oidc(app):
    with open(app.config["OIDC_CLIENT_SECRETS"]) as client_secrets_file:
        client_secrets = json.load(client_secrets_file)

    provider = app.config.get("OIDC_PROVIDER", "web")
    metadata = client_secrets[provider]
    app.config.update(
        {
            "OIDC_PROVIDER": provider,
            "OIDC_REDIRECT_URI": metadata["redirect_uris"][0],
        }
    )
    client_metadata = ClientMetadata(metadata["client_id"], metadata["client_secret"])
    provider_metadata = ProviderMetadata(
        issuer=metadata["issuer"],
        authorization_endpoint=metadata["auth_uri"],
        token_endpoint=metadata["token_uri"],
        userinfo_endpoint=metadata["userinfo_uri"],
        introspection_endpoint=metadata["token_introspection_uri"],
        jwks_uri=metadata.get(
            "jwks_uri", metadata["token_uri"].replace("/token", "/certs")
        ),
    )
    config = ProviderConfiguration(
        issuer=metadata["issuer"],
        client_metadata=client_metadata,
        provider_metadata=provider_metadata,
        session_refresh_interval_seconds=app.config[
            "OIDC_SESSION_REFRESH_INTERVAL_SECONDS"
        ],
    )
    oidc = OIDCAuthentication({provider: config}, app)

    @app.route("/auth/oidclogin")
    @oidc.oidc_auth(provider)
    def login():
        user_session = UserSession(session)
        return jsonify(
            {
                "username": user_session.userinfo[app.config["OIDC_USERNAME_FIELD"]],
                "token": user_session.access_token,
            }
        )

    @app.route("/auth/logout")
    @oidc.oidc_logout
    def logout():
        return jsonify({"message": "Logged out"})

    app.oidc = oidc

    create_endpoints(oidc, provider)


def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "favicon.png",
        mimetype="image/png",
    )
