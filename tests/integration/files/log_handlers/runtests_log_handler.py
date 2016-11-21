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
import logging
import threading
from multiprocessing import Queue

# Import 3rd-party libs
import msgpack

# Import Salt libs
import salt.log.setup

log = logging.getLogger(__name__)

__virtualname__ = 'runtests_log_handler'


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
    import errno
    import logging
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.connect(('localhost', port))
    except socket.error as exc:
        if exc.errno == errno.ECONNREFUSED:
            log.warning('Failed to connect to log server')
            return
    while True:
        try:
            record = queue.get()
            if record is None:
                # A sentinel to stop processing the queue
                break
            # Just log everything, filtering will happen on the main process
            # logging handlers
            sock.sendall(msgpack.dumps(record.__dict__, encoding='utf-8'))
        except (IOError, EOFError, KeyboardInterrupt, SystemExit):
            break
        except socket.error as exc:
            if exc.errno == errno.EPIPE:
                # Broken pipe
                break
            logging.getLogger(__name__).exception(exc)
        except Exception as exc:  # pylint: disable=broad-except
            logging.getLogger(__name__).warning(
                'An exception occurred in the pytest salt logging '
                'queue thread: {0}'.format(exc),
                exc_info_on_loglevel=logging.DEBUG
            )
