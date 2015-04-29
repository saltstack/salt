# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.transport.client import ReqChannel

log = logging.getLogger(__name__)


class LocalChannel(ReqChannel):
    '''
    Local channel for testing purposes
    '''
    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self.tries = 0

    def send(self, load, tries=3, timeout=60):

        if self.tries == 0:
            log.debug('LocalChannel load: {0}').format(load)
            #data = json.loads(load)
            #{'path': 'apt-cacher-ng/map.jinja', 'saltenv': 'base', 'cmd': '_serve_file', 'loc': 0}
            #f = open(data['path'])
            f = open(load['path'])
            ret = {
                'data': ''.join(f.readlines()),
                'dest': load['path'],
            }
            print ('returning', ret)
        else:
            # end of buffer
            ret = {
                'data': None,
                'dest': None,
            }
        self.tries = self.tries + 1
        return ret

    def crypted_transfer_decode_dictentry(self, load, dictkey=None, tries=3, timeout=60):
        super(LocalChannel, self).crypted_transfer_decode_dictentry()
