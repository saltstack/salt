"""
A minimalist REST API for Salt
==============================

This ``rest_wsgi`` module provides a no-frills REST interface for sending
commands to the Salt master. There are no dependencies.

Extra care must be taken when deploying this module into production. Please
read this documentation in entirety.

All authentication is done through Salt's :ref:`external auth <acl-eauth>`
system.

Usage
=====

* All requests must be sent to the root URL (``/``).
* All requests must be sent as a POST request with JSON content in the request
  body.
* All responses are in JSON.

.. seealso:: :py:mod:`rest_cherrypy <salt.netapi.rest_cherrypy.app>`

    The :py:mod:`rest_cherrypy <salt.netapi.rest_cherrypy.app>` module is
    more full-featured, production-ready, and has builtin security features.

Deployment
==========

The ``rest_wsgi`` netapi module is a standard Python WSGI app. It can be
deployed one of two ways.

Using a WSGI-compliant web server
---------------------------------

This module may be run via any WSGI-compliant production server such as Apache
with mod_wsgi or Nginx with FastCGI.

It is strongly recommended that this app be used with a server that supports
HTTPS encryption since raw Salt authentication credentials must be sent with
every request. Any apps that access Salt through this interface will need to
manually manage authentication credentials (either username and password or a
Salt token). Tread carefully.

:program:`salt-api` using a development-only server
---------------------------------------------------

If run directly via the salt-api daemon it uses the `wsgiref.simple_server()`__
that ships in the Python standard library. This is a single-threaded server
that is intended for testing and development. **This server does not use
encryption**; please note that raw Salt authentication credentials must be sent
with every HTTP request.

**Running this module via salt-api is not recommended!**

In order to start this module via the ``salt-api`` daemon the following must be
put into the Salt master config::

    rest_wsgi:
        port: 8001

.. __: http://docs.python.org/2/library/wsgiref.html#module-wsgiref.simple_server

Usage examples
==============

.. http:post:: /

    **Example request** for a basic ``test.ping``::

        % curl -sS -i \\
                -H 'Content-Type: application/json' \\
                -d '[{"eauth":"pam","username":"saltdev","password":"saltdev","client":"local","tgt":"*","fun":"test.ping"}]' localhost:8001

    **Example response**:

    .. code-block:: http

        HTTP/1.0 200 OK
        Content-Length: 89
        Content-Type: application/json

        {"return": [{"ms--4": true, "ms--3": true, "ms--2": true, "ms--1": true, "ms--0": true}]}

    **Example request** for an asynchronous ``test.ping``::

        % curl -sS -i \\
                -H 'Content-Type: application/json' \\
                -d '[{"eauth":"pam","username":"saltdev","password":"saltdev","client":"local_async","tgt":"*","fun":"test.ping"}]' localhost:8001

    **Example response**:

    .. code-block:: http

        HTTP/1.0 200 OK
        Content-Length: 103
        Content-Type: application/json

        {"return": [{"jid": "20130412192112593739", "minions": ["ms--4", "ms--3", "ms--2", "ms--1", "ms--0"]}]}

    **Example request** for looking up a job ID::

        % curl -sS -i \\
                -H 'Content-Type: application/json' \\
                -d '[{"eauth":"pam","username":"saltdev","password":"saltdev","client":"runner","fun":"jobs.lookup_jid","jid":"20130412192112593739"}]' localhost:8001

    **Example response**:

    .. code-block:: http

        HTTP/1.0 200 OK
        Content-Length: 89
        Content-Type: application/json

        {"return": [{"ms--4": true, "ms--3": true, "ms--2": true, "ms--1": true, "ms--0": true}]}

:form lowstate: A list of lowstate data appropriate for the
    :ref:`client <client-apis>` interface you are calling.
:status 200: success
:status 401: authentication required

"""

import errno
import logging
import os

import salt
import salt.netapi
import salt.utils.json

# HTTP response codes to response headers map
H = {
    200: "200 OK",
    400: "400 BAD REQUEST",
    401: "401 UNAUTHORIZED",
    404: "404 NOT FOUND",
    405: "405 METHOD NOT ALLOWED",
    406: "406 NOT ACCEPTABLE",
    500: "500 INTERNAL SERVER ERROR",
}

__virtualname__ = "rest_wsgi"

logger = logging.getLogger(__virtualname__)


def __virtual__():
    mod_opts = __opts__.get(__virtualname__, {})

    if "port" in mod_opts:
        return __virtualname__

    return False


class HTTPError(Exception):
    """
    A custom exception that can take action based on an HTTP error code
    """

    def __init__(self, code, message):
        self.code = code
        Exception.__init__(self, f"{code}: {message}")


def mkdir_p(path):
    """
    mkdir -p
    http://stackoverflow.com/a/600612/127816
    """
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def read_body(environ):
    """
    Pull the body from the request and return it
    """
    length = environ.get("CONTENT_LENGTH", "0")
    length = 0 if length == "" else int(length)

    return environ["wsgi.input"].read(length)


def get_json(environ):
    """
    Return the request body as JSON
    """
    content_type = environ.get("CONTENT_TYPE", "")
    if content_type != "application/json":
        raise HTTPError(406, "JSON required")

    try:
        return salt.utils.json.loads(read_body(environ))
    except ValueError as exc:
        raise HTTPError(400, exc)


def get_headers(data, extra_headers=None):
    """
    Takes the response data as well as any additional headers and returns a
    tuple of tuples of headers suitable for passing to start_response()
    """
    response_headers = {
        "Content-Length": str(len(data)),
    }

    if extra_headers:
        response_headers.update(extra_headers)

    return list(response_headers.items())


def run_chunk(environ, lowstate):
    """
    Expects a list of lowstate dictionaries that are executed and returned in
    order
    """
    client = environ["SALT_APIClient"]

    for chunk in lowstate:
        yield client.run(chunk)


def dispatch(environ):
    """
    Do any path/method dispatching here and return a JSON-serializable data
    structure appropriate for the response
    """
    method = environ["REQUEST_METHOD"].upper()

    if method == "GET":
        return "They found me. I don't know how, but they found me. Run for it, Marty!"
    elif method == "POST":
        data = get_json(environ)
        return run_chunk(environ, data)
    else:
        raise HTTPError(405, "Method Not Allowed")


def saltenviron(environ):
    """
    Make Salt's opts dict and the APIClient available in the WSGI environ
    """
    if "__opts__" not in locals():
        import salt.config

        __opts__ = salt.config.client_config(
            os.environ.get("SALT_MASTER_CONFIG", "/etc/salt/master")
        )

    environ["SALT_OPTS"] = __opts__
    environ["SALT_APIClient"] = salt.netapi.NetapiClient(__opts__)


def application(environ, start_response):
    """
    Process the request and return a JSON response. Catch errors and return the
    appropriate HTTP code.
    """
    # Instantiate APIClient once for the whole app
    saltenviron(environ)

    # Call the dispatcher
    try:
        resp = list(dispatch(environ))
        code = 200
    except HTTPError as exc:
        code = exc.code
        resp = str(exc)
    except salt.exceptions.EauthAuthenticationError as exc:
        code = 401
        resp = str(exc)
    except Exception as exc:  # pylint: disable=broad-except
        code = 500
        resp = str(exc)

    # Convert the response to JSON
    try:
        ret = salt.utils.json.dumps({"return": resp})
    except TypeError as exc:
        code = 500
        ret = str(exc)

    # Return the response
    start_response(H[code], get_headers(ret, {"Content-Type": "application/json"}))
    return (ret,)


def get_opts():
    """
    Return the Salt master config as __opts__
    """
    import salt.config

    return salt.config.client_config(
        os.environ.get("SALT_MASTER_CONFIG", "/etc/salt/master")
    )


def start():
    """
    Start simple_server()
    """
    from wsgiref.simple_server import make_server

    # When started outside of salt-api __opts__ will not be injected
    if "__opts__" not in globals():
        globals()["__opts__"] = get_opts()

        if __virtual__() is False:
            raise SystemExit(1)

    mod_opts = __opts__.get(__virtualname__, {})

    # pylint: disable=C0103
    httpd = make_server("localhost", mod_opts["port"], application)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        raise SystemExit(0)


if __name__ == "__main__":
    start()
