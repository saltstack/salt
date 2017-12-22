# encoding: utf-8
'''
The main entry point for salt-api
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import signal
import logging

# Import salt-api libs
import salt.loader
import salt.utils.process

log = logging.getLogger(__name__)


class NetapiClient(object):
    '''
    Start each netapi module that is configured to run
    '''
    def __init__(self, opts):
        self.opts = opts
        self.process_manager = salt.utils.process.ProcessManager(name='NetAPIProcessManager')
        self.netapi = salt.loader.netapi(self.opts)

    def run(self):
        '''
        Load and start all available api modules
        '''
        if not len(self.netapi):
            log.error("Did not find any netapi configurations, nothing to start")

        for fun in self.netapi:
            if fun.endswith('.start'):
                log.info('Starting %s netapi module', fun)
                self.process_manager.add_process(self.netapi[fun])

        # Install the SIGINT/SIGTERM handlers if not done so far
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGINT, self._handle_signals)

        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGTERM, self._handle_signals)

        self.process_manager.run()

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        # escalate the signals to the process manager
        self.process_manager.stop_restarting()
        self.process_manager.send_signal_to_processes(signum)
        # kill any remaining processes
        self.process_manager.kill_children()
