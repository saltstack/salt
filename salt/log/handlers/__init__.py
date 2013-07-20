# -*- coding: utf-8 -*-
'''
    salt.log.handlers
    ~~~~~~~~~~~~~~~~~

    Custom logging handlers to be used in salt.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import sys
import logging

# Import salt libs
from salt.log.mixins import NewStyleClassMixIn


if sys.version_info < (2, 7):
    # Since the NullHandler is only available on python >= 2.7, here's a copy
    # with NewStyleClassMixIn so it's also a new style class
    class NullHandler(logging.Handler, NewStyleClassMixIn):
        '''
        This is 1 to 1 copy of python's 2.7 NullHandler
        '''
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):  # pylint: disable=C0103
            self.lock = None

    logging.NullHandler = NullHandler


class QueueLoggingHandler(logging.NullHandler):

    def __init__(self, *args, **kwargs):
        self.__max_queue_size = kwargs.pop('max_queue_size', 10000)
        super(QueueLoggingHandler, self).__init__(*args, **kwargs)
        self.__messages = []

    def handle(self, record):
        self.acquire()
        if len(self.__messages) >= self.__max_queue_size:
            # Loose the initial log records
            self.__messages.pop(0)
        self.__messages.append(record)
        self.release()

    def sync_with_handlers(self, handlers=()):
        if not handlers:
            return

        while self.__messages:
            record = self.__messages.pop(0)
            for handler in handlers:
                handler.handle(record)
