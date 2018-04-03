# encoding: utf-8
'''
A Websockets add-on to saltnado
===============================

.. py:currentmodule:: salt.netapi.rest_tornado.saltnado

:depends:   - tornado Python module

In order to enable saltnado_websockets you must add websockets: True to your
saltnado config block.

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
        websockets: True

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
`client <https://tornado.readthedocs.io/en/latest/websocket.html#client-side-support>`_.

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
`client <https://tornado.readthedocs.io/en/latest/websocket.html#client-side-support>`_.

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
'''
from __future__ import absolute_import, print_function, unicode_literals

import tornado.websocket
from . import event_processor
from .saltnado import _check_cors_origin

import tornado.gen

import salt.utils.json
import salt.netapi

_json = salt.utils.json.import_json()

import logging
log = logging.getLogger(__name__)


class AllEventsHandler(tornado.websocket.WebSocketHandler):  # pylint: disable=W0223,W0232
    '''
    Server side websocket handler.
    '''

    # pylint: disable=W0221
    def get(self, token):
        '''
        Check the token, returns a 401 if the token is invalid.
        Else open the websocket connection
        '''
        log.debug('In the websocket get method')

        self.token = token
        # close the connection, if not authenticated
        if not self.application.auth.get_tok(token):
            log.debug('Refusing websocket connection, bad token!')
            self.send_error(401)
            return
        super(AllEventsHandler, self).get(token)

    def open(self, token):  # pylint: disable=W0221
        '''
        Return a websocket connection to Salt
        representing Salt's "real time" event stream.
        '''
        self.connected = False

    @tornado.gen.coroutine
    def on_message(self, message):
        """Listens for a "websocket client ready" message.
        Once that message is received an asynchronous job
        is stated that yields messages to the client.
        These messages make up salt's
        "real time" event stream.
        """
        log.debug('Got websocket message %s', message)
        if message == 'websocket client ready':
            if self.connected:
                # TBD: Add ability to run commands in this branch
                log.debug('Websocket already connected, returning')
                return

            self.connected = True

            while True:
                try:
                    event = yield self.application.event_listener.get_event(self)
                    self.write_message(
                        salt.utils.json.dumps(event, _json_module=_json))
                except Exception as err:
                    log.info('Error! Ending server side websocket connection. Reason = %s', err)
                    break

            self.close()
        else:
            # TBD: Add logic to run salt commands here
            pass

    def on_close(self, *args, **kwargs):
        '''Cleanup.

        '''
        log.debug('In the websocket close method')
        self.close()

    def check_origin(self, origin):
        """
        If cors is enabled, check that the origin is allowed
        """

        mod_opts = self.application.mod_opts

        if mod_opts.get('cors_origin'):
            return bool(_check_cors_origin(origin, mod_opts['cors_origin']))
        else:
            return super(AllEventsHandler, self).check_origin(origin)


class FormattedEventsHandler(AllEventsHandler):  # pylint: disable=W0223,W0232

    @tornado.gen.coroutine
    def on_message(self, message):
        """Listens for a "websocket client ready" message.
        Once that message is received an asynchronous job
        is stated that yields messages to the client.
        These messages make up salt's
        "real time" event stream.
        """
        log.debug('Got websocket message %s', message)
        if message == 'websocket client ready':
            if self.connected:
                # TBD: Add ability to run commands in this branch
                log.debug('Websocket already connected, returning')
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
                    # self.write_message('data: {0}\n\n'.format(salt.utils.json.dumps(event, _json_module=_json)))
                except Exception as err:
                    log.debug('Error! Ending server side websocket connection. Reason = %s', err)
                    break

            self.close()
        else:
            # TBD: Add logic to run salt commands here
            pass
