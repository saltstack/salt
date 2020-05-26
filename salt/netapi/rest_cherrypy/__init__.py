# encoding: utf-8
"""
A script to start the CherryPy WSGI server

This is run by ``salt-api`` and started in a multiprocess.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import os

# pylint: disable=C0103


# Import CherryPy without traceback so we can provide an intelligent log
# message in the __virtual__ function
try:
    import cherrypy

    cpy_error = None
except ImportError as exc:
    cpy_error = exc

__virtualname__ = os.path.abspath(__file__).rsplit(os.sep)[-2] or "rest_cherrypy"

logger = logging.getLogger(__virtualname__)
cpy_min = "3.2.2"


def __virtual__():
    short_name = __name__.rsplit(".")[-1]
    mod_opts = __opts__.get(short_name, {})

    if mod_opts:
        # User has a rest_cherrypy section in config; assume the user wants to
        # run the module and increase logging severity to be helpful

        # Everything looks good; return the module name
        if not cpy_error and "port" in mod_opts:
            return __virtualname__

        # CherryPy wasn't imported; explain why
        if cpy_error:
            from salt.utils.versions import LooseVersion as V

            if "cherrypy" in globals() and V(cherrypy.__version__) < V(cpy_min):
                error_msg = "Required version of CherryPy is {0} or " "greater.".format(
                    cpy_min
                )
            else:
                error_msg = cpy_error

            logger.error(
                "Not loading '%s'. Error loading CherryPy: %s", __name__, error_msg
            )

        # Missing port config
        if "port" not in mod_opts:
            logger.error("Not loading '%s'. 'port' not specified in config", __name__)

    return False


def verify_certs(*args):
    """
    Sanity checking for the specified SSL certificates
    """
    msg = (
        "Could not find a certificate: {0}\n"
        "If you want to quickly generate a self-signed certificate, "
        "use the tls.create_self_signed_cert function in Salt"
    )

    for arg in args:
        if not os.path.exists(arg):
            raise Exception(msg.format(arg))


def start():
    """
    Start the server loop
    """
    from . import app

    root, apiopts, conf = app.get_app(__opts__)

    if not apiopts.get("disable_ssl", False):
        if "ssl_crt" not in apiopts or "ssl_key" not in apiopts:
            logger.error(
                "Not starting '%s'. Options 'ssl_crt' and "
                "'ssl_key' are required if SSL is not disabled.",
                __name__,
            )

            return None

        verify_certs(apiopts["ssl_crt"], apiopts["ssl_key"])

        cherrypy.server.ssl_module = "builtin"
        cherrypy.server.ssl_certificate = apiopts["ssl_crt"]
        cherrypy.server.ssl_private_key = apiopts["ssl_key"]
        if "ssl_chain" in apiopts.keys():
            cherrypy.server.ssl_certificate_chain = apiopts["ssl_chain"]

    cherrypy.quickstart(root, apiopts.get("root_prefix", "/"), conf)
