# -*- coding: utf-8 -*-

'''
Tests for the Git state
'''

# Import python libs
import os
import shutil
import socket

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class GitTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
    '''
    Validate the git state
    '''

    def setUp(self):
        super(GitTest, self).setUp()
        self.__domain = 'github.com'
        try:
            if hasattr(socket, 'setdefaulttimeout'):
                # 10 second dns timeout
                socket.setdefaulttimeout(10)
            socket.gethostbyname(self.__domain)
        except socket.error:
            msg = 'error resolving {0}, possible network issue?'
            self.skipTest(msg.format(self.__domain))

    def test_latest(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-bootstrap.git'.format(self.__domain),
                rev='develop',
                target=name,
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_failure(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://youSpelledGithubWrong.com/saltstack/salt.git',
                rev='develop',
                target=name,
                submodules=True
            )
            self.assertSaltFalseReturn(ret)
            self.assertFalse(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_empty_dir(self):
        '''
        git.latest
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if not os.path.isdir(name):
            os.mkdir(name)
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-bootstrap.git'.format(self.__domain),
                rev='develop',
                target=name,
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_latest_unless_no_cwd_issue_6800(self):
        '''
        cwd=target was being passed to _run_check which blew up if
        target dir did not already exist.
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if os.path.isdir(name):
            shutil.rmtree(name)
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt-bootstrap.git'.format(self.__domain),
                rev='develop',
                target=name,
                unless='test -e {0}'.format(name),
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_numeric_rev(self):
        '''
        git.latest with numeric revision
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.latest',
                name='https://{0}/saltstack/salt.git'.format(self.__domain),
                rev=0.11,
                target=name,
                submodules=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isdir(os.path.join(name, '.git')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_present(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        try:
            ret = self.run_state(
                'git.present',
                name=name,
                bare=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(os.path.join(name, 'HEAD')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_present_failure(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if not os.path.isdir(name):
            os.mkdir(name)
        try:
            fname = os.path.join(name, 'stoptheprocess')
            with file(fname, 'a'):
                pass
            ret = self.run_state(
                'git.present',
                name=name,
                bare=True
            )
            self.assertSaltFalseReturn(ret)
            self.assertFalse(os.path.isfile(os.path.join(name, 'HEAD')))
        finally:
            shutil.rmtree(name, ignore_errors=True)

    def test_present_empty_dir(self):
        '''
        git.present
        '''
        name = os.path.join(integration.TMP, 'salt_repo')
        if not os.path.isdir(name):
            os.mkdir(name)
        try:
            ret = self.run_state(
                'git.present',
                name=name,
                bare=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(os.path.join(name, 'HEAD')))
        finally:
            shutil.rmtree(name, ignore_errors=True)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTest)
