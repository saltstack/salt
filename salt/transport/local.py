# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Libs
import salt.utils.files
from salt.transport.client import ReqChannel

log = logging.getLogger(__name__)


class LocalChannel(ReqChannel):
    """
    Local channel for testing purposes
    """

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self.tries = 0

    def close(self):
        """
        Close the local channel.

        Currently a NOOP
        """

    def send(self, load, tries=3, timeout=60, raw=False):

        if self.tries == 0:
            log.debug("LocalChannel load: %s", load)
            # data = json.loads(load)
            # {'path': 'apt-cacher-ng/map.jinja', 'saltenv': 'base', 'cmd': '_serve_file', 'loc': 0}
            # f = open(data['path'])
            with salt.utils.files.fopen(load["path"]) as f:
                ret = {
                    "data": "".join(f.readlines()),
                    "dest": load["path"],
                }
                print("returning", ret)
        else:
            # end of buffer
            ret = {
                "data": None,
                "dest": None,
            }
        self.tries = self.tries + 1
        return ret

    def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, tries=3, timeout=60
    ):
        super(LocalChannel, self).crypted_transfer_decode_dictentry(
            load, dictkey=dictkey, tries=tries, timeout=timeout
        )
