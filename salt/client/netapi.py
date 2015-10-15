# encoding: utf-8
'''
The main entry point for salt-api
'''
from __future__ import absolute_import
# Import python libs
import logging

# Import salt-api libs
import salt.loader
import salt.utils.process

logger = logging.getLogger(__name__)


class NetapiClient(object):
    '''
    Start each netapi module that is configured to run
    '''
    def __init__(self, opts):
        self.opts = opts
        self.process_manager = salt.utils.process.ProcessManager()
        self.netapi = salt.loader.netapi(self.opts)

    def run(self):
        '''
        Load and start all available api modules
        '''
        for fun in self.netapi:
            if fun.endswith('.start'):
                logger.info('Starting {0} netapi module'.format(fun))
                self.process_manager.add_process(self.netapi[fun])

        self.process_manager.run()
