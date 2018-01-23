# -*- coding: utf-8 -*-
'''
Integration tests for the docker_container states
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import functools
import random
import string
import tempfile

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase
from tests.support.paths import TMP
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Libs
import salt.utils.path

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def _random_name(prefix=''):
    ret = prefix
    for _ in range(8):
        ret += random.choice(string.ascii_lowercase)
    return ret


def with_random_name(func):
    '''
    generate a randomized name for a container
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        name = _random_name(prefix='salt_')
        return func(self, _random_name(prefix='salt_test_'), *args, **kwargs)
    return wrapper


@destructiveTest
@skipIf(not salt.utils.path.which('dockerd'), 'Docker not installed')
class DockerCallTestCase(ModuleCase, SaltReturnAssertsMixin):
    '''
    Test docker_container states
    '''
    @with_random_name
    def setUp(self, name):
        '''
        setup docker.call tests
        '''
        # Create temp dir
        self.random_name = name
        self.tmp_build_dir = tempfile.mkdtemp(dir=TMP)

        self.run_state('file.managed',
                       source='salt://docker_non_root/Dockerfile',
                       name='{0}/Dockerfile'.format(self.tmp_build_dir))
        self.run_state('docker_image.present',
                       build=self.tmp_build_dir,
                       name=self.random_name)
        self.run_state('docker_container.running',
                       name=self.random_name,
                       image=self.random_name)

    def tearDown(self):
        '''
        teardown docker.call tests
        '''
        self.run_state('file.absent',
                       name=self.tmp_build_dir)
        self.run_state('docker_container.absent',
                       name=self.random_name,
                       force=True)
        self.run_state('docker_image.absent',
                       images=[self.random_name, 'docker.io/opensuse/python:latest'],
                       force=True)

    def test_docker_call(self):
        '''
        check that docker.call works, and works with a container not running as root
        '''
        ret = self.run_function('docker.call', [self.random_name, 'test.ping'])
        self.assertTrue(ret)
