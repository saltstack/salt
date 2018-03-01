# -*- coding: utf-8 -*-
'''
This module contains routines shared by the virt system.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import time
import logging

# Import salt libs
import salt.utils.files


log = logging.getLogger(__name__)


class VirtKey(object):
    '''
    Used to manage key signing requests.
    '''
    def __init__(self, hyper, id_, opts):
        self.opts = opts
        self.hyper = hyper
        self.id = id_
        path = os.path.join(self.opts['pki_dir'], 'virtkeys', hyper)
        if not os.path.isdir(path):
            os.makedirs(path)
        self.path = os.path.join(path, id_)

    def accept(self, pub):
        '''
        Accept the provided key
        '''
        try:
            with salt.utils.files.fopen(self.path, 'r') as fp_:
                expiry = int(fp_.read())
        except (OSError, IOError):
            log.error(
                'Request to sign key for minion \'%s\' on hyper \'%s\' '
                'denied: no authorization', self.id, self.hyper
            )
            return False
        except ValueError:
            log.error('Invalid expiry data in %s', self.path)
            return False

        # Limit acceptance window to 10 minutes
        # TODO: Move this value to the master config file
        if (time.time() - expiry) > 600:
            log.warning(
                'Request to sign key for minion "%s" on hyper "%s" denied: '
                'authorization expired', self.id, self.hyper
            )
            return False

        pubfn = os.path.join(self.opts['pki_dir'],
                'minions',
                self.id)
        with salt.utils.files.fopen(pubfn, 'w+') as fp_:
            fp_.write(pub)
        self.void()
        return True

    def authorize(self):
        '''
        Prepare the master to expect a signing request
        '''
        with salt.utils.files.fopen(self.path, 'w+') as fp_:
            fp_.write(str(int(time.time())))  # future lint: disable=blacklisted-function
        return True

    def void(self):
        '''
        Invalidate any existing authorization
        '''
        try:
            os.unlink(self.path)
            return True
        except OSError:
            return False
