# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2016 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    pytestsalt.salt.log_handlers.pytest_log_handler
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt External Logging Handler
'''

# Import python libs
from __future__ import absolute_import
import socket
import threading
import logging
import msgpack
import salt.log.setup
from salt.ext.six.moves.queue import Queue

__virtualname__ = 'runtests_log_handler'

log = logging.getLogger(__name__)

def __virtual__():
    if 'runtests_log_port' not in __opts__:
        return False, "'runtests_log_port' not in options"
    return True


def setup_handlers():
    queue = Queue()
    handler = salt.log.setup.QueueHandler(queue)
    handler.setLevel(1)
    process_queue_thread = threading.Thread(target=process_queue, args=(__opts__['runtests_log_port'], queue))
    process_queue_thread.daemon = True
    process_queue_thread.start()
    return handler


def process_queue(port, queue):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', port))
    while True:
        try:
            record = queue.get()
            if record is None:
                # A sentinel to stop processing the queue
                break
            # Just log everything, filtering will happen on the main process
            # logging handlers
            sock.sendall(msgpack.dumps(record.__dict__, encoding='utf-8'))
        except (EOFError, KeyboardInterrupt, SystemExit):
            break
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(
                'An exception occurred in the pytest salt logging '
                'queue thread: {0}'.format(exc),
                exc_info_on_loglevel=logging.DEBUG
            )
