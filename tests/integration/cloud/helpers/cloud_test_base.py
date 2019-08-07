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
        query = self.run_cloud('--query')
        log.debug('INSTANCE EXISTS? {}: {}'.format(self.INSTANCE_NAME, query))
        return '        {0}:'.format(self.INSTANCE_NAME) in query

    def _destroy_instance(self):
        log.debug('Deleting instance "{}"'.format(self.INSTANCE_NAME))
        delete = self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME), timeout=TIMEOUT)
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)
        log.debug('Deletion status: {}'.format(delete_str))

        if any([x in delete_str for x in (
            'True',
            'was successfully deleted'
        )]):
            log.debug('Instance "{}" was successfully deleted'.format(self.INSTANCE_NAME))
        elif any([x in delete_str for x in (
            'shutting-down',
            '.delete',
        )]):
            log.debug('Instance "{}" is cleaning up'.format(self.INSTANCE_NAME))
            sleep(60)
        else:
            log.error('Instance "{}" may not have been deleted properly'.format(self.INSTANCE_NAME))

        # By now it should all be over
        self.assertEqual(self._instance_exists(), False)
        log.debug('Instance "{}" no longer exists'.format(self.INSTANCE_NAME))

    def tearDown(self):
        '''
        Clean up after tests, If the instance still exists for any reason, delete it
        '''
        if self._instance_exists():
            log.warning('Destroying instance from CloudTest tearDown conditional.  This shouldn\'t happen.  '
                        'Make sure the instance is explicitly destroyed at the end of the test case')
            self._destroy_instance()
