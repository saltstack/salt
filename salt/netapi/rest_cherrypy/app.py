# encoding: utf-8
'''
A REST API for Salt
===================

.. versionadded:: 2014.7.0

.. py:currentmodule:: salt.netapi.rest_cherrypy.app

:depends:
    - CherryPy Python module. Version 3.2.3 is currently recommended when
      SSL is enabled, since this version worked the best with SSL in
      internal testing. Versions 3.2.3 - 4.x can be used if SSL is not enabled.
      Be aware that there is a known
      `SSL error <https://github.com/cherrypy/cherrypy/issues/1298>`_
      introduced in version 3.2.5. The issue was reportedly resolved with
      CherryPy milestone 3.3, but the patch was committed for version 3.6.1.
:optdepends:    - ws4py Python module for websockets support.
:client_libraries:
    - Java: https://github.com/SUSE/salt-netapi-client
    - Python: https://github.com/saltstack/pepper
:setup:
    All steps below are performed on the machine running the Salt Master
    daemon. Configuration goes into the Master configuration file.

    1.  Install ``salt-api``. (This step varies between OS and Linux distros.
        Some package systems have a split package, others include salt-api in
        the main Salt package. Ensure the ``salt-api --version`` output matches
        the ``salt --version`` output.)
    2.  Install CherryPy. (Read the version caveat in the section above.)
    3.  Optional: generate self-signed SSL certificates.

        Using a secure HTTPS connection is strongly recommended since Salt
        eauth authentication credentials will be sent over the wire.

        1.  Install the PyOpenSSL package.
        2.  Generate a self-signed certificate using the
            :py:func:`~salt.modules.tls.create_self_signed_cert` execution
            function.

            .. code-block:: bash

                salt-call --local tls.create_self_signed_cert

    4.  Edit the master config to create at least one external auth user or
        group following the :ref:`full external auth instructions <acl-eauth>`.
    5.  Edit the master config with the following production-ready example to
        enable the ``rest_cherrypy`` module. (Adjust cert paths as needed, or
        disable SSL (not recommended!).)

        .. code-block:: yaml

            rest_cherrypy:
              port: 8000
              ssl_crt: /etc/pki/tls/certs/localhost.crt
              ssl_key: /etc/pki/tls/certs/localhost.key

    6.  Restart the ``salt-master`` daemon.
    7.  Start the ``salt-api`` daemon.

:configuration:
    All available configuration options are detailed below. These settings
    configure the CherryPy HTTP server and do not apply when using an external
    server such as Apache or Nginx.

    port
        **Required**

        The port for the webserver to listen on.
    host : ``0.0.0.0``
        The socket interface for the HTTP server to listen on.
    debug : ``False``
        Starts the web server in development mode. It will reload itself when
        the underlying code is changed and will output more debugging info.
    log_access_file
        Path to a file to write HTTP access logs.

        .. versionaddedd:: 2016.11.0

    log_error_file
        Path to a file to write HTTP error logs.

        .. versionaddedd:: 2016.11.0

    ssl_crt
        The path to a SSL certificate. (See below)
    ssl_key
        The path to the private key for your SSL certificate. (See below)
    ssl_chain
        (Optional when using PyOpenSSL) the certificate chain to pass to
        ``Context.load_verify_locations``.
    disable_ssl
        A flag to disable SSL. Warning: your Salt authentication credentials
        will be sent in the clear!
    webhook_disable_auth : False
        The :py:class:`Webhook` URL requires authentication by default but
        external services cannot always be configured to send authentication.
        See the Webhook documentation for suggestions on securing this
        interface.
    webhook_url : /hook
        Configure the URL endpoint for the :py:class:`Webhook` entry point.
    thread_pool : ``100``
        The number of worker threads to start up in the pool.
    socket_queue_size : ``30``
        Specify the maximum number of HTTP connections to queue.
    expire_responses : True
        Whether to check for and kill HTTP responses that have exceeded the
        default timeout.
    max_request_body_size : ``1048576``
        Maximum size for the HTTP request body.
    collect_stats : False
        Collect and report statistics about the CherryPy server

        Reports are available via the :py:class:`Stats` URL.
    static
        A filesystem path to static HTML/JavaScript/CSS/image assets.
    static_path : ``/static``
        The URL prefix to use when serving static assets out of the directory
        specified in the ``static`` setting.
    app
        A filesystem path to an HTML file that will be served as a static file.
        This is useful for bootstrapping a single-page JavaScript app.
    app_path : ``/app``
        The URL prefix to use for serving the HTML file specified in the ``app``
        setting. This should be a simple name containing no slashes.

        Any path information after the specified path is ignored; this is
        useful for apps that utilize the HTML5 history API.
    root_prefix : ``/``
        A URL path to the main entry point for the application. This is useful
        for serving multiple applications from the same URL.

.. _rest_cherrypy-auth:

Authentication
--------------

Authentication is performed by passing a session token with each request.
Tokens are generated via the :py:class:`Login` URL.

The token may be sent in one of two ways: as a custom header or as a session
cookie. The latter is far more convenient for clients that support cookies.

* Include a custom header named :mailheader:`X-Auth-Token`.

  For example, using curl:

  .. code-block:: bash

      curl -sSk https://localhost:8000/login \\
          -H 'Accept: application/x-yaml' \\
          -d username=saltdev \\
          -d password=saltdev \\
          -d eauth=auto

  Copy the ``token`` value from the output and include it in subsequent requests:

  .. code-block:: bash

      curl -sSk https://localhost:8000 \\
          -H 'Accept: application/x-yaml' \\
          -H 'X-Auth-Token: 697adbdc8fe971d09ae4c2a3add7248859c87079'\\
          -d client=local \\
          -d tgt='*' \\
          -d fun=test.ping

* Sent via a cookie. This option is a convenience for HTTP clients that
  automatically handle cookie support (such as browsers).

  For example, using curl:

  .. code-block:: bash

      # Write the cookie file:
      curl -sSk https://localhost:8000/login \\
            -c ~/cookies.txt \\
            -H 'Accept: application/x-yaml' \\
            -d username=saltdev \\
            -d password=saltdev \\
            -d eauth=auto

      # Read the cookie file:
      curl -sSk https://localhost:8000 \\
            -b ~/cookies.txt \\
            -H 'Accept: application/x-yaml' \\
            -d client=local \\
            -d tgt='*' \\
            -d fun=test.ping

  Another example using the :program:`requests` library in Python:

  .. code-block:: python

      >>> import requests
      >>> session = requests.Session()
      >>> session.post('http://localhost:8000/login', json={
          'username': 'saltdev',
          'password': 'saltdev',
          'eauth': 'auto',
      })
      <Response [200]>
      >>> resp = session.post('http://localhost:8000', json=[{
          'client': 'local',
          'tgt': '*',
          'fun': 'test.arg',
          'arg': ['foo', 'bar'],
          'kwarg': {'baz': 'Baz!'},
      }])
      >>> resp.json()
      {u'return': [{
          ...snip...
      }]}

.. seealso:: You can bypass the session handling via the :py:class:`Run` URL.

Usage
-----

This interface directly exposes Salt's :ref:`Python API <python-api>`.
Everything possible at the CLI is possible through the Python API. Commands are
executed on the Salt Master.

The root URL (``/``) is RPC-like in that it accepts instructions in the request
body for what Salt functions to execute, and the response contains the result
of those function calls.

For example:

.. code-block:: text

    % curl -sSi https://localhost:8000 \
        -H 'Content-type: application/json' \
        -d '[{
            "client": "local",
            "tgt": "*",
            "fun": "test.ping"
        }]'
    HTTP/1.1 200 OK
    Content-Type: application/json
    [...snip...]

    {"return": [{"jerry": true}]}

The request body must be an array of commands. Use this workflow to build a
command:

1.  Choose a client interface.
2.  Choose a function.
3.  Fill out the remaining parameters needed for the chosen client.

The ``client`` field is a reference to the main Python classes used in Salt's
Python API. Read the full :ref:`client interfaces <netapi-clients>`
documentation, but in short:

* "local" uses :py:class:`LocalClient <salt.client.LocalClient>` which sends
  commands to Minions. Equivalent to the ``salt`` CLI command.
* "runner" uses :py:class:`RunnerClient <salt.runner.RunnerClient>` which
  invokes runner modules on the Master. Equivalent to the ``salt-run`` CLI
  command.
* "wheel" uses :py:class:`WheelClient <salt.wheel.WheelClient>` which invokes
  wheel modules on the Master. Wheel modules do not have a direct CLI
  equivalent but they typically manage Master-side resources such as state
  files, pillar files, the Salt config files, and the :py:mod:`key wheel module
  <salt.wheel.key>` exposes similar functionality as the ``salt-key`` CLI
  command.

Most clients have variants like synchronous or asynchronous execution as well as
others like batch execution. See the :ref:`full list of client interfaces
<netapi-clients>`.

Each client requires different arguments and sometimes has different syntax.
For example, ``LocalClient`` requires the ``tgt`` argument because it forwards
the command to Minions and the other client interfaces do not. ``LocalClient``
also takes ``arg`` (array) and ``kwarg`` (dictionary) arguments because these
values are sent to the Minions and used to execute the requested function
there. ``RunnerClient`` and ``WheelClient`` are executed directly on the Master
and thus do not need or accept those arguments.

Read the method signatures in the client documentation linked above, but
hopefully an example will help illustrate the concept. This example causes Salt
to execute two functions -- the :py:func:`test.arg execution function
<salt.modules.test.arg>` using ``LocalClient`` and the :py:func:`test.arg
runner function <salt.runners.test.arg>` using ``RunnerClient``; note the
different structure for each command. The results for both are combined and
returned as one response.

.. code-block:: text

    % curl -b ~/cookies.txt -sSi localhost:8000 \
        -H 'Content-type: application/json' \
        -d '
    [
        {
            "client": "local",
            "tgt": "*",
            "fun": "test.arg",
            "arg": ["positional arg one", "positional arg two"],
            "kwarg": {
                "keyword arg one": "Hello from a minion",
                "keyword arg two": "Hello again from a minion"
            }
        },
        {
            "client": "runner",
            "fun": "test.arg",
            "keyword arg one": "Hello from a master",
            "keyword arg two": "Runners do not support positional args"
        }
    ]
    '
    HTTP/1.1 200 OK
    [...snip...]
    {
      "return": [
        {
          "jerry": {
            "args": [
              "positional arg one",
              "positional arg two"
            ],
            "kwargs": {
              "keyword arg one": "Hello from a minion",
              "keyword arg two": "Hello again from a minion",
              [...snip...]
            }
          },
          [...snip; other minion returns here...]
        },
        {
          "args": [],
          "kwargs": {
            "keyword arg two": "Runners do not support positional args",
            "keyword arg one": "Hello from a master"
          }
        }
      ]
    }

One more example, this time with more commonly used functions:

.. code-block:: text

    curl -b /tmp/cookies.txt -sSi localhost:8000 \
        -H 'Content-type: application/json' \
        -d '
    [
        {
            "client": "local",
            "tgt": "*",
            "fun": "state.sls",
            "kwarg": {
                "mods": "apache",
                "pillar": {
                    "lookup": {
                        "wwwdir": "/srv/httpd/htdocs"
                    }
                }
            }
        },
        {
            "client": "runner",
            "fun": "cloud.create",
            "provider": "my-ec2-provider",
            "instances": "my-centos-6",
            "image": "ami-1624987f",
            "delvol_on_destroy", true
        }
    ]
    '
    HTTP/1.1 200 OK
    [...snip...]
    {
      "return": [
        {
          "jerry": {
            "pkg_|-install_apache_|-httpd_|-installed": {
                [...snip full state return here...]
            }
          }
          [...snip other minion returns here...]
        },
        {
            [...snip full salt-cloud output here...]
        }
      ]
    }

Content negotiation
-------------------

This REST interface is flexible in what data formats it will accept as well
as what formats it will return (e.g., JSON, YAML, urlencoded).

* Specify the format of data in the request body by including the
  :mailheader:`Content-Type` header.
* Specify the desired data format for the response body with the
  :mailheader:`Accept` header.

We recommend the JSON format for most HTTP requests. urlencoded data is simple
and cannot express complex data structures -- and that is often required for
some Salt commands, such as starting a state run that uses Pillar data. Salt's
CLI tool can reformat strings passed in at the CLI into complex data
structures, and that behavior also works via salt-api, but that can be brittle
and since salt-api can accept JSON it is best just to send JSON.

Here is an example of sending urlencoded data:

.. code-block:: bash

    curl -sSik https://localhost:8000 \\
        -b ~/cookies.txt \\
        -d client=runner \\
        -d fun='jobs.lookup_jid' \\
        -d jid='20150129182456704682'

.. admonition:: urlencoded data caveats

    * Only a single command may be sent per HTTP request.
    * Repeating the ``arg`` parameter multiple times will cause those
      parameters to be combined into a single list.

      Note, some popular frameworks and languages (notably jQuery, PHP, and
      Ruby on Rails) will automatically append empty brackets onto repeated
      query string parameters. E.g., ``?foo[]=fooone&foo[]=footwo``. This is
      **not** supported; send ``?foo=fooone&foo=footwo`` instead, or send JSON
      or YAML.

    A note about ``curl``

    The ``-d`` flag to curl does *not* automatically urlencode data which can
    affect passwords and other data that contains characters that must be
    encoded. Use the ``--data-urlencode`` flag instead. E.g.:

    .. code-block:: bash

        curl -ksi http://localhost:8000/login \\
        -H "Accept: application/json" \\
        -d username='myapiuser' \\
        --data-urlencode password='1234+' \\
        -d eauth='pam'

.. |req_token| replace:: a session token from :py:class:`~Login`.
.. |req_accept| replace:: the desired response format.
.. |req_ct| replace:: the format of the request body.

.. |res_ct| replace:: the format of the response body; depends on the
    :mailheader:`Accept` request header.

.. |200| replace:: success
.. |400| replace:: bad or malformed request
.. |401| replace:: authentication required
.. |406| replace:: requested Content-Type not available

'''
# We need a custom pylintrc here...
# pylint: disable=W0212,E1101,C0103,R0201,W0221,W0613

# Import Python libs
from __future__ import absolute_import
import collections
import itertools
import functools
import logging
import json
import os
import signal
import tarfile
import time
from multiprocessing import Process, Pipe

# Import third-party libs
# pylint: disable=import-error
import cherrypy
import yaml
import salt.ext.six as six
# pylint: enable=import-error


# Import Salt libs
import salt
import salt.auth
import salt.utils.event

# Import salt-api libs
import salt.netapi

logger = logging.getLogger(__name__)

# Imports related to websocket
try:
    from .tools import websockets
    from . import event_processor

    HAS_WEBSOCKETS = True
except ImportError:
    websockets = type('websockets', (object,), {
        'SynchronizingWebsocket': None,
    })

    HAS_WEBSOCKETS = False


def html_override_tool():
    '''
    Bypass the normal handler and serve HTML for all URLs

    The ``app_path`` setting must be non-empty and the request must ask for
    ``text/html`` in the ``Accept`` header.
    '''
    apiopts = cherrypy.config['apiopts']
    request = cherrypy.request

    url_blacklist = (
        apiopts.get('app_path', '/app'),
        apiopts.get('static_path', '/static'),
    )

    if 'app' not in cherrypy.config['apiopts']:
        return

    if request.path_info.startswith(url_blacklist):
        return

    if request.headers.get('Accept') == '*/*':
        return

    try:
        wants_html = cherrypy.lib.cptools.accept('text/html')
    except cherrypy.HTTPError:
        return
    else:
        if wants_html != 'text/html':
            return

    raise cherrypy.InternalRedirect(apiopts.get('app_path', '/app'))


def salt_token_tool():
    '''
    If the custom authentication header is supplied, put it in the cookie dict
    so the rest of the session-based auth works as intended
    '''
    x_auth = cherrypy.request.headers.get('X-Auth-Token', None)

    # X-Auth-Token header trumps session cookie
    if x_auth:
        cherrypy.request.cookie['session_id'] = x_auth


def salt_api_acl_tool(username, request):
    '''
    ..versionadded:: 2016.3.0

    Verifies user requests against the API whitelist. (User/IP pair)
    in order to provide whitelisting for the API similar to the
    master, but over the API.

    ..code-block:: yaml

        rest_cherrypy:
            api_acl:
                users:
                    '*':
                        - 1.1.1.1
                        - 1.1.1.2
                    foo:
                        - 8.8.4.4
                    bar:
                        - '*'

    :param username: Username to check against the API.
    :type username: str
    :param request: Cherrypy request to check against the API.
    :type request: cherrypy.request
    '''
    failure_str = ("[api_acl] Authentication failed for "
                   "user {0} from IP {1}")
    success_str = ("[api_acl] Authentication sucessful for "
                   "user {0} from IP {1}")
    pass_str = ("[api_acl] Authentication not checked for "
                "user {0} from IP {1}")

    acl = None
    # Salt Configuration
    salt_config = cherrypy.config.get('saltopts', None)
    if salt_config:
        # Cherrypy Config.
        cherrypy_conf = salt_config.get('rest_cherrypy', None)
        if cherrypy_conf:
            # ACL Config.
            acl = cherrypy_conf.get('api_acl', None)

    ip = request.remote.ip
    if acl:
        users = acl.get('users', {})
        if users:
            if username in users:
                if ip in users[username] or '*' in users[username]:
                    logger.info(success_str.format(username, ip))
                    return True
                else:
                    logger.info(failure_str.format(username, ip))
                    return False
            elif username not in users and '*' in users:
                if ip in users['*'] or '*' in users['*']:
                    logger.info(success_str.format(username, ip))
                    return True
                else:
                    logger.info(failure_str.format(username, ip))
                    return False
            else:
                logger.info(failure_str.format(username, ip))
                return False
    else:
        logger.info(pass_str.format(username, ip))
        return True


def salt_ip_verify_tool():
    '''
    If there is a list of restricted IPs, verify current
    client is coming from one of those IPs.
    '''
    # This is overly cumbersome and crude,
    # But, it's also safe... ish...
    salt_config = cherrypy.config.get('saltopts', None)
    if salt_config:
        cherrypy_conf = salt_config.get('rest_cherrypy', None)
        if cherrypy_conf:
            auth_ip_list = cherrypy_conf.get('authorized_ips', None)
            if auth_ip_list:
                logger.debug("Found IP list: {0}".format(auth_ip_list))
                rem_ip = cherrypy.request.headers.get('Remote-Addr', None)
                logger.debug("Request from IP: {0}".format(rem_ip))
                if rem_ip not in auth_ip_list:
                    logger.error("Blocked IP: {0}".format(rem_ip))
                    raise cherrypy.HTTPError(403, 'Bad IP')


def salt_auth_tool():
    '''
    Redirect all unauthenticated requests to the login page
    '''
    # Redirect to the login page if the session hasn't been authed
    if 'token' not in cherrypy.session:  # pylint: disable=W8601
        raise cherrypy.HTTPError(401)

    # Session is authenticated; inform caches
    cherrypy.response.headers['Cache-Control'] = 'private'


def cors_handler(*args, **kwargs):
    '''
    Check a CORS preflight request and return a valid response
    '''
    req_head = cherrypy.request.headers
    resp_head = cherrypy.response.headers

    ac_method = req_head.get('Access-Control-Request-Method', None)

    allowed_methods = ['GET', 'POST']
    allowed_headers = ['X-Auth-Token', 'Content-Type']

    if ac_method and ac_method in allowed_methods:
        resp_head['Access-Control-Allow-Methods'] = ', '.join(allowed_methods)
        resp_head['Access-Control-Allow-Headers'] = ', '.join(allowed_headers)

        resp_head['Connection'] = 'keep-alive'
        resp_head['Access-Control-Max-Age'] = '1400'

    return {}


def cors_tool():
    '''
    Handle both simple and complex CORS requests

    Add CORS headers to each response. If the request is a CORS preflight
    request swap out the default handler with a simple, single-purpose handler
    that verifies the request and provides a valid CORS response.
    '''
    req_head = cherrypy.request.headers
    resp_head = cherrypy.response.headers

    # Always set response headers necessary for 'simple' CORS.
    resp_head['Access-Control-Allow-Origin'] = req_head.get('Origin', '*')
    resp_head['Access-Control-Expose-Headers'] = 'GET, POST'
    resp_head['Access-Control-Allow-Credentials'] = 'true'

    # If this is a non-simple CORS preflight request swap out the handler.
    if cherrypy.request.method == 'OPTIONS':
        cherrypy.serving.request.handler = cors_handler


# Be conservative in what you send
# Maps Content-Type to serialization functions; this is a tuple of tuples to
# preserve order of preference.
ct_out_map = (
    ('application/json', json.dumps),
    ('application/x-yaml', functools.partial(
        yaml.safe_dump, default_flow_style=False)),
)


def hypermedia_handler(*args, **kwargs):
    '''
    Determine the best output format based on the Accept header, execute the
    regular handler, and transform the output to the request content type (even
    if it's an error).

    :param args: Pass args through to the main handler
    :param kwargs: Pass kwargs through to the main handler
    '''
    # Execute the real handler. Handle or pass-through any errors we know how
    # to handle (auth & HTTP errors). Reformat any errors we don't know how to
    # handle as a data structure.
    try:
        cherrypy.response.processors = dict(ct_out_map)
        ret = cherrypy.serving.request._hypermedia_inner_handler(*args, **kwargs)
    except (salt.exceptions.EauthAuthenticationError,
            salt.exceptions.TokenAuthenticationError):
        raise cherrypy.HTTPError(401)
    except salt.exceptions.SaltInvocationError:
        raise cherrypy.HTTPError(400)
    except (salt.exceptions.SaltDaemonNotRunning,
            salt.exceptions.SaltReqTimeoutError) as exc:
        raise cherrypy.HTTPError(503, exc.strerror)
    except (cherrypy.TimeoutError, salt.exceptions.SaltClientTimeout):
        raise cherrypy.HTTPError(504)
    except cherrypy.CherryPyException:
        raise
    except Exception as exc:
        import traceback

        logger.debug("Error while processing request for: %s",
                cherrypy.request.path_info,
                exc_info=True)

        cherrypy.response.status = 500

        ret = {
            'status': cherrypy.response.status,
            'return': '{0}'.format(traceback.format_exc(exc))
                    if cherrypy.config['debug']
                    else "An unexpected error occurred"}

    # Raises 406 if requested content-type is not supported
    best = cherrypy.lib.cptools.accept([i for (i, _) in ct_out_map])

    # Transform the output from the handler into the requested output format
    cherrypy.response.headers['Content-Type'] = best
    out = cherrypy.response.processors[best]
    try:
        return out(ret)
    except Exception:
        msg = 'Could not serialize the return data from Salt.'
        logger.debug(msg, exc_info=True)
        raise cherrypy.HTTPError(500, msg)


def hypermedia_out():
    '''
    Determine the best handler for the requested content type

    Wrap the normal handler and transform the output from that handler into the
    requested content type
    '''
    request = cherrypy.serving.request
    request._hypermedia_inner_handler = request.handler
    request.handler = hypermedia_handler


@functools.wraps
def process_request_body(fn):
    '''
    A decorator to skip a processor function if process_request_body is False
    '''
    def wrapped(*args, **kwargs):  # pylint: disable=C0111
        if cherrypy.request.process_request_body is not False:
            fn(*args, **kwargs)
    return wrapped


def urlencoded_processor(entity):
    '''
    Accept x-www-form-urlencoded data (run through CherryPy's formatter)
    and reformat it into a Low State data structure.

    Since we can't easily represent complicated data structures with
    key-value pairs, any more complicated requirements (e.g. compound
    commands) must instead be delivered via JSON or YAML.

    For example::

    .. code-block:: bash

        curl -si localhost:8000 -d client=local -d tgt='*' \\
                -d fun='test.kwarg' -d arg='one=1' -d arg='two=2'

    :param entity: raw POST data
    '''
    # First call out to CherryPy's default processor
    cherrypy._cpreqbody.process_urlencoded(entity)
    cherrypy.serving.request.unserialized_data = entity.params
    cherrypy.serving.request.raw_body = ''


@process_request_body
def json_processor(entity):
    '''
    Unserialize raw POST data in JSON format to a Python data structure.

    :param entity: raw POST data
    '''
    body = entity.fp.read()
    try:
        cherrypy.serving.request.unserialized_data = json.loads(body)
    except ValueError:
        raise cherrypy.HTTPError(400, 'Invalid JSON document')

    cherrypy.serving.request.raw_body = body


@process_request_body
def yaml_processor(entity):
    '''
    Unserialize raw POST data in YAML format to a Python data structure.

    :param entity: raw POST data
    '''
    body = entity.fp.read()
    try:
        cherrypy.serving.request.unserialized_data = yaml.safe_load(body)
    except ValueError:
        raise cherrypy.HTTPError(400, 'Invalid YAML document')

    cherrypy.serving.request.raw_body = body


@process_request_body
def text_processor(entity):
    '''
    Attempt to unserialize plain text as JSON

    Some large services still send JSON with a text/plain Content-Type. Those
    services are bad and should feel bad.

    :param entity: raw POST data
    '''
    body = entity.fp.read()
    try:
        cherrypy.serving.request.unserialized_data = json.loads(body)
    except ValueError:
        cherrypy.serving.request.unserialized_data = body

    cherrypy.serving.request.raw_body = body


def hypermedia_in():
    '''
    Unserialize POST/PUT data of a specified Content-Type.

    The following custom processors all are intended to format Low State data
    and will place that data structure into the request object.

    :raises HTTPError: if the request contains a Content-Type that we do not
        have a processor for
    '''
    # Be liberal in what you accept
    ct_in_map = {
        'application/x-www-form-urlencoded': urlencoded_processor,
        'application/json': json_processor,
        'application/x-yaml': yaml_processor,
        'text/yaml': yaml_processor,
        'text/plain': text_processor,
    }

    # Do not process the body for POST requests that have specified no content
    # or have not specified Content-Length
    if (cherrypy.request.method.upper() == 'POST'
            and cherrypy.request.headers.get('Content-Length', '0') == '0'):
        cherrypy.request.process_request_body = False
        cherrypy.request.unserialized_data = None

    cherrypy.request.body.processors.clear()
    cherrypy.request.body.default_proc = cherrypy.HTTPError(
            406, 'Content type not supported')
    cherrypy.request.body.processors = ct_in_map


def lowdata_fmt():
    '''
    Validate and format lowdata from incoming unserialized request data

    This tool requires that the hypermedia_in tool has already been run.
    '''
    if cherrypy.request.method.upper() != 'POST':
        return

    data = cherrypy.request.unserialized_data

    # if the data was sent as urlencoded, we need to make it a list.
    # this is a very forgiving implementation as different clients set different
    # headers for form encoded data (including charset or something similar)
    if data and isinstance(data, collections.Mapping):
        # Make the 'arg' param a list if not already
        if 'arg' in data and not isinstance(data['arg'], list):
            data['arg'] = [data['arg']]

        # Finally, make a Low State and put it in request
        cherrypy.request.lowstate = [data]
    else:
        cherrypy.serving.request.lowstate = data


cherrypy.tools.html_override = cherrypy.Tool('on_start_resource',
        html_override_tool, priority=53)
cherrypy.tools.salt_token = cherrypy.Tool('on_start_resource',
        salt_token_tool, priority=55)
cherrypy.tools.cors_tool = cherrypy.Tool('before_request_body',
        cors_tool, priority=50)
cherrypy.tools.salt_auth = cherrypy.Tool('before_request_body',
        salt_auth_tool, priority=60)
cherrypy.tools.hypermedia_in = cherrypy.Tool('before_request_body',
        hypermedia_in)
cherrypy.tools.lowdata_fmt = cherrypy.Tool('before_handler',
        lowdata_fmt, priority=40)
cherrypy.tools.hypermedia_out = cherrypy.Tool('before_handler',
        hypermedia_out)
cherrypy.tools.salt_ip_verify = cherrypy.Tool('before_handler',
        salt_ip_verify_tool)


###############################################################################


class LowDataAdapter(object):
    '''
    The primary entry point to Salt's REST API

    '''
    exposed = True

    _cp_config = {
        'tools.sessions.on': True,
        'tools.sessions.timeout': 60 * 10,  # 10 hours

        # 'tools.autovary.on': True,

        'tools.hypermedia_out.on': True,
        'tools.hypermedia_in.on': True,
        'tools.lowdata_fmt.on': True,
        'tools.salt_ip_verify.on': True,
    }

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.api = salt.netapi.NetapiClient(self.opts)

    def exec_lowstate(self, client=None, token=None):
        '''
        Pull a Low State data structure from request and execute the low-data
        chunks through Salt. The low-data chunks will be updated to include the
        authorization token for the current session.
        '''
        lowstate = cherrypy.request.lowstate

        # Release the session lock before executing any potentially
        # long-running Salt commands. This allows different threads to execute
        # Salt commands concurrently without blocking.
        if cherrypy.request.config.get('tools.sessions.on', False):
            cherrypy.session.release_lock()

        # if the lowstate loaded isn't a list, lets notify the client
        if not isinstance(lowstate, list):
            raise cherrypy.HTTPError(400, 'Lowstates must be a list')

        # Make any requested additions or modifications to each lowstate, then
        # execute each one and yield the result.
        for chunk in lowstate:
            if token:
                chunk['token'] = token
                if cherrypy.session.get('user'):
                    chunk['__current_eauth_user'] = cherrypy.session.get('user')
                if cherrypy.session.get('groups'):
                    chunk['__current_eauth_groups'] = cherrypy.session.get('groups')

            if client:
                chunk['client'] = client

            # Make any 'arg' params a list if not already.
            # This is largely to fix a deficiency in the urlencoded format.
            if 'arg' in chunk and not isinstance(chunk['arg'], list):
                chunk['arg'] = [chunk['arg']]

            ret = self.api.run(chunk)

            # Sometimes Salt gives us a return and sometimes an iterator
            if isinstance(ret, collections.Iterator):
                for i in ret:
                    yield i
            else:
                yield ret

    def GET(self):
        '''
        An explanation of the API with links of where to go next

        .. http:get:: /

            :reqheader Accept: |req_accept|

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000

        .. code-block:: http

            GET / HTTP/1.1
            Host: localhost:8000
            Accept: application/json

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Type: application/json
        '''
        import inspect

        return {
            'return': "Welcome",
            'clients': salt.netapi.CLIENTS,
        }

    @cherrypy.tools.salt_token()
    @cherrypy.tools.salt_auth()
    def POST(self, **kwargs):
        '''
        Send one or more Salt commands in the request body

        .. http:post:: /

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|
            :reqheader Content-Type: |req_ct|

            :resheader Content-Type: |res_ct|

            :status 200: |200|
            :status 400: |400|
            :status 401: |401|
            :status 406: |406|

            :term:`lowstate` data describing Salt commands must be sent in the
            request body.

        **Example request:**

        .. code-block:: bash

            curl -sSik https://localhost:8000 \\
                -b ~/cookies.txt \\
                -H "Accept: application/x-yaml" \\
                -H "Content-type: application/json" \\
                -d '[{"client": "local", "tgt": "*", "fun": "test.ping"}]'

        .. code-block:: http

            POST / HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml
            X-Auth-Token: d40d1e1e
            Content-Type: application/json

            [{"client": "local", "tgt": "*", "fun": "test.ping"}]

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 200
            Allow: GET, HEAD, POST
            Content-Type: application/x-yaml

            return:
            - ms-0: true
              ms-1: true
              ms-2: true
              ms-3: true
              ms-4: true
        '''
        return {
            'return': list(self.exec_lowstate(
                token=cherrypy.session.get('token')))
        }


class Minions(LowDataAdapter):
    '''
    Convenience URLs for working with minions
    '''
    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,
    })

    def GET(self, mid=None):
        '''
        A convenience URL for getting lists of minions or getting minion
        details

        .. http:get:: /minions/(mid)

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000/minions/ms-3

        .. code-block:: http

            GET /minions/ms-3 HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 129005
            Content-Type: application/x-yaml

            return:
            - ms-3:
                grains.items:
                    ...
        '''
        cherrypy.request.lowstate = [{
            'client': 'local', 'tgt': mid or '*', 'fun': 'grains.items',
        }]
        return {
            'return': list(self.exec_lowstate(
                token=cherrypy.session.get('token'))),
        }

    def POST(self, **kwargs):
        '''
        Start an execution command and immediately return the job id

        .. http:post:: /minions

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|
            :reqheader Content-Type: |req_ct|

            :resheader Content-Type: |res_ct|

            :status 200: |200|
            :status 400: |400|
            :status 401: |401|
            :status 406: |406|

            :term:`lowstate` data describing Salt commands must be sent in the
            request body. The ``client`` option will be set to
            :py:meth:`~salt.client.LocalClient.local_async`.

        **Example request:**

        .. code-block:: bash

            curl -sSi localhost:8000/minions \\
                -b ~/cookies.txt \\
                -H "Accept: application/x-yaml" \\
                -d '[{"tgt": "*", "fun": "status.diskusage"}]'

        .. code-block:: http

            POST /minions HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml
            Content-Type: application/json

            tgt=*&fun=status.diskusage

        **Example response:**

        .. code-block:: http

            HTTP/1.1 202 Accepted
            Content-Length: 86
            Content-Type: application/x-yaml

            return:
            - jid: '20130603122505459265'
              minions: [ms-4, ms-3, ms-2, ms-1, ms-0]
            _links:
              jobs:
                - href: /jobs/20130603122505459265
        '''
        job_data = list(self.exec_lowstate(client='local_async',
            token=cherrypy.session.get('token')))

        cherrypy.response.status = 202
        return {
            'return': job_data,
            '_links': {
                'jobs': [{'href': '/jobs/{0}'.format(i['jid'])}
                    for i in job_data if i],
            },
        }


class Jobs(LowDataAdapter):
    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,
    })

    def GET(self, jid=None, timeout=''):
        '''
        A convenience URL for getting lists of previously run jobs or getting
        the return from a single job

        .. http:get:: /jobs/(jid)

            List jobs or show a single job from the job cache.

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000/jobs

        .. code-block:: http

            GET /jobs HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 165
            Content-Type: application/x-yaml

            return:
            - '20121130104633606931':
                Arguments:
                - '3'
                Function: test.fib
                Start Time: 2012, Nov 30 10:46:33.606931
                Target: jerry
                Target-type: glob

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000/jobs/20121130104633606931

        .. code-block:: http

            GET /jobs/20121130104633606931 HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 73
            Content-Type: application/x-yaml

            info:
            - Arguments:
                - '3'
                Function: test.fib
                Minions:
                - jerry
                Start Time: 2012, Nov 30 10:46:33.606931
                Target: '*'
                Target-type: glob
                User: saltdev
                jid: '20121130104633606931'
            return:
            - jerry:
                - - 0
                - 1
                - 1
                - 2
                - 6.9141387939453125e-06
        '''
        lowstate = [{
            'client': 'runner',
            'fun': 'jobs.list_job' if jid else 'jobs.list_jobs',
            'jid': jid,
        }]

        cherrypy.request.lowstate = lowstate
        job_ret_info = list(self.exec_lowstate(
            token=cherrypy.session.get('token')))

        ret = {}
        if jid:
            ret['info'] = job_ret_info[0]
            ret['return'] = [dict((k, job_ret_info[0]['Result'][k]['return']) for k in job_ret_info[0]['Result'])]
        else:
            ret['return'] = job_ret_info[0]

        return ret


class Keys(LowDataAdapter):
    '''
    Convenience URLs for working with minion keys

    .. versionadded:: 2014.7.0

    These URLs wrap the functionality provided by the :py:mod:`key wheel
    module <salt.wheel.key>` functions.
    '''

    @cherrypy.config(**{'tools.salt_token.on': True})
    def GET(self, mid=None):
        '''
        Show the list of minion keys or detail on a specific key

        .. versionadded:: 2014.7.0

        .. http:get:: /keys/(mid)

            List all keys or show a specific key

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000/keys

        .. code-block:: http

            GET /keys HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 165
            Content-Type: application/x-yaml

            return:
              local:
              - master.pem
              - master.pub
              minions:
              - jerry
              minions_pre: []
              minions_rejected: []

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000/keys/jerry

        .. code-block:: http

            GET /keys/jerry HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 73
            Content-Type: application/x-yaml

            return:
              minions:
                jerry: 51:93:b3:d0:9f:3a:6d:e5:28:67:c2:4b:27:d6:cd:2b
        '''
        if mid:
            lowstate = [{
                'client': 'wheel',
                'fun': 'key.finger',
                'match': mid,
            }]
        else:
            lowstate = [{
                'client': 'wheel',
                'fun': 'key.list_all',
            }]

        cherrypy.request.lowstate = lowstate
        result = self.exec_lowstate(token=cherrypy.session.get('token'))

        return {'return': next(result, {}).get('data', {}).get('return', {})}

    @cherrypy.config(**{'tools.hypermedia_out.on': False, 'tools.sessions.on': False})
    def POST(self, **kwargs):
        r'''
        Easily generate keys for a minion and auto-accept the new key

        Accepts all the same parameters as the :py:func:`key.gen_accept
        <salt.wheel.key.gen_accept>`.

        Example partial kickstart script to bootstrap a new minion:

        .. code-block:: text

            %post
            mkdir -p /etc/salt/pki/minion
            curl -sSk https://localhost:8000/keys \
                    -d mid=jerry \
                    -d username=kickstart \
                    -d password=kickstart \
                    -d eauth=pam \
                | tar -C /etc/salt/pki/minion -xf -

            mkdir -p /etc/salt/minion.d
            printf 'master: 10.0.0.5\nid: jerry' > /etc/salt/minion.d/id.conf
            %end

        .. http:post:: /keys

            Generate a public and private key and return both as a tarball

            Authentication credentials must be passed in the request.

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -sSk https://localhost:8000/keys \
                    -d mid=jerry \
                    -d username=kickstart \
                    -d password=kickstart \
                    -d eauth=pam \
                    -o jerry-salt-keys.tar

        .. code-block:: http

            POST /keys HTTP/1.1
            Host: localhost:8000

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 10240
            Content-Disposition: attachment; filename="saltkeys-jerry.tar"
            Content-Type: application/x-tar

            jerry.pub0000644000000000000000000000070300000000000010730 0ustar  00000000000000
        '''
        lowstate = cherrypy.request.lowstate
        lowstate[0].update({
            'client': 'wheel',
            'fun': 'key.gen_accept',
        })

        if 'mid' in lowstate[0]:
            lowstate[0]['id_'] = lowstate[0].pop('mid')

        result = self.exec_lowstate()
        ret = next(result, {}).get('data', {}).get('return', {})

        pub_key = ret.get('pub', '')
        pub_key_file = tarfile.TarInfo('minion.pub')
        pub_key_file.size = len(pub_key)

        priv_key = ret.get('priv', '')
        priv_key_file = tarfile.TarInfo('minion.pem')
        priv_key_file.size = len(priv_key)

        fileobj = six.moves.StringIO()
        tarball = tarfile.open(fileobj=fileobj, mode='w')
        tarball.addfile(pub_key_file, six.moves.StringIO(pub_key))
        tarball.addfile(priv_key_file, six.moves.StringIO(priv_key))
        tarball.close()

        headers = cherrypy.response.headers
        headers['Content-Disposition'] = 'attachment; filename="saltkeys-{0}.tar"'.format(lowstate[0]['id_'])
        headers['Content-Type'] = 'application/x-tar'
        headers['Content-Length'] = fileobj.len
        headers['Cache-Control'] = 'no-cache'

        fileobj.seek(0)
        return fileobj


class Login(LowDataAdapter):
    '''
    Log in to receive a session token

    :ref:`Authentication information <rest_cherrypy-auth>`.
    '''

    def __init__(self, *args, **kwargs):
        super(Login, self).__init__(*args, **kwargs)

        self.auth = salt.auth.Resolver(self.opts)

    def GET(self):
        '''
        Present the login interface

        .. http:get:: /login

            An explanation of how to log in.

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000/login

        .. code-block:: http

            GET /login HTTP/1.1
            Host: localhost:8000
            Accept: text/html

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Type: text/html
        '''
        cherrypy.response.headers['WWW-Authenticate'] = 'Session'

        return {
            'status': cherrypy.response.status,
            'return': "Please log in",
        }

    def POST(self, **kwargs):
        '''
        :ref:`Authenticate  <rest_cherrypy-auth>` against Salt's eauth system

        .. http:post:: /login

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|
            :reqheader Content-Type: |req_ct|

            :form eauth: the eauth backend configured for the user
            :form username: username
            :form password: password

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -si localhost:8000/login \\
                -c ~/cookies.txt \\
                -H "Accept: application/json" \\
                -H "Content-type: application/json" \\
                -d '{
                    "username": "saltuser",
                    "password": "saltuser",
                    "eauth": "auto"
                }'

        .. code-block:: http

            POST / HTTP/1.1
            Host: localhost:8000
            Content-Length: 42
            Content-Type: application/json
            Accept: application/json

            {"username": "saltuser", "password": "saltuser", "eauth": "auto"}


        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Type: application/json
            Content-Length: 206
            X-Auth-Token: 6d1b722e
            Set-Cookie: session_id=6d1b722e; expires=Sat, 17 Nov 2012 03:23:52 GMT; Path=/

            {"return": {
                "token": "6d1b722e",
                "start": 1363805943.776223,
                "expire": 1363849143.776224,
                "user": "saltuser",
                "eauth": "pam",
                "perms": [
                    "grains.*",
                    "status.*",
                    "sys.*",
                    "test.*"
                ]
            }}
        '''
        if not self.api._is_master_running():
            raise salt.exceptions.SaltDaemonNotRunning(
                'Salt Master is not available.')

        # the urlencoded_processor will wrap this in a list
        if isinstance(cherrypy.serving.request.lowstate, list):
            creds = cherrypy.serving.request.lowstate[0]
        else:
            creds = cherrypy.serving.request.lowstate

        username = creds.get('username', None)
        # Validate against the whitelist.
        if not salt_api_acl_tool(username, cherrypy.request):
            raise cherrypy.HTTPError(401)

        # Mint token.
        token = self.auth.mk_token(creds)
        if 'token' not in token:
            raise cherrypy.HTTPError(401,
                    'Could not authenticate using provided credentials')

        cherrypy.response.headers['X-Auth-Token'] = cherrypy.session.id
        cherrypy.session['token'] = token['token']
        cherrypy.session['timeout'] = (token['expire'] - token['start']) / 60
        cherrypy.session['user'] = token['name']
        if 'groups' in token:
            cherrypy.session['groups'] = token['groups']

        # Grab eauth config for the current backend for the current user
        try:
            eauth = self.opts.get('external_auth', {}).get(token['eauth'], {})

            if token['eauth'] == 'django' and '^model' in eauth:
                perms = token['auth_list']
            else:
                # Get sum of '*' perms, user-specific perms, and group-specific perms
                perms = eauth.get(token['name'], [])
                perms.extend(eauth.get('*', []))

                if 'groups' in token and token['groups']:
                    user_groups = set(token['groups'])
                    eauth_groups = set([i.rstrip('%') for i in eauth.keys() if i.endswith('%')])

                    for group in user_groups & eauth_groups:
                        perms.extend(eauth['{0}%'.format(group)])

            if not perms:
                logger.debug("Eauth permission list not found.")
        except Exception:
            logger.debug("Configuration for external_auth malformed for "
                "eauth '{0}', and user '{1}'."
                .format(token.get('eauth'), token.get('name')), exc_info=True)
            perms = None

        return {'return': [{
            'token': cherrypy.session.id,
            'expire': token['expire'],
            'start': token['start'],
            'user': token['name'],
            'eauth': token['eauth'],
            'perms': perms or {},
        }]}


class Logout(LowDataAdapter):
    '''
    Class to remove or invalidate sessions
    '''
    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,

        'tools.lowdata_fmt.on': False,
    })

    def POST(self):
        '''
        Destroy the currently active session and expire the session cookie
        '''
        cherrypy.lib.sessions.expire()  # set client-side to expire
        cherrypy.session.regenerate()  # replace server-side with new

        return {'return': "Your token has been cleared"}


class Run(LowDataAdapter):
    '''
    Class to run commands without normal session handling
    '''
    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.sessions.on': False,
    })

    def POST(self, **kwargs):
        '''
        Run commands bypassing the :ref:`normal session handling
        <rest_cherrypy-auth>`

        .. http:post:: /run

            This entry point is primarily for "one-off" commands. Each request
            must pass full Salt authentication credentials. Otherwise this URL
            is identical to the :py:meth:`root URL (/) <LowDataAdapter.POST>`.

            :term:`lowstate` data describing Salt commands must be sent in the
            request body.

            :status 200: |200|
            :status 400: |400|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -sS localhost:8000/run \\
                -H 'Accept: application/x-yaml' \\
                -H 'Content-type: application/json' \\
                -d '[{
                    "client": "local",
                    "tgt": "*",
                    "fun": "test.ping",
                    "username": "saltdev",
                    "password": "saltdev",
                    "eauth": "auto"
                }]'

        .. code-block:: http

            POST /run HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml
            Content-Length: 75
            Content-Type: application/json

            [{"client": "local", "tgt": "*", "fun": "test.ping", "username": "saltdev", "password": "saltdev", "eauth": "auto"}]

        **Example response:**

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 73
            Content-Type: application/x-yaml

            return:
            - ms-0: true
              ms-1: true
              ms-2: true
              ms-3: true
              ms-4: true

        The /run enpoint can also be used to issue commands using the salt-ssh
        subsystem.

        When using salt-ssh, eauth credentials should not be supplied. Instad,
        authentication should be handled by the SSH layer itself. The use of
        the salt-ssh client does not require a salt master to be running.
        Instead, only a roster file must be present in the salt configuration
        directory.

        All SSH client requests are synchronous.

        **Example SSH client request:**

        .. code-block:: bash

            curl -sS localhost:8000/run \\
                -H 'Accept: application/x-yaml' \\
                -d client='ssh' \\
                -d tgt='*' \\
                -d fun='test.ping'

        .. code-block:: http

            POST /run HTTP/1.1
            Host: localhost:8000
            Accept: application/x-yaml
            Content-Length: 75
            Content-Type: application/x-www-form-urlencoded

            client=ssh&tgt=*&fun=test.ping

        **Example SSH response:**

        .. code-block:: http

                return:
                - silver:
                  fun: test.ping
                  fun_args: []
                  id: silver
                  jid: '20141203103525666185'
                  retcode: 0
                  return: true
                  success: true
        '''
        return {
            'return': list(self.exec_lowstate()),
        }


class Events(object):
    '''
    Expose the Salt event bus

    The event bus on the Salt master exposes a large variety of things, notably
    when executions are started on the master and also when minions ultimately
    return their results. This URL provides a real-time window into a running
    Salt infrastructure.

    .. seealso:: :ref:`events`

    '''
    exposed = True

    _cp_config = dict(LowDataAdapter._cp_config, **{
        'response.stream': True,
        'tools.encode.encoding': 'utf-8',

        # Auth handled manually below
        'tools.salt_token.on': True,
        'tools.salt_auth.on': False,

        'tools.hypermedia_in.on': False,
        'tools.hypermedia_out.on': False,
    })

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.resolver = salt.auth.Resolver(self.opts)

    def _is_valid_token(self, auth_token):
        '''
        Check if this is a valid salt-api token or valid Salt token

        salt-api tokens are regular session tokens that tie back to a real Salt
        token. Salt tokens are tokens generated by Salt's eauth system.

        :return bool: True if valid, False if not valid.
        '''
        if auth_token is None:
            return False

        # First check if the given token is in our session table; if so it's a
        # salt-api token and we need to get the Salt token from there.
        orig_session, _ = cherrypy.session.cache.get(auth_token, ({}, None))
        # If it's not in the session table, assume it's a regular Salt token.
        salt_token = orig_session.get('token', auth_token)

        # The eauth system does not currently support perms for the event
        # stream, so we're just checking if the token exists not if the token
        # allows access.
        if salt_token and self.resolver.get_token(salt_token):
            return True

        return False

    def GET(self, token=None, salt_token=None):
        r'''
        An HTTP stream of the Salt master event bus

        This stream is formatted per the Server Sent Events (SSE) spec. Each
        event is formatted as JSON.

        .. http:get:: /events

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|
            :query token: **optional** parameter containing the token
                ordinarily supplied via the X-Auth-Token header in order to
                allow cross-domain requests in browsers that do not include
                CORS support in the EventSource API. E.g.,
                ``curl -NsS localhost:8000/events?token=308650d``
            :query salt_token: **optional** parameter containing a raw Salt
                *eauth token* (not to be confused with the token returned from
                the /login URL). E.g.,
                ``curl -NsS localhost:8000/events?salt_token=30742765``

        **Example request:**

        .. code-block:: bash

            curl -NsS localhost:8000/events

        .. code-block:: http

            GET /events HTTP/1.1
            Host: localhost:8000

        **Example response:**

        Note, the ``tag`` field is not part of the spec. SSE compliant clients
        should ignore unknown fields. This addition allows non-compliant
        clients to only watch for certain tags without having to deserialze the
        JSON object each time.

        .. code-block:: http

            HTTP/1.1 200 OK
            Connection: keep-alive
            Cache-Control: no-cache
            Content-Type: text/event-stream;charset=utf-8

            retry: 400

            tag: salt/job/20130802115730568475/new
            data: {'tag': 'salt/job/20130802115730568475/new', 'data': {'minions': ['ms-4', 'ms-3', 'ms-2', 'ms-1', 'ms-0']}}

            tag: salt/job/20130802115730568475/ret/jerry
            data: {'tag': 'salt/job/20130802115730568475/ret/jerry', 'data': {'jid': '20130802115730568475', 'return': True, 'retcode': 0, 'success': True, 'cmd': '_return', 'fun': 'test.ping', 'id': 'ms-1'}}

        The event stream can be easily consumed via JavaScript:

        .. code-block:: javascript

            var source = new EventSource('/events');
            source.onopen = function() { console.info('Listening ...') };
            source.onerror = function(err) { console.error(err) };
            source.onmessage = function(message) {
              var saltEvent = JSON.parse(message.data);
              console.info(saltEvent.tag)
              console.debug(saltEvent.data)
            };

        Or using CORS:

        .. code-block:: javascript

            var source = new EventSource('/events?token=ecd589e4e01912cf3c4035afad73426dbb8dba75', {withCredentials: true});

        It is also possible to consume the stream via the shell.

        Records are separated by blank lines; the ``data:`` and ``tag:``
        prefixes will need to be removed manually before attempting to
        unserialize the JSON.

        curl's ``-N`` flag turns off input buffering which is required to
        process the stream incrementally.

        Here is a basic example of printing each event as it comes in:

        .. code-block:: bash

            curl -NsS localhost:8000/events |\
                    while IFS= read -r line ; do
                        echo $line
                    done

        Here is an example of using awk to filter events based on tag:

        .. code-block:: bash

            curl -NsS localhost:8000/events |\
                    awk '
                        BEGIN { RS=""; FS="\\n" }
                        $1 ~ /^tag: salt\/job\/[0-9]+\/new$/ { print $0 }
                    '
            tag: salt/job/20140112010149808995/new
            data: {"tag": "salt/job/20140112010149808995/new", "data": {"tgt_type": "glob", "jid": "20140112010149808995", "tgt": "jerry", "_stamp": "2014-01-12_01:01:49.809617", "user": "shouse", "arg": [], "fun": "test.ping", "minions": ["jerry"]}}
            tag: 20140112010149808995
            data: {"tag": "20140112010149808995", "data": {"fun_args": [], "jid": "20140112010149808995", "return": true, "retcode": 0, "success": true, "cmd": "_return", "_stamp": "2014-01-12_01:01:49.819316", "fun": "test.ping", "id": "jerry"}}
        '''
        cookies = cherrypy.request.cookie
        auth_token = token or salt_token or (
            cookies['session_id'].value if 'session_id' in cookies else None)

        if not self._is_valid_token(auth_token):
            raise cherrypy.HTTPError(401)

        # Release the session lock before starting the long-running response
        cherrypy.session.release_lock()

        cherrypy.response.headers['Content-Type'] = 'text/event-stream'
        cherrypy.response.headers['Cache-Control'] = 'no-cache'
        cherrypy.response.headers['Connection'] = 'keep-alive'

        def listen():
            '''
            An iterator to yield Salt events
            '''
            event = salt.utils.event.get_event(
                    'master',
                    sock_dir=self.opts['sock_dir'],
                    transport=self.opts['transport'],
                    opts=self.opts,
                    listen=True)
            stream = event.iter_events(full=True, auto_reconnect=True)

            yield u'retry: {0}\n'.format(400)

            while True:
                data = next(stream)
                yield u'tag: {0}\n'.format(data.get('tag', ''))
                yield u'data: {0}\n\n'.format(json.dumps(data))

        return listen()


class WebsocketEndpoint(object):
    '''
    Open a WebSocket connection to Salt's event bus

    The event bus on the Salt master exposes a large variety of things, notably
    when executions are started on the master and also when minions ultimately
    return their results. This URL provides a real-time window into a running
    Salt infrastructure. Uses websocket as the transport mechanism.

    .. seealso:: :ref:`events`
    '''
    exposed = True

    _cp_config = dict(LowDataAdapter._cp_config, **{
        'response.stream': True,
        'tools.encode.encoding': 'utf-8',

        # Auth handled manually below
        'tools.salt_token.on': True,
        'tools.salt_auth.on': False,

        'tools.hypermedia_in.on': False,
        'tools.hypermedia_out.on': False,
        'tools.websocket.on': True,
        'tools.websocket.handler_cls': websockets.SynchronizingWebsocket,
    })

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.auth = salt.auth.LoadAuth(self.opts)

    def GET(self, token=None, **kwargs):
        '''
        Return a websocket connection of Salt's event stream

        .. http:get:: /ws/(token)

        :query format_events: The event stream will undergo server-side
            formatting if the ``format_events`` URL parameter is included
            in the request. This can be useful to avoid formatting on the
            client-side:

            .. code-block:: bash

                curl -NsS <...snip...> localhost:8000/ws?format_events

        :reqheader X-Auth-Token: an authentication token from
            :py:class:`~Login`.

        :status 101: switching to the websockets protocol
        :status 401: |401|
        :status 406: |406|

        **Example request:** ::

            curl -NsSk \\
                -H 'X-Auth-Token: ffedf49d' \\
                -H 'Host: localhost:8000' \\
                -H 'Connection: Upgrade' \\
                -H 'Upgrade: websocket' \\
                -H 'Origin: https://localhost:8000' \\
                -H 'Sec-WebSocket-Version: 13' \\
                -H 'Sec-WebSocket-Key: '"$(echo -n $RANDOM | base64)" \\
                localhost:8000/ws

        .. code-block:: http

            GET /ws HTTP/1.1
            Connection: Upgrade
            Upgrade: websocket
            Host: localhost:8000
            Origin: https://localhost:8000
            Sec-WebSocket-Version: 13
            Sec-WebSocket-Key: s65VsgHigh7v/Jcf4nXHnA==
            X-Auth-Token: ffedf49d

        **Example response**:

        .. code-block:: http

            HTTP/1.1 101 Switching Protocols
            Upgrade: websocket
            Connection: Upgrade
            Sec-WebSocket-Accept: mWZjBV9FCglzn1rIKJAxrTFlnJE=
            Sec-WebSocket-Version: 13

        An authentication token **may optionally** be passed as part of the URL
        for browsers that cannot be configured to send the authentication
        header or cookie:

        .. code-block:: bash

            curl -NsS <...snip...> localhost:8000/ws/ffedf49d

        The event stream can be easily consumed via JavaScript:

        .. code-block:: javascript

            // Note, you must be authenticated!
            var source = new Websocket('ws://localhost:8000/ws/d0ce6c1a');
            source.onerror = function(e) { console.debug('error!', e); };
            source.onmessage = function(e) { console.debug(e.data); };

            source.send('websocket client ready')

            source.close();

        Or via Python, using the Python module `websocket-client
        <https://pypi.python.org/pypi/websocket-client/>`_ for example.

        .. code-block:: python

            # Note, you must be authenticated!

            from websocket import create_connection

            ws = create_connection('ws://localhost:8000/ws/d0ce6c1a')
            ws.send('websocket client ready')

            # Look at https://pypi.python.org/pypi/websocket-client/ for more
            # examples.
            while listening_to_events:
                print ws.recv()

            ws.close()

        Above examples show how to establish a websocket connection to Salt and
        activating real time updates from Salt's event stream by signaling
        ``websocket client ready``.
        '''
        # Pulling the session token from an URL param is a workaround for
        # browsers not supporting CORS in the EventSource API.
        if token:
            orig_session, _ = cherrypy.session.cache.get(token, ({}, None))
            salt_token = orig_session.get('token')
        else:
            salt_token = cherrypy.session.get('token')

        # Manually verify the token
        if not salt_token or not self.auth.get_tok(salt_token):
            raise cherrypy.HTTPError(401)

        # Release the session lock before starting the long-running response
        cherrypy.session.release_lock()

        # A handler is the server side end of the websocket connection. Each
        # request spawns a new instance of this handler
        handler = cherrypy.request.ws_handler

        def event_stream(handler, pipe):
            '''
            An iterator to return Salt events (and optionally format them)
            '''
            # blocks until send is called on the parent end of this pipe.
            pipe.recv()

            event = salt.utils.event.get_event(
                    'master',
                    sock_dir=self.opts['sock_dir'],
                    transport=self.opts['transport'],
                    opts=self.opts,
                    listen=True)
            stream = event.iter_events(full=True, auto_reconnect=True)
            SaltInfo = event_processor.SaltInfo(handler)

            def signal_handler(signal, frame):
                os._exit(0)

            signal.signal(signal.SIGTERM, signal_handler)

            while True:
                data = next(stream)
                if data:
                    try:  # work around try to decode catch unicode errors
                        if 'format_events' in kwargs:
                            SaltInfo.process(data, salt_token, self.opts)
                        else:
                            handler.send('data: {0}\n\n'.format(
                                json.dumps(data)), False)
                    except UnicodeDecodeError:
                        logger.error(
                                "Error: Salt event has non UTF-8 data:\n{0}"
                                .format(data))
                time.sleep(0.1)

        parent_pipe, child_pipe = Pipe()
        handler.pipe = parent_pipe
        handler.opts = self.opts
        # Process to handle async push to a client.
        # Each GET request causes a process to be kicked off.
        proc = Process(target=event_stream, args=(handler, child_pipe))
        proc.start()


class Webhook(object):
    '''
    A generic web hook entry point that fires an event on Salt's event bus

    External services can POST data to this URL to trigger an event in Salt.
    For example, Amazon SNS, Jenkins-CI or Travis-CI, or GitHub web hooks.

    .. note:: Be mindful of security

        Salt's Reactor can run any code. A Reactor SLS that responds to a hook
        event is responsible for validating that the event came from a trusted
        source and contains valid data.

        **This is a generic interface and securing it is up to you!**

        This URL requires authentication however not all external services can
        be configured to authenticate. For this reason authentication can be
        selectively disabled for this URL. Follow best practices -- always use
        SSL, pass a secret key, configure the firewall to only allow traffic
        from a known source, etc.

    The event data is taken from the request body. The
    :mailheader:`Content-Type` header is respected for the payload.

    The event tag is prefixed with ``salt/netapi/hook`` and the URL path is
    appended to the end. For example, a ``POST`` request sent to
    ``/hook/mycompany/myapp/mydata`` will produce a Salt event with the tag
    ``salt/netapi/hook/mycompany/myapp/mydata``.

    The following is an example ``.travis.yml`` file to send notifications to
    Salt of successful test runs:

    .. code-block:: yaml

        language: python
        script: python -m unittest tests
        after_success:
            - |
                curl -sSk https://saltapi-url.example.com:8000/hook/travis/build/success \
                        -d branch="${TRAVIS_BRANCH}" \
                        -d commit="${TRAVIS_COMMIT}"

    .. seealso:: :ref:`events`, :ref:`reactor`
    '''
    exposed = True
    tag_base = ['salt', 'netapi', 'hook']

    _cp_config = dict(LowDataAdapter._cp_config, **{
        # Don't do any lowdata processing on the POST data
        'tools.lowdata_fmt.on': True,

        # Auth can be overridden in __init__().
        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,
    })

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.event = salt.utils.event.get_event(
                'master',
                sock_dir=self.opts['sock_dir'],
                transport=self.opts['transport'],
                opts=self.opts,
                listen=False)

        if cherrypy.config['apiopts'].get('webhook_disable_auth'):
            self._cp_config['tools.salt_token.on'] = False
            self._cp_config['tools.salt_auth.on'] = False

    def POST(self, *args, **kwargs):
        '''
        Fire an event in Salt with a custom event tag and data

        .. http:post:: /hook

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|
            :status 413: request body is too large

        **Example request:**

        .. code-block:: bash

            curl -sS localhost:8000/hook \\
                -H 'Content-type: application/json' \\
                -d '{"foo": "Foo!", "bar": "Bar!"}'

        .. code-block:: http

            POST /hook HTTP/1.1
            Host: localhost:8000
            Content-Length: 16
            Content-Type: application/json

            {"foo": "Foo!", "bar": "Bar!"}

        **Example response**:

        .. code-block:: http

            HTTP/1.1 200 OK
            Content-Length: 14
            Content-Type: application/json

            {"success": true}

        As a practical example, an internal continuous-integration build
        server could send an HTTP POST request to the URL
        ``https://localhost:8000/hook/mycompany/build/success`` which contains
        the result of a build and the SHA of the version that was built as
        JSON. That would then produce the following event in Salt that could be
        used to kick off a deployment via Salt's Reactor::

            Event fired at Fri Feb 14 17:40:11 2014
            *************************
            Tag: salt/netapi/hook/mycompany/build/success
            Data:
            {'_stamp': '2014-02-14_17:40:11.440996',
                'headers': {
                    'X-My-Secret-Key': 'F0fAgoQjIT@W',
                    'Content-Length': '37',
                    'Content-Type': 'application/json',
                    'Host': 'localhost:8000',
                    'Remote-Addr': '127.0.0.1'},
                'post': {'revision': 'aa22a3c4b2e7', 'result': True}}

        Salt's Reactor could listen for the event:

        .. code-block:: yaml

            reactor:
              - 'salt/netapi/hook/mycompany/build/*':
                - /srv/reactor/react_ci_builds.sls

        And finally deploy the new build:

        .. code-block:: jinja

            {% set secret_key = data.get('headers', {}).get('X-My-Secret-Key') %}
            {% set build = data.get('post', {}) %}

            {% if secret_key == 'F0fAgoQjIT@W' and build.result == True %}
            deploy_my_app:
              cmd.state.sls:
                - tgt: 'application*'
                - arg:
                  - myapp.deploy
                - kwarg:
                    pillar:
                      revision: {{ revision }}
            {% endif %}
        '''
        tag = '/'.join(itertools.chain(self.tag_base, args))
        data = cherrypy.serving.request.unserialized_data
        if not data:
            data = {}
        raw_body = getattr(cherrypy.serving.request, 'raw_body', '')
        headers = dict(cherrypy.request.headers)

        ret = self.event.fire_event({
            'body': raw_body,
            'post': data,
            'headers': headers,
        }, tag)
        return {'success': ret}


class Stats(object):
    '''
    Expose statistics on the running CherryPy server
    '''
    exposed = True

    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,
    })

    def GET(self):
        '''
        Return a dump of statistics collected from the CherryPy server

        .. http:get:: /stats

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|

            :resheader Content-Type: |res_ct|

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|
        '''
        if hasattr(logging, 'statistics'):
            # Late import
            try:
                from cherrypy.lib import cpstats
            except ImportError:
                logger.error('Import of cherrypy.cpstats failed. Possible '
                        'upstream bug here: https://github.com/cherrypy/cherrypy/issues/1444')
                return {}
            return cpstats.extrapolate_statistics(logging.statistics)

        return {}


class App(object):
    '''
    Class to serve HTML5 apps
    '''
    exposed = True

    def GET(self, *args):
        '''
        Serve a single static file ignoring the remaining path

        This is useful in combination with a browser-based app using the HTML5
        history API.

        .. http::get:: /app

            :reqheader X-Auth-Token: |req_token|

            :status 200: |200|
            :status 401: |401|
        '''
        apiopts = cherrypy.config['apiopts']
        return cherrypy.lib.static.serve_file(apiopts['app'])


class API(object):
    '''
    Collect configuration and URL map for building the CherryPy app
    '''
    url_map = {
        'index': LowDataAdapter,
        'login': Login,
        'logout': Logout,
        'minions': Minions,
        'run': Run,
        'jobs': Jobs,
        'keys': Keys,
        'events': Events,
        'stats': Stats,
    }

    def _setattr_url_map(self):
        '''
        Set an attribute on the local instance for each key/val in url_map

        CherryPy uses class attributes to resolve URLs.
        '''
        for url, cls in six.iteritems(self.url_map):
            setattr(self, url, cls())

    def _update_url_map(self):
        '''
        Assemble any dynamic or configurable URLs
        '''
        if HAS_WEBSOCKETS:
            self.url_map.update({
                'ws': WebsocketEndpoint,
            })

        # Allow the Webhook URL to be overridden from the conf.
        self.url_map.update({
            self.apiopts.get('webhook_url', 'hook').lstrip('/'): Webhook,
        })

        # Enable the single-page JS app URL.
        if 'app' in self.apiopts:
            self.url_map.update({
                self.apiopts.get('app_path', 'app').lstrip('/'): App,
            })

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.apiopts = cherrypy.config['apiopts']

        self._update_url_map()
        self._setattr_url_map()

    def get_conf(self):
        '''
        Combine the CherryPy configuration with the rest_cherrypy config values
        pulled from the master config and return the CherryPy configuration
        '''
        conf = {
            'global': {
                'server.socket_host': self.apiopts.get('host', '0.0.0.0'),
                'server.socket_port': self.apiopts.get('port', 8000),
                'server.thread_pool': self.apiopts.get('thread_pool', 100),
                'server.socket_queue_size': self.apiopts.get('queue_size', 30),
                'engine.timeout_monitor.on': self.apiopts.get(
                    'expire_responses', True),
                'max_request_body_size': self.apiopts.get(
                    'max_request_body_size', 1048576),
                'debug': self.apiopts.get('debug', False),
                'log.access_file': self.apiopts.get('log_access_file', ''),
                'log.error_file': self.apiopts.get('log_error_file', ''),
            },
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),

                'tools.trailing_slash.on': True,
                'tools.gzip.on': True,

                'tools.cpstats.on': self.apiopts.get('collect_stats', False),

                'tools.html_override.on': True,
                'tools.cors_tool.on': True,
            },
        }

        if 'favicon' in self.apiopts:
            conf['/favicon.ico'] = {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': self.apiopts['favicon'],
            }

        if self.apiopts.get('debug', False) is False:
            conf['global']['environment'] = 'production'

        # Serve static media if the directory has been set in the configuration
        if 'static' in self.apiopts:
            conf[self.apiopts.get('static_path', '/static')] = {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': self.apiopts['static'],
            }

        # Add to global config
        cherrypy.config.update(conf['global'])

        return conf


def get_app(opts):
    '''
    Returns a WSGI app and a configuration dictionary
    '''
    apiopts = opts.get(__name__.rsplit('.', 2)[-2], {})  # rest_cherrypy opts

    # Add Salt and salt-api config options to the main CherryPy config dict
    cherrypy.config['saltopts'] = opts
    cherrypy.config['apiopts'] = apiopts

    root = API()  # cherrypy app
    cpyopts = root.get_conf()  # cherrypy app opts

    return root, apiopts, cpyopts
