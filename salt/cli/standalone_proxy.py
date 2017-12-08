# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function
import sys
sys.modules['pkg_resources'] = None
import time
import multiprocessing

# Import Salt libs
# We import log ASAP because we NEED to make sure that any logger instance salt
# instantiates is using salt.log.setup.SaltLoggingClass
import salt.log.setup
import salt.utils.parsers
from salt.scripts import standalone_proxy_process
from salt.cli.daemons import ProxyMinion
from salt.utils.verify import verify_log

# Let's instantiate log using salt.log.setup.logging.getLogger() so pylint
# leaves us alone and stops complaining about an un-used import
log = salt.log.setup.logging.getLogger(__name__)


class StandaloneProxyMinionCMD(salt.utils.parsers.SaltCMDOptionParser):
    '''
    The execution of a salt-proxy-standalone command happens here
    '''

    def run(self):
        '''
        Execute the salt command line
        '''
        import salt.client
        self.parse_args()

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)
        try:
            # We don't need to bail on config file permission errors
            # if the CLI process is run with the -a flag
            skip_perm_errors = self.options.eauth != ''

            self.local_client = salt.client.get_local_client(
                self.get_config_file_path(),
                skip_perm_errors=skip_perm_errors,
                auto_reconnect=True)
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return
        # Determine what minions should execute against,
        # Eventually using cached data.
        preview_target = self.local_client.gather_minions(self.config['tgt'],
                                                          self.selected_target_option or 'glob')
        log.error(preview_target)
        log.debug('Starting a process for each of the targeted:')
        for targeted_minion in preview_target:
            log.debug('Starting process for %s', targeted_minion)
            process = multiprocessing.Process(target=standalone_proxy_process,
                                              args=(targeted_minion,))
            process.start()
