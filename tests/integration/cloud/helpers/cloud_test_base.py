# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import re
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
            re_subclass = re.compile('\'\w+\.?(\w+)\'')
            subclass = re_subclass.findall(str(type(self))).pop()
            self._instance_name = generate_random_name('CLOUD-TEST-{}-'.format(subclass)).upper()
            print('Created instance for {}: {}'.format(subclass, self.instance_name))
        return self._instance_name

    def _instance_exists(self, instance_name=None):
        # salt-cloud -a show_instance myinstance
        if not instance_name:
            instance_name = self.instance_name
        query = self.run_cloud('--query')
        print('INSTANCE EXISTS? {}: {}'.format(self.instance_name, query))
        return '        {0}:'.format(self.instance_name) in query

    def _destroy_instance(self):
        log.debug('Deleting instance "{}"'.format(self.instance_name))
        delete = self.run_cloud('-d {0} --assume-yes'.format(self.instance_name), timeout=TIMEOUT)
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)
        log.debug('Deletion status: {}'.format(delete_str))

        if any([x in delete_str for x in (
            'True',
            'was successfully deleted'
        )]):
            log.debug('Instance "{}" was successfully deleted'.format(self.instance_name))
        elif any([x in delete_str for x in (
            'shutting-down',
            '.delete',
        )]):
            log.debug('Instance "{}" is cleaning up'.format(self.instance_name))
            sleep(30)
        else:
            print('Instance "{}" may not have been deleted properly'.format(self.instance_name))

        # By now it should all be over
        self.assertEqual(self._instance_exists(), False)
        log.debug('Instance "{}" no longer exists'.format(self.instance_name))

    def tearDown(self):
        '''
        Clean up after tests, If the instance still exists for any reason, delete it.
        Instances should be destroyed before the tearDown, _destroy_instance() should be called exactly
        one time in a test for each instance created.  This is a failSafe and something went wrong
        if the tearDown is where an instance is destroyed.
        '''
        instance_deleted = True
        for tries in range(12):
            if self._instance_exists():
                instance_deleted = False
                try:
                    self._destroy_instance()
                    log.debug('Instance "{}" destroyed after {} tries'.format(self.instance_name, tries))
                except AssertionError as e:
                    log.error(e)
                    sleep(30)
            else:
                break
        self.assertEqual(self._instance_exists(), False, 'Instance exists after multiple attempts to delete: {}'
                         .format(self.instance_name))
        # Complain if the instance was destroyed in this tearDown.
        # Destroying instances in the tearDown is a contingency, not the way things should work by default.
        self.assertEqual(instance_deleted, True, 'The Instance "{}" was not deleted properly at the end of the test'
                         .format(self.instance_name))
