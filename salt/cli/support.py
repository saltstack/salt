# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals
import sys
sys.modules['pkg_resources'] = None
import salt.utils.parsers
import salt.utils.verify
import salt.cli.caller
import copy
import yaml
import json

DEFAULT_SCENARIO = '''
grains.yml:
  - info: System grains
  - actions:
    - grains.items:

packages.yml:
  - info: Installed packages
  - actions:
    - pkg.list_pkgs:

repositories.yml:
  - info: Available repositories
  - actions:
    - pkg.list_repos:

upgrades.yml:
  - info: Possible upgrades
  - actions:
    - pkg.list_upgrades:
'''


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

        self.collector = SupportDataCollector('master')
        self.collector.open()
        self.collect_master_data()
        self.collect_targets_data()
        self.collector.close()
