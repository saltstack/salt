# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
from time import sleep
import logging

# Import Salt libs
from salt.ext.six.moves import range

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.helpers import generate_random_name

log = logging.getLogger(__name__)
TIMEOUT = 500


class CloudTest(ShellCase):
    @property
    def INSTANCE_NAME(self):
        if not hasattr(self, '_instance_name'):
            # Create the cloud instance name to be used throughout the tests
            self._instance_name = generate_random_name('cloud-test-').lower()
        return self._instance_name

    def _instance_exists(self):
        # salt-cloud -a show_instance myinstance
        return '        {0}:'.format(self.INSTANCE_NAME) in self.run_cloud('--query')

    def tearDown(self):
        '''
        Clean up after tests, share this between all the cloud tests
        '''
        for _ in range(4):
            if self._instance_exists():
                delete = self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME), timeout=TIMEOUT)
                # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
                delete_str = ''.join(delete)
                self.assertIn(self.INSTANCE_NAME, delete_str)

                if 'shutting-down' in ''.join(delete):
                    log.debug('Instance "{}" was deleted properly'.format(self.INSTANCE_NAME))
                    break
                else:
                    log.warning('Instance "{}" was not deleted'.format(self.INSTANCE_NAME))
                    sleep(10)
        self.assertEqual(self._instance_exists(), False)
