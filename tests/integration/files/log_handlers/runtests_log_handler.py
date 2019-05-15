# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    :copyright: Copyright 2016 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    pytestsalt.salt.log_handlers.pytest_log_handler
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt External Logging Handler
'''

# Import python libs
from __future__ import absolute_import
import errno
import socket
import logging
import threading
from multiprocessing import Queue

# Import 3rd-party libs
import msgpack

# Import Salt libs
from salt.ext import six
from salt.utils.platform import is_darwin
import salt.log.setup

log = logging.getLogger(__name__)

__virtualname__ = 'runtests_log_handler'


def __virtual__():
    if 'runtests_log_port' not in __opts__:
        return False, "'runtests_log_port' not in options"
    if six.PY3:
        return False, "runtests external logging handler is temporarily disabled for Python 3 tests"
    return True


def setup_handlers():
    port = __opts__['runtests_log_port']
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.connect(('localhost', port))
    except socket.error as exc:
        if exc.errno == errno.ECONNREFUSED:
            log.warning('Failed to connect to log server')
            return
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    # One million log messages is more than enough to queue.
    # Above that value, if `process_queue` can't process fast enough,
    # start dropping. This will contain a memory leak in case `process_queue`
    # can't process fast enough of in case it can't deliver the log records at all.
    if is_darwin():
        queue_size = 32767
    else:
        queue_size = 10000000
    queue = Queue(queue_size)
    handler = salt.log.setup.QueueHandler(queue)
    level = salt.log.setup.LOG_LEVELS[(__opts__.get('runtests_log_level') or 'error').lower()]
    handler.setLevel(level)
    process_queue_thread = threading.Thread(target=process_queue, args=(port, queue))
    process_queue_thread.daemon = True
    process_queue_thread.start()
    return handler


def process_queue(port, queue):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.connect(('localhost', port))
    except socket.error as exc:
        if exc.errno == errno.ECONNREFUSED:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
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
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            break
        except socket.error as exc:
            if exc.errno == errno.EPIPE:
                # Broken pipe
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except OSError:
                    pass
                break
            log.exception(exc)
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(
                'An exception occurred in the pytest salt logging '
                'queue thread: %s',
                exc,
                exc_info_on_loglevel=logging.DEBUG
            )
