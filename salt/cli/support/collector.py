# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals
import sys
import copy
import yaml
import json
import logging

sys.modules['pkg_resources'] = None

import salt.utils.parsers
import salt.utils.verify
import salt.cli.caller
import salt.cli.support

log = logging.getLogger(__name__)

class SupportDataCollector(object):
    '''
    Data collector. It behaves just like another outputter,
    except it grabs the data to the archive files.
    '''
    def __init__(self, name, path=None, format='gzip'):
        '''
        constructor of the data collector
        :param name:
        :param path:
        :param format:
        '''
        self.__path = path
        self.__name = name

    def open(self):
        '''
        Opens archive.
        :return:
        '''

    def close(self):
        '''
        Closes the archive.
        :return:
        '''

    def add(self, name, data):
        '''
        Adds a data set as a name.
        :return:
        '''
        print('-' * 80)
        data = json.loads(json.dumps(data))
        print(yaml.safe_dump(data.get('return', {}), default_flow_style=False, indent=4))
        print('\n\n')


class SaltSupport(salt.utils.parsers.SaltSupportOptionParser):
    '''
    Class to run Salt Support subsystem.
    '''
    def _get_caller(self, conf):
        if not getattr(self, '_caller', None):
            self._caller = salt.cli.caller.Caller.factory(conf)
        else:
            self._caller.opts = conf

        return self._caller

    def _local_call(self, call_conf):
        '''
        Execute local call
        '''
        conf = copy.deepcopy(self.config)

        conf['file_client'] = 'local'
        conf['fun'] = ''
        conf['arg'] = []
        conf['cache_jobs'] = False
        conf['print_metadata'] = False
        conf.update(call_conf)

        return self._get_caller(conf).call()

    def _get_action(self, action_meta):
        '''
        Parse action and turn into a calling point.
        :param action_meta:
        :return:
        '''
        conf = {
            'fun': action_meta.keys()[0],
            'arg': [],
        }
        action_meta = action_meta[conf['fun']]
        info = action_meta.get('info', 'Action for {}'.format(conf['fun']))
        for arg in action_meta.get('args') or []:
            if not isinstance(arg, dict):
                conf['arg'].append(arg)

        return info, conf

    def collect_master_data(self):
        '''
        Collects master system data.
        :return:
        '''
        scenario = salt.cli.support.get_scenario()
        for category_name in scenario:
            print(category_name)
            self.collector.add(category_name)
            for action in scenario[category_name]:
                info, conf = self._get_action(action)
                print('  Collecting', info.lower())
                self.collector.write(info, self._local_call(conf))

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

        self.collector = SupportDataCollector('master-info')
        self.collector.open()
        self.collect_master_data()
        self.collect_targets_data()
        self.collector.close()
