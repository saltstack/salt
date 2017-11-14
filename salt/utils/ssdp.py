# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
Salt Service Discovery Protocol.
JSON-based service discovery protocol, used by minions to find running Master.
'''

import datetime
import logging
import socket

from salt.utils import json
json = json.import_json()
if not hasattr(json, 'dumps'):
    json = None

try:
    import asyncio
except ImportError:
    try:
        # Python 2 doesn't have asyncio
        import trollius as asyncio
    except ImportError:
        asyncio = None


class SSDPBase(object):
    '''
    Salt Service Discovery Protocol.
    '''
    log = logging.getLogger(__name__)

    # Fields
    SIGNATURE = 'signature'
    ANSWER = 'answer'
    PORT = 'port'
    LISTEN_IP = 'listen_ip'

    # Default values
    DEFAULTS = {
        SIGNATURE: '__salt_master_service',
        PORT: 30777,
        LISTEN_IP: '0.0.0.0',
    }

    @staticmethod
    def _is_available():
        '''
        Return True if the USSDP dependencies are satisfied.
        :return:
        '''
        return bool(asyncio and json)

    @staticmethod
    def get_self_ip():
        '''
        Find out localhost outside IP.

        :return:
        '''
        sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sck.connect(('1.255.255.255', 1))  # Does not needs to be reachable
            ip_addr = sck.getsockname()[0]
        except Exception:
            ip_addr = socket.gethostbyname(socket.gethostname())
        finally:
            sck.close()
        return ip_addr


class SSDPFactory(SSDPBase):
    '''
    Socket protocol factory.
    '''

    def __init__(self, **config):
        '''
        Initialize

        :param config:
        '''
        for attr in (self.SIGNATURE, self.ANSWER):
            setattr(self, attr, config.get(attr, self.DEFAULTS[attr]))
        self.disable_hidden = False
        self.transport = None
        self.my_ip = socket.gethostbyname(socket.gethostname())
        self.DEFAULTS[self.ANSWER] = '{}'

    def __call__(self, *args, **kwargs):
        '''
        Return instance on Factory call.
        :param args:
        :param kwargs:
        :return:
        '''
        return self

    def connection_made(self, transport):
        '''
        On connection.

        :param transport:
        :return:
        '''
        self.transport = transport

    def datagram_received(self, data, addr):
        '''
        On datagram receive.

        :param data:
        :param addr:
        :return:
        '''
        message = data.decode()
        if message.startswith(self.signature):
            try:
                timestamp = float(message[len(self.signature):])
            except TypeError:
                self.log.debug('Received invalid timestamp in package from %s' % ("%s:%s" % addr))
                if self.disable_hidden:
                    self.transport.sendto('{0}#ERROR#{1}'.format(self.signature, 'Invalid timestamp'), addr)
                return

            if datetime.datetime.fromtimestamp(timestamp) < (datetime.datetime.now() - datetime.timedelta(seconds=20)):
                if self.disable_hidden:
                    self.transport.sendto('{0}#ERROR#{1}'.format(self.signature, 'Timestamp is too old'), addr)
                self.log.debug('Received outdated package from %s' % ("%s:%s" % addr))
                return

            self.log.debug('Received %r from %s' % (message, "%s:%s" % addr))
            self.transport.sendto('{0}#OK#{1}'.format(self.signature, self.answer), addr)
        else:
            if self.disable_hidden:
                self.transport.sendto('{0}#ERROR#{1}'.format(self.signature,
                                                             'Invalid packet signature').encode(), addr)
            self.log.debug('Received bad magic or password from %s:%s' % addr)
