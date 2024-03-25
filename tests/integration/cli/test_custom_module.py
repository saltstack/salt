"""
    :codeauthor: Daniel Mizyrycki (mzdaniel@glidelink.net)


    tests.integration.cli.custom_module
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test salt-ssh sls with a custom module work.

    $ cat srv/custom_module.sls
    custom-module:
      module.run:
        - name: test.recho
        - text: hello


    $ cat srv/_modules/override_test.py
    __virtualname__ = 'test'

    def __virtual__():
        return __virtualname__

    def recho(text):
        return text[::-1]


    $ salt-ssh localhost state.sls custom_module
    localhost:
        olleh
"""

import pytest

from tests.support.case import SSHCase

pytestmark = [
    pytest.mark.skipif(
        "grains['osfinger'] == 'Fedora Linux-39'",
        reason="Fedora 39 ships with Python 3.12. Test can't run with system Python on 3.12",
        # Actually, the problem is that the tornado we ship is not prepared for Python 3.12,
        # and it imports `ssl` and checks if the `match_hostname` function is defined, which
        # has been deprecated since Python 3.7, so, the logic goes into trying to import
        # backports.ssl-match-hostname which is not installed on the system.
    )
]


@pytest.mark.skip_on_windows
class SSHCustomModuleTest(SSHCase):
    """
    Test sls with custom module functionality using ssh
    """

    @pytest.mark.slow_test
    def test_ssh_regular_module(self):
        """
        Test regular module work using SSHCase environment
        """
        expected = "hello"
        cmd = self.run_function("test.echo", arg=["hello"])
        self.assertEqual(expected, cmd)

    @pytest.mark.slow_test
    @pytest.mark.timeout(120)
    def test_ssh_custom_module(self):
        """
        Test custom module work using SSHCase environment
        """
        expected = "hello"[::-1]
        cmd = self.run_function("test.recho", arg=["hello"])
        self.assertEqual(expected, cmd)

    @pytest.mark.slow_test
    def test_ssh_sls_with_custom_module(self):
        """
        Test sls with custom module work using SSHCase environment
        """
        expected = {
            "module_|-regular-module_|-test.echo_|-run": "hello",
            "module_|-custom-module_|-test.recho_|-run": "olleh",
        }
        cmd = self.run_function("state.sls", arg=["custom_module"])
        for key in cmd:
            if not isinstance(cmd, dict) or not isinstance(cmd[key], dict):
                raise AssertionError(f"{cmd} is not a proper state return")
            elif not cmd[key]["result"]:
                raise AssertionError(cmd[key]["comment"])
            cmd_ret = cmd[key]["changes"].get("ret", None)
            self.assertEqual(cmd_ret, expected[key])
