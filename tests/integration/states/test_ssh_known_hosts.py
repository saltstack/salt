# -*- coding: utf-8 -*-
'''
Test the ssh_known_hosts states
'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function

import os
import shutil
import sys

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import skip_if_binaries_missing

# Import 3rd-party libs
from salt.ext import six

KNOWN_HOSTS = os.path.join(RUNTIME_VARS.TMP, 'known_hosts')
GITHUB_FINGERPRINT = '9d:38:5b:83:a9:17:52:92:56:1a:5e:c4:d4:81:8e:0a:ca:51:a2:64:f1:74:20:11:2e:f8:8a:c3:a1:39:49:8f'
GITHUB_IP = '192.30.253.113'


@skip_if_binaries_missing(['ssh', 'ssh-keygen'], check_all=True)
class SSHKnownHostsStateTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the ssh state
    '''
    def tearDown(self):
        if os.path.isfile(KNOWN_HOSTS):
            os.remove(KNOWN_HOSTS)
        super(SSHKnownHostsStateTest, self).tearDown()

    def test_present(self):
        '''
        ssh_known_hosts.present
        '''
        kwargs = {
            'name': 'github.com',
            'user': 'root',
            'fingerprint': GITHUB_FINGERPRINT,
            'config': KNOWN_HOSTS
        }
        # test first
        ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        self.assertSaltNoneReturn(ret)

        # save once, new key appears
        ret = self.run_state('ssh_known_hosts.present', **kwargs)
        try:
            self.assertSaltTrueReturn(ret)
        except AssertionError as err:
            try:
                self.assertInSaltComment(
                    'Unable to receive remote host key', ret
                )
                self.skipTest('Unable to receive remote host key')
            except AssertionError:
                six.reraise(*sys.exc_info())

        self.assertSaltStateChangesEqual(
            ret, GITHUB_FINGERPRINT, keys=('new', 0, 'fingerprint')
        )

        # save twice, no changes
        self.run_state('ssh_known_hosts.present', **kwargs)

        # test again, nothing is about to be changed
        ret = self.run_state('ssh_known_hosts.present', test=True, **kwargs)
        self.assertSaltTrueReturn(ret)

        # then add a record for IP address
        ret = self.run_state('ssh_known_hosts.present',  # pylint: disable=repeated-keyword
                             **dict(kwargs, name=GITHUB_IP))
        try:
            self.assertSaltStateChangesEqual(
                ret, GITHUB_FINGERPRINT, keys=('new', 0, 'fingerprint')
            )
        except AssertionError as err:
            try:
                self.assertInSaltComment(
                        'Unable to receive remote host key', ret
                        )
                self.skipTest('Unable to receive remote host key')
            except AssertionError:
                six.reraise(*sys.exc_info())

        # record for every host must be available
        ret = self.run_function(
            'ssh.get_known_host_entries', ['root', 'github.com'], config=KNOWN_HOSTS
        )[0]
        try:
            self.assertNotIn(ret, ('', None))
        except AssertionError:
            raise AssertionError(
                'Salt return \'{0}\' is in (\'\', None).'.format(ret)
            )
        ret = self.run_function(
            'ssh.get_known_host_entries', ['root', GITHUB_IP], config=KNOWN_HOSTS
        )[0]
        try:
            self.assertNotIn(ret, ('', None, {}))
        except AssertionError:
            raise AssertionError(
                'Salt return \'{0}\' is in (\'\', None,'.format(ret) + ' {})'
            )

    def test_present_fail(self):
        # save something wrong
        ret = self.run_state(
            'ssh_known_hosts.present',
            name='github.com',
            user='root',
            fingerprint='aa:bb:cc:dd',
            config=KNOWN_HOSTS
        )
        self.assertSaltFalseReturn(ret)

    def test_absent(self):
        '''
        ssh_known_hosts.absent
        '''
        known_hosts = os.path.join(RUNTIME_VARS.FILES, 'ssh', 'known_hosts')
        shutil.copyfile(known_hosts, KNOWN_HOSTS)
        if not os.path.isfile(KNOWN_HOSTS):
            self.skipTest(
                'Unable to copy {0} to {1}'.format(
                    known_hosts, KNOWN_HOSTS
                )
            )

        kwargs = {'name': 'github.com', 'user': 'root', 'config': KNOWN_HOSTS}
        # test first
        ret = self.run_state('ssh_known_hosts.absent', test=True, **kwargs)
        self.assertSaltNoneReturn(ret)

        # remove once, the key is gone
        ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        self.assertSaltStateChangesEqual(
            ret, GITHUB_FINGERPRINT, keys=('old', 0, 'fingerprint')
        )

        # remove twice, nothing has changed
        ret = self.run_state('ssh_known_hosts.absent', **kwargs)
        self.assertSaltStateChangesEqual(ret, {})

        # test again
        ret = self.run_state('ssh_known_hosts.absent', test=True, **kwargs)
        self.assertSaltTrueReturn(ret)
