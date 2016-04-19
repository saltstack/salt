# encoding: utf-8
from __future__ import absolute_import, print_function

'''
A non-blocking REST API for Salt
================================

.. py:currentmodule:: salt.netapi.rest_tornado.saltnado

:depends:   - tornado Python module

:configuration: All authentication is done through Salt's :ref:`external auth
    <acl-eauth>` system which requires additional configuration not described
    here.


In order to run rest_tornado with the salt-master
add the following to the Salt master config file.

.. code-block:: yaml

    rest_tornado:
        # can be any port
        port: 8000
        # address to bind to (defaults to 0.0.0.0)
        address: 0.0.0.0
        # socket backlog
        backlog: 128
        ssl_crt: /etc/pki/api/certs/server.crt
        # no need to specify ssl_key if cert and key
        # are in one single file
        ssl_key: /etc/pki/api/certs/server.key
        debug: False
        disable_ssl: False
        webhook_disable_auth: False
        cors_origin: null

.. _rest_tornado-auth:

Authentication
--------------

Authentication is performed by passing a session token with each request.
Tokens are generated via the :py:class:`SaltAuthHandler` URL.

The token may be sent in one of two ways:

* Include a custom header named :mailheader:`X-Auth-Token`.
* Sent via a cookie. This option is a convenience for HTTP clients that
  automatically handle cookie support (such as browsers).

.. seealso:: You can bypass the session handling via the :py:class:`RunSaltAPIHandler` URL.

CORS
----

rest_tornado supports Cross-site HTTP requests out of the box. It is by default
deactivated and controlled by the `cors_origin` config key.

You can allow all origins by settings `cors_origin` to `*`.

You can allow only one origin with this configuration:

.. code-block:: yaml

    rest_tornado:
        cors_origin: http://salt.yourcompany.com

You can also be more specific and select only a few allowed origins by using
a list. For example:

.. code-block:: yaml

    rest_tornado:
        cors_origin:
            - http://salt.yourcompany.com
            - http://salt-preprod.yourcampany.com

The format for origin are full URL, with both scheme and port if not standard.

In this case, rest_tornado will check if the Origin header is in the allowed
list if it's the case allow the origin. Else it will returns nothing,
effectively preventing the origin to make request.

For reference, CORS is a mechanism used by browser to allow (or disallow)
requests made from browser from a different origin than salt-api. It's
complementary to Authentication and mandatory only if you plan to use
a salt client developed as a Javascript browser application.

Usage
-----

Commands are sent to a running Salt master via this module by sending HTTP
requests to the URLs detailed below.

.. admonition:: Content negotiation

    This REST interface is flexible in what data formats it will accept as well
    as what formats it will return (e.g., JSON, YAML, x-www-form-urlencoded).

    * Specify the format of data in the request body by including the
      :mailheader:`Content-Type` header.
    * Specify the desired data format for the response body with the
      :mailheader:`Accept` header.

Data sent in :http:method:`post` and :http:method:`put` requests  must be in
the format of a list of lowstate dictionaries. This allows multiple commands to
be executed in a single HTTP request.

.. glossary::

    lowstate
        A dictionary containing various keys that instruct Salt which command
        to run, where that command lives, any parameters for that command, any
        authentication credentials, what returner to use, etc.

        Salt uses the lowstate data format internally in many places to pass
        command data between functions. Salt also uses lowstate for the
        :ref:`LocalClient() <python-api>` Python API interface.

The following example (in JSON format) causes Salt to execute two commands::

    [{
        "client": "local",
        "tgt": "*",
        "fun": "test.fib",
        "arg": ["10"]
    },
    {
        "client": "runner",
        "fun": "jobs.lookup_jid",
        "jid": "20130603122505459265"
    }]

Multiple commands in a Salt API request will be executed in serial and makes
no gaurantees that all commands will run. Meaning that if test.fib (from the
example above) had an exception, the API would still execute "jobs.lookup_jid".

Responses to these lowstates are an in-order list of dicts containing the
return data, a yaml response could look like::

    - ms-1: true
      ms-2: true
    - ms-1: foo
      ms-2: bar

In the event of an exception while executing a command the return for that lowstate
will be a string, for example if no minions matched the first lowstate we would get
a return like::

    - No minions matched the target. No command was sent, no jid was assigned.
    - ms-1: true
      ms-2: true

.. admonition:: x-www-form-urlencoded

    Sending JSON or YAML in the request body is simple and most flexible,
    however sending data in urlencoded format is also supported with the
    caveats below. It is the default format for HTML forms, many JavaScript
    libraries, and the :command:`curl` command.

    For example, the equivalent to running ``salt '*' test.ping`` is sending
    ``fun=test.ping&arg&client=local&tgt=*`` in the HTTP request body.

    Caveats:

    * Only a single command may be sent per HTTP request.
    * Repeating the ``arg`` parameter multiple times will cause those
      parameters to be combined into a single list.

      Note, some popular frameworks and languages (notably jQuery, PHP, and
      Ruby on Rails) will automatically append empty brackets onto repeated
      parameters. E.g., ``arg=one``, ``arg=two`` will be sent as ``arg[]=one``,
      ``arg[]=two``. This is not supported; send JSON or YAML instead.


.. |req_token| replace:: a session token from :py:class:`~SaltAuthHandler`.
.. |req_accept| replace:: the desired response format.
.. |req_ct| replace:: the format of the request body.

.. |res_ct| replace:: the format of the response body; depends on the
    :mailheader:`Accept` request header.

.. |200| replace:: success
.. |400| replace:: bad request
.. |401| replace:: authentication required
.. |406| replace:: requested Content-Type not available
.. |500| replace:: internal server error
'''  # pylint: disable=W0105
# pylint: disable=W0232

# Import Python libs
import time
import math
import fnmatch
import logging
from copy import copy
from collections import defaultdict

# pylint: disable=import-error
import cgi
import yaml
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.gen
from tornado.concurrent import Future
from zmq.eventloop import ioloop
import salt.ext.six as six
# pylint: enable=import-error

# instantiate the zmq IOLoop (specialized poller)
ioloop.install()

# salt imports
import salt.netapi
import salt.utils
import salt.utils.event
from salt.utils.event import tagify
import salt.client
import salt.runner
import salt.auth
from salt.exceptions import EauthAuthenticationError

json = salt.utils.import_json()
logger = logging.getLogger()

# The clients rest_cherrypi supports. We want to mimic the interface, but not
#     necessarily use the same API under the hood
# # all of these require coordinating minion stuff
#  - "local" (done)
#  - "local_async" (done)
#  - "local_batch" (done)

# # master side
#  - "runner" (done)
#  - "wheel" (need async api...)


class SaltClientsMixIn(object):
    '''
    MixIn class to container all of the salt clients that the API needs
    '''
    # TODO: load this proactively, instead of waiting for a request
    __saltclients = None

    @property
    def saltclients(self):
        if SaltClientsMixIn.__saltclients is None:
            local_client = salt.client.get_local_client(mopts=self.application.opts)
            # TODO: refreshing clients using cachedict
            SaltClientsMixIn.__saltclients = {
                'local': local_client.run_job,
                # not the actual client we'll use.. but its what we'll use to get args
                'local_batch': local_client.cmd_batch,
                'local_async': local_client.run_job,
                'runner': salt.runner.RunnerClient(opts=self.application.opts).async,
                'runner_async': None,  # empty, since we use the same client as `runner`
                }
        return SaltClientsMixIn.__saltclients


AUTH_TOKEN_HEADER = 'X-Auth-Token'
AUTH_COOKIE_NAME = 'session_id'


class TimeoutException(Exception):
    pass


class Any(Future):
    '''
    Future that wraps other futures to "block" until one is done
    '''
    def __init__(self, futures):  # pylint: disable=E1002
        super(Any, self).__init__()
        for future in futures:
            future.add_done_callback(self.done_callback)

    def done_callback(self, future):
        # Any is completed once one is done, we don't set for the rest
        if not self.done():
            self.set_result(future)


class EventListener(object):
    '''
    Class responsible for listening to the salt master event bus and updating
    futures. This is the core of what makes this async, this allows us to do
    non-blocking work in the main processes and "wait" for an event to happen
    '''

    def __init__(self, mod_opts, opts):
        self.mod_opts = mod_opts
        self.opts = opts
        self.event = salt.utils.event.get_event(
            'master',
            opts['sock_dir'],
            opts['transport'],
            opts=opts,
            listen=True,
            io_loop=tornado.ioloop.IOLoop.current()
        )

        # tag -> list of futures
        self.tag_map = defaultdict(list)

        # request_obj -> list of (tag, future)
        self.request_map = defaultdict(list)

        # map of future -> timeout_callback
        self.timeout_map = {}

        self.event.set_event_handler(self._handle_event_socket_recv)

    def clean_timeout_futures(self, request):
        '''
        Remove all futures that were waiting for request `request` since it is done waiting
        '''
        if request not in self.request_map:
            return
        for tag, future in self.request_map[request]:
            # timeout the future
            self._timeout_future(tag, future)
            # remove the timeout
            if future in self.timeout_map:
                tornado.ioloop.IOLoop.current().remove_timeout(self.timeout_map[future])
                del self.timeout_map[future]

        del self.request_map[request]

    def get_event(self,
                  request,
                  tag='',
                  callback=None,
                  timeout=None
                  ):
        '''
        Get an event (async of course) return a future that will get it later
        '''
        # if the request finished, no reason to allow event fetching, since we
        # can't send back to the client
        if request._finished:
            future = Future()
            future.set_exception(TimeoutException())
            return future

        future = Future()
        if callback is not None:
            def handle_future(future):
                tornado.ioloop.IOLoop.current().add_callback(callback, future)
            future.add_done_callback(handle_future)
        # add this tag and future to the callbacks
        self.tag_map[tag].append(future)
        self.request_map[request].append((tag, future))

        if timeout:
            timeout_future = tornado.ioloop.IOLoop.current().call_later(timeout, self._timeout_future, tag, future)
            self.timeout_map[future] = timeout_future

        return future

    def _timeout_future(self, tag, future):
        '''
        Timeout a specific future
        '''
        if tag not in self.tag_map:
            return
        if not future.done():
            future.set_exception(TimeoutException())
            self.tag_map[tag].remove(future)
        if len(self.tag_map[tag]) == 0:
            del self.tag_map[tag]

    def _handle_event_socket_recv(self, raw):
        '''
        Callback for events on the event sub socket
        '''
        mtag, data = self.event.unpack(raw, self.event.serial)
        # see if we have any futures that need this info:
        for tag_prefix, futures in six.iteritems(self.tag_map):
            if mtag.startswith(tag_prefix):
                for future in futures:
                    if future.done():
                        continue
                    future.set_result({'data': data, 'tag': mtag})
                    self.tag_map[tag_prefix].remove(future)
                    if future in self.timeout_map:
                        tornado.ioloop.IOLoop.current().remove_timeout(self.timeout_map[future])
                        del self.timeout_map[future]


# TODO: move to a utils function within salt-- the batching stuff is a bit tied together
def get_batch_size(batch, num_minions):
    '''
    Return the batch size that you should have
        batch: string
        num_minions: int

    '''
    # figure out how many we can keep in flight
    partition = lambda x: float(x) / 100.0 * num_minions
    try:
        if '%' in batch:
            res = partition(float(batch.strip('%')))
            if res < 1:
                return int(math.ceil(res))
            else:
                return int(res)
        else:
            return int(batch)
    except ValueError:
        print(('Invalid batch data sent: {0}\nData must be in the form'
               'of %10, 10% or 3').format(batch))


class BaseSaltAPIHandler(tornado.web.RequestHandler, SaltClientsMixIn):  # pylint: disable=W0223
    ct_out_map = (
        ('application/json', json.dumps),
        ('application/x-yaml', yaml.safe_dump),
    )

    def _verify_client(self, low):
        '''
        Verify that the client is in fact one we have
        '''
        if 'client' not in low or low.get('client') not in self.saltclients:
            self.set_status(400)
            self.write("400 Invalid Client: Client not found in salt clients")
            self.finish()
            return False
        return True

    def initialize(self):
        '''
        Initialize the handler before requests are called
        '''
        if not hasattr(self.application, 'event_listener'):
            logger.critical('init a listener')
            self.application.event_listener = EventListener(
                self.application.mod_opts,
                self.application.opts,
            )

    @property
    def token(self):
        '''
        The token used for the request
        '''
        # find the token (cookie or headers)
        if AUTH_TOKEN_HEADER in self.request.headers:
            return self.request.headers[AUTH_TOKEN_HEADER]
        else:
            return self.get_cookie(AUTH_COOKIE_NAME)

    def _verify_auth(self):
        '''
        Boolean whether the request is auth'd
        '''

        return self.token and bool(self.application.auth.get_tok(self.token))

    def prepare(self):
        '''
        Run before get/posts etc. Pre-flight checks:
            - verify that we can speak back to them (compatible accept header)
        '''
        # Find an acceptable content-type
        accept_header = self.request.headers.get('Accept', '*/*')
        # Ignore any parameter, including q (quality) one
        parsed_accept_header = [cgi.parse_header(h)[0] for h in accept_header.split(',')]

        def find_acceptable_content_type(parsed_accept_header):
            for media_range in parsed_accept_header:
                for content_type, dumper in self.ct_out_map:
                    if fnmatch.fnmatch(content_type, media_range):
                        return content_type, dumper
            return None, None

        content_type, dumper = find_acceptable_content_type(parsed_accept_header)

        # better return message?
        if not content_type:
            self.send_error(406)

        self.content_type = content_type
        self.dumper = dumper

        # do the common parts
        self.start = time.time()
        self.connected = True

        self.lowstate = self._get_lowstate()

    def timeout_futures(self):
        '''
        timeout a session
        '''
        # TODO: set a header or something??? so we know it was a timeout
        self.application.event_listener.clean_timeout_futures(self)

    def on_finish(self):
        '''
        When the job has been done, lets cleanup
        '''
        # timeout all the futures
        self.timeout_futures()

    def on_connection_close(self):
        '''
        If the client disconnects, lets close out
        '''
        self.finish()

    def serialize(self, data):
        '''
        Serlialize the output based on the Accept header
        '''
        self.set_header('Content-Type', self.content_type)

        return self.dumper(data)

    def _form_loader(self, _):
        '''
        function to get the data from the urlencoded forms
        ignore the data passed in and just get the args from wherever they are
        '''
        data = {}
        for key, val in six.iteritems(self.request.arguments):
            if len(val) == 1:
                data[key] = val[0]
            else:
                data[key] = val
        return data

    def deserialize(self, data):
        '''
        Deserialize the data based on request content type headers
        '''
        ct_in_map = {
            'application/x-www-form-urlencoded': self._form_loader,
            'application/json': json.loads,
            'application/x-yaml': yaml.safe_load,
            'text/yaml': yaml.safe_load,
            # because people are terrible and don't mean what they say
            'text/plain': json.loads
        }

        try:
            # Use cgi.parse_header to correctly separate parameters from value
            header = cgi.parse_header(self.request.headers['Content-Type'])
            value, parameters = header
            return ct_in_map[value](data)
        except KeyError:
            self.send_error(406)
        except ValueError:
            self.send_error(400)

    def _get_lowstate(self):
        '''
        Format the incoming data into a lowstate object
        '''
        if not self.request.body:
            return
        data = self.deserialize(self.request.body)
        self.raw_data = copy(data)

        if 'arg' in data and not isinstance(data['arg'], list):
            data['arg'] = [data['arg']]

        if not isinstance(data, list):
            lowstate = [data]
        else:
            lowstate = data

        return lowstate

    def set_default_headers(self):
        '''
        Set default CORS headers
        '''
        mod_opts = self.application.mod_opts

        if mod_opts.get('cors_origin'):
            origin = self.request.headers.get('Origin')

            allowed_origin = _check_cors_origin(origin, mod_opts['cors_origin'])

            if allowed_origin:
                self.set_header("Access-Control-Allow-Origin", allowed_origin)

    def options(self, *args, **kwargs):
        '''
        Return CORS headers for preflight requests
        '''
        # Allow X-Auth-Token in requests
        request_headers = self.request.headers.get('Access-Control-Request-Headers')
        allowed_headers = request_headers.split(',')

        # Filter allowed header here if needed.

        # Allow request headers
        self.set_header('Access-Control-Allow-Headers', ','.join(allowed_headers))

        # Allow X-Auth-Token in responses
        self.set_header('Access-Control-Expose-Headers', 'X-Auth-Token')

        # Allow all methods
        self.set_header('Access-Control-Allow-Methods', 'OPTIONS, GET, POST')

        self.set_status(204)
        self.finish()


class SaltAuthHandler(BaseSaltAPIHandler):  # pylint: disable=W0223
    '''
    Handler for login requests
    '''
    def get(self):
        '''
        All logins are done over post, this is a parked enpoint

        .. http:get:: /login

            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -i localhost:8000/login

        .. code-block:: http

            GET /login HTTP/1.1
            Host: localhost:8000
            Accept: application/json

        **Example response:**

        .. code-block:: http

            HTTP/1.1 401 Unauthorized
            Content-Type: application/json
            Content-Length: 58

            {"status": "401 Unauthorized", "return": "Please log in"}
        '''
        self.set_status(401)
        self.set_header('WWW-Authenticate', 'Session')

        ret = {'status': '401 Unauthorized',
               'return': 'Please log in'}

        self.write(self.serialize(ret))

    # TODO: make async? Underlying library isn't... and we ARE making disk calls :(
    def post(self):
        '''
        :ref:`Authenticate  <rest_tornado-auth>` against Salt's eauth system

        .. http:post:: /login

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|
            :reqheader Content-Type: |req_ct|

            :form eauth: the eauth backend configured for the user
            :form username: username
            :form password: password

            :status 200: |200|
            :status 400: |400|
            :status 401: |401|
            :status 406: |406|
            :status 500: |500|

        **Example request:**

        .. code-block:: bash

            curl -si localhost:8000/login \\
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
        try:
            request_payload = self.deserialize(self.request.body)

            if not isinstance(request_payload, dict):
                self.send_error(400)
                return

            creds = {'username': request_payload['username'],
                     'password': request_payload['password'],
                     'eauth': request_payload['eauth'],
                     }
        # if any of the args are missing, its a bad request
        except KeyError:
            self.send_error(400)
            return

        token = self.application.auth.mk_token(creds)
        if 'token' not in token:
            # TODO: nicer error message
            # 'Could not authenticate using provided credentials')
            self.send_error(401)
            # return since we don't want to execute any more
            return

        # Grab eauth config for the current backend for the current user
        try:
            perms = self.application.opts['external_auth'][token['eauth']][token['name']]

        # If we can't find the creds, then they aren't authorized
        except KeyError:
            self.send_error(401)
            return

        except (AttributeError, IndexError):
            logging.debug("Configuration for external_auth malformed for "
                          "eauth '{0}', and user '{1}'."
                          .format(token.get('eauth'), token.get('name')), exc_info=True)
            # TODO better error -- 'Configuration for external_auth could not be read.'
            self.send_error(500)
            return

        ret = {'return': [{
            'token': token['token'],
            'expire': token['expire'],
            'start': token['start'],
            'user': token['name'],
            'eauth': token['eauth'],
            'perms': perms,
            }]}

        self.write(self.serialize(ret))


class SaltAPIHandler(BaseSaltAPIHandler, SaltClientsMixIn):  # pylint: disable=W0223
    '''
    Main API handler for base "/"
    '''
    def get(self):
        '''
        An enpoint to determine salt-api capabilities

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
            Content-Legnth: 83

            {"clients": ["local", "local_batch", "local_async", "runner", "runner_async"], "return": "Welcome"}
        '''
        ret = {"clients": list(self.saltclients.keys()),
               "return": "Welcome"}
        self.write(self.serialize(ret))

    @tornado.web.asynchronous
    def post(self):
        '''
        Send one or more Salt commands (lowstates) in the request body

        .. http:post:: /

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|
            :reqheader Content-Type: |req_ct|

            :resheader Content-Type: |res_ct|

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

            :term:`lowstate` data describing Salt commands must be sent in the
            request body.

        **Example request:**

        .. code-block:: bash

            curl -si https://localhost:8000 \\
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

        **Example response:**
        Responses are an in-order list of the lowstate's return data. In the
        event of an exception running a command the return will be a string
        instead of a mapping.

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

        .. admonition:: multiple commands
            Note that if multiple :term:`lowstate` structures are sent, the Salt
            API will execute them in serial, and will not stop execution upon failure
            of a previous job. If you need to have commands executed in order and
            stop on failure please use compount-command-execution.

        '''
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        self.disbatch()

    @tornado.gen.coroutine
    def disbatch(self):
        '''
        Disbatch all lowstates to the appropriate clients

        Auth must have been verified before this point
        '''
        ret = []

        # check clients before going, we want to throw 400 if one is bad
        for low in self.lowstate:
            if not self._verify_client(low):
                return

        for low in self.lowstate:
            # make sure that the chunk has a token, if not we can't do auth per-request
            # Note: this means that you can send different tokens per lowstate
            # as long as the base token (to auth with the API) is valid
            if 'token' not in low:
                low['token'] = self.token
            # disbatch to the correct handler
            try:
                chunk_ret = yield getattr(self, '_disbatch_{0}'.format(low['client']))(low)
                ret.append(chunk_ret)
            except Exception as ex:
                ret.append('Unexpected exception while handling request: {0}'.format(ex))
                logger.error('Unexpected exception while handling request:', exc_info=True)

        self.write(self.serialize({'return': ret}))
        self.finish()

    @tornado.gen.coroutine
    def _disbatch_local_batch(self, chunk):
        '''
        Disbatch local client batched commands
        '''
        f_call = salt.utils.format_call(self.saltclients['local_batch'], chunk)

        # ping all the minions (to see who we have to talk to)
        # Don't catch any exception, since we won't know what to do, we'll
        # let the upper level deal with this one
        ping_ret = yield self._disbatch_local({'tgt': chunk['tgt'],
                                               'fun': 'test.ping',
                                               'expr_form': f_call['kwargs']['expr_form']})

        chunk_ret = {}

        if not isinstance(ping_ret, dict):
            raise tornado.gen.Return(chunk_ret)
        minions = list(ping_ret.keys())

        maxflight = get_batch_size(f_call['kwargs']['batch'], len(minions))
        inflight_futures = []

        # override the expr_form
        f_call['kwargs']['expr_form'] = 'list'
        # do this batch
        while len(minions) > 0 or len(inflight_futures) > 0:
            # if you have more to go, lets disbatch jobs
            while len(inflight_futures) < maxflight and len(minions) > 0:
                minion_id = minions.pop(0)
                batch_chunk = dict(chunk)
                batch_chunk['tgt'] = [minion_id]
                batch_chunk['expr_form'] = 'list'
                future = self._disbatch_local(batch_chunk)
                inflight_futures.append(future)

            # if we have nothing to wait for, don't wait
            if len(inflight_futures) == 0:
                continue

            # wait until someone is done
            finished_future = yield Any(inflight_futures)
            try:
                b_ret = finished_future.result()
            except TimeoutException:
                break
            chunk_ret.update(b_ret)
            inflight_futures.remove(finished_future)

        raise tornado.gen.Return(chunk_ret)

    @tornado.gen.coroutine
    def _disbatch_local(self, chunk):
        '''
        Dispatch local client commands
        '''
        chunk_ret = {}

        f_call = salt.utils.format_call(self.saltclients['local'], chunk)
        # fire a job off
        try:
            pub_data = self.saltclients['local'](*f_call.get('args', ()), **f_call.get('kwargs', {}))
        except EauthAuthenticationError:
            raise tornado.gen.Return('Not authorized to run this job')

        # if the job didn't publish, lets not wait around for nothing
        # TODO: set header??
        if 'jid' not in pub_data:
            raise tornado.gen.Return('No minions matched the target. No command was sent, no jid was assigned.')

        # seed minions_remaining with the pub_data
        minions_remaining = pub_data['minions']

        syndic_min_wait = None
        if self.application.opts['order_masters']:
            syndic_min_wait = tornado.gen.sleep(self.application.opts['syndic_wait'])

        job_not_running = self.job_not_running(pub_data['jid'],
                                               chunk['tgt'],
                                               f_call['kwargs']['expr_form'],
                                               minions_remaining=minions_remaining
                                               )

        # if we have a min_wait, do that
        if syndic_min_wait is not None:
            yield syndic_min_wait
        # we are completed when either all minions return or the job isn't running anywhere
        chunk_ret = yield self.all_returns(pub_data['jid'],
                                           finish_futures=[job_not_running],
                                           minions_remaining=minions_remaining,
                                           )

        raise tornado.gen.Return(chunk_ret)

    @tornado.gen.coroutine
    def all_returns(self,
                    jid,
                    finish_futures=None,
                    minions_remaining=None,
                    ):
        '''
        Return a future which will complete once all returns are completed
        (according to minions_remaining), or one of the passed in "finish_futures" completes
        '''
        if finish_futures is None:
            finish_futures = []
        if minions_remaining is None:
            minions_remaining = []

        ret_tag = tagify([jid, 'ret'], 'job')
        chunk_ret = {}
        while True:
            ret_event = self.application.event_listener.get_event(self,
                                                      tag=ret_tag,
                                                      )
            f = yield Any([ret_event] + finish_futures)
            if f in finish_futures:
                raise tornado.gen.Return(chunk_ret)
            event = f.result()
            chunk_ret[event['data']['id']] = event['data']['return']
            # its possible to get a return that wasn't in the minion_remaining list
            try:
                minions_remaining.remove(event['data']['id'])
            except ValueError:
                pass
            if len(minions_remaining) == 0:
                raise tornado.gen.Return(chunk_ret)

    @tornado.gen.coroutine
    def job_not_running(self,
                  jid,
                  tgt,
                  tgt_type,
                  minions_remaining=None,
                  ):
        '''
        Return a future which will complete once jid (passed in) is no longer
        running on tgt
        '''
        if minions_remaining is None:
            minions_remaining = []

        ping_pub_data = self.saltclients['local'](tgt,
                                                  'saltutil.find_job',
                                                  [jid],
                                                  expr_form=tgt_type)
        ping_tag = tagify([ping_pub_data['jid'], 'ret'], 'job')

        minion_running = False
        while True:
            try:
                event = yield self.application.event_listener.get_event(self,
                                                                        tag=ping_tag,
                                                                        timeout=self.application.opts['gather_job_timeout'],
                                                                        )
            except TimeoutException:
                if not minion_running:
                    raise tornado.gen.Return(True)
                else:
                    ping_pub_data = self.saltclients['local'](tgt,
                                                              'saltutil.find_job',
                                                              [jid],
                                                              expr_form=tgt_type)
                    ping_tag = tagify([ping_pub_data['jid'], 'ret'], 'job')
                    minion_running = False
                    continue
            # Minions can return, we want to see if the job is running...
            if event['data'].get('return', {}) == {}:
                continue
            minion_running = True
            id_ = event['data']['id']
            if id_ not in minions_remaining:
                minions_remaining.append(event['data']['id'])

    @tornado.gen.coroutine
    def _disbatch_local_async(self, chunk):
        '''
        Disbatch local client_async commands
        '''
        f_call = salt.utils.format_call(self.saltclients['local_async'], chunk)
        # fire a job off
        pub_data = self.saltclients['local_async'](*f_call.get('args', ()), **f_call.get('kwargs', {}))

        raise tornado.gen.Return(pub_data)

    @tornado.gen.coroutine
    def _disbatch_runner(self, chunk):
        '''
        Disbatch runner client commands
        '''
        f_call = {'args': [chunk['fun'], chunk]}
        pub_data = self.saltclients['runner'](chunk['fun'], chunk)
        tag = pub_data['tag'] + '/ret'
        try:
            event = yield self.application.event_listener.get_event(self, tag=tag)

            # only return the return data
            raise tornado.gen.Return(event['data']['return'])
        except TimeoutException:
            raise tornado.gen.Return('Timeout waiting for runner to execute')

    @tornado.gen.coroutine
    def _disbatch_runner_async(self, chunk):
        '''
        Disbatch runner client_async commands
        '''
        f_call = {'args': [chunk['fun'], chunk]}
        pub_data = self.saltclients['runner'](chunk['fun'], chunk)
        raise tornado.gen.Return(pub_data)


class MinionSaltAPIHandler(SaltAPIHandler):  # pylint: disable=W0223
    '''
    A convenience endpoint for minion related functions
    '''
    @tornado.web.asynchronous
    def get(self, mid=None):  # pylint: disable=W0221
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
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        self.lowstate = [{
            'client': 'local',
            'tgt': mid or '*',
            'fun': 'grains.items',
        }]
        self.disbatch()

    @tornado.web.asynchronous
    def post(self):
        '''
        Start an execution command and immediately return the job id

        .. http:post:: /minions

            :reqheader X-Auth-Token: |req_token|
            :reqheader Accept: |req_accept|
            :reqheader Content-Type: |req_ct|

            :resheader Content-Type: |res_ct|

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

            :term:`lowstate` data describing Salt commands must be sent in the
            request body. The ``client`` option will be set to
            :py:meth:`~salt.client.LocalClient.local_async`.

        **Example request:**

        .. code-block:: bash

            curl -sSi localhost:8000/minions \\
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

        **Example response:**

        .. code-block:: http

            HTTP/1.1 202 Accepted
            Content-Length: 86
            Content-Type: application/x-yaml

            return:
            - jid: '20130603122505459265'
              minions: [ms-4, ms-3, ms-2, ms-1, ms-0]
        '''
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        # verify that all lowstates are the correct client type
        for low in self.lowstate:
            # if you didn't specify, its fine
            if 'client' not in low:
                low['client'] = 'local_async'
                continue
            # if you specified something else, we don't do that
            if low.get('client') != 'local_async':
                self.set_status(400)
                self.write('We don\'t serve your kind here')
                self.finish()
                return

        self.disbatch()


class JobsSaltAPIHandler(SaltAPIHandler):  # pylint: disable=W0223
    '''
    A convenience endpoint for job cache data
    '''
    @tornado.web.asynchronous
    def get(self, jid=None):  # pylint: disable=W0221
        '''
        A convenience URL for getting lists of previously run jobs or getting
        the return from a single job

        .. http:get:: /jobs/(jid)

            List jobs or show a single job from the job cache.

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
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        if jid:
            self.lowstate = [{
                'fun': 'jobs.list_job',
                'jid': jid,
                'client': 'runner',
            }]
        else:
            self.lowstate = [{
                'fun': 'jobs.list_jobs',
                'client': 'runner',
            }]

        self.disbatch()


class RunSaltAPIHandler(SaltAPIHandler):  # pylint: disable=W0223
    '''
    Endpoint to run commands without normal session handling
    '''
    @tornado.web.asynchronous
    def post(self):
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
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -sS localhost:8000/run \\
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
        '''
        self.disbatch()


class EventsSaltAPIHandler(SaltAPIHandler):  # pylint: disable=W0223
    '''
    Expose the Salt event bus

    The event bus on the Salt master exposes a large variety of things, notably
    when executions are started on the master and also when minions ultimately
    return their results. This URL provides a real-time window into a running
    Salt infrastructure.

    .. seealso:: :ref:`events`
    '''
    @tornado.gen.coroutine
    def get(self):
        r'''
        An HTTP stream of the Salt master event bus

        This stream is formatted per the Server Sent Events (SSE) spec. Each
        event is formatted as JSON.

        .. http:get:: /events

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|

        **Example request:**

        .. code-block:: bash

            curl -NsS localhost:8000/events

        .. code-block:: http

            GET /events HTTP/1.1
            Host: localhost:8000

        **Example response:**

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

        Or using CORS:

        .. code-block:: javascript

            var source = new EventSource('/events', {withCredentials: true});

        Some browser clients lack CORS support for the ``EventSource()`` API. Such
        clients may instead pass the :mailheader:`X-Auth-Token` value as an URL
        parameter:

        .. code-block:: bash

            curl -NsS localhost:8000/events/6d1b722e

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
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return
        # set the streaming headers
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('Connection', 'keep-alive')

        self.write(u'retry: {0}\n'.format(400))
        self.flush()

        while True:
            try:
                event = yield self.application.event_listener.get_event(self)
                self.write(u'tag: {0}\n'.format(event.get('tag', '')))
                self.write(u'data: {0}\n\n'.format(json.dumps(event)))
                self.flush()
            except TimeoutException:
                break


class WebhookSaltAPIHandler(SaltAPIHandler):  # pylint: disable=W0223
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
            - 'curl -sS http://saltapi-url.example.com:8000/hook/travis/build/success -d branch="${TRAVIS_BRANCH}" -d commit="${TRAVIS_COMMIT}"'

    .. seealso:: :ref:`events`, :ref:`reactor`
    '''
    def post(self, tag_suffix=None):  # pylint: disable=W0221
        '''
        Fire an event in Salt with a custom event tag and data

        .. http:post:: /hook

            :status 200: |200|
            :status 401: |401|
            :status 406: |406|
            :status 413: request body is too large

        **Example request:**

        .. code-block:: bash

            curl -sS localhost:8000/hook -d foo='Foo!' -d bar='Bar!'

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
        '''
        disable_auth = self.application.mod_opts.get('webhook_disable_auth')
        if not disable_auth and not self._verify_auth():
            self.redirect('/login')
            return

        # if you have the tag, prefix
        tag = 'salt/netapi/hook'
        if tag_suffix:
            tag += tag_suffix

        # TODO: consolidate??
        self.event = salt.utils.event.get_event(
            'master',
            self.application.opts['sock_dir'],
            self.application.opts['transport'],
            opts=self.application.opts,
            listen=False)

        ret = self.event.fire_event({
            'post': self.raw_data,
            'get': dict(self.request.query_arguments),
            # In Tornado >= v4.0.3, the headers come
            # back as an HTTPHeaders instance, which
            # is a dictionary. We must cast this as
            # a dictionary in order for msgpack to
            # serialize it.
            'headers': dict(self.request.headers),
        }, tag)

        self.write(self.serialize({'success': ret}))


def _check_cors_origin(origin, allowed_origins):
    """
    Check if an origin match cors allowed origins
    """
    if isinstance(allowed_origins, list):
        if origin in allowed_origins:
            return origin
    elif allowed_origins == '*':
        return allowed_origins
    elif allowed_origins == origin:
        # Cors origin is either * or specific origin
        return allowed_origins
