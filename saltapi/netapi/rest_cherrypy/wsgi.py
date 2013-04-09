#!/usr/bin/env python
'''
A WSGI app to start a REST interface to Salt

This WSGI app can be used with any WSGI-compliant server. See the rest_cherrypy
netapi module to see how this app is run with the CherryPy WSGI server.

Apache's mod_wsgi instructions
------------------------------

Add the path to this script as a WSGIScriptAlias in the Apache configuration
for your site. For example a virtual host configuration may look something
like::

    <VirtualHost *:80>
        ServerName example.com
        ServerAlias *.example.com

        ServerAdmin webmaster@example.com

        LogLevel warn
        ErrorLog /var/www/example.com/logs/error.log
        CustomLog /var/www/example.com/logs/access.log combined

        DocumentRoot /var/www/example.com/htdocs

        WSGIScriptAlias / /path/to/saltapi/netapi/rest_cherrypy/wsgi.py
    </VirtualHost>

'''
# pylint: disable=C0103

import cherrypy

from . import app

def bootstrap_app():
    '''
    Grab the opts dict of the master config by trying to import Salt
    '''
    import salt.client
    opts = salt.client.LocalClient().opts
    return app.get_app(opts)

def get_application(*args):
    '''
    Returns a WSGI application function. If you supply the WSGI app and config
    it will use that, otherwise it will try to obtain them from a local Salt
    installation
    '''
    opts_tuple = args

    def wsgi_app(environ, start_response):
        root, _, conf = opts_tuple or bootstrap_app()

        cherrypy.tree.mount(root, '/', conf)
        return cherrypy.tree(environ, start_response)

    return wsgi_app

application = get_application()
