# -*- coding: utf-8 -*-

'''
Tests for the supervisord state
'''

# Import python lins
from __future__ import absolute_import
import os
import time
import subprocess

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf

# Import salt libs
import salt.utils
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES


@skipIf(salt.utils.which_bin(KNOWN_BINARY_NAMES) is None, 'virtualenv not installed')
@skipIf(salt.utils.which('supervisorctl') is None, 'supervisord not installed')
class SupervisordTest(integration.ModuleCase,
                      integration.SaltReturnAssertsMixIn):
    '''
    Validate the supervisord states.
    '''
    def setUp(self):
        super(SupervisordTest, self).setUp()

        self.venv_test_dir = os.path.join(integration.TMP, 'supervisortests')
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')
        self.supervisor_sock = os.path.join(self.venv_dir, 'supervisor.sock')

        if not os.path.exists(self.venv_dir):
            os.makedirs(self.venv_test_dir)
            self.run_function('virtualenv.create', [self.venv_dir])
            self.run_function(
                'pip.install', [], pkgs='supervisor', bin_env=self.venv_dir)

        self.supervisord = os.path.join(self.venv_dir, 'bin', 'supervisord')
        if not os.path.exists(self.supervisord):
            self.skipTest('Failed to installe supervisor in test virtualenv')

        self.supervisor_conf = os.path.join(self.venv_dir, 'supervisor.conf')

    def start_supervisord(self, autostart=True):
        self.run_state(
            'file.managed', name=self.supervisor_conf,
            source='salt://supervisor.conf', template='jinja',
            context={
                'supervisor_sock': self.supervisor_sock,
                'virtual_env': self.venv_dir,
                'autostart': autostart
            }
        )
        if not os.path.exists(self.supervisor_conf):
            self.skipTest('failed to create supervisor config file')
        self.supervisor_proc = subprocess.Popen(
            [self.supervisord, '-c', self.supervisor_conf]
        )
        if self.supervisor_proc.poll() is not None:
            self.skipTest('failed to start supervisord')
        timeout = 10
        while not os.path.exists(self.supervisor_sock):
            if timeout == 0:
                self.skipTest(
                    'supervisor socket not found - failed to start supervisord'
                )
                break
            else:
                time.sleep(1)
                timeout -= 1

    def tearDown(self):
        if hasattr(self, 'supervisor_proc') and \
                self.supervisor_proc.poll() is not None:
            self.run_function(
                'supervisord.custom', ['shutdown'],
                conf_file=self.supervisor_conf, bin_env=self.venv_dir)
            self.supervisor_proc.wait()

    def test_running_stopped(self):
        '''
        supervisord.running restart = False
        When service is stopped.
        '''
        self.start_supervisord(autostart=False)
        ret = self.run_state(
            'supervisord.running', name='sleep_service',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('sleep_service', ret, ['changes'])

    def test_running_started(self):
        '''
        supervisord.running restart = False
        When service is running.
        '''
        self.start_supervisord(autostart=True)
        ret = self.run_state(
            'supervisord.running', name='sleep_service',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)
        self.assertNotInSaltReturn('sleep_service', ret, ['changes'])

    def test_running_needsupdate(self):
        '''
        supervisord.running restart = False
        When service needs to be added.
        '''
        self.start_supervisord(autostart=False)
        self.run_function('supervisord.remove', [
            'sleep_service',
            None,
            self.supervisor_conf,
            self.venv_dir
        ])
        ret = self.run_state(
            'supervisord.running', name='sleep_service',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('sleep_service', ret, ['changes'])

    def test_running_notexists(self):
        '''
        supervisord.running restart = False
        When service doesn't exist.
        '''
        self.start_supervisord(autostart=True)
        ret = self.run_state(
            'supervisord.running', name='does_not_exist',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltFalseReturn(ret)

    def test_restart_started(self):
        '''
        supervisord.running restart = True
        When service is running.
        '''
        self.start_supervisord(autostart=True)
        ret = self.run_state(
            'supervisord.running', name='sleep_service',
            restart=True,
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('sleep_service', ret, ['changes'])

    def test_restart_stopped(self):
        '''
        supervisord.running restart = True
        When service is stopped.
        '''
        self.start_supervisord(autostart=False)
        ret = self.run_state(
            'supervisord.running', name='sleep_service',
            restart=True,
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('sleep_service', ret, ['changes'])

    def test_restart_needsupdate(self):
        '''
        supervisord.running restart = True
        When service needs to be added.
        '''
        self.start_supervisord(autostart=False)
        self.run_function('supervisord.remove', [
            'sleep_service',
            None,
            self.supervisor_conf,
            self.venv_dir
        ])
        ret = self.run_state(
            'supervisord.running', name='sleep_service',
            restart=True,
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)
        self.assertInSaltReturn('sleep_service', ret, ['changes'])

    def test_restart_notexists(self):
        '''
        supervisord.running restart = True
        When service does not exist.
        '''
        self.start_supervisord(autostart=True)
        ret = self.run_state(
            'supervisord.running', name='does_not_exist',
            restart=True,
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltFalseReturn(ret)
        self.assertNotInSaltReturn('sleep_service', ret, ['changes'])

    def test_dead_started(self):
        '''
        supervisord.dead
        When service is running.
        '''
        self.start_supervisord(autostart=True)
        ret = self.run_state(
            'supervisord.dead', name='sleep_service',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)

    def test_dead_stopped(self):
        '''
        supervisord.dead
        When service is stopped.
        '''
        self.start_supervisord(autostart=False)
        ret = self.run_state(
            'supervisord.dead', name='sleep_service',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)

    def test_dead_removed(self):
        '''
        supervisord.dead
        When service needs to be added.
        '''
        self.start_supervisord(autostart=False)
        self.run_function('supervisord.remove', [
            'sleep_service',
            None,
            self.supervisor_conf,
            self.venv_dir
        ])
        ret = self.run_state(
            'supervisord.dead', name='sleep_service',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)

    def test_dead_notexists(self):
        '''
        supervisord.dead
        When service does not exist.
        '''
        self.start_supervisord(autostart=True)
        ret = self.run_state(
            'supervisord.dead', name='does_not_exist',
            bin_env=self.venv_dir, conf_file=self.supervisor_conf
        )
        self.assertSaltTrueReturn(ret)
