# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals
import sys
sys.modules['pkg_resources'] = None
import salt.utils.parsers
import salt.utils.verify
import salt.cli.caller
import copy


class SaltSupport(salt.utils.parsers.SaltSupportOptionParser):
    '''
    Class to run Salt Support subsystem.
    '''
    def _local_call(self):
        '''
        Execute local call
        '''
        conf = copy.deepcopy(self.config)

        conf['file_client'] = 'local'
        conf['fun'] = 'grains.items'
        conf['arg'] = []
        conf['cache_jobs'] = False
        conf['print_metadata'] = False

        caller = salt.cli.caller.Caller.factory(conf)

        return caller.call()

    def collect_master_data(self):
        '''
        Collects master system data.
        :return:
        '''

    def collect_targets_data(self):
        '''
        Collects minion targets data
        :return:
        '''

    def run(self):
        self.parse_args()
        if self.config['log_level'] not in ('quiet', ):
            self.setup_logfile_logger()
            salt.utils.verify.verify_log(self.config)

        self._local_call()
        sys.exit(127)
