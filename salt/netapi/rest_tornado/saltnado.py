'''
A REST API for Salt
===================

.. py:currentmodule:: salt.netapi.rest_tornado.saltnado

:depends:   - tornado Python module

All Events
----------

Exposes ``all`` "real-time" events from Salt's event bus on a websocket connection.
It should be noted that "Real-time" here means these events are made available
to the server as soon as any salt related action (changes to minions, new jobs etc) happens.
Clients are however assumed to be able to tolerate any network transport related latencies.
Functionality provided by this endpoint is similar to the ``/events`` end point.

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
in subsequent websocket requests (as part of the URL).

The event stream can be easily consumed via JavaScript:

.. code-block:: javascript

    // Note, you must be authenticated!

    // Get the Websocket connection to Salt
    var source = new Websocket('wss://localhost:8000/all_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7');

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
Or the tornado
`client <http://tornado.readthedocs.org/en/latest/websocket.html#client-side-support>`_.

.. code-block:: python

    # Note, you must be authenticated!

    from websocket import create_connection

    # Get the Websocket connection to Salt
    ws = create_connection('wss://localhost:8000/all_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7')

    # Get Salt's "real time" event stream.
    ws.send('websocket client ready')


    # Simple listener to print results of Salt's "real time" event stream.
    # Look at https://pypi.python.org/pypi/websocket-client/ for more examples.
    while listening_to_events:
        print ws.recv()       #  Salt's "real time" event data as serialized JSON.

    # Terminates websocket connection and Salt's "real time" event stream on the server.
    ws.close()

    # Please refer to https://github.com/liris/websocket-client/issues/81 when using a self signed cert

Above examples show how to establish a websocket connection to Salt and activating
real time updates from Salt's event stream by signaling ``websocket client ready``.


Formatted Events
-----------------

Exposes ``formatted`` "real-time" events from Salt's event bus on a websocket connection.
It should be noted that "Real-time" here means these events are made available
to the server as soon as any salt related action (changes to minions, new jobs etc) happens.
Clients are however assumed to be able to tolerate any network transport related latencies.
Functionality provided by this endpoint is similar to the ``/events`` end point.

The event bus on the Salt master exposes a large variety of things, notably
when executions are started on the master and also when minions ultimately
return their results. This URL provides a real-time window into a running
Salt infrastructure. Uses websocket as the transport mechanism.

Formatted events parses the raw "real time" event stream and maintains
a current view of the following:

- minions
- jobs

A change to the minions (such as addition, removal of keys or connection drops)
or jobs is processed and clients are updated.
Since we use salt's presence events to track minions,
please enable ``presence_events``
and set a small value for the ``loop_interval``
in the salt master config file.

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
in subsequent websocket requests (as part of the URL).

The event stream can be easily consumed via JavaScript:

.. code-block:: javascript

    // Note, you must be authenticated!

    // Get the Websocket connection to Salt
    var source = new Websocket('wss://localhost:8000/formatted_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7');

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
Or the tornado
`client <http://tornado.readthedocs.org/en/latest/websocket.html#client-side-support>`_.

.. code-block:: python

    # Note, you must be authenticated!

    from websocket import create_connection

    # Get the Websocket connection to Salt
    ws = create_connection('wss://localhost:8000/formatted_events/d0ce6c1a37e99dcc0374392f272fe19c0090cca7')

    # Get Salt's "real time" event stream.
    ws.send('websocket client ready')


    # Simple listener to print results of Salt's "real time" event stream.
    # Look at https://pypi.python.org/pypi/websocket-client/ for more examples.
    while listening_to_events:
        print ws.recv()       #  Salt's "real time" event data as serialized JSON.

    # Terminates websocket connection and Salt's "real time" event stream on the server.
    ws.close()

    # Please refer to https://github.com/liris/websocket-client/issues/81 when using a self signed cert

Above examples show how to establish a websocket connection to Salt and activating
real time updates from Salt's event stream by signaling ``websocket client ready``.

Example responses
-----------------

``Minion information`` is a dictionary keyed by each connected minion's ``id`` (``mid``),
grains information for each minion is also included.

Minion information is sent in response to the following minion events:

- connection drops
    - requires running ``manage.present`` periodically every ``loop_interval`` seconds
- minion addition
- minon removal

.. code-block:: python

    # Not all grains are shown
    data: {
        "minions": {
            "minion1": {
                "id": "minion1",
                "grains": {
                    "kernel": "Darwin",
                    "domain": "local",
                    "zmqversion": "4.0.3",
                    "kernelrelease": "13.2.0"
                }
            }
        }
    }

``Job information`` is also tracked and delivered.

Job information is also a dictionary
in which each job's information is keyed by salt's ``jid``.

.. code-block:: python

    data: {
        "jobs": {
            "20140609153646699137": {
                "tgt_type": "glob",
                "jid": "20140609153646699137",
                "tgt": "*",
                "start_time": "2014-06-09T15:36:46.700315",
                "state": "complete",
                "fun": "test.ping",
                "minions": {
                    "minion1": {
                        "return": true,
                        "retcode": 0,
                        "success": true
                    }
                }
            }
        }
    }

Setup
=====

In order to run rest_tornado with the salt-master
add the following to your salt master config file.

.. code-block:: yaml

    rest_tornado:
        # can be any port
        port: 8000
        ssl_crt: /etc/pki/api/certs/server.crt
        # no need to specify ssl_key if cert and key
        # are in one single file
        ssl_key: /etc/pki/api/certs/server.key
        debug: False
        disable_ssl: False

'''


'''
Notes
=====

.. code-block:: bash

    curl localhost:8888/login -d client=local -d username=username -d password=password -d eauth=pam

    # for testing
    curl -H 'X-Auth-Token: 89010c15bcbc8e4fc4ce4605b6699165' localhost:8888 -d client=local -d tgt='*' -d fun='test.ping'

    # not working.... but in siege 3.0.1 and posts..
    siege -c 1 -n 1 "http://127.0.0.1:8888 POST client=local&tgt=*&fun=test.ping"

    # this works
    ab - c 50 -n 100 -p body -T 'application/x-www-form-urlencoded' http://localhost:8888/

    {"return": [{"perms": ["*.*"], "start": 1396151398.373983, "token": "cb86b805e8915c84bceb0d466026caab", "expire": 1396194598.373983, "user": "jacksontj", "eauth": "pam"}]}[jacksontj@Thomas-PC netapi]$
'''

import logging
from copy import copy

import time

import sys

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.gen
import tornado.websocket
from tornado.concurrent import Future
import event_processor

from collections import defaultdict

import math
import functools
import json
import yaml
import zmq
import fnmatch

# salt imports
import salt.netapi
import salt.utils
import salt.utils.event
from salt.utils.event import tagify
import salt.client
import salt.runner
import salt.auth

logger = logging.getLogger()

'''
The clients rest_cherrypi supports. We want to mimic the interface, but not
    necessarily use the same API under the hood
# all of these require coordinating minion stuff
 - "local" (done)
 - "local_async" (done)
 - "local_batch" (done)

# master side
 - "runner" (done)
 - "wheel" (need async api...)
'''


# TODO: refreshing clients using cachedict
saltclients = {'local': salt.client.get_local_client().run_job,
               # not the actual client we'll use.. but its what we'll use to get args
               'local_batch': salt.client.get_local_client().cmd_batch,
               'local_async': salt.client.get_local_client().run_job,
               'runner': salt.runner.RunnerClient(salt.config.master_config('/etc/salt/master')).async,
               }


AUTH_TOKEN_HEADER = 'X-Auth-Token'
AUTH_COOKIE_NAME = 'session_id'


class TimeoutException(Exception):
    pass


class Any(Future):
    '''
    Future that wraps other futures to "block" until one is done
    '''
    def __init__(self, futures):
        super(Any, self).__init__()
        for future in futures:
            future.add_done_callback(self.done_callback)

    def done_callback(self, future):
        self.set_result(future)


class EventListener():
    def __init__(self, mod_opts, opts):
        self.mod_opts = mod_opts
        self.opts = opts
        self.event = salt.utils.event.get_event(
                'master',
                opts['sock_dir'],
                opts['transport'])

        # tag -> list of futures
        self.tag_map = defaultdict(list)

        # request_obj -> list of (tag, future)
        self.request_map = defaultdict(list)

    def clean_timeout_futures(self, request):
        '''
        Remove all futures that were waiting for request `request` since it is done waiting
        '''
        if request not in self.request_map:
            return
        for tag, future in self.request_map[request]:
            # TODO: log, this shouldn't happen...
            if tag not in self.tag_map:
                continue
            # mark the future done
            future.set_exception(TimeoutException())
            self.tag_map[tag].remove(future)

            # if that was the last of them, remove the key all together
            if len(self.tag_map[tag]) == 0:
                del self.tag_map[tag]

    def get_event(self, request,
                        tag='',
                        callback=None):
        '''
        Get an event (async of course) return a future that will get it later
        '''
        future = Future()
        if callback is not None:
            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)
            future.add_done_callback(handle_future)
        # add this tag and future to the callbacks
        self.tag_map[tag].append(future)
        self.request_map[request].append((tag, future))

        return future

    def iter_events(self):
        '''
        Iterate over all events that could happen
        '''
        try:
            data = self.event.get_event_noblock()
            # see if we have any futures that need this info:
            for tag_prefix, futures in self.tag_map.items():
                if data['tag'].startswith(tag_prefix):
                    for future in futures:
                        if future.done():
                            continue
                        future.set_result(data)
                    del self.tag_map[tag_prefix]

            # call yourself back!
            tornado.ioloop.IOLoop.instance().add_callback(self.iter_events)

        except zmq.ZMQError as e:
            # TODO: not sure what other errors we can get...
            if e.errno != zmq.EAGAIN:
                raise Exception()
            # add callback in the future (to avoid spinning)
            # TODO: configurable timeout
            tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 0.1, self.iter_events)
        except:
            logging.critical('Uncaught exception in the event_listener: {0}'.format(sys.exc_info()))
            # TODO: configurable timeout
            tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 0.1, self.iter_events)


# TODO: move to a utils function within salt-- the batching stuff is a bit tied together
def get_batch_size(batch, num_minions):
    '''
    Return the batch size that you should have
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


class BaseSaltAPIHandler(tornado.web.RequestHandler):
    ct_out_map = (
        ('application/json', json.dumps),
        ('application/x-yaml', functools.partial(
            yaml.safe_dump, default_flow_style=False)),
    )

    def _verify_client(self, client):
        '''
        Verify that the client is in fact one we have
        '''
        if client not in saltclients:
            self.set_status(400)
            self.write('We don\'t serve your kind here')
            self.finish()

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
        Boolean wether the request is auth'd
        '''

        return self.token and bool(self.application.auth.get_tok(self.token))

    def prepare(self):
        '''
        Run before get/posts etc. Pre-flight checks:
            - verify that we can speak back to them (compatible accept header)
        '''
        # verify the content type
        found = False
        for content_type, dumper in self.ct_out_map:
            if fnmatch.fnmatch(content_type, self.request.headers['Accept']):
                found = True
                break

        # better return message?
        if not found:
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
        for key, val in self.request.arguments.iteritems():
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
            'application/x-yaml': functools.partial(
                yaml.safe_load, default_flow_style=False),
            'text/yaml': functools.partial(
                yaml.safe_load, default_flow_style=False),
            # because people are terrible and dont mean what they say
            'text/plain': json.loads
        }

        try:
            if self.request.headers['Content-Type'] not in ct_in_map:
                self.send_error(406)
            return ct_in_map[self.request.headers['Content-Type']](data)
        except KeyError:
            return []

    def _get_lowstate(self):
        '''
        Format the incoming data into a lowstate object
        '''
        data = self.deserialize(self.request.body)
        self.raw_data = copy(data)

        if self.request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            if 'arg' in data and not isinstance(data['arg'], list):
                data['arg'] = [data['arg']]
            lowstate = [data]
        else:
            lowstate = data
        return lowstate


class SaltAuthHandler(BaseSaltAPIHandler):
    '''
    Handler for login resquests
    '''
    def get(self):
        '''
        We don't allow gets on the login path, so lets send back a nice message
        '''
        self.set_status(401)
        self.set_header('WWW-Authenticate', 'Session')

        ret = {'status': '401 Unauthorized',
               'return': 'Please log in'}

        self.write(self.serialize(ret))
        self.finish()

    # TODO: make async? Underlying library isn't... and we ARE making disk calls :(
    def post(self):
        '''
        Authenticate against Salt's eauth system
        {"return": {"start": 1395507384.320007, "token": "6ff4cd2b770ada48713afc629cd3178c", "expire": 1395550584.320007, "name": "jacksontj", "eauth": "pam"}}
        {"return": [{"perms": ["*.*"], "start": 1395507675.396021, "token": "dea8274dc359fee86357d9d0263ec93c0498888e", "expire": 1395550875.396021, "user": "jacksontj", "eauth": "pam"}]}
        '''
        creds = {'username': self.get_arguments('username')[0],
                 'password': self.get_arguments('password')[0],
                 'eauth': self.get_arguments('eauth')[0],
                 }

        token = self.application.auth.mk_token(creds)
        if not 'token' in token:
            # TODO: nicer error message
            # 'Could not authenticate using provided credentials')
            self.send_error(401)
            # return since we don't want to execute any more
            return

        # Grab eauth config for the current backend for the current user
        try:
            perms = self.application.opts['external_auth'][token['eauth']][token['name']]
        except (AttributeError, IndexError):
            logging.debug("Configuration for external_auth malformed for "
                         "eauth '{0}', and user '{1}'."
                         .format(token.get('eauth'), token.get('name')), exc_info=True)
            # TODO better error -- 'Configuration for external_auth could not be read.'
            self.send_error(500)

        ret = {'return': [{
            'token': token['token'],
            'expire': token['expire'],
            'start': token['start'],
            'user': token['name'],
            'eauth': token['eauth'],
            'perms': perms,
            }]}

        self.write(self.serialize(ret))
        self.finish()


class SaltAPIHandler(BaseSaltAPIHandler):
    '''
    Main API handler for base "/"
    '''
    def get(self):
        '''
        return data about what clients you have
        '''
        ret = {"clients": saltclients.keys(),
               "return": "Welcome"}
        self.write(self.serialize(ret))
        self.finish()

    @tornado.web.asynchronous
    def post(self):
        '''
        This function takes in all the args for dispatching requests
            **Example request**::

            % curl -si https://localhost:8000 \\
                    -H "Accept: application/x-yaml" \\
                    -H "X-Auth-Token: d40d1e1e" \\
                    -d client=local \\
                    -d tgt='*' \\
                    -d fun='test.sleep' \\
                    -d arg=1
        '''
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        client = self.get_arguments('client')[0]
        self._verify_client(client)
        self.disbatch(client)

    def disbatch(self, client):
        '''
        Disbatch a lowstate job to the appropriate client
        '''
        self.client = client

        for low in self.lowstate:
            if (not self._verify_auth() or 'eauth' in low):
                # TODO: better error?
                self.set_status(401)
                self.finish()
                return
        # disbatch to the correct handler
        try:
            getattr(self, '_disbatch_{0}'.format(self.client))()
        except AttributeError:
            # TODO set the right status... this means we didn't implement it...
            self.set_status(500)
            self.finish()

    @tornado.gen.coroutine
    def _disbatch_local_batch(self):
        '''
        Disbatch local client batched commands
        '''
        self.ret = []

        for chunk in self.lowstate:
            f_call = salt.utils.format_call(saltclients['local_batch'], chunk)

            timeout = float(chunk.get('timeout', self.application.opts['timeout']))
            # set the timeout
            timeout_obj = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + timeout, self.timeout_futures)

            # ping all the minions (to see who we have to talk to)
            # TODO: actually ping them all? this just gets the pub data
            minions = saltclients['local'](chunk['tgt'],
                                           'test.ping',
                                           [],
                                           expr_form=f_call['kwargs']['expr_form'])['minions']

            chunk_ret = {}
            maxflight = get_batch_size(f_call['kwargs']['batch'], len(minions))
            inflight_futures = []
            # do this batch
            while len(minions) > 0:
                # if you have more to go, lets disbatch jobs
                while len(inflight_futures) < maxflight:
                    minion_id = minions.pop(0)
                    f_call['args'][0] = minion_id
                    # TODO: list??
                    f_call['kwargs']['expr_form'] = 'glob'
                    pub_data = saltclients['local'](*f_call.get('args', ()), **f_call.get('kwargs', {}))
                    print pub_data
                    tag = tagify([pub_data['jid'], 'ret', minion_id], 'job')
                    future = self.application.event_listener.get_event(self, tag=tag)
                    inflight_futures.append(future)

                # wait until someone is done
                finished_future = yield Any(inflight_futures)
                try:
                    event = finished_future.result()
                except TimeoutException:
                    break
                print event
                chunk_ret[event['data']['id']] = event['data']['return']
                inflight_futures.remove(finished_future)

            self.ret.append(chunk_ret)

            # if we finish in time, cancel the timeout
            tornado.ioloop.IOLoop.instance().remove_timeout(timeout_obj)

        self.write(self.serialize({'return': self.ret}))
        self.finish()

    @tornado.gen.coroutine
    def _disbatch_local(self):
        '''
        Disbatch local client commands
        '''
        self.ret = []

        for chunk in self.lowstate:
            timeout = float(chunk.get('timeout', self.application.opts['timeout']))
            # set the timeout
            tornado.ioloop.IOLoop.instance().add_timeout(time.time() + timeout, self.timeout_futures)
            timeout_obj = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + timeout, self.timeout_futures)

            # TODO: not sure why.... we already verify auth, probably for ACLs
            # require token or eauth
            chunk['token'] = self.token

            chunk_ret = {}

            f_call = salt.utils.format_call(saltclients[self.client], chunk)
            # fire a job off
            pub_data = saltclients[self.client](*f_call.get('args', ()), **f_call.get('kwargs', {}))

            # get the tag that we are looking for
            tag = tagify([pub_data['jid'], 'ret'], 'job')

            minions_remaining = pub_data['minions']

            # while we are waiting on all the mininons
            while len(minions_remaining) > 0:
                try:
                    event = yield self.application.event_listener.get_event(self, tag=tag)
                    chunk_ret[event['data']['id']] = event['data']['return']
                    minions_remaining.remove(event['data']['id'])
                # if you hit a timeout, just stop waiting ;)
                except TimeoutException:
                    break
            self.ret.append(chunk_ret)

            # if we finish in time, cancel the timeout
            tornado.ioloop.IOLoop.instance().remove_timeout(timeout_obj)

        self.write(self.serialize({'return': self.ret}))
        self.finish()

    def _disbatch_local_async(self):
        '''
        Disbatch local client_async commands
        '''
        ret = []
        for chunk in self.lowstate:
            f_call = salt.utils.format_call(saltclients[self.client], chunk)
            # fire a job off
            pub_data = saltclients[self.client](*f_call.get('args', ()), **f_call.get('kwargs', {}))
            ret.append(pub_data)

        self.write(self.serialize({'return': ret}))
        self.finish()

    @tornado.gen.coroutine
    def _disbatch_runner(self):
        '''
        Disbatch runner client commands
        '''
        self.ret = []
        for chunk in self.lowstate:
            timeout = float(chunk.get('timeout', self.application.opts['timeout']))
            # set the timeout
            tornado.ioloop.IOLoop.instance().add_timeout(time.time() + timeout, self.timeout_futures)
            timeout_obj = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + timeout, self.timeout_futures)

            f_call = {'args': [chunk['fun'], chunk]}
            pub_data = saltclients[self.client](chunk['fun'], chunk)
            tag = pub_data['tag'] + '/ret'
            try:
                event = yield self.application.event_listener.get_event(self, tag=tag)
                # only return the return data
                self.ret.append(event['data']['return'])

                # if we finish in time, cancel the timeout
                tornado.ioloop.IOLoop.instance().remove_timeout(timeout_obj)
            except TimeoutException:
                break

        self.write(self.serialize({'return': self.ret}))
        self.finish()


class MinionSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /minion requests
    '''
    @tornado.web.asynchronous
    def get(self, mid):
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        #'client': 'local', 'tgt': mid or '*', 'fun': 'grains.items',
        self.lowstate = [{
            'client': 'local', 'tgt': mid or '*', 'fun': 'grains.items',
        }]
        self.disbatch('local')

    @tornado.web.asynchronous
    def post(self):
        '''
        local_async post endpoint
        '''
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        self.disbatch('local_async')


class JobsSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /minion requests
    '''
    @tornado.web.asynchronous
    def get(self, jid=None):
        # if you aren't authenticated, redirect to login
        if not self._verify_auth():
            self.redirect('/login')
            return

        self.lowstate = [{
            'fun': 'jobs.lookup_jid' if jid else 'jobs.list_jobs',
            'jid': jid,
        }]

        if jid:
            self.lowstate.append({
                'fun': 'jobs.list_job',
                'jid': jid,
            })

        self.disbatch('runner')


class RunSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /run requests
    '''
    @tornado.web.asynchronous
    def post(self):
        client = self.get_arguments('client')[0]
        self._verify_client(client)
        self.disbatch(client)


class EventsSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /events requests
    '''
    @tornado.gen.coroutine
    def get(self):
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

        self.finish()


class AllEventsHandler(tornado.websocket.WebSocketHandler):
    '''
    Server side websocket handler.
    '''
    def open(self, token):
        '''
        Return a websocket connection to Salt
        representing Salt's "real time" event stream.
        '''
        logger.debug('In the websocket open method')

        self.token = token
        # close the connection, if not authenticated
        if not self.application.auth.get_tok(token):
            logger.debug('Refusing websocket connection, bad token!')
            self.close()
            return

        self.connected = False

    @tornado.gen.coroutine
    def on_message(self, message):
        """Listens for a "websocket client ready" message.
        Once that message is received an asynchronous job
        is stated that yeilds messages to the client.
        These messages make up salt's
        "real time" event stream.
        """
        logger.debug('Got websocket message {}'.format(message))
        if message == 'websocket client ready':
            if self.connected:
                # TBD: Add ability to run commands in this branch
                logger.debug('Websocket already connected, returning')
                return

            self.connected = True

            while True:
                try:
                    event = yield self.application.event_listener.get_event(self)
                    self.write_message(u'data: {0}\n\n'.format(json.dumps(event)))
                except Exception as err:
                    logger.info('Error! Ending server side websocket connection. Reason = {}'.format(str(err)))
                    break

            self.close()
        else:
            # TBD: Add logic to run salt commands here
            pass

    def on_close(self, *args, **kwargs):
        '''Cleanup.

        '''
        logger.debug('In the websocket close method')
        self.close()


class FormattedEventsHandler(AllEventsHandler):

    @tornado.gen.coroutine
    def on_message(self, message):
        """Listens for a "websocket client ready" message.
        Once that message is received an asynchronous job
        is stated that yeilds messages to the client.
        These messages make up salt's
        "real time" event stream.
        """
        logger.debug('Got websocket message {}'.format(message))
        if message == 'websocket client ready':
            if self.connected:
                # TBD: Add ability to run commands in this branch
                logger.debug('Websocket already connected, returning')
                return

            self.connected = True

            evt_processor = event_processor.SaltInfo(self)
            client = salt.netapi.NetapiClient(self.application.opts)
            client.run({
                'fun': 'grains.items',
                'tgt': '*',
                'token': self.token,
                'mode': 'client',
                'async': 'local_async',
                'client': 'local'
                })
            while True:
                try:
                    event = yield self.application.event_listener.get_event(self)
                    evt_processor.process(event, self.token, self.application.opts)
                    # self.write_message(u'data: {0}\n\n'.format(json.dumps(event)))
                except Exception as err:
                    logger.debug('Error! Ending server side websocket connection. Reason = {}'.format(str(err)))
                    break

            self.close()
        else:
            # TBD: Add logic to run salt commands here
            pass


class WebhookSaltAPIHandler(SaltAPIHandler):
    '''
    Handler for /run requests
    '''
    def post(self, tag_suffix=None):
        if not self._verify_auth():
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
                self.application.opts['transport'])

        ret = self.event.fire_event({
            'post': self.raw_data,
            'headers': self.request.headers,
        }, tag)

        self.write(self.serialize({'success': ret}))
