import sys

import salt.modules.pkg_resource as pkg_resource
import salt.modules.solarisipspkg as solarisips
import salt.utils.data
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


@skipIf(sys.platform != "solaris", "Skip when not running on Solaris")
class IpsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.solarisips
    """

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(opts, whitelist=["pkg", "path", "platform"])
        return {
            pkg_resource: {
                "__grains__": {
                    "osarch": "sparcv9",
                    "os_family": "Solaris",
                    "osmajorrelease": 11,
                    "kernelrelease": 5.11,
                },
            },
            solarisips: {"__opts__": opts, "__utils__": utils},
        }

    def test_install_single_package(self):
        """
        Test installing a single package
        """
        pkg_list_pre = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
        }
        pkg_list_post = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
            "pkg://solaris/text/less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
        }
        install_cmd = {
            "pid": 1234,
            "retcode": 0,
            "stderr": "",
            "stdout": "",
        }
        mock_install_cmd = MagicMock(return_value=install_cmd)
        list_pkgs_responses = [pkg_list_pre, pkg_list_post]
        with patch.object(solarisips, "is_installed", return_value=False), patch.object(
            solarisips, "list_pkgs", side_effect=list_pkgs_responses
        ), patch.dict(solarisips.__salt__, {"cmd.run_all": mock_install_cmd}):
            result = solarisips.install(name="less", refresh=False)
            self.assertEqual(
                result, salt.utils.data.compare_dicts(pkg_list_pre, pkg_list_post)
            )

    def test_install_list_pkgs(self):
        """
        Test installing a list of packages
        """
        pkg_list_pre = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
        }
        pkg_list_post = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
            "pkg://solaris/text/less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
            "pkg://solaris/system/library/security/libsasl": (
                "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"
            ),
        }
        install_cmd = {
            "pid": 1234,
            "retcode": 0,
            "stderr": "",
            "stdout": "",
        }
        mock_install_cmd = MagicMock(return_value=install_cmd)
        list_pkgs_responses = [pkg_list_pre, pkg_list_post]
        with patch.object(solarisips, "is_installed", return_value=False), patch.object(
            solarisips, "list_pkgs", side_effect=list_pkgs_responses
        ), patch.dict(solarisips.__salt__, {"cmd.run_all": mock_install_cmd}):
            result = solarisips.install(pkgs=["less", "libsasl"], refresh=False)
            self.assertEqual(
                result, salt.utils.data.compare_dicts(pkg_list_pre, pkg_list_post)
            )

    def test_install_dict_pkgs_no_version(self):
        """
        Test installing a list of packages
        """
        pkg_list_pre = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
        }
        pkg_list_post = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
            "pkg://solaris/text/less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
            "pkg://solaris/system/library/security/libsasl": (
                "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"
            ),
        }
        install_cmd = {
            "pid": 1234,
            "retcode": 0,
            "stderr": "",
            "stdout": "",
        }
        mock_install_cmd = MagicMock(return_value=install_cmd)
        list_pkgs_responses = [pkg_list_pre, pkg_list_post]
        with patch.object(solarisips, "is_installed", return_value=False), patch.object(
            solarisips, "list_pkgs", side_effect=list_pkgs_responses
        ), patch.dict(solarisips.__salt__, {"cmd.run_all": mock_install_cmd}):
            result = solarisips.install(
                pkgs=[{"less": ""}, {"libsasl": ""}], refresh=False
            )
            self.assertEqual(
                result, salt.utils.data.compare_dicts(pkg_list_pre, pkg_list_post)
            )

    def test_install_dict_pkgs_with_version(self):
        """
        Test installing a list of packages
        """
        pkg_list_pre = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
        }
        pkg_list_post = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
            "pkg://solaris/text/less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
            "pkg://solaris/system/library/security/libsasl": (
                "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"
            ),
        }
        install_cmd = {
            "pid": 1234,
            "retcode": 0,
            "stderr": "",
            "stdout": "",
        }
        mock_install_cmd = MagicMock(return_value=install_cmd)
        list_pkgs_responses = [pkg_list_pre, pkg_list_post]
        with patch.object(solarisips, "is_installed", return_value=False), patch.object(
            solarisips, "list_pkgs", side_effect=list_pkgs_responses
        ), patch.dict(solarisips.__salt__, {"cmd.run_all": mock_install_cmd}):
            result = solarisips.install(
                pkgs=[
                    {"less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z"},
                    {"libsasl": "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"},
                ],
                refresh=False,
            )
            self.assertEqual(
                result, salt.utils.data.compare_dicts(pkg_list_pre, pkg_list_post)
            )

    def test_install_already_installed_single_pkg(self):
        """
        Test installing a package that is already installed
        """
        result = None
        expected_result = {}
        with patch.object(solarisips, "is_installed", return_value=True):
            result = solarisips.install(name="less")
        self.assertEqual(result, expected_result)

    def test_install_dict_pkgs_with_version_validate_cmd(self):
        """
        Test installing a list of packages
        """

        def check_param(arg, **kwargs):
            self.assertEqual(
                arg,
                [
                    "pkg",
                    "install",
                    "-v",
                    "--accept",
                    "less@458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
                    "libsasl@0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z",
                ],
            )
            return {
                "pid": 1234,
                "retcode": 0,
                "stderr": "",
                "stdout": "",
            }

        pkg_list_pre = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
        }
        pkg_list_post = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
            "pkg://solaris/text/less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
            "pkg://solaris/system/library/security/libsasl": (
                "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"
            ),
        }
        mock_install_cmd = MagicMock(side_effect=check_param)
        list_pkgs_responses = [pkg_list_pre, pkg_list_post]
        with patch.object(solarisips, "is_installed", return_value=False), patch.object(
            solarisips, "list_pkgs", side_effect=list_pkgs_responses
        ):
            with patch.dict(solarisips.__salt__, {"cmd.run_all": mock_install_cmd}):
                result = solarisips.install(
                    pkgs=[
                        {"less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z"},
                        {"libsasl": "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"},
                    ],
                    refresh=False,
                )

    def test_install_dict_pkgs_no_version_validate_cmd(self):
        """
        Test installing a list of packages
        """

        def check_param(arg, **kwargs):
            self.assertEqual(
                arg, ["pkg", "install", "-v", "--accept", "less", "libsasl"]
            )
            return {
                "pid": 1234,
                "retcode": 0,
                "stderr": "",
                "stdout": "",
            }

        pkg_list_pre = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
        }
        pkg_list_post = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
            "pkg://solaris/text/less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
            "pkg://solaris/system/library/security/libsasl": (
                "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"
            ),
        }
        mock_install_cmd = MagicMock(side_effect=check_param)
        list_pkgs_responses = [pkg_list_pre, pkg_list_post]
        with patch.object(solarisips, "is_installed", return_value=False), patch.object(
            solarisips, "list_pkgs", side_effect=list_pkgs_responses
        ):
            with patch.dict(solarisips.__salt__, {"cmd.run_all": mock_install_cmd}):
                result = solarisips.install(
                    pkgs=[{"less": ""}, {"libsasl": ""}], refresh=False
                )

    def test_install_list_pkgs_validate_cmd(self):
        """
        Test installing a list of packages
        """

        def check_param(arg, **kwargs):
            self.assertEqual(
                arg, ["pkg", "install", "-v", "--accept", "less", "libsasl"]
            )
            return {
                "pid": 1234,
                "retcode": 0,
                "stderr": "",
                "stdout": "",
            }

        pkg_list_pre = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
        }
        pkg_list_post = {
            "pkg://solaris/compress/bzip2": (
                "1.0.6,5.11-0.175.3.10.0.4.0:20160630T215500Z"
            ),
            "pkg://solaris/compress/gzip": "1.5,5.11-0.175.3.0.0.30.0:20150821T161446Z",
            "pkg://solaris/compress/p7zip": (
                "16.2.3,5.11-0.175.3.34.0.2.0:20180614T204908Z"
            ),
            "pkg://solaris/text/less": "458,5.11-0.175.3.0.0.30.0:20150821T172730Z",
            "pkg://solaris/system/library/security/libsasl": (
                "0.5.11,5.11-0.175.3.32.0.1.0:20180406T191209Z"
            ),
        }
        mock_install_cmd = MagicMock(side_effect=check_param)
        list_pkgs_responses = [pkg_list_pre, pkg_list_post]
        with patch.object(solarisips, "is_installed", return_value=False), patch.object(
            solarisips, "list_pkgs", side_effect=list_pkgs_responses
        ):
            with patch.dict(solarisips.__salt__, {"cmd.run_all": mock_install_cmd}):
                result = solarisips.install(pkgs=["less", "libsasl"], refresh=False)
