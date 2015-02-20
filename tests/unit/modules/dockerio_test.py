# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

from salt.modules import dockerio

HAS_DOCKER = dockerio.__virtual__()


@skipIf(not HAS_DOCKER, 'The docker execution module must be available to run the DockerIO test case')
class DockerIoTestCase(TestCase):
    def test__sizeof_fmt(self):
        self.assertEqual('0.0 bytes', dockerio._sizeof_fmt(0))
        self.assertEqual('1.0 KB', dockerio._sizeof_fmt(1024))
        self.assertEqual('1.0 MB', dockerio._sizeof_fmt(1024**2))
        self.assertEqual('1.0 GB', dockerio._sizeof_fmt(1024**3))
        self.assertEqual('1.0 TB', dockerio._sizeof_fmt(1024**4))
        self.assertEqual('1.0 PB', dockerio._sizeof_fmt(1024**5))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerIoTestCase, needs_daemon=False)
