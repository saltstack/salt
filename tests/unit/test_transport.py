# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

import logging

from salt.transport import MessageClientPool

# Import Salt Testing libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class MessageClientPoolTest(TestCase):
    class MockClass(object):
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    def test_init(self):
        opts = {"sock_pool_size": 10}
        args = (0,)
        kwargs = {"kwarg": 1}
        message_client_pool = MessageClientPool(
            self.MockClass, opts, args=args, kwargs=kwargs
        )
        self.assertEqual(
            opts["sock_pool_size"], len(message_client_pool.message_clients)
        )
        for message_client in message_client_pool.message_clients:
            self.assertEqual(message_client.args, args)
            self.assertEqual(message_client.kwargs, kwargs)

    def test_init_without_config(self):
        opts = {}
        args = (0,)
        kwargs = {"kwarg": 1}
        message_client_pool = MessageClientPool(
            self.MockClass, opts, args=args, kwargs=kwargs
        )
        # The size of pool is set as 1 by the MessageClientPool init method.
        self.assertEqual(1, len(message_client_pool.message_clients))
        for message_client in message_client_pool.message_clients:
            self.assertEqual(message_client.args, args)
            self.assertEqual(message_client.kwargs, kwargs)

    def test_init_less_than_one(self):
        opts = {"sock_pool_size": -1}
        args = (0,)
        kwargs = {"kwarg": 1}
        message_client_pool = MessageClientPool(
            self.MockClass, opts, args=args, kwargs=kwargs
        )
        # The size of pool is set as 1 by the MessageClientPool init method.
        self.assertEqual(1, len(message_client_pool.message_clients))
        for message_client in message_client_pool.message_clients:
            self.assertEqual(message_client.args, args)
            self.assertEqual(message_client.kwargs, kwargs)
