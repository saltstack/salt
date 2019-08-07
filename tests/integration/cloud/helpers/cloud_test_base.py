# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
from time import sleep

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.helpers import generate_random_name, expensiveTest
from tests.support.paths import FILES

# Import Salt Libs
from salt.ext.six import text_type

# Import Salt Libs
from salt.ext import six

log = logging.getLogger(__name__)
TIMEOUT = 500

log = logging.getLogger(__name__)


class CloudTest(ShellCase):
    @property
    def instance_name(self):
        if not hasattr(self, '_instance_name'):
            # Create the cloud instance name to be used throughout the tests
            subclass = type(self).split('.').pop()
            self._instance_name = generate_random_name('cloud-test-{}-'.format(subclass).lower())
            print('Created instance for {}: {}'.format(subclass, self.instance_name))
        return self._instance_name

    def _instance_exists(self, instance_name=None):
        # salt-cloud -a show_instance myinstance
        query = self.run_cloud('--query')
        log.debug('INSTANCE EXISTS? {}: {}'.format(self.INSTANCE_NAME, query))
        return '        {0}:'.format(self.INSTANCE_NAME) in query

    def _destroy_instance(self):
        log.debug('Deleting instance "{}"'.format(self.INSTANCE_NAME))
        delete = self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME), timeout=TIMEOUT)
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)
        log.debug('Deletion status: {}'.format(delete_str))

        print('e' * 100)
        print(delete_str)
        # TODO assert that 'shutting-down' will be in the delete_str?
        if 'shutting-down' in delete_str:
            print('Instance "{}" was deleted properly'.format(self.INSTANCE_NAME))
        else:
            print('Instance "{}" was not deleted'.format(self.INSTANCE_NAME))
        self.assertEqual(self._instance_exists(), False)
        log.debug('Instance "{}" no longer exists'.format(self.INSTANCE_NAME))

    def tearDown(self):
        '''
        Clean up after tests, If the instance still exists for any reason, delete it.
        Instances should be destroyed before the tearDown, _destroy_instance() should be called exactly
        one time in a test for each instance created.  This is a failSafe and something went wrong
        if the tearDown is where an instance is destroyed.
        '''
        if self._instance_exists():
            log.warning('Destroying instance from CloudTest tearDown conditional.  This shouldn\'t happen.  '
                        'Make sure the instance is explicitly destroyed at the end of the test case')
            self._destroy_instance()
