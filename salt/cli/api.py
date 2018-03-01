# -*- coding: utf-8 -*-
'''
    salt.cli.api
    ~~~~~~~~~~~~~

    Salt's api cli parser.

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging

# Import Salt libs
import salt.client.netapi
import salt.utils.parsers as parsers
from salt.utils.verify import check_user, verify_files, verify_log

log = logging.getLogger(__name__)


class SaltAPI(parsers.SaltAPIParser):
    '''
    The cli parser object used to fire up the salt api system.
    '''

    def prepare(self):
        '''
        Run the preparation sequence required to start a salt-api daemon.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        super(SaltAPI, self).prepare()

        try:
            if self.config['verify_env']:
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith(('tcp://',
                                                                   'udp://',
                                                                   'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)
        except OSError as err:
            log.exception('Failed to prepare salt environment')
            self.shutdown(err.errno)

        self.setup_logfile_logger()
        verify_log(self.config)
        log.info('Setting up the Salt API')
        self.api = salt.client.netapi.NetapiClient(self.config)
        self.daemonize_if_required()
        self.set_pidfile()

    def start(self):
        '''
        Start the actual master.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        '''
        super(SaltAPI, self).start()
        if check_user(self.config['user']):
            log.info('The salt-api is starting up')
            self.api.run()

    def shutdown(self, exitcode=0, exitmsg=None):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''
        log.info('The salt-api is shutting down..')
        msg = 'The salt-api is shutdown. '
        if exitmsg is not None:
            exitmsg = msg + exitmsg
        else:
            exitmsg = msg.strip()
        super(SaltAPI, self).shutdown(exitcode, exitmsg)

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        # escalate signal to the process manager processes
        self.api.process_manager.stop_restarting()
        self.api.process_manager.send_signal_to_processes(signum)
        # kill any remaining processes
        self.api.process_manager.kill_children()
        super(SaltAPI, self)._handle_signals(signum, sigframe)
