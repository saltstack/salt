#!/usr/bin/env python
# encoding: utf-8
"""
Deployment
==========

The ``rest_cherrypy`` netapi module is a standard Python WSGI app. It can be
deployed one of two ways.

:program:`salt-api` using the CherryPy server
---------------------------------------------

The default configuration is to run this module using :program:`salt-api` to
start the Python-based CherryPy server. This server is lightweight,
multi-threaded, encrypted with SSL, and should be considered production-ready.
See the section above for performance expectations.

Using a WSGI-compliant web server
---------------------------------

This module may be deployed on any WSGI-compliant server such as Apache with
mod_wsgi or Nginx with FastCGI, to name just two (there are many).

Note, external WSGI servers handle URLs, paths, and SSL certs directly. The
``rest_cherrypy`` configuration options are ignored and the ``salt-api`` daemon
does not need to be running at all. Remember Salt authentication credentials
are sent in the clear unless SSL is being enforced!

An example Apache virtual host configuration::

    <VirtualHost *:80>
        ServerName example.com
        ServerAlias *.example.com

        ServerAdmin webmaster@example.com

        LogLevel warn
        ErrorLog /var/www/example.com/logs/error.log
        CustomLog /var/www/example.com/logs/access.log combined

        DocumentRoot /var/www/example.com/htdocs

        WSGIScriptAlias / /path/to/salt/netapi/rest_cherrypy/wsgi.py
    </VirtualHost>

"""
from __future__ import absolute_import, print_function, unicode_literals

import os

import cherrypy  # pylint: disable=3rd-party-module-not-gated

# pylint: disable=C0103


def bootstrap_app():
    """
    Grab the opts dict of the master config by trying to import Salt
    """
    from salt.netapi.rest_cherrypy import app
    import salt.config

    __opts__ = salt.config.client_config(
        os.environ.get("SALT_MASTER_CONFIG", "/etc/salt/master")
    )
    return app.get_app(__opts__)


def get_application(*args):
    """
    Returns a WSGI application function. If you supply the WSGI app and config
    it will use that, otherwise it will try to obtain them from a local Salt
    installation
    """
    opts_tuple = args

    def wsgi_app(environ, start_response):
        root, _, conf = opts_tuple or bootstrap_app()
        cherrypy.config.update({"environment": "embedded"})

        cherrypy.tree.mount(root, "/", conf)
        return cherrypy.tree(environ, start_response)

    return wsgi_app


application = get_application()
