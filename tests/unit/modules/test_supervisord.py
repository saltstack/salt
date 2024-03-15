"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.modules.supervisord as supervisord
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SupervisordTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.supervisord
    """

    def setup_loader_modules(self):
        return {supervisord: {}}

    @staticmethod
    def _m_all(stdout=True):
        """
        Return value for cmd.run_all.
        """
        return MagicMock(return_value={"retcode": 0, "stdout": stdout})

    @staticmethod
    def _m_bin():
        """
        Return value for cmd.which_bin.
        """
        return MagicMock(return_value="/tmp/bin_env")

    # 'start' function tests: 1

    def test_start(self):
        """
        Tests if it start the named service.
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.start())

    # 'restart' function tests: 1

    def test_restart(self):
        """
        Tests if it restart the named service.
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.restart())

    # 'stop' function tests: 1

    def test_stop(self):
        """
        Tests if it stop the named service.
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.stop())

    # 'add' function tests: 1

    def test_add(self):
        """
        Tests if it activates any updates in config for process/group.
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.add("salt"))

    # 'remove' function tests: 1

    def test_remove(self):
        """
        Tests if it removes process/group from active config
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.remove("salt"))

    # 'reread' function tests: 1

    def test_reread(self):
        """
        Tests if it reload the daemon's configuration files
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.reread())

    # 'update' function tests: 1

    def test_update(self):
        """
        Tests if it reload config and add/remove as necessary
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.update())

    # 'status' function tests: 1

    def test_status(self):
        """
        Tests if it list programs and its state
        """
        with patch.dict(
            supervisord.__salt__,
            {
                "cmd.run_all": self._m_all("salt running"),
                "cmd.which_bin": self._m_bin(),
            },
        ):
            self.assertDictEqual(
                supervisord.status(), {"salt": {"state": "running", "reason": ""}}
            )

    # 'status_raw' function tests: 1

    def test_status_raw(self):
        """
        Tests if it display the raw output of status
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.status_raw())

    # 'custom' function tests: 1

    def test_custom(self):
        """
        Tests if it run any custom supervisord command
        """
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(supervisord.custom("mstop '*gunicorn*'"))

    # 'options' function tests: 1

    def test_options(self):
        """
        Tests if it read the config file and return the config options
        for a given process
        """

        class MockConfig:
            """
            Mock Config class
            """

            flag = None

            def __init__(self):
                self.name = None

            def sections(self):
                """
                Mock sections methos
                """
                if self.flag == 1:
                    return []
                return ["program:salt"]

            def items(self, name):
                """
                Mock sections methos
                """
                self.name = name
                return [("salt", "True")]

        with patch.object(
            supervisord, "_read_config", MagicMock(return_value=MockConfig())
        ):
            MockConfig.flag = 1
            self.assertRaises(CommandExecutionError, supervisord.options, "salt")

            MockConfig.flag = 0
            self.assertDictEqual(supervisord.options("salt"), {"salt": True})

    # 'status_bool' function tests: 4

    def test_status_bool_name_correct(self):
        """
        Tests if it returns bool results for process status check
        """

        return_str = (
            "salt-minion                     RUNNING   pid 25563, uptime 4 days,"
            " 12:39:42"
        )
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(return_str), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(
                supervisord.status_bool(name="salt-minion", expected_state=None)
            )

    def test_status_bool_name_wrong(self):
        """
        Tests if it returns bool results for process status check
        """

        return_str = (
            "salt-master                     RUNNING   pid 25563, uptime 4 days,"
            " 12:39:42"
        )
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(return_str), "cmd.which_bin": self._m_bin()},
        ):
            self.assertFalse(
                supervisord.status_bool(name="salt-minion", expected_state=None)
            )

    def test_status_bool_expected_state_running_success(self):
        """
        Tests if it returns bool results for process status check
        """

        return_str = (
            "salt-minion                     RUNNING   pid 25563, uptime 4 days,"
            " 12:39:42"
        )
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(return_str), "cmd.which_bin": self._m_bin()},
        ):
            self.assertTrue(
                supervisord.status_bool(name="salt-minion", expected_state="RUNNING")
            )

    def test_status_bool_expected_state_running_fail(self):
        """
        Tests if it returns bool results for process status check
        """

        return_str = (
            "salt-minion                     STOPPED   pid 25563, uptime 4 days,"
            " 12:39:42"
        )
        with patch.dict(
            supervisord.__salt__,
            {"cmd.run_all": self._m_all(return_str), "cmd.which_bin": self._m_bin()},
        ):
            self.assertFalse(
                supervisord.status_bool(name="salt-minion", expected_state="RUNNING")
            )
