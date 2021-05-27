import salt.modules.openscap as openscap
from salt.exceptions import ArgumentValueError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class OpenscapTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.module.openscap
    """

    def setup_loader_modules(self):
        return {openscap: {}}

    def test_version(self):
        """
        Test, if the short version is returned.
        """

        mocked_oscap_string = """OpenSCAP command line tool (oscap) 1.2.16
Copyright 2009--2017 Red Hat Inc., Durham, North Carolina.

==== Supported specifications ====
XCCDF Version: 1.2
OVAL Version: 5.11.1

==== Capabilities added by auto-loaded plugins ====
SCE Version: 1.0 (from libopenscap_sce.so.8)

==== Paths ====
Schema files: /usr/share/openscap/schemas
Default CPE files: /usr/share/openscap/cpe
Probes: /usr/lib/x86_64-linux-gnu/openscap

==== Inbuilt CPE names ====
Red Hat Enterprise Linux - cpe:/o:redhat:enterprise_linux
Red Hat Enterprise Linux 5 - cpe:/o:redhat:enterprise_linux:5

==== Supported OVAL objects and associated OpenSCAP probes ====
OVAL family   OVAL object                  OpenSCAP probe
----------    ----------                   ----------
(null)        system_info                  probe_system_info
independent   family                       probe_family"""

        with patch.dict(
            openscap.__salt__, {"cmd.run": MagicMock(return_value=mocked_oscap_string)}
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ):
            # Test if short output is correct
            self.assertEqual(openscap.version(), {"oscap": "1.2.16"})

            # Test if long output is correct
            self.assertIsInstance(openscap.version("all"), dict)

    def test_build_cmd(self):
        """
        Test if _build_cmd returns well formed cmds.
        """
        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ):

            _module = "xccdf"
            _operation = "eval"
            _kwargs = {
                "check-engine-results": True,
                "without-syschar": True,
                "progress": True,
                "profile": "test",
                "tailoring-file": "/var/oscap/test_tailoring.xml",
            }

            # Test, if module and operation are added properly to Command. With and **kwargs
            self.assertEqual(
                openscap._build_cmd(_module, _operation, **_kwargs),
                "/usr/bin/oscap xccdf eval --check-engine-results --without-syschar --progress --profile test --tailoring-file /var/oscap/test_tailoring.xml",
            )

            # Test, if only the module without the operation is properly added to the command.
            self.assertEqual(
                openscap._build_cmd("info", **{"profiles": True}),
                "/usr/bin/oscap info --profiles",
            )

            # Test, if only the module without the operation is properly added to the command.
            self.assertEqual(
                openscap._build_cmd("info", **{"profile": "test"}),
                "/usr/bin/oscap info --profile test",
            )

        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=False)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ):

            _module = "xccdf"
            _operation = "wrong_op"
            _kwargs = {
                "profile": "test",
                "tailoring-file": "/var/oscap/test_tailoring.xml",
            }

            # Test, if operation is supported by module
            with self.assertRaises(
                expected_exception=ArgumentValueError,
                msg="'xccdf' does not support 'wrong_op' operation!",
            ):
                openscap._build_cmd(_module, _operation, **_kwargs)

        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=False)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ):

            _module = "xccdf"
            _operation = "eval"
            _kwargs = {
                "wrong-kw-param": "test",
                "profile": "test",
                "tailoring-file": "/var/oscap/test_tailoring.xml",
            }

            # Test, if args Param is supported by operation and module
            with self.assertRaises(
                expected_exception=ArgumentValueError,
                msg="'xccdf eval' does not support 'wrong-kw-param' parameter!",
            ):
                openscap._build_cmd(_module, _operation, **_kwargs)

    def test_xccdf(self):
        """
        Test the output of info.
        """
        _file = "/var/oscap/test.xml"
        _operation = "eval"
        _kwargs = {
            "profile": "test",
            "tailoring-file": "/var/oscap/test_tailoring.xml",
        }

        with patch.object(
            openscap, "_build_cmd", MagicMock(return_value="/usr/lib/oscap xccdf eval")
        ):

            # Test if 'file' parameter is set.
            self.assertEqual(openscap.xccdf(), "A File must be defined!")

        # Test resulsts with upload successful upload
        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ), patch.dict(
            openscap.__salt__, {"cp.push_dir": MagicMock(return_value=True)}
        ), patch(
            "salt.modules.openscap.tempfile.mkdtemp",
            MagicMock(return_value="/tmp/rand/path"),
        ), patch.dict(
            openscap.__salt__, {"cmd.retcode": MagicMock(side_effect=[0, 1, 2])}
        ):

            _kwargs = {
                "check-engine-results": True,
                "without-syschar": True,
                "progress": True,
            }

            # Test a Normal run with successful upload
            self.assertEqual(
                openscap.xccdf(_file, _operation, **_kwargs),
                {
                    "success": True,
                    "upload_dir": "/tmp/rand/path",
                    "error": None,
                    "returncode": 0,
                },
            )

            # Test a SCAP Fail, which prevents the Upload
            self.assertEqual(
                openscap.xccdf(_file, _operation, **_kwargs),
                {"success": False, "upload_dir": None, "error": None, "returncode": 1},
            )

            # Test a SCAP Success with failed checks and successful Upload
            self.assertEqual(
                openscap.xccdf(_file, _operation, **_kwargs),
                {
                    "success": True,
                    "upload_dir": "/tmp/rand/path",
                    "error": None,
                    "returncode": 2,
                },
            )

        # Test resulsts with upload failed upload
        with patch.object(
            openscap, "_has_operation", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_has_param", MagicMock(return_value=True)
        ), patch.object(
            openscap, "_oscap_cmd", MagicMock(return_value="/usr/bin/oscap")
        ), patch.dict(
            openscap.__salt__, {"cp.push_dir": MagicMock(return_value=False)}
        ), patch.dict(
            openscap.__salt__, {"cmd.retcode": MagicMock(side_effect=[0, 1, 2])}
        ):

            _kwargs = {
                "check-engine-results": True,
                "without-syschar": True,
                "progress": True,
            }

            # Test a Normal run with failed upload
            self.assertEqual(
                openscap.xccdf(_file, _operation, **_kwargs),
                {"success": True, "upload_dir": None, "error": None, "returncode": 0},
            )

            # Test a Failing OpenSCAP run with failed upload (Gets disabled)
            self.assertEqual(
                openscap.xccdf(_file, _operation, **_kwargs),
                {"success": False, "upload_dir": None, "error": None, "returncode": 1},
            )

            # Test a SCAP Success with failed checks and failed Upload
            self.assertEqual(
                openscap.xccdf(_file, _operation, **_kwargs),
                {"success": True, "upload_dir": None, "error": None, "returncode": 2},
            )
