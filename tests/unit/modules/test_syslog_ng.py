# -*- coding: utf-8 -*-
"""
Test module for syslog_ng
"""

# Import Python modules
from __future__ import absolute_import, print_function, unicode_literals

import os
from textwrap import dedent

import salt.modules.syslog_ng as syslog_ng

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

_VERSION = "3.6.0alpha0"
_MODULES = (
    "syslogformat,json-plugin,basicfuncs,afstomp,afsocket,cryptofuncs,"
    "afmongodb,dbparser,system-source,affile,pseudofile,afamqp,"
    "afsocket-notls,csvparser,linux-kmsg-format,afuser,confgen,afprog"
)

VERSION_OUTPUT = """syslog-ng {0}
Installer-Version: {0}
Revision:
Compile-Date: Apr  4 2014 20:26:18
Error opening plugin module; module='afsocket-tls', error='/home/tibi/install/syslog-ng/lib/syslog-ng/libafsocket-tls.so: undefined symbol: tls_context_setup_session'
Available-Modules: {1}
Enable-Debug: on
Enable-GProf: off
Enable-Memtrace: off
Enable-IPv6: on
Enable-Spoof-Source: off
Enable-TCP-Wrapper: off
Enable-Linux-Caps: off""".format(
    _VERSION, _MODULES
)

STATS_OUTPUT = """SourceName;SourceId;SourceInstance;State;Type;Number
center;;received;a;processed;0
destination;#anon-destination0;;a;processed;0
destination;#anon-destination1;;a;processed;0
source;s_gsoc2014;;a;processed;0
center;;queued;a;processed;0
global;payload_reallocs;;a;processed;0
global;sdata_updates;;a;processed;0
global;msg_clones;;a;processed;0"""

_SYSLOG_NG_NOT_INSTALLED_RETURN_VALUE = {
    "retcode": -1,
    "stderr": "Unable to execute the command 'syslog-ng'. It is not in the PATH.",
}
_SYSLOG_NG_CTL_NOT_INSTALLED_RETURN_VALUE = {
    "retcode": -1,
    "stderr": "Unable to execute the command 'syslog-ng-ctl'. It is not in the PATH.",
}


class SyslogNGTestCase(TestCase, LoaderModuleMockMixin):

    # pylint: disable=blacklisted-function
    orig_env = {str("PATH"): str("/foo:/bar")}
    bin_dir = str("/baz")
    mocked_env = {str("PATH"): str("/foo:/bar:/baz")}
    # pylint: enable=blacklisted-function

    def setup_loader_modules(self):
        return {syslog_ng: {}}

    def test_statement_without_options(self):
        s = syslog_ng.Statement("source", "s_local", options=[])
        b = s.build()
        self.assertEqual(
            dedent(
                """\
            source s_local {
            };
            """
            ),
            b,
        )

    def test_non_empty_statement(self):
        o1 = syslog_ng.Option("file")
        o2 = syslog_ng.Option("tcp")
        s = syslog_ng.Statement("source", "s_local", options=[o1, o2])
        b = s.build()
        self.assertEqual(
            dedent(
                """\
            source s_local {
                file(
                );
                tcp(
                );
            };
            """
            ),
            b,
        )

    def test_option_with_parameters(self):
        o1 = syslog_ng.Option("file")
        p1 = syslog_ng.SimpleParameter('"/var/log/messages"')
        p2 = syslog_ng.SimpleParameter()
        p3 = syslog_ng.TypedParameter()
        p3.type = "tls"
        p2.value = '"/var/log/syslog"'
        o1.add_parameter(p1)
        o1.add_parameter(p2)
        o1.add_parameter(p3)
        b = o1.build()
        self.assertEqual(
            dedent(
                """\
            file(
                "/var/log/messages",
                "/var/log/syslog",
                tls(
                )
            );
            """
            ),
            b,
        )

    def test_parameter_with_values(self):
        p = syslog_ng.TypedParameter()
        p.type = "tls"
        v1 = syslog_ng.TypedParameterValue()
        v1.type = "key_file"

        v2 = syslog_ng.TypedParameterValue()
        v2.type = "cert_file"

        p.add_value(v1)
        p.add_value(v2)

        b = p.build()
        self.assertEqual(
            dedent(
                """\
            tls(
                key_file(
                ),
                cert_file(
                )
            )"""
            ),
            b,
        )

    def test_value_with_arguments(self):
        t = syslog_ng.TypedParameterValue()
        t.type = "key_file"

        a1 = syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"')
        a2 = syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"')

        t.add_argument(a1)
        t.add_argument(a2)

        b = t.build()
        self.assertEqual(
            dedent(
                """\
            key_file(
                "/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"
                "/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"
            )"""
            ),
            b,
        )

    def test_end_to_end_statement_generation(self):
        s = syslog_ng.Statement("source", "s_tls")

        o = syslog_ng.Option("tcp")

        ip = syslog_ng.TypedParameter("ip")
        ip.add_value(syslog_ng.SimpleParameterValue("'192.168.42.2'"))
        o.add_parameter(ip)

        port = syslog_ng.TypedParameter("port")
        port.add_value(syslog_ng.SimpleParameterValue(514))
        o.add_parameter(port)

        tls = syslog_ng.TypedParameter("tls")
        key_file = syslog_ng.TypedParameterValue("key_file")
        key_file.add_argument(
            syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"')
        )
        cert_file = syslog_ng.TypedParameterValue("cert_file")
        cert_file.add_argument(
            syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/cert.d/syslog-ng.cert"')
        )
        peer_verify = syslog_ng.TypedParameterValue("peer_verify")
        peer_verify.add_argument(syslog_ng.Argument("optional-untrusted"))
        tls.add_value(key_file)
        tls.add_value(cert_file)
        tls.add_value(peer_verify)
        o.add_parameter(tls)

        s.add_child(o)
        b = s.build()
        self.assertEqual(
            dedent(
                """\
            source s_tls {
                tcp(
                    ip(
                        '192.168.42.2'
                    ),
                    port(
                        514
                    ),
                    tls(
                        key_file(
                            "/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"
                        ),
                        cert_file(
                            "/opt/syslog-ng/etc/syslog-ng/cert.d/syslog-ng.cert"
                        ),
                        peer_verify(
                            optional-untrusted
                        )
                    )
                );
            };
            """
            ),
            b,
        )

    @skipIf(salt.utils.platform.is_windows(), "Module not available on Windows")
    def test_version(self):
        cmd_ret = {"retcode": 0, "stdout": VERSION_OUTPUT}
        expected_output = {"retcode": 0, "stdout": _VERSION}
        cmd_args = ["syslog-ng", "-V"]

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.version()
            self.assertEqual(result, expected_output)
            cmd_mock.assert_called_once_with(cmd_args, env=None, python_shell=False)

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.version(syslog_ng_sbin_dir=self.bin_dir)
            self.assertEqual(result, expected_output)
            cmd_mock.assert_called_once_with(
                cmd_args, env=self.mocked_env, python_shell=False
            )

    @skipIf(salt.utils.platform.is_windows(), "Module not available on Windows")
    def test_stats(self):
        cmd_ret = {"retcode": 0, "stdout": STATS_OUTPUT}
        cmd_args = ["syslog-ng-ctl", "stats"]

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.stats()
            self.assertEqual(result, cmd_ret)
            cmd_mock.assert_called_once_with(cmd_args, env=None, python_shell=False)

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.stats(syslog_ng_sbin_dir=self.bin_dir)
            self.assertEqual(result, cmd_ret)
            cmd_mock.assert_called_once_with(
                cmd_args, env=self.mocked_env, python_shell=False
            )

    @skipIf(salt.utils.platform.is_windows(), "Module not available on Windows")
    def test_modules(self):
        cmd_ret = {"retcode": 0, "stdout": VERSION_OUTPUT}
        expected_output = {"retcode": 0, "stdout": _MODULES}
        cmd_args = ["syslog-ng", "-V"]

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.modules()
            self.assertEqual(result, expected_output)
            cmd_mock.assert_called_once_with(cmd_args, env=None, python_shell=False)

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.modules(syslog_ng_sbin_dir=self.bin_dir)
            self.assertEqual(result, expected_output)
            cmd_mock.assert_called_once_with(
                cmd_args, env=self.mocked_env, python_shell=False
            )

    @skipIf(salt.utils.platform.is_windows(), "Module not available on Windows")
    def test_config_test(self):
        cmd_ret = {"retcode": 0, "stderr": "", "stdout": "Foo"}
        cmd_args = ["syslog-ng", "--syntax-only"]

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.config_test()
            self.assertEqual(result, cmd_ret)
            cmd_mock.assert_called_once_with(cmd_args, env=None, python_shell=False)

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            result = syslog_ng.config_test(syslog_ng_sbin_dir=self.bin_dir)
            self.assertEqual(result, cmd_ret)
            cmd_mock.assert_called_once_with(
                cmd_args, env=self.mocked_env, python_shell=False
            )

    @skipIf(salt.utils.platform.is_windows(), "Module not available on Windows")
    def test_config_test_cfgfile(self):
        cfgfile = "/path/to/syslog-ng.conf"
        cmd_ret = {"retcode": 1, "stderr": "Syntax error...", "stdout": ""}
        cmd_args = ["syslog-ng", "--syntax-only", "--cfgfile={0}".format(cfgfile)]

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            self.assertEqual(syslog_ng.config_test(cfgfile=cfgfile), cmd_ret)
            cmd_mock.assert_called_once_with(cmd_args, env=None, python_shell=False)

        cmd_mock = MagicMock(return_value=cmd_ret)
        with patch.dict(syslog_ng.__salt__, {"cmd.run_all": cmd_mock}), patch.dict(
            os.environ, self.orig_env
        ):
            self.assertEqual(
                syslog_ng.config_test(syslog_ng_sbin_dir=self.bin_dir, cfgfile=cfgfile),
                cmd_ret,
            )
            cmd_mock.assert_called_once_with(
                cmd_args, env=self.mocked_env, python_shell=False
            )
