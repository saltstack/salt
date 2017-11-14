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

import socket
import logging
import datetime

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

    # Default values
    DEFAULTS = {
        SIGNATURE: '__salt_master_service'
    }

    @staticmethod
    def _is_available():
        '''
        Return True if the USSDP dependencies are satisfied.
        :return:
        '''
        return bool(asyncio)

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
