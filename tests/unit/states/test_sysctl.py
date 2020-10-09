"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.states.sysctl as sysctl
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SysctlTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.sysctl
    """

    def setup_loader_modules(self):
        return {sysctl: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure that the named sysctl value is set
        in memory and persisted to the named configuration file.
        """
        name = "net.ipv4.conf.all.rp_filter"
        value = "1"
        config = "/etc/sysctl.conf"

        comment = (
            "Sysctl option {} might be changed, we failed to check "
            "config file at {}. The file is either unreadable, or "
            "missing.".format(name, config)
        )

        ret = {"name": name, "result": None, "changes": {}, "comment": comment}

        comment_empty = "Sysctl option {} would be changed to {}" "".format(name, value)

        comment1 = "Sysctl option {} set to be changed to {}".format(name, value)

        comment2 = (
            "Sysctl value is currently set on the running system but "
            "not in a config file. Sysctl option {} set to be "
            "changed to 2 in config file.".format(name)
        )

        comt3 = (
            "Sysctl value {0} is present in configuration file but is not "
            "present in the running config. The value {0} is set to be "
            "changed to {1}".format(name, value)
        )

        comt4 = "Sysctl value {} = {} is already set".format(name, value)

        comt5 = "Sysctl option {} would be changed to {}".format(name, value)

        comt6 = "Failed to set {} to {}: ".format(name, value)

        comt7 = "Sysctl value {} = {} is already set".format(name, value)

        def mock_current(config_file=None):
            """
            Mock return value for __salt__.
            """
            if config_file is None:
                return {name: "2"}
            return [""]

        def mock_config(config_file=None):
            """
            Mock return value for __salt__.
            """
            if config_file is None:
                return {"salt": "2"}
            return [name]

        def mock_both(config_file=None):
            """
            Mock return value for __salt__.
            """
            if config_file is None:
                return {name: value}
            return [name]

        with patch.dict(sysctl.__opts__, {"test": True}):
            mock = MagicMock(return_value=None)
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock}):
                self.assertDictEqual(sysctl.present(name, value), ret)

            mock = MagicMock(return_value=[])
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock}):
                ret.update({"comment": comment_empty})
                self.assertDictEqual(sysctl.present(name, value), ret)

            with patch.dict(sysctl.__salt__, {"sysctl.show": mock_current}):
                ret.update({"comment": comment1})
                self.assertDictEqual(sysctl.present(name, value), ret)

                ret.update({"comment": comment2})
                self.assertDictEqual(sysctl.present(name, "2"), ret)

            with patch.dict(sysctl.__salt__, {"sysctl.show": mock_config}):
                ret.update({"comment": comt3})
                self.assertDictEqual(sysctl.present(name, value), ret)

            mock = MagicMock(return_value=value)
            with patch.dict(
                sysctl.__salt__, {"sysctl.show": mock_both, "sysctl.get": mock}
            ):
                ret.update({"comment": comt4, "result": True})
                self.assertDictEqual(sysctl.present(name, value), ret)

            mock = MagicMock(return_value=[True])
            with patch.dict(sysctl.__salt__, {"sysctl.show": mock}):
                ret.update({"comment": comt5, "result": None})
                self.assertDictEqual(sysctl.present(name, value), ret)

        with patch.dict(sysctl.__opts__, {"test": False}):
            mock = MagicMock(side_effect=CommandExecutionError)
            with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
                ret.update({"comment": comt6, "result": False})
                self.assertDictEqual(sysctl.present(name, value), ret)

            mock = MagicMock(return_value="Already set")
            with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
                ret.update({"comment": comt7, "result": True})
                self.assertDictEqual(sysctl.present(name, value), ret)
