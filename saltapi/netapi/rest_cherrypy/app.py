'''
A REST API for Salt
===================

:depends:   - CherryPy Python module
:configuration: All authentication is done through Salt's :ref:`external auth
    <acl-eauth>` system. Be sure that it is enabled and the user you are
    authenticating as has permissions for all the functions you will be
    running.

    The configuration options for this module resides in the Salt master config
    file. All available options are detailed below.

    port
        **Required**

        The port for the webserver to listen on.
    debug : ``False``
        Starts a for-development web server instead of the production-ready web
        server.

        Does not use SSL and ignores the certificate configuration options.
    ssl_crt
        Required when ``debug`` is ``False``

        The path to a SSL certificate. (See below)
    ssl_key
        Required when ``debug`` is ``False``

        The path to the private key for your SSL certificate. (See below)
    static
        A filesystem path to static HTML/JavaScript/CSS/image assets.
        If this directory contains a ``index.html`` file, it will be served at
        the root URL when HTML is requested by a client via the ``Accept``
        header.

        This directory may point to a clone of the `salt-ui`_ project to
        bootstrap a graphical interface for interacting with Salt.

    .. _`salt-ui`: https://github.com/saltstack/salt-ui

    Example production configuration block:

    .. code-block:: yaml

        rest_cherrypy:
          port: 8000
          ssl_crt: /etc/pki/tls/certs/localhost.crt
          ssl_key: /etc/pki/tls/certs/localhost.key

    The REST interface requires a secure HTTPS connection. You must provide an
    SSL certificate to use. If you don't already have a certificate and don't
    wish to buy one, you can generate a self-signed certificate using the
    :py:func:`~salt.modules.tls.create_self_signed_cert` function in Salt (note
    the dependencies for this module):

    .. code-block:: bash

        % salt-call tls.create_self_signed_cert

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
        authentication credientials, what returner to use, etc.

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

The main entry point is the root URL (``/``) and all functionality is available
at that URL. The other URLs are largely convenience URLs that wrap that main
entry point.

'''
# We need a custom pylintrc here...
# pylint: disable=W0212,E1101,C0103,R0201,W0221,W0613

# Import Python libs
import functools
import os
import json

# Import third-party libs
import cherrypy
import yaml

# Import Salt libs
import salt
import salt.auth
import salt.log

# Import salt-api libs
import saltapi

logger = salt.log.logging.getLogger(__name__)


def salt_token_tool():
    '''
    If the custom authentication header is supplied, put it in the cookie dict
    so the rest of the session-based auth works as intended
    '''
    x_auth = cherrypy.request.headers.get('X-Auth-Token', None)

    # X-Auth-Token header trumps session cookie
    if x_auth:
        cherrypy.request.cookie['session_id'] = x_auth


def salt_auth_tool():
    '''
    Redirect all unauthenticated requests to the login page
    '''
    # Short-circuit for the login page
    ignore_urls = ('/login', '/logout', '/run')

    if cherrypy.request.path_info.startswith(ignore_urls):
        return

    # Otherwise redirect to the login page if the session hasn't been authed
    if not cherrypy.session.get('token', None):
        raise cherrypy.InternalRedirect('/login')

    # Session is authenticated; inform caches
    cherrypy.response.headers['Cache-Control'] = 'private'


def wants_html():
    '''
    Determine if the request is asking for HTML specifically.

    Returns an empty string or a string containing the output of the
    cherrypy.lib.cptools.accept() function.
    '''
    # Short-circuit if the request is vague or overly broad
    if (not 'Accept' in cherrypy.request.headers
            or cherrypy.request.headers['Accept'] == '*/*'):
        return ''

    try:
        return cherrypy.lib.cptools.accept(
                ['text/html'] + [i for (i, _) in ct_out_map])
    except (AttributeError, cherrypy.CherryPyException):
        return ''

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
    # If we're being asked for HTML, try to serve index.html from the 'static'
    # directory; this is useful (as a random, non-specific example) for
    # bootstrapping the salt-ui app
    if 'static' in cherrypy.config and 'html' in wants_html():
        index = os.path.join(cherrypy.config['static'], 'index.html')
        if os.path.exists(index):
            return cherrypy.lib.static.serve_file(index)

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
    Wrap the normal handler and transform the output from that handler into the
    requested content type
    '''
    request = cherrypy.serving.request
    request._hypermedia_inner_handler = request.handler
    request.handler = hypermedia_handler

    # cherrypy.response.headers['Alternates'] = self.ct_out_map.keys()
    # TODO: add 'negotiate' to Vary header and 'list' to TCN header
    # Alternates: {"paper.1" 0.9 {type text/html} {language en}},
    #          {"paper.2" 0.7 {type text/html} {language fr}},
    #          {"paper.3" 1.0 {type application/postscript} {language en}}



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
    and reformat it into a Low State datastructure.

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
    lowdata = entity.params

    # Make the 'arg' param a list if not already
    if 'arg' in lowdata and not isinstance(lowdata['arg'], list):
        lowdata['arg'] = [lowdata['arg']]

    # Finally, make a Low State and put it in request
    cherrypy.request.lowstate = [lowdata]


@process_request_body
def json_processor(entity):
    '''
    Unserialize raw POST data in JSON format to a Python datastructure.

    :param entity: raw POST data
    '''
    body = entity.fp.read()
    try:
        cherrypy.serving.request.lowstate = json.loads(body)
    except ValueError:
        raise cherrypy.HTTPError(400, 'Invalid JSON document')


@process_request_body
def yaml_processor(entity):
    '''
    Unserialize raw POST data in YAML format to a Python datastructure.

    :param entity: raw POST data
    '''
    body = entity.fp.read()
    try:
        cherrypy.serving.request.lowstate = yaml.load(body)
    except ValueError:
        raise cherrypy.HTTPError(400, 'Invalid YAML document')


def hypermedia_in():
    '''
    Unserialize POST/PUT data of a specified Content-Type.

    The following custom processors all are intended to format Low State data
    and will place that datastructure into the request object.

    :raises HTTPError: if the request contains a Content-Type that we do not
        have a processor for
    '''
    # Be liberal in what you accept
    ct_in_map = {
        'application/x-www-form-urlencoded': urlencoded_processor,
        'application/json': json_processor,
        'application/x-yaml': yaml_processor,
        'text/yaml': yaml_processor,
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

        'tools.salt_token.on': True,
        'tools.salt_auth.on': True,

        'tools.hypermedia_out.on': True,
        'tools.hypermedia_in.on': True,
    }

    def __init__(self, opts):
        '''
        :param opts: A dictionary of options from Salt's master config (e.g.
            Salt's, ``__opts__``)
        '''
        self.opts = opts
        self.api = saltapi.APIClient(opts)

    def exec_lowstate(self):
        '''
        Pull a Low State datastructure from request and execute the low-data
        chunks through Salt. The low-data chunks will be updated to include the
        authorization token for the current session.
        '''
        lowstate = cherrypy.request.lowstate
        token = cherrypy.session.get('token', None)

        for chunk in lowstate:
            if token:
                chunk['token'] = token
            yield self.api.run(chunk)

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
        return {
            'status': cherrypy.response.status,
            'return': "Welcome",
        }

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
            'return': list(self.exec_lowstate()),
        }


class Minions(LowDataAdapter):
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
            'return': list(self.exec_lowstate()),
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

                - return:
                    jid: '20130118105423694155'
                    minions: [ms-4, ms-3, ms-2, ms-1, ms-0]

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
        for chunk in cherrypy.request.lowstate:
            chunk['client'] = 'local_async'
        job_data = next(self.exec_lowstate(), {})

        cherrypy.response.status = 202
        return [{
            'return': job_data,
        }]


class Jobs(LowDataAdapter):
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
                    Target: ms-3
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

                return:
                - ms-3:
                  - - 0
                    - 1
                    - 1
                    - 2
                  - 9.059906005859375e-06

        :param mid: (optional) a minion id
        :status 200: success
        :status 401: authentication required
        :status 406: requested Content-Type not available
        '''
        cherrypy.request.lowstate = [{
            'client': 'runner',
            'fun': 'jobs.lookup_jid' if jid else 'jobs.list_jobs',
            'jid': jid,
        }]
        return {
            'return': list(self.exec_lowstate()),
        }


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
    exposed = True

    def __init__(self, *args, **kwargs):
        super(Login, self).__init__(*args, **kwargs)

        self.auth = salt.auth.LoadAuth(self.opts)

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
        cherrypy.response.status = '401 Unauthorized'
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
        
        .. versionchanged:: 0.8.0
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
            raise cherrypy.HTTPError(401, 'Could not authenticate using provided credentials')
            
        cherrypy.response.headers['X-Auth-Token'] = cherrypy.session.id
        cherrypy.session['token'] = token['token']
        cherrypy.session['timeout'] = (token['expire'] - token['start']) / 60

        # Grab eauth config for the current backend for the current user
        perms = self.opts['external_auth'][token['eauth']][token['name']] if token['name'] in self.opts['external_auth'][token['eauth']] else self.opts['external_auth'][token['eauth']]['*'] 

        return {'return': [{
            'token': cherrypy.session.id,
            'expire': token['expire'],
            'start': token['start'],
            'user': token['name'],
            'eauth': token['eauth'],
            'perms': perms,
        }]}


class Logout(LowDataAdapter):
    def POST(self):
        '''
        Destroy the currently active session and expire the session cookie

        .. versionadded:: 0.8.0
        '''
        cherrypy.lib.sessions.expire() # set client-side to expire
        cherrypy.session.regenerate() # replace server-side with new

        return {'return': "Your token has been cleared"}


class Run(LowDataAdapter):
    def POST(self, **kwargs):
        '''
        Run commands bypassing the normal session handling

        .. versionadded:: 0.8.0

        This entry point is primarily for "one-off" commands. Each request must
        pass full Salt external authentication credentials. Otherwise this URL
        is identical to the root (``/``) execution URL.

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
    }

    def __init__(self, opts):
        self.opts = opts
        for url, cls in self.url_map.items():
            setattr(self, url, cls(self.opts))

    def get_conf(self, apiopts):
        '''
        Combine the CherryPy configuration with the rest_cherrypy config values
        pulled from the master config and return the CherryPy configuration
        '''
        conf = {
            'global': {
                'server.socket_host': '0.0.0.0',
                'server.socket_port': apiopts.get('port', 8000),
                'debug': apiopts.get('debug', False),
            },
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),

                'tools.trailing_slash.on': True,
                'tools.gzip.on': True,

                'tools.staticdir.on': True if 'static' in apiopts else False,
                'tools.staticdir.dir': apiopts.get('static', ''),
            },
        }

        conf['global'].update(apiopts)

        # Add to global config
        cherrypy.config.update(conf['global'])

        return conf


def get_app(opts):
    '''
    Returns a WSGI app and a configuration dictionary
    '''
    root = API(opts) # cherrypy app
    apiopts = opts.get(__name__.rsplit('.', 2)[-2], {}) # rest_cherrypy opts

    cpyopts = root.get_conf(apiopts) # cherrypy app opts
    gconf = cpyopts.get('global', {}) # 'global' section of cpyopts

    # Register salt-specific hooks
    cherrypy.tools.salt_token = cherrypy.Tool('on_start_resource',
            salt_token_tool, priority=55)
    cherrypy.tools.salt_auth = cherrypy.Tool('before_request_body',
            salt_auth_tool, priority=60)
    cherrypy.tools.hypermedia_out = cherrypy.Tool('before_handler',
            hypermedia_out)
    cherrypy.tools.hypermedia_in = cherrypy.Tool('before_request_body',
            hypermedia_in)

    return root, apiopts, cpyopts
