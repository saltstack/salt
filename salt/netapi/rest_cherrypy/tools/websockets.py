# encoding: utf-8
from __future__ import absolute_import
import cherrypy

from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

cherrypy.tools.websocket = WebSocketTool()
WebSocketPlugin(cherrypy.engine).subscribe()


class SynchronizingWebsocket(WebSocket):
    '''
    Class to handle requests sent to this websocket connection.
    Each instance of this class represents a Salt websocket connection.
    Waits to receive a ``ready`` message from the client.
    Calls send on it's end of the pipe to signal to the sender on receipt
    of ``ready``.

    This class also kicks off initial information probing jobs when clients
    initially connect. These jobs help gather information about minions, jobs,
    and documentation.
    '''
    def __init__(self, *args, **kwargs):  # pylint: disable=E1002
        super(SynchronizingWebsocket, self).__init__(*args, **kwargs)

        # This pipe needs to represent the parent end of a pipe.
        # Clients need to ensure that the pipe assigned to ``self.pipe`` is
        # the ``parent end`` of a
        # `pipe <https://docs.python.org/2/library/multiprocessing.html#exchanging-objects-between-processes>`_.
        self.pipe = None

        # The token that we can use to make API calls.
        # There are times when we would like to kick off jobs,
        # examples include trying to obtain minions connected.
        self.token = None

        # Options represent ``salt`` options defined in the configs.
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
        self.send('server received message', False)
