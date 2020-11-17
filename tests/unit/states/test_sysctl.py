"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.states.sysctl as sysctl
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SysctlTestCase(TestCase):
    """
    Test cases for salt.states.sysctl
    """


class SysctlPresentTestCase(SysctlTestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.sysctl.present
    """

    def setup_loader_modules(self):
        return {sysctl: {}}

    def test_empty_config_file_and_value_not_found(self):
        """
        Test sysctl.present for an unknown sysctl, not present in config file
        """
        name = "some.unknown.oid"
        value = "1"
        comment = "Sysctl option {} would be changed to {}" "".format(name, value)

        ret = {"name": name, "result": None, "changes": {}, "comment": comment}

        with patch.dict(sysctl.__opts__, {"test": True}):
            mock = MagicMock(return_value={})
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock}):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_inaccessible_config_file(self):
        """
        Test sysctl.present with a config file that cannot be opened
        """
        name = "some.unknown.oid"
        value = "1"
        config = "/etc/sysctl.conf"
        comment = (
            "Sysctl option {} might be changed, we failed to check "
            "config file at {}. The file is either unreadable, or "
            "missing.".format(name, config)
        )
        ret = {"name": name, "result": None, "changes": {}, "comment": comment}

        with patch.dict(sysctl.__opts__, {"test": True}):
            mock = MagicMock(return_value=None)
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock}):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_to_be_changed_not_configured(self):
        """
        Test sysctl.present for a sysctl that isn't in the config file and must
        be changed.
        """
        name = "vfs.usermount"
        value = "1"
        comment = "Sysctl option {} set to be changed to {}".format(name, value)
        ret = {"name": name, "result": None, "changes": {}, "comment": comment}

        def mock_current(config_file=None):
            """
            Mock return value for __salt__.
            """
            if config_file is None:
                return {name: "0"}
            return [""]

        with patch.dict(sysctl.__opts__, {"test": True}):
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock_current}):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_not_to_be_changed_not_configured(self):
        """
        Test sysctl.present for a sysctl that isn't in the config file but
        already has the correct value
        """
        name = "some.unknown.oid"
        value = "1"
        comment = (
            "Sysctl value is currently set on the running system but "
            "not in a config file. Sysctl option {} set to be "
            "changed to 1 in config file.".format(name)
        )

        ret = {"name": name, "result": None, "changes": {}, "comment": comment}

        def mock_current(config_file=None):
            if config_file is None:
                return {name: "1"}
            return [""]

        with patch.dict(sysctl.__opts__, {"test": True}):
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock_current}):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_configured_but_unknown(self):
        """
        Test sysctl.present for a sysctl that is already configured but is
        not known by the system.  For example, a sysctl used by a kernel module
        that isn't loaded.
        """
        name = "vfs.usermount"
        value = "1"
        comment = (
            "Sysctl value {0} is present in configuration file but is not "
            "present in the running config. The value {0} is set to be "
            "changed to {1}".format(name, value)
        )
        ret = {"name": name, "result": None, "changes": {}, "comment": comment}

        def mock_config(config_file=None):
            if config_file is None:
                return {}
            return {name: 1}

        with patch.dict(sysctl.__opts__, {"test": True}):
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock_config}):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_no_change(self):
        """
        Test sysctl.present for an already-configured value
        """
        name = "vfs.usermount"
        value = "1"
        comment = "Sysctl value {} = {} is already set".format(name, value)
        ret = {"name": name, "result": True, "changes": {}, "comment": comment}

        def mock_both(config_file=None):
            if config_file is None:
                return {name: value}
            return {name: value}

        with patch.dict(sysctl.__opts__, {"test": True}):
            mock = MagicMock(return_value=value)
            with patch.dict(
                sysctl.__salt__, {"sysctl.show": mock_both, "sysctl.get": mock}
            ):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_change(self):
        """
        Test sysctl.present for a value whose configuration must change
        """
        name = "vfs.usermount"
        value = "1"
        comment = "Sysctl option {} would be changed to {}".format(name, value)
        ret = {"name": name, "result": None, "changes": {}, "comment": comment}

        def mock_both(config_file=None):
            if config_file is None:
                return {name: "2"}
            return {name: "2"}

        with patch.dict(sysctl.__opts__, {"test": True}):
            mock = MagicMock(return_value="2")
            with patch.dict(
                sysctl.__salt__, {"sysctl.show": mock_both, "sysctl.get": mock}
            ):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_failed_to_set(self):
        """
        Test sysctl.present when the sysctl command fails to change a value
        """
        name = "net.isr.maxthreads"
        value = "8"
        comment = "Failed to set {} to {}: ".format(name, value)
        ret = {"name": name, "result": False, "changes": {}, "comment": comment}

        with patch.dict(sysctl.__opts__, {"test": False}):
            mock = MagicMock(side_effect=CommandExecutionError)
            with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_already_set(self):
        """
        Test sysctl.present when the value is already set
        """
        name = "vfs.usermount"
        value = "1"
        comment = "Sysctl value {} = {} is already set".format(name, value)
        ret = {"name": name, "result": True, "changes": {}, "comment": comment}
        with patch.dict(sysctl.__opts__, {"test": False}):
            mock = MagicMock(return_value="Already set")
            with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
                self.assertDictEqual(sysctl.present(name, value), ret)

    def test_updated(self):
        """
        Test sysctl.present when the value is not already set
        """
        name = "vfs.usermount"
        value = "1"
        comment = "Updated sysctl value {} = {}".format(name, value)
        changes = {name: value}
        ret = {"name": name, "result": True, "changes": changes, "comment": comment}
        with patch.dict(sysctl.__opts__, {"test": False}):
            mock = MagicMock(return_value="Updated")
            with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
                self.assertDictEqual(sysctl.present(name, value), ret)
