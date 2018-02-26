# -*- coding: utf-8 -*-
'''
Splay function calls across targeted minions

@author: Dmitry Kuzmenko <dmitry.kuzmenko@dsr-company.com>
'''
# Import Python Libs
from __future__ import absolute_import
import time
import logging

from salt.executors import ModuleExecutorBase

log = logging.getLogger(__name__)

_DEFAULT_SPLAYTIME = 300
_DEFAULT_SIZE = 8192


def get(*args, **kwargs):
    return SplayExecutor(*args, **kwargs)


class SplayExecutor(ModuleExecutorBase):
    '''
    classdocs
    '''

    def __init__(self, opts, data, executor):
        '''
        Constructor
        '''
        super(SplayExecutor, self).__init__()
        self.splaytime = data.get('splaytime') or opts.get('splaytime', _DEFAULT_SPLAYTIME)
        if self.splaytime <= 0:
            raise ValueError('splaytime must be a positive integer')
        self.executor = executor
        self.fun_name = data.get('fun')

    def _get_hash(self, hashable, size):
        '''
        Jenkins One-At-A-Time Hash Function
        More Info: http://en.wikipedia.org/wiki/Jenkins_hash_function#one-at-a-time
        '''
        # Using bitmask to emulate rollover behavior of C unsigned 32 bit int
        bitmask = 0xffffffff
        h = 0

        for i in bytearray(hashable):
            h = (h + i) & bitmask
            h = (h + (h << 10)) & bitmask
            h = (h ^ (h >> 6)) & bitmask

        h = (h + (h << 3)) & bitmask
        h = (h ^ (h >> 11)) & bitmask
        h = (h + (h << 15)) & bitmask

        return (h & (size - 1)) & bitmask

    def _calc_splay(self, hashable, splaytime=_DEFAULT_SPLAYTIME, size=_DEFAULT_SIZE):
        hash_val = self._get_hash(hashable, size)
        return int(splaytime * hash_val / float(size))

    def execute(self):
        '''
        Splay a salt function call execution time across minions over
        a number of seconds (default: 600)

        .. note::
            You *probably* want to use --async here and look up the job results later.
            If you're dead set on getting the output from the CLI command, then make
            sure to set the timeout (with the -t flag) to something greater than the
            splaytime (max splaytime + time to execute job).
            Otherwise, it's very likely that the cli will time out before the job returns.

        CLI Example:

        .. code-block:: bash

            # With default splaytime
            salt --async '*' splay.splay pkg.install cowsay version=3.03-8.el6

        .. code-block:: bash

            # With specified splaytime (5 minutes) and timeout with 10 second buffer
            salt -t 310 '*' splay.splay 300 pkg.version cowsay
        '''
        my_delay = self._calc_splay(__grains__['id'], splaytime=self.splaytime)
        log.debug("Splay is sleeping {0} secs on {1}".format(my_delay, self.fun_name))
        time.sleep(my_delay)
        return self.executor.execute()
