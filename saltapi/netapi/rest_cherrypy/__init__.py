'''
A script to start the CherryPy WSGI server

This is run by ``salt-api`` and started in a multiprocess.
'''
# pylint: disable=C0103

# Import Python libs
import os
import signal

# Import CherryPy without traceback so we can provide an intelligent log
# message in the __virtual__ function
try:
    import cherrypy
    import cherrypy.wsgiserver as wsgiserver
    import cherrypy.wsgiserver.ssl_builtin

    cpy_error = None
except ImportError as exc:
    cpy_error = exc

# Import Salt libs
import salt.log

logger = salt.log.logging.getLogger(__name__)
cpy_min = '3.2.2'

def __virtual__():
    short_name = __name__.rsplit('.')[-1]
    mod_opts = __opts__.get(short_name, {})

    if mod_opts:
        # User has a rest_cherrypy section in config; assume the user wants to
        # run the module and increase logging severity to be helpful

        # Everything looks good; return the module name
        if not cpy_error and 'port' in mod_opts:
            return 'rest'

        # CherryPy wasn't imported; explain why
        if cpy_error:
            from distutils.version import LooseVersion as V

            if 'cherrypy' in globals() and V(cherrypy.__version__) < V(cpy_min):
                error_msg = ("Required version of CherryPy is {0} or "
                        "greater.".format(cpy_min))
            else:
                error_msg = cpy_error

            logger.error("Not loading '%s'. Error loading CherryPy: %s",
                    __name__, error_msg)

        # Missing port config
        if not 'port' in mod_opts:
            logger.error("Not loading '%s'. 'port' not specified in config",
                    __name__)

    return False

def verify_certs(self, *args):
    '''
    Sanity checking for the specified SSL certificates
    '''
    msg = ("Could not find a certificate: {0}\n"
            "If you want to quickly generate a self-signed certificate, "
            "use the tls.create_self_signed_cert function in Salt")

    for arg in args:
        if not os.path.exists(arg):
            raise Exception(msg.format(arg))

def start():
    '''
    Start the server loop
    '''
    from . import app

    root, apiopts, conf = app.get_app(__opts__)

    if apiopts.get('debug', False):
        # Start the development server
        cherrypy.quickstart(root, '/', conf)
    else:
        from . import wsgi
        application = wsgi.get_application(root, apiopts, conf)

        # Mount and start the WSGI app using the production CherryPy server
        verify_certs(apiopts['ssl_crt'], apiopts['ssl_key'])

        ssl_a = wsgiserver.ssl_builtin.BuiltinSSLAdapter(
                apiopts['ssl_crt'], apiopts['ssl_key'])
        wsgi_d = wsgiserver.WSGIPathInfoDispatcher({'/': application})
        server = wsgiserver.CherryPyWSGIServer(
                (apiopts['host'], apiopts['port']),
                wsgi_app=wsgi_d)
        server.ssl_adapter = ssl_a

        signal.signal(signal.SIGINT, lambda *args: server.stop())
        server.start()
