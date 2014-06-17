'''
A REST API for Salt
===================

.. py:currentmodule:: saltapi.netapi.rest_cherrypy.app

:depends:   - CherryPy Python module
:depends:   - ws4py Python module
:configuration: All authentication is done through Salt's :ref:`external auth
    <acl-eauth>` system. Be sure that it is enabled and the user you are
    authenticating as has permissions for all the functions you will be
    running.

    Example production configuration block; add to the Salt master config file:

    .. code-block:: yaml

        rest_cherrypy:
          port: 8000
          ssl_crt: /etc/pki/tls/certs/localhost.crt
          ssl_key: /etc/pki/tls/certs/localhost.key

    The REST interface strongly recommends a secure HTTPS connection since Salt
    authentication credentials will be sent over the wire. If you don't already
    have a certificate and don't wish to buy one, you can generate a
    self-signed certificate using the
    :py:func:`~salt.modules.tls.create_self_signed_cert` function in Salt (note
    the dependencies for this module):

    .. code-block:: bash

        % salt-call tls.create_self_signed_cert

    All available configuration options are detailed below. These settings
    configure the CherryPy HTTP server and do not apply when using an external
    server such as Apache or Nginx.

    port
        **Required**

        The port for the webserver to listen on.
    host : ``0.0.0.0``
        The socket interface for the HTTP server to listen on.

        .. versionadded:: 0.8.2
    debug : ``False``
        Starts the web server in development mode. It will reload itself when
        the underlying code is changed and will output more debugging info.
    ssl_crt
        The path to a SSL certificate. (See below)
    ssl_key
        The path to the private key for your SSL certificate. (See below)
    disable_ssl
        A flag to disable SSL. Warning: your Salt authentication credentials
        will be sent in the clear!

        .. versionadded:: 0.8.3
    webhook_disable_auth : False
        The :py:class:`Webhook` URL requires authentication by default but
        external services cannot always be configured to send authentication.
        See the Webhook documentation for suggestions on securing this
        interface.

        .. versionadded:: 0.8.4.1
    webhook_url : /hook
        Configure the URL endpoint for the :py:class:`Webhook` entry point.

        .. versionadded:: 0.8.4.1
    thread_pool : ``100``
        The number of worker threads to start up in the pool.

        .. versionchanged:: 0.8.4
            Previous versions defaulted to a pool of ``10``
    socket_queue_size : ``30``
        Specify the maximum number of HTTP connections to queue.

        .. versionchanged:: 0.8.4
            Previous versions defaulted to ``5`` connections.
    max_request_body_size : ``1048576``
        .. versionchanged:: 0.8.4
            Previous versions defaulted to ``104857600`` for the size of the
            request body
    collect_stats : False
        Collect and report statistics about the CherryPy server

        .. versionadded:: 0.8.4

        Reports are available via the :py:class:`Stats` URL.
    static
        A filesystem path to static HTML/JavaScript/CSS/image assets.
    static_path : ``/static``
        The URL prefix to use when serving static assets out of the directory
        specified in the ``static`` setting.

        .. versionadded:: 0.8.2
    app
        A filesystem path to an HTML file that will be served as a static file.
        This is useful for bootstrapping a single-page JavaScript app.

        .. versionadded:: 0.8.2
    app_path : ``/app``
        The URL prefix to use for serving the HTML file specified in the ``app``
        setting. This should be a simple name containing no slashes.

        Any path information after the specified path is ignored; this is
        useful for apps that utilize the HTML5 history API.

        .. versionadded:: 0.8.2
    root_prefix : ``/``
        A URL path to the main entry point for the application. This is useful
        for serving multiple applications from the same URL.

        .. versionadded:: 0.8.4

Authentication
--------------

Authentication is performed by passing a session token with each request. The
token may be sent either via a custom header named :mailheader:`X-Auth-Token`
or sent inside a cookie. (The result is the same but browsers and some HTTP
clients handle cookies automatically and transparently so it is a convenience.)

Token are generated via the :py:class:`Login` URL.

.. seealso:: You can bypass the session handling via the :py:class:`Run` URL.

Usage
-----

You access a running Salt master via this module by sending HTTP requests to
the URLs detailed below.

.. admonition:: Content negotiation

    This REST interface is flexible in what data formats it will accept as well
    as what formats it will return (e.g., JSON, YAML, x-www-form-urlencoded).

    * Specify the format of data you are sending in a request by including the
      :mailheader:`Content-Type` header.
    * Specify your desired output format for the response with the
      :mailheader:`Accept` header.

This REST interface expects data sent in :http:method:`post` and
:http:method:`put` requests  to be in the format of a list of lowstate
dictionaries. This allows you to specify multiple commands in a single request.

.. glossary::

    lowstate
        A dictionary containing various keys that instruct Salt which command
        to run, where that command lives, any parameters for that command, any
        authentication credentials, what returner to use, etc.

        Salt uses the lowstate data format internally in many places to pass
        command data between functions. Salt also uses lowstate for the
        :ref:`LocalClient() <python-api>` Python API interface.

For example (in JSON format)::

    [{
        'client': 'local',
        'tgt': '*',
        'fun': 'test.fib',
        'arg': ['10'],
    }]

.. admonition:: x-www-form-urlencoded

    This REST interface accepts data in the x-www-form-urlencoded format. This
    is the format used by HTML forms, the default format used by
    :command:`curl`, the default format used by many JavaScript AJAX libraries
    (such as jQuery), etc. This format will be converted to the
    :term:`lowstate` format as best as possible with the caveats below. It is
    always preferable to format data in the lowstate format directly in a more
    capable format such as JSON or YAML.

    * Only a single command may be sent in this format per HTTP request.
    * Multiple ``arg`` params will be sent as a single list of params.

      Note, some popular frameworks and languages (notably jQuery, PHP, and
      Ruby on Rails) will automatically append empty brackets onto repeated
      parameters. E.g., arg=one, arg=two will be sent as arg[]=one, arg[]=two.
      Again, it is preferable to send lowstate via JSON or YAML directly by
      specifying the :mailheader:`Content-Type` header in the request.

URL reference
-------------

The main entry point is the :py:class:`root URL (/) <LowDataAdapter>` and all
functionality is available at that URL. The other URLs are largely convenience
URLs that wrap that main entry point with shorthand or specialized
functionality.

'''
# We need a custom pylintrc here...
# pylint: disable=W0212,E1101,C0103,R0201,W0221,W0613

# Import Python libs
import collections
import itertools
import functools
import logging
import json

# Import third-party libs
import cherrypy
from cherrypy.lib import cpstats
import yaml

# Import Salt libs
import salt
import salt.auth
import salt.utils.event

# Import salt-api libs
import saltapi

# Imports related to websocket
import time
import event_processor
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket
from multiprocessing import Process, Lock, Pipe

logger = logging.getLogger(__name__)


def salt_token_tool():
    '''
    If the custom authentication header is supplied, put it in the cookie dict
    so the rest of the session-based auth works as intended
    '''
    x_auth = cherrypy.request.headers.get('X-Auth-Token', None)

    # X-Auth-Token header trumps session cookie
    if x_auth:
        cherrypy.request.cookie['session_id'] = x_auth

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
                if not rem_ip in auth_ip_list:
                    logger.error("Blocked IP: {0}".format(rem_ip))
                    cherrypy.response.status = 403
                    return {
                        'status': cherrypy.response.status,
                        'return': "Bad IP",
                    }
    request = cherrypy.serving.request
    cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'


def salt_auth_tool():
    '''
    Redirect all unauthenticated requests to the login page
    '''
    # Redirect to the login page if the session hasn't been authed
    if not cherrypy.session.has_key('token'):
        raise cherrypy.InternalRedirect('/login')

    # Session is authenticated; inform caches
    cherrypy.response.headers['Cache-Control'] = 'private'

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
        cherrypy.response.processors = dict(ct_out_map) # handlers may modify this
        ret = cherrypy.serving.request._hypermedia_inner_handler(*args, **kwargs)
    except salt.exceptions.EauthAuthenticationError:
        raise cherrypy.InternalRedirect('/login')
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
    return out(ret)


def hypermedia_out():
    '''
    Determine the best handler for the requested content type

    Wrap the normal handler and transform the output from that handler into the
    requested content type
    '''
    request = cherrypy.serving.request
    request._hypermedia_inner_handler = request.handler
    request.handler = hypermedia_handler

    cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'


@functools.wraps
def process_request_body(fn):
    '''
    A decorator to skip a processor function if process_request_body is False
    '''
    def wrapped(*args, **kwargs):
        if cherrypy.request.process_request_body != False:
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

        curl -si localhost:8000 -d client=local -d tgt='*' \\
                -d fun='test.kwarg' -d arg='one=1' -d arg='two=2'

    :param entity: raw POST data
    '''
    # First call out to CherryPy's default processor
    cherrypy._cpreqbody.process_urlencoded(entity)
    cherrypy.serving.request.unserialized_data = entity.params


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

    # TODO: call lowdata validation routines from here

    data = cherrypy.request.unserialized_data

    if cherrypy.request.headers['Content-Type'] == 'application/x-www-form-urlencoded':
        # Make the 'arg' param a list if not already
        if 'arg' in data and not isinstance(data['arg'], list):
            data['arg'] = [data['arg']]

        # Finally, make a Low State and put it in request
        cherrypy.request.lowstate = [data]
    else:
        cherrypy.serving.request.lowstate = data


cherrypy.tools.salt_token = cherrypy.Tool('on_start_resource',
        salt_token_tool, priority=55)
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
    The primary entry point to the REST API. All functionality is available
    through this URL. The other available URLs provide convenience wrappers
    around this URL.
    '''
    exposed = True

    _cp_config = {
        'tools.sessions.on': True,
        'tools.sessions.timeout': 60 * 10, # 10 hours

        # 'tools.autovary.on': True,

        'tools.hypermedia_out.on': True,
        'tools.hypermedia_in.on': True,
        'tools.lowdata_fmt.on': True,
        'tools.salt_ip_verify.on': True,
    }

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.api = saltapi.APIClient(self.opts)

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
        cherrypy.session.release_lock()

        # if the lowstate loaded isn't a list, lets notify the client
        if type(lowstate) != list:
            raise cherrypy.HTTPError(400, 'Lowstates must be a list')

        # Make any requested additions or modifications to each lowstate, then
        # execute each one and yield the result.
        for chunk in lowstate:
            if token:
                chunk['token'] = token

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
        .. http:get:: /

            An explanation of the API with links of where to go next.

            **Example request**::

                % curl -i localhost:8000

            .. code-block:: http

                GET / HTTP/1.1
                Host: localhost:8000
                Accept: application/json

            **Example response**:

            .. code-block:: http

                HTTP/1.1 200 OK
                Content-Type: application/json

        :status 200: success
        :status 401: authentication required
        :status 406: requested Content-Type not available
        '''
        import inspect

        # Grab all available client interfaces
        clients = [name for name, _ in inspect.getmembers(saltapi.APIClient,
            predicate=inspect.ismethod) if not name.startswith('__')]
        clients.remove('run') # run method calls client interfaces

        return {
            'return': "Welcome",
            'clients': clients,
        }

    @cherrypy.tools.salt_token()
    @cherrypy.tools.salt_auth()
    def POST(self, **kwargs):
        '''
        The primary execution interface for the rest of the API

        .. http:post:: /

            **Example request**::

                % curl -si https://localhost:8000 \\
                        -H "Accept: application/x-yaml" \\
                        -H "X-Auth-Token: d40d1e1e" \\
                        -d client=local \\
                        -d tgt='*' \\
                        -d fun='test.ping' \\
                        -d arg

            .. code-block:: http

                POST / HTTP/1.1
                Host: localhost:8000
                Accept: application/x-yaml
                X-Auth-Token: d40d1e1e
                Content-Length: 36
                Content-Type: application/x-www-form-urlencoded

                fun=test.ping&arg&client=local&tgt=*

            **Example response**:

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

        :form lowstate: A list of :term:`lowstate` data appropriate for the
            :ref:`client <client-apis>` interface you are calling.

            Lowstate may be supplied in any supported format by specifying the
            :mailheader:`Content-Type` header in the request. Supported formats
            are listed in the :mailheader:`Alternates` response header.
        :status 200: success
        :status 401: authentication required
        :status 406: requested Content-Type not available
        '''
        return {
            'return': list(self.exec_lowstate(
                token=cherrypy.session.get('token')))
        }


class Minions(LowDataAdapter):
    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,
    })

    def GET(self, mid=None):
        '''
        A convenience URL for getting lists of minions or getting minion
        details

        .. http:get:: /minions/(mid)

            Get grains, modules, functions, and inline function documentation
            for all minions or a single minion

            **Example request**::

                % curl -i localhost:8000/minions/ms-3

            .. code-block:: http

                GET /minions/ms-3 HTTP/1.1
                Host: localhost:8000
                Accept: application/x-yaml

            **Example response**:

            .. code-block:: http

                HTTP/1.1 200 OK
                Content-Length: 129005
                Content-Type: application/x-yaml

                return:
                - ms-3:
                    grains.items:
                      ...

        :param mid: (optional) a minion id
        :status 200: success
        :status 401: authentication required
        :status 406: requested Content-Type not available
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

            You must pass low-data in the request body either from an HTML form
            or as JSON or YAML. The ``client`` option is pre-set to
            ``local_async``.

            **Example request**::

                % curl -sSi localhost:8000/minions \\
                    -H "Accept: application/x-yaml" \\
                    -d tgt='*' \\
                    -d fun='status.diskusage'

            .. code-block:: http

                POST /minions HTTP/1.1
                Host: localhost:8000
                Accept: application/x-yaml
                Content-Length: 26
                Content-Type: application/x-www-form-urlencoded

                tgt=*&fun=status.diskusage

            **Example response**:

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

        :form lowstate: lowstate data for the
            :py:mod:`~salt.client.LocalClient`; the ``client`` parameter will
            be set to ``local_async``

            Lowstate may be supplied in any supported format by specifying the
            :mailheader:`Content-Type` header in the request. Supported formats
            are listed in the :mailheader:`Alternates` response header.
        :status 202: success
        :status 401: authentication required
        :status 406: requested :mailheader:`Content-Type` not available
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

    def GET(self, jid=None):
        '''
        A convenience URL for getting lists of previously run jobs or getting
        the return from a single job

        .. http:get:: /jobs/(jid)

            Get grains, modules, functions, and inline function documentation
            for all minions or a single minion

            **Example request**::

                % curl -i localhost:8000/jobs

            .. code-block:: http

                GET /jobs HTTP/1.1
                Host: localhost:8000
                Accept: application/x-yaml

            **Example response**:

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

            **Example request**::

                % curl -i localhost:8000/jobs/20121130104633606931

            .. code-block:: http

                GET /jobs/20121130104633606931 HTTP/1.1
                Host: localhost:8000
                Accept: application/x-yaml

            **Example response**:

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

        :param mid: (optional) a minion id
        :status 200: success
        :status 401: authentication required
        :status 406: requested Content-Type not available
        '''
        lowstate = [{
            'client': 'runner',
            'fun': 'jobs.lookup_jid' if jid else 'jobs.list_jobs',
            'jid': jid,
        }]

        if jid:
            lowstate.append({
                'client': 'runner',
                'fun': 'jobs.list_job',
                'jid': jid,
            })

        cherrypy.request.lowstate = lowstate
        job_ret_info = list(self.exec_lowstate(
            token=cherrypy.session.get('token')))

        ret = {}
        if jid:
            job_ret, job_info = job_ret_info
            ret['info'] = [job_info]
        else:
            job_ret = job_ret_info[0]

        ret['return'] = [job_ret]
        return ret


class Login(LowDataAdapter):
    '''
    All interactions with this REST API must be authenticated. Authentication
    is performed through Salt's eauth system. You must set the eauth backend
    and allowed users by editing the :conf_master:`external_auth` section in
    your master config.

    Authentication credentials are passed to the REST API via a session id in
    one of two ways:

    If the request is initiated from a browser it must pass a session id via a
    cookie and that session must be valid and active.

    If the request is initiated programmatically, the request must contain a
    :mailheader:`X-Auth-Token` header with valid and active session id.
    '''

    def __init__(self, *args, **kwargs):
        super(Login, self).__init__(*args, **kwargs)

        self.auth = salt.auth.Resolver(self.opts)

    def GET(self):
        '''
        Present the login interface

        .. http:get:: /login

            An explanation of how to log in.

            **Example request**::

                % curl -i localhost:8000/login

            .. code-block:: http

                GET /login HTTP/1.1
                Host: localhost:8000
                Accept: text/html

            **Example response**:

            .. code-block:: http

                HTTP/1.1 200 OK
                Content-Type: text/html

        :status 401: authentication required
        :status 406: requested Content-Type not available
        '''
        cherrypy.response.headers['WWW-Authenticate'] = 'Session'

        return {
            'status': cherrypy.response.status,
            'return': "Please log in",
        }

    def POST(self, **kwargs):
        '''
        Authenticate against Salt's eauth system

        .. versionchanged:: 0.8.0
            No longer returns a 302 redirect on success.

        .. versionchanged:: 0.8.1
            Returns 401 on authentication failure

        .. http:post:: /login

            **Example request**::

                % curl -si localhost:8000/login \\
                        -H "Accept: application/json" \\
                        -d username='saltuser' \\
                        -d password='saltpass' \\
                        -d eauth='pam'

            .. code-block:: http

                POST / HTTP/1.1
                Host: localhost:8000
                Content-Length: 42
                Content-Type: application/x-www-form-urlencoded
                Accept: application/json

                username=saltuser&password=saltpass&eauth=pam

            **Example response**:

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

        :form eauth: the eauth backend configured in your master config
        :form username: username
        :form password: password
        :status 200: success
        :status 401: could not authenticate using provided credentials
        :status 406: requested Content-Type not available
        '''
        # the urlencoded_processor will wrap this in a list
        if isinstance(cherrypy.serving.request.lowstate, list):
            creds = cherrypy.serving.request.lowstate[0]
        else:
            creds = cherrypy.serving.request.lowstate

        token = self.auth.mk_token(creds)
        if not 'token' in token:
            raise cherrypy.HTTPError(401,
                    'Could not authenticate using provided credentials')

        cherrypy.response.headers['X-Auth-Token'] = cherrypy.session.id
        cherrypy.session['token'] = token['token']
        cherrypy.session['timeout'] = (token['expire'] - token['start']) / 60

        # Grab eauth config for the current backend for the current user
        try:
            perms = self.opts['external_auth'][token['eauth']][token['name']]
        except (AttributeError, IndexError):
            logger.debug("Configuration for external_auth malformed for "\
                "eauth '{0}', and user '{1}'."
                .format(token.get('eauth'), token.get('name')), exc_info=True)
            raise cherrypy.HTTPError(500,
                'Configuration for external_auth could not be read.')

        return {'return': [{
            'token': cherrypy.session.id,
            'expire': token['expire'],
            'start': token['start'],
            'user': token['name'],
            'eauth': token['eauth'],
            'perms': perms,
        }]}


class Logout(LowDataAdapter):
    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,
    })

    def POST(self):
        '''
        Destroy the currently active session and expire the session cookie

        .. versionadded:: 0.8.0
        '''
        cherrypy.lib.sessions.expire() # set client-side to expire
        cherrypy.session.regenerate() # replace server-side with new

        return {'return': "Your token has been cleared"}


class Run(LowDataAdapter):
    _cp_config = dict(LowDataAdapter._cp_config, **{
        'tools.sessions.on': False,
    })

    def POST(self, **kwargs):
        '''
        Run commands bypassing the normal session handling

        .. versionadded:: 0.8.0

        .. http:post:: /run

            This entry point is primarily for "one-off" commands. Each request
            must pass full Salt authentication credentials. Otherwise this URL
            is identical to the root (``/``) execution URL.

            **Example request**::

                % curl -sS localhost:8000/run \\
                    -H 'Accept: application/x-yaml' \\
                    -d client='local' \\
                    -d tgt='*' \\
                    -d fun='test.ping' \\
                    -d username='saltdev' \\
                    -d password='saltdev' \\
                    -d eauth='pam'

            .. code-block:: http

                POST /run HTTP/1.1
                Host: localhost:8000
                Accept: application/x-yaml
                Content-Length: 75
                Content-Type: application/x-www-form-urlencoded

                client=local&tgt=*&fun=test.ping&username=saltdev&password=saltdev&eauth=pam

            **Example response**:

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

        :form lowstate: A list of :term:`lowstate` data appropriate for the
            :ref:`client <client-apis>` specified client interface. Full
            external authentication credentials must be included.
        :status 200: success
        :status 401: authentication failed
        :status 406: requested Content-Type not available
        '''
        return {
            'return': list(self.exec_lowstate()),
        }


class Events(object):
    '''
    The event bus on the Salt master exposes a large variety of things, notably
    when executions are started on the master and also when minions ultimately
    return their results. This URL provides a real-time window into a running
    Salt infrastructure.
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
        self.auth = salt.auth.LoadAuth(self.opts)

    def GET(self, token=None):
        '''
        Return an HTTP stream of the Salt master event bus; this stream is
        formatted per the Server Sent Events (SSE) spec

        .. versionadded:: 0.8.3

        Browser clients currently lack Cross-origin resource sharing (CORS)
        support for the ``EventSource()`` API. Cross-domain requests from a
        browser may instead pass the :mailheader:`X-Auth-Token` value as an URL
        parameter::

            % curl -NsS localhost:8000/events/6d1b722e

        .. http:get:: /events

            **Example request**::

                % curl -NsS localhost:8000/events

            .. code-block:: http

                GET /events HTTP/1.1
                Host: localhost:8000

            **Example response**:

            .. code-block:: http

                HTTP/1.1 200 OK
                Connection: keep-alive
                Cache-Control: no-cache
                Content-Type: text/event-stream;charset=utf-8

                retry: 400
                data: {'tag': '', 'data': {'minions': ['ms-4', 'ms-3', 'ms-2', 'ms-1', 'ms-0']}}

                data: {'tag': '20130802115730568475', 'data': {'jid': '20130802115730568475', 'return': True, 'retcode': 0, 'success': True, 'cmd': '_return', 'fun': 'test.ping', 'id': 'ms-1'}}

        The event stream can be easily consumed via JavaScript:

        .. code-block:: javascript

            # Note, you must be authenticated!
            var source = new EventSource('/events');
            source.onopen = function() { console.debug('opening') };
            source.onerror = function(e) { console.debug('error!', e) };
            source.onmessage = function(e) { console.debug(e.data) };

        It is also possible to consume the stream via the shell.

        Records are separated by blank lines; the ``data:`` and ``tag:``
        prefixes will need to be removed manually before attempting to
        unserialize the JSON.

        curl's ``-N`` flag turns off input buffering which is required to
        process the stream incrementally.

        Here is a basic example of printing each event as it comes in:

        .. code-block:: bash

            % curl -NsS localhost:8000/events |\\
                    while IFS= read -r line ; do
                        echo $line
                    done

        Here is an example of using awk to filter events based on tag:

        .. code-block:: bash

            % curl -NsS localhost:8000/events |\\
                    awk '
                        BEGIN { RS=""; FS="\\n" }
                        $1 ~ /^tag: salt\/job\/[0-9]+\/new$/ { print $0 }
                    '
            tag: salt/job/20140112010149808995/new
            data: {"tag": "salt/job/20140112010149808995/new", "data": {"tgt_type": "glob", "jid": "20140112010149808995", "tgt": "jerry", "_stamp": "2014-01-12_01:01:49.809617", "user": "shouse", "arg": [], "fun": "test.ping", "minions": ["jerry"]}}
            tag: 20140112010149808995
            data: {"tag": "20140112010149808995", "data": {"fun_args": [], "jid": "20140112010149808995", "return": true, "retcode": 0, "success": true, "cmd": "_return", "_stamp": "2014-01-12_01:01:49.819316", "fun": "test.ping", "id": "jerry"}}

        :status 200: success
        :status 401: could not authenticate using provided credentials
        '''
        # Pulling the session token from an URL param is a workaround for
        # browsers not supporting CORS in the EventSource API.
        if token:
            orig_sesion, _ = cherrypy.session.cache.get(token, ({}, None))
            salt_token = orig_sesion.get('token')
        else:
            salt_token = cherrypy.session.get('token')

        # Manually verify the token
        if not salt_token or not self.auth.get_tok(salt_token):
            raise cherrypy.InternalRedirect('/login')

        # Release the session lock before starting the long-running response
        cherrypy.session.release_lock()

        cherrypy.response.headers['Content-Type'] = 'text/event-stream'
        cherrypy.response.headers['Cache-Control'] = 'no-cache'
        cherrypy.response.headers['Connection'] = 'keep-alive'

        def listen():
            event = salt.utils.event.SaltEvent('master', self.opts['sock_dir'])
            stream = event.iter_events(full=True)

            yield u'retry: {0}\n'.format(400)

            while True:
                data = stream.next()
                yield u'tag: {0}\n'.format(data.get('tag', ''))
                yield u'data: {0}\n\n'.format(json.dumps(data))

        return listen()


class SynchronizingWebsocket(WebSocket):
    '''
    Class to handle requests sent to this websocket connection.
    Each instance of this class represents a Salt websocket connection.
    Waits to receive a ``ready`` message fom the client.
    Calls send on it's end of the pipe to signal to the sender on receipt
    of ``ready``.

    This class also kicks off initial information probing jobs when clients
    initially connect. These jobs help gather information about minions, jobs,
    and documentation.
    '''
    def __init__(self, *args, **kwargs):
        super(SynchronizingWebsocket, self).__init__(*args, **kwargs)

        '''
        This pipe needs to represent the parent end of a pipe.
        Clients need to ensure that the pipe assigned to ``self.pipe`` is
        the ``parent end`` of a
        `pipe <https://docs.python.org/2/library/multiprocessing.html#exchanging-objects-between-processes>`_.
        '''
        self.pipe = None

        '''
        The token that we can use to make API calls.
        There are times when we would like to kick off jobs,
        examples include trying to obtain minions connected.
        '''
        self.token = None

        '''
        Options represent ``salt`` options defined in the configs.
        '''
        self.opts = None

    def received_message(self, message):
        '''
        Checks if the client has sent a ready message.
        A ready message causes ``send()`` to be called on the
        ``parent end`` of the pipe.

        Clients need to ensure that the pipe assigned to ``self.pipe`` is
        the ``parent end`` of a pipe.

        This ensures completion of the underlying websocket connection
        and can be used to synchronize parallel senders.
        '''
        if message.data == 'websocket client ready':
            self.pipe.send(message)
            client = saltapi.APIClient(self.opts)
            client.run({
                'fun': 'grains.items',
                'tgt': '*',
                'token': self.token,
                'mode': 'client',
                'async': 'local_async',
                'client': 'local'
                })
        self.send('server received message', False)


class WebsocketEndpoint(object):
    '''
    Exposes formatted results from Salt's event bus.
    The event bus on the Salt master exposes a large variety of things, notably
    when executions are started on the master and also when minions ultimately
    return their results. This URL provides a real-time window into a running
    Salt infrastructure. Uses websocket as the transport mechanism.

    Exposes GET method to return websocket connections.
    All requests should include an auth token.
    A way to obtain obtain authentication tokens is shown below.

    .. code-block:: bash

        % curl -si localhost:8000/login \\
            -H "Accept: application/json" \\
            -d username='salt' \\
            -d password='salt' \\
            -d eauth='pam'

    Which results in the response

    .. code-block:: json

        {
            "return": [{
                "perms": [".*", "@runner", "@wheel"],
                "start": 1400556492.277421,
                "token": "d0ce6c1a37e99dcc0374392f272fe19c0090cca7",
                "expire": 1400599692.277422,
                "user": "salt",
                "eauth": "pam"
            }]
        }

    In this example the ``token`` returned is ``d0ce6c1a37e99dcc0374392f272fe19c0090cca7`` and can be included
    in subsequent websocket requests (perhaps as part of the URL).
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
        'tools.websocket.handler_cls': SynchronizingWebsocket,
    })

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.auth = salt.auth.LoadAuth(self.opts)

    def GET(self, token=None):
        '''
        Return a websocket connection to Salt
        representing Salt's formatted "real time" event stream.

        Makes use of Salt's ``presence
        events`` to track minions connected. Presence events are OFF by default and
        can be turned on using the ``presence_events`` and ``loop_interval`` options
        in the Salt master :ref:`config file <configuration-salt-master>`.

        Provides a convenient way for clients to make an HTTP
        call and obtain a websocket connection.

        .. http:get:: /formatted_events

            **Example response**:

            .. code-block:: http

                Request URL:ws://localhost:8000/formatted_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7
                Request Method:GET
                Status Code:101 Switching Protocols
                Host:localhost:8000
                Origin:http://localhost:8000
                Pragma:no-cache
                Sec-WebSocket-Extensions:permessage-deflate; client_max_window_bits, x-webkit-deflate-frame
                Sec-WebSocket-Key:Bdp7VlCtPvkieC3epOiIgA==
                Sec-WebSocket-Version:13
                Upgrade:websocket
                Connection:Upgrade
                Content-Type:text/plain;charset=utf-8
                Date:Tue, 20 May 2014 02:03:08 GMT
                Server:CherryPy/3.2.3
                Upgrade:websocket

        :status 401: could not authenticate using provided credentials

        The event stream can be easily consumed via JavaScript:

        .. code-block:: javascript

            // Note, you must be authenticated!

            // Get the Websocket connection to Salt
            var source = new Websocket('ws://localhost:8000/formatted_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7');

            // Get Salt's "real time" event stream.
            source.onopen = function() { source.send('websocket client ready'); };

            // Other handlers
            source.onerror = function(e) { console.debug('error!', e); };

            // e.data represents Salt's "real time" event data as serialized JSON.
            source.onmessage = function(e) { console.debug(e.data); };

            // Terminates websocket connection and Salt's "real time" event stream on the server.
            source.close();

        Or via Python, using the Python module
        `websocket-client <https://pypi.python.org/pypi/websocket-client/>`_ for example.

        .. code-block:: python

            # Note, you must be authenticated!

            from websocket import create_connection

            # Get the Websocket connection to Salt
            ws = create_connection('ws://localhost:8000/formatted_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7')

            # Get Salt's "real time" event stream.
            ws.send('websocket client ready')


            # Simple listener to print results of Salt's "real time" event stream.
            # Look at https://pypi.python.org/pypi/websocket-client/ for more examples.
            while listening_to_events:
                print ws.recv()       #  Salt's "real time" event data as serialized JSON.

            # Terminates websocket connection and Salt's "real time" event stream on the server.
            ws.close()

        Above examples show how to establish a websocket connection to Salt and activating
        real time updates from Salt's event stream by signaling ``websocket client ready``.
        '''
        # Pulling the session token from an URL param is a workaround for
        # browsers not supporting CORS in the EventSource API.
        if token:
            orig_sesion, _ = cherrypy.session.cache.get(token, ({}, None))
            salt_token = orig_sesion.get('token')
        else:
            salt_token = cherrypy.session.get('token')

        # Manually verify the token
        if not salt_token or not self.auth.get_tok(salt_token):
            raise cherrypy.HTTPError(401)  # unauthorized

        # Release the session lock before starting the long-running response


        cherrypy.session.release_lock()


        '''
        A handler is the server side end of the websocket connection.
        Each request spawns a new instance of this handler
        '''
        handler = cherrypy.request.ws_handler


        minions = {
            'fun': 'grains.items',
            'tgt': '*',
            'expr_type': 'glob',
            'mode': 'async',
            'token': salt_token
        }

        def event_stream(handler, pipe):
            pipe.recv()  # blocks until send is called on the parent end of this pipe.

            event = salt.utils.event.SaltEvent('master', self.opts['sock_dir'])
            stream = event.iter_events(full=True)
            SaltInfo = event_processor.SaltInfo(handler)
            while True:
                # data =  client.get_event(wait=0.025, tag='salt/', full=True)
                data = stream.next()
                if data:
                    try: #work around try to decode catch unicode errors
                        SaltInfo.process(data, salt_token, self.opts)
                        # handler.send('data: {0}\n\n'.format(json.dumps(data)), False)
                    except UnicodeDecodeError as ex:
                        logger.error("Error: Salt event has non UTF-8 data:\n{0}".format(data))
                time.sleep(0.1)

        parent_pipe, child_pipe = Pipe()
        handler.pipe = parent_pipe
        handler.opts = self.opts
        # Process to handle async push to a client.
        # Each GET request causes a process to be kicked off.
        proc = Process(target=event_stream, args=(handler,child_pipe))
        proc.start()



class SynchronizingHandler(WebSocket):
    '''
    Class to handle requests sent to this websocket connection.
    Each instance of this class represents a Salt websocket connection.
    Waits to receive a ``ready`` message fom the client.
    Calls send on it's end of the pipe to signal to the sender on receipt
    of ``ready``.

    This class also kicks off initial information probing jobs when clients
    initially connect. These jobs help gather information about minions, jobs,
    and documentation.
    '''
    def __init__(self, *args, **kwargs):
        super(SynchronizingHandler, self).__init__(*args, **kwargs)

        '''
        This pipe needs to represent the parent end of a pipe.
        Clients need to ensure that the pipe assigned to ``self.pipe`` is
        the ``parent end`` of a
        `pipe <https://docs.python.org/2/library/multiprocessing.html#exchanging-objects-between-processes>`_.
        '''
        self.pipe = None

        '''
        The token that we can use to make API calls.
        There are times when we would like to kick off jobs,
        examples include trying to obtain minions connected.
        '''
        self.token = None

    def received_message(self, message):
        '''
        Checks if the client has sent a ready message.
        A ready message causes ``send()`` to be called on the
        ``parent end`` of the pipe.

        Clients need to ensure that the pipe assigned to ``self.pipe`` is
        the ``parent end`` of a pipe.

        This ensures completion of the underlying websocket connection
        and can be used to synchronize parallel senders.
        '''
        if message.data == 'websocket client ready':
            self.pipe.send(message)
        self.send('server received message', False)


class AllEvents(object):
    '''
    Exposes ``all`` events from Salt's event bus on a websocket connection.
    The event bus on the Salt master exposes a large variety of things, notably
    when executions are started on the master and also when minions ultimately
    return their results. This URL provides a real-time window into a running
    Salt infrastructure. Uses websocket as the transport mechanism.

    Exposes GET method to return websocket connections.
    All requests should include an auth token.
    A way to obtain obtain authentication tokens is shown below.

    .. code-block:: bash

        % curl -si localhost:8000/login \\
            -H "Accept: application/json" \\
            -d username='salt' \\
            -d password='salt' \\
            -d eauth='pam'

    Which results in the response

    .. code-block:: json

        {
            "return": [{
                "perms": [".*", "@runner", "@wheel"],
                "start": 1400556492.277421,
                "token": "d0ce6c1a37e99dcc0374392f272fe19c0090cca7",
                "expire": 1400599692.277422,
                "user": "salt",
                "eauth": "pam"
            }]
        }

    In this example the ``token`` returned is ``d0ce6c1a37e99dcc0374392f272fe19c0090cca7`` and can be included
    in subsequent websocket requests (perhaps as part of the URL).
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
        'tools.websocket.handler_cls': SynchronizingHandler,
    })

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.auth = salt.auth.LoadAuth(self.opts)

    def GET(self, token=None):
        '''
        Return a websocket connection to Salt
        representing Salt's "real time" event stream.

        Provides a convenient way for clients to make an HTTP
        call and obtain a websocket connection.

        .. http:get:: /all_events

            **Example response**:

            .. code-block:: http

                Request URL:ws://localhost:8000/all_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7
                Request Method:GET
                Status Code:101 Switching Protocols
                Host:localhost:8000
                Origin:http://localhost:8000
                Pragma:no-cache
                Sec-WebSocket-Extensions:permessage-deflate; client_max_window_bits, x-webkit-deflate-frame
                Sec-WebSocket-Key:Bdp7VlCtPvkieC3epOiIgA==
                Sec-WebSocket-Version:13
                Upgrade:websocket
                Connection:Upgrade
                Content-Type:text/plain;charset=utf-8
                Date:Tue, 20 May 2014 02:03:08 GMT
                Server:CherryPy/3.2.3
                Upgrade:websocket

        :status 401: could not authenticate using provided credentials

        The event stream can be easily consumed via JavaScript:

        .. code-block:: javascript

            // Note, you must be authenticated!

            // Get the Websocket connection to Salt
            var source = new Websocket('ws://localhost:8000/all_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7');

            // Get Salt's "real time" event stream.
            source.onopen = function() { source.send('websocket client ready'); };

            // Other handlers
            source.onerror = function(e) { console.debug('error!', e); };

            // e.data represents Salt's "real time" event data as serialized JSON.
            source.onmessage = function(e) { console.debug(e.data); };

            // Terminates websocket connection and Salt's "real time" event stream on the server.
            source.close();

        Or via Python, using the Python module
        `websocket-client <https://pypi.python.org/pypi/websocket-client/>`_ for example.

        .. code-block:: python

            # Note, you must be authenticated!

            from websocket import create_connection

            # Get the Websocket connection to Salt
            ws = create_connection('ws://localhost:8000/all_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7')

            # Get Salt's "real time" event stream.
            ws.send('websocket client ready')


            # Simple listener to print results of Salt's "real time" event stream.
            # Look at https://pypi.python.org/pypi/websocket-client/ for more examples.
            while listening_to_events:
                print ws.recv()       #  Salt's "real time" event data as serialized JSON.

            # Terminates websocket connection and Salt's "real time" event stream on the server.
            ws.close()

        Above examples show how to establish a websocket connection to Salt and activating
        real time updates from Salt's event stream by signaling ``websocket client ready``.
        '''
        # Pulling the session token from an URL param is a workaround for
        # browsers not supporting CORS in the EventSource API.
        if token:
            orig_sesion, _ = cherrypy.session.cache.get(token, ({}, None))
            salt_token = orig_sesion.get('token')
        else:
            salt_token = cherrypy.session.get('token')

        # Manually verify the token
        if not salt_token or not self.auth.get_tok(salt_token):
            raise cherrypy.HTTPError(401)  # unauthorized

        # Release the session lock before starting the long-running response


        cherrypy.session.release_lock()


        '''
        A handler is the server side end of the websocket connection.
        Each request spawns a new instance of this handler
        '''
        handler = cherrypy.request.ws_handler

        def event_stream(handler, pipe):
            pipe.recv()  # blocks until send is called on the parent end of this pipe.

            event = salt.utils.event.SaltEvent('master', self.opts['sock_dir'])
            stream = event.iter_events(full=True)

            while True:
                data = stream.next()
                if data:
                    try: #work around try to decode catch unicode errors
                        handler.send('data: {0}\n\n'.format(json.dumps(data)), False)
                    except UnicodeDecodeError as ex:
                        logger.error("Error: Salt event has non UTF-8 data:\n{0}".format(data))
                time.sleep(0.1)

        parent_pipe, child_pipe = Pipe()
        handler.pipe = parent_pipe
        # Process to handle async push to a client.
        # Each GET request causes a process to be kicked off.
        proc = Process(target=event_stream, args=(handler,child_pipe))
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
    ``salt/netapi/hook/mycompany/myapp/mydata``. See the :ref:`Salt Reactor
    <reactor>` documentation for how to react to events with various tags.

    The following is an example ``.travis.yml`` file to send notifications to
    Salt of successful test runs:

    .. code-block:: yaml

        language: python
        script: python -m unittest tests
        after_success:
            - 'curl -sS http://saltapi-url.example.com:8000/hook/travis/build/success -d branch="${TRAVIS_BRANCH}" -d commit="${TRAVIS_COMMIT}"'

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
        self.event = salt.utils.event.SaltEvent('master',
                self.opts.get('sock_dir', ''))

        if cherrypy.config['apiopts'].get('webhook_disable_auth'):
            self._cp_config['tools.salt_token.on'] = False
            self._cp_config['tools.salt_auth.on'] = False

    def POST(self, *args, **kwargs):
        '''
        Fire an event in Salt with a custom event tag and data

        .. versionadded:: 0.8.4

        .. http:post:: /hook

            **Example request**::

                % curl -sS localhost:8000/hook -d foo='Foo!' -d bar='Bar!'

            .. code-block:: http

                POST /hook HTTP/1.1
                Host: localhost:8000
                Content-Length: 16
                Content-Type: application/x-www-form-urlencoded

                foo=Foo&bar=Bar!

            **Example response**:

            .. code-block:: http

                HTTP/1.1 200 OK
                Content-Length: 14
                Content-Type: application/json

                {"success": true}

        As a practical example, an internal continuous-integration build
        server could send an HTTP POST request to the URL
        ``http://localhost:8000/hook/mycompany/build/success`` which contains
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

        .. code-block:: yaml

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

        :status 200: success
        :status 406: requested Content-Type not available
        :status 413: request body is too large
        '''
        tag = '/'.join(itertools.chain(self.tag_base, args))
        data = cherrypy.serving.request.unserialized_data
        headers = dict(cherrypy.request.headers)

        ret = self.event.fire_event({
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

        :status 200: success
        :status 406: requested Content-Type not available
        '''
        if hasattr(logging, 'statistics'):
            return cpstats.extrapolate_statistics(logging.statistics)

        return {}


class App(object):
    exposed = True
    def GET(self, *args):
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
        'events': Events,
        'stats': Stats,
        'formatted_events': WebsocketEndpoint,
        'all_events': AllEvents,
    }

    def __init__(self):
        self.opts = cherrypy.config['saltopts']
        self.apiopts = cherrypy.config['apiopts']

        for url, cls in self.url_map.items():
            setattr(self, url, cls())

        # Allow the Webhook URL to be overridden from the conf.
        setattr(self, self.apiopts.get('webhook_url', 'hook').lstrip('/'), Webhook())

        if 'app' in self.apiopts:
            setattr(self, self.apiopts.get('app_path', 'app').lstrip('/'), App())

        cherrypy.tools.websocket = WebSocketTool()
        WebSocketPlugin(cherrypy.engine).subscribe()

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
                'max_request_body_size': self.apiopts.get('max_request_body_size', 1048576),
                'debug': self.apiopts.get('debug', False),
            },
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),

                'tools.trailing_slash.on': True,
                'tools.gzip.on': True,

                'tools.cpstats.on': self.apiopts.get('collect_stats', False),
            },
        }

        if self.apiopts.get('debug', False) == False:
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
    apiopts = opts.get(__name__.rsplit('.', 2)[-2], {}) # rest_cherrypy opts

    # Add Salt and salt-api config options to the main CherryPy config dict
    cherrypy.config['saltopts'] = opts
    cherrypy.config['apiopts'] = apiopts

    root = API() # cherrypy app
    cpyopts = root.get_conf() # cherrypy app opts

    return root, apiopts, cpyopts
