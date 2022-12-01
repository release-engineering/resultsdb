# -*- coding: utf-8 -*-
# Copyright 2009-2014, Red Hat, Inc.
# License: GPL-2.0+ <http://spdx.org/licenses/GPL-2.0+>

"""
Makes fedocal an application behind a reverse proxy and thus ensure the
redirects are using ``https``.

Original Source: http://flask.pocoo.org/snippets/35/ by Peter Hansen
Source: https://github.com/fedora-infra/fedocal/blob/master/fedocal/proxy.py
"""


class ReverseProxied(object):

    """Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In apache:
    RewriteEngine On

    <Location /myprefix/ >
        ProxyPass http://192.168.0.1:5001/
        ProxyPassReverse http://192.168.0.1:5001/
        RequestHeader set X-Forwarded-Scheme $scheme
        RequestHeader add X-Script-Name /myprefix/
    </Location>

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get("HTTP_X_SCRIPT_NAME", "")
        if script_name:
            environ["SCRIPT_NAME"] = script_name
            path_info = environ["PATH_INFO"]
            if path_info.startswith(script_name):
                prefix_len = len(script_name)
                environ["PATH_INFO"] = path_info[prefix_len:]

        server = environ.get("HTTP_X_FORWARDED_HOST", "")
        if server:
            environ["HTTP_HOST"] = server

        scheme = environ.get("HTTP_X_FORWARDED_SCHEME", "")
        if scheme:
            environ["wsgi.url_scheme"] = scheme
        return self.app(environ, start_response)
