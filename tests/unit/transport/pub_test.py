# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
import salt.transport.client


class PubChannelMixin(object):
    def test_basic(self):
        self.pub = None

        def handle_pub(ret):
            self.pub = ret
            self.stop()
        self.pub_channel = salt.transport.client.AsyncPubChannel.factory(self.minion_opts, io_loop=self.io_loop)
        connect_future = self.pub_channel.connect()
        connect_future.add_done_callback(lambda f: self.stop())
        self.wait()
        connect_future.result()
        self.pub_channel.on_recv(handle_pub)
        load = {
                    'fun': 'f',
                    'arg': 'a',
                    'tgt': 't',
                    'jid': 'j',
                    'ret': 'r',
                    'tgt_type': 'glob',
                }
        self.server_channel.publish(load)
        self.wait()
        self.assertEqual(self.pub['load'], load)
        self.pub_channel.on_recv(None)
        self.server_channel.publish(load)
        with self.assertRaises(self.failureException):
            self.wait(timeout=0.5)

        # close our pub_channel, to pass our FD checks
        del self.pub_channel
