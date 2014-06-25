# encoding: utf-8
'''
The main entry point for salt-api
'''
# Import python libs
import logging
import multiprocessing
import signal

# Import salt-api libs
import salt.loader

logger = logging.getLogger(__name__)


class NetapiClient(object):
    '''
    Start each netapi module that is configured to run
    '''
    def __init__(self, opts):
        self.opts = opts
        self.processes = []

    def run(self):
        '''
        Load and start all available api modules
        '''
        netapi = salt.loader.netapi(self.opts)
        for fun in netapi:
            if fun.endswith('.start'):
                logger.info("Starting '{0}' api module".format(fun))
                p = multiprocessing.Process(target=netapi[fun])
                p.start()
                self.processes.append(p)

        # make sure to kill the subprocesses if the parent is killed
        signal.signal(signal.SIGTERM, self.kill_children)

    def kill_children(self, *args):
        '''
        Kill all of the children
        '''
        for p in self.processes:
            p.terminate()
            p.join()
