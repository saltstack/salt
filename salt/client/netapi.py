# encoding: utf-8
'''
The main entry point for salt-api
'''
# Import python libs
import logging
import multiprocessing
import signal
import os

# Import salt-api libs
import salt.loader

logger = logging.getLogger(__name__)


class NetapiClient(object):
    '''
    Start each netapi module that is configured to run
    '''
    def __init__(self, opts):
        self.opts = opts
        # pid -> {fun: foo, Process: object}
        self.pid_map = {}
        self.netapi = salt.loader.netapi(self.opts)

    def add_process(self, fun):
        '''
        Start a netapi child process of "fun"
        '''
        p = multiprocessing.Process(target=self.netapi[fun])
        p.start()
        logger.info("Started '{0}' api module with pid {1}".format(fun, p.pid))
        self.pid_map[p.pid] = {'fun': fun,
                               'Process': p}

    def run(self):
        '''
        Load and start all available api modules
        '''
        for fun in self.netapi:
            if fun.endswith('.start'):
                self.add_process(fun)

        # make sure to kill the subprocesses if the parent is killed
        signal.signal(signal.SIGTERM, self.kill_children)

        while True:
            pid, exit_status = os.wait()
            if pid not in self.pid_map:
                logger.info(('Process of pid {0} died, not a known netapi'
                             ' process, will not restart').format(pid))
                continue
            logger.info(('Process {0} ({1}) died with exit status {2},'
                         ' restarting...').format(self.pid_map[pid]['fun'],
                                                  pid,
                                                  exit_status))
            self.pid_map[pid]['Process'].join(1)
            self.add_process(self.pid_map[pid]['fun'])
            del self.pid_map[pid]

    def kill_children(self, *args):
        '''
        Kill all of the children
        '''
        for pid, p_map in self.pid_map.items():
            p_map['Process'].terminate()
            p_map['Process'].join()
            del self.pid_map[pid]
