# -*- coding: utf-8 -*-

# Import python
from __future__ import absolute_import, print_function, unicode_literals

import os
import subprocess
import time

# Import salt libs
import salt.utils.path

# Import 3rd-party libs
from salt.ext import six
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.case import ModuleCase

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@skipIf(six.PY3, "supervisor does not work under python 3")
@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
@skipIf(salt.utils.path.which("supervisorctl") is None, "supervisord not installed")
class SupervisordModuleTest(ModuleCase):
    """
    Validates the supervisorctl functions.
    """

    def setUp(self):
        super(SupervisordModuleTest, self).setUp()

        self.venv_test_dir = os.path.join(RUNTIME_VARS.TMP, "supervisortests")
        self.venv_dir = os.path.join(self.venv_test_dir, "venv")
        self.supervisor_sock = os.path.join(self.venv_dir, "supervisor.sock")

        if not os.path.exists(self.venv_dir):
            os.makedirs(self.venv_test_dir)
            self.run_function("virtualenv.create", [self.venv_dir])
            self.run_function(
                "pip.install", [], pkgs="supervisor", bin_env=self.venv_dir
            )

        self.supervisord = os.path.join(self.venv_dir, "bin", "supervisord")
        if not os.path.exists(self.supervisord):
            self.skipTest("Failed to install supervisor in test virtualenv")
        self.supervisor_conf = os.path.join(self.venv_dir, "supervisor.conf")

    def start_supervisord(self, autostart=True):
        self.run_state(
            "file.managed",
            name=self.supervisor_conf,
            source="salt://supervisor.conf",
            template="jinja",
            context={
                "supervisor_sock": self.supervisor_sock,
                "virtual_env": self.venv_dir,
                "autostart": autostart,
            },
        )
        if not os.path.exists(self.supervisor_conf):
            self.skipTest("failed to create supervisor config file")
        self.supervisor_proc = subprocess.Popen(
            [self.supervisord, "-c", self.supervisor_conf]
        )
        if self.supervisor_proc.poll() is not None:
            self.skipTest("failed to start supervisord")
        timeout = 10
        while not os.path.exists(self.supervisor_sock):
            if timeout == 0:
                self.skipTest(
                    "supervisor socket not found - failed to start supervisord"
                )
                break
            else:
                time.sleep(1)
                timeout -= 1

    def tearDown(self):
        if hasattr(self, "supervisor_proc") and self.supervisor_proc.poll() is not None:
            self.run_function(
                "supervisord.custom",
                ["shutdown"],
                conf_file=self.supervisor_conf,
                bin_env=self.venv_dir,
            )
            self.supervisor_proc.wait()
        del self.venv_dir
        del self.venv_test_dir
        del self.supervisor_sock
        del self.supervisord
        del self.supervisor_conf

    def test_start_all(self):
        """
        Start all services when they are not running.
        """
        self.start_supervisord(autostart=False)
        ret = self.run_function(
            "supervisord.start",
            [],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertIn("sleep_service: started", ret)
        self.assertIn("sleep_service2: started", ret)

    def test_start_all_already_running(self):
        """
        Start all services when they are running.
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.start",
            [],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(ret, "")

    def test_start_one(self):
        """
        Start a specific service that is not running.
        """
        self.start_supervisord(autostart=False)
        ret = self.run_function(
            "supervisord.start",
            ["sleep_service"],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(ret, "sleep_service: started")

    def test_start_one_already_running(self):
        """
        Try to start a specific service that is running.
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.start",
            ["sleep_service"],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(ret, "sleep_service: ERROR (already started)")

    def test_restart_all(self):
        """
        Restart all services when they are running.
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.restart",
            [],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertIn("sleep_service: stopped", ret)
        self.assertIn("sleep_service2: stopped", ret)
        self.assertIn("sleep_service: started", ret)
        self.assertIn("sleep_service2: started", ret)

    def test_restart_all_not_running(self):
        """
        Restart all services when they are not running.
        """
        self.start_supervisord(autostart=False)
        ret = self.run_function(
            "supervisord.restart",
            [],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        # These 2 services might return in different orders so test separately
        self.assertIn("sleep_service: started", ret)
        self.assertIn("sleep_service2: started", ret)

    def test_restart_one(self):
        """
        Restart a specific service that is running.
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.restart",
            ["sleep_service"],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(ret, "sleep_service: stopped\nsleep_service: started")

    def test_restart_one_not_running(self):
        """
        Restart a specific service that is not running.
        """
        self.start_supervisord(autostart=False)
        ret = self.run_function(
            "supervisord.restart",
            ["sleep_service"],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertIn("sleep_service: ERROR (not running)", ret)
        self.assertIn("sleep_service: started", ret)

    def test_stop_all(self):
        """
        Stop all services when they are running.
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.stop",
            [],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertIn("sleep_service: stopped", ret)
        self.assertIn("sleep_service2: stopped", ret)

    def test_stop_all_not_running(self):
        """
        Stop all services when they are not running.
        """
        self.start_supervisord(autostart=False)
        ret = self.run_function(
            "supervisord.stop",
            [],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(ret, "")

    def test_stop_one(self):
        """
        Stop a specific service that is running.
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.stop",
            ["sleep_service"],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(ret, "sleep_service: stopped")

    def test_stop_one_not_running(self):
        """
        Stop a specific service that is not running.
        """
        self.start_supervisord(autostart=False)
        ret = self.run_function(
            "supervisord.stop",
            ["sleep_service"],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(ret, "sleep_service: ERROR (not running)")

    def test_status_all(self):
        """
        Status for all services
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.status",
            [],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertEqual(sorted(ret), ["sleep_service", "sleep_service2"])

    def test_status_one(self):
        """
        Status for a specific service.
        """
        self.start_supervisord(autostart=True)
        ret = self.run_function(
            "supervisord.status",
            ["sleep_service"],
            conf_file=self.supervisor_conf,
            bin_env=self.venv_dir,
        )
        self.assertTrue(ret)
