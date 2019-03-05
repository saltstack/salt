# -*- coding: utf-8 -*-
'''
Integration tests for the zookeeper states
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Libs
import salt.utils.path

try:
    import kazoo  # pylint: disable=import-error,unused-import
    HAS_KAZOO = True
except ImportError:
    HAS_KAZOO = False

log = logging.getLogger(__name__)


@destructiveTest
@skipIf(not salt.utils.path.which('dockerd'), 'Docker not installed')
@skipIf(not HAS_KAZOO, 'kazoo python library not installed')
class ZookeeperTestCase(ModuleCase, SaltReturnAssertsMixin):
    '''
    Test zookeeper states
    '''
    @classmethod
    def setUpClass(cls):
        cls.container_name = 'zookeeper_salt'

    def setUp(self):
        self.run_state('docker_image.present', name='zookeeper')
        self.run_state('docker_container.running', name=self.container_name, image='zookeeper', port_bindings='2181:2181')

    def tearDown(self):
        self.run_state('docker_container.stopped', name=self.container_name)
        self.run_state('docker_container.absent', name=self.container_name)
        self.run_state('docker_image.absent', name='docker.io/zookeeper', force=True)

    def test_zookeeper_present(self):
        ret = self.run_state(
            'zookeeper.present',
            name='/test/name',
            value='testuser',
            makepath=True,
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_state(
            'zookeeper.present',
            name='/test/name',
            value='daniel',
            acls=[
                {'username': 'daniel', 'password': 'test', 'read': True, 'admin': True, 'write': True, },
                {'username': 'testuser', 'password': 'test', 'read': True},
            ],
            profile='prod',
        )
        self.assertSaltTrueReturn(ret)

    def test_zookeeper_absent(self):
        self.run_state(
            'zookeeper.present',
            name='/test/name',
            value='testuser',
            makepath=True,
        )
        ret = self.run_state(
            'zookeeper.absent',
            name='/test/name',
        )
        self.assertSaltTrueReturn(ret)
        self.assertTrue(bool(ret['zookeeper_|-/test/name_|-/test/name_|-absent']['changes']))
        ret = self.run_state(
            'zookeeper.absent',
            name='/test/name',
        )
        self.assertFalse(bool(ret['zookeeper_|-/test/name_|-/test/name_|-absent']['changes']))

    def test_zookeeper_acls(self):
        ret = self.run_state(
            'zookeeper.acls',
            name='/test/name',
            acls=[
                {'username': 'daniel', 'password': 'test', 'read': True, 'admin': True, 'write': True, },
                {'username': 'testuser', 'password': 'test', 'read': True},
            ]
        )
        self.assertSaltFalseReturn(ret)

        ret = self.run_state(
            'zookeeper.present',
            name='/test/name',
            value='testuser',
            makepath=True,
        )

        ret = self.run_state(
            'zookeeper.acls',
            name='/test/name',
            acls=[
                {'username': 'daniel', 'password': 'test', 'read': True, 'admin': True, 'write': True, },
                {'username': 'testuser', 'password': 'test', 'read': True},
            ]
        )
        self.assertSaltTrueReturn(ret)
