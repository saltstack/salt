"""
A script to start the CherryPy WSGI server

This is run by ``salt-api`` and started in a multiprocess.
"""

import logging
import os

import cherrypy

from salt.utils.versions import Version

__virtualname__ = os.path.abspath(__file__).rsplit(os.sep)[-2] or "rest_cherrypy"

logger = logging.getLogger(__virtualname__)


def __virtual__():
    short_name = __name__.rsplit(".")[-1]
    mod_opts = __opts__.get(short_name, {})

    if mod_opts:
        # User has a rest_cherrypy section in config; assume the user wants to
        # run the module and increase logging severity to be helpful

        # Everything looks good; return the module name
        if "port" in mod_opts:
            return __virtualname__

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
