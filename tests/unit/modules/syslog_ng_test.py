# -*- coding: utf-8 -*-
'''
Test module for syslog_ng
'''

# Import Python modules
from __future__ import absolute_import
from textwrap import dedent

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch


ensure_in_syspath('../../')

# Import Salt libs
import salt
from salt.modules import syslog_ng

syslog_ng.__salt__ = {}
syslog_ng.__opts__ = {}

_VERSION = "3.6.0alpha0"
_MODULES = ("syslogformat,json-plugin,basicfuncs,afstomp,afsocket,cryptofuncs,"
            "afmongodb,dbparser,system-source,affile,pseudofile,afamqp,"
            "afsocket-notls,csvparser,linux-kmsg-format,afuser,confgen,afprog")

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
Enable-Linux-Caps: off""".format(_VERSION, _MODULES)

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
    "retcode": -1, "stderr":
    "Unable to execute the command 'syslog-ng'. It is not in the PATH."
}
_SYSLOG_NG_CTL_NOT_INSTALLED_RETURN_VALUE = {
    "retcode": -1, "stderr":
    "Unable to execute the command 'syslog-ng-ctl'. It is not in the PATH."
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SyslogNGTestCase(TestCase):

    def test_statement_without_options(self):
        s = syslog_ng.Statement("source", "s_local", options=[])
        b = s.build()
        self.assertEqual(dedent(
            """\
            source s_local {
            };
            """), b)

    def test_non_empty_statement(self):
        o1 = syslog_ng.Option("file")
        o2 = syslog_ng.Option("tcp")
        s = syslog_ng.Statement("source", "s_local", options=[o1, o2])
        b = s.build()
        self.assertEqual(dedent(
            """\
            source s_local {
                file(
                );
                tcp(
                );
            };
            """), b)

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
        self.assertEqual(dedent(
            """\
            file(
                "/var/log/messages",
                "/var/log/syslog",
                tls(
                )
            );
            """), b)

    def test_parameter_with_values(self):
        p = syslog_ng.TypedParameter()
        p.type = "tls"
        v1 = syslog_ng.TypedParameterValue()
        v1.type = 'key_file'

        v2 = syslog_ng.TypedParameterValue()
        v2.type = 'cert_file'

        p.add_value(v1)
        p.add_value(v2)

        b = p.build()
        self.assertEqual(dedent(
            """\
            tls(
                key_file(
                ),
                cert_file(
                )
            )"""), b)

    def test_value_with_arguments(self):
        t = syslog_ng.TypedParameterValue()
        t.type = 'key_file'

        a1 = syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"')
        a2 = syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"')

        t.add_argument(a1)
        t.add_argument(a2)

        b = t.build()
        self.assertEqual(dedent(
            '''\
            key_file(
                "/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"
                "/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"
            )'''), b)

    def test_end_to_end_statement_generation(self):
        s = syslog_ng.Statement('source', 's_tls')

        o = syslog_ng.Option('tcp')

        ip = syslog_ng.TypedParameter('ip')
        ip.add_value(syslog_ng.SimpleParameterValue("'192.168.42.2'"))
        o.add_parameter(ip)

        port = syslog_ng.TypedParameter('port')
        port.add_value(syslog_ng.SimpleParameterValue(514))
        o.add_parameter(port)

        tls = syslog_ng.TypedParameter('tls')
        key_file = syslog_ng.TypedParameterValue('key_file')
        key_file.add_argument(syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/key.d/syslog-ng.key"'))
        cert_file = syslog_ng.TypedParameterValue('cert_file')
        cert_file.add_argument(syslog_ng.Argument('"/opt/syslog-ng/etc/syslog-ng/cert.d/syslog-ng.cert"'))
        peer_verify = syslog_ng.TypedParameterValue('peer_verify')
        peer_verify.add_argument(syslog_ng.Argument('optional-untrusted'))
        tls.add_value(key_file)
        tls.add_value(cert_file)
        tls.add_value(peer_verify)
        o.add_parameter(tls)

        s.add_child(o)
        b = s.build()
        self.assertEqual(dedent(
            '''\
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
            '''), b)

    def test_version(self):
        mock_return_value = {"retcode": 0, 'stdout': VERSION_OUTPUT}
        expected_output = {"retcode": 0, "stdout": "3.6.0alpha0"}
        mock_args = "syslog-ng -V"
        self._assert_template(mock_args,
                              mock_return_value,
                              function_to_call=syslog_ng.version,
                              expected_output=expected_output)

    def test_stats(self):
        mock_return_value = {"retcode": 0, 'stdout': STATS_OUTPUT}
        expected_output = {"retcode": 0, "stdout": STATS_OUTPUT}
        mock_args = "syslog-ng-ctl stats"
        self._assert_template(mock_args,
                              mock_return_value,
                              function_to_call=syslog_ng.stats,
                              expected_output=expected_output)

    def test_modules(self):
        mock_return_value = {"retcode": 0, 'stdout': VERSION_OUTPUT}
        expected_output = {"retcode": 0, "stdout": _MODULES}
        mock_args = "syslog-ng -V"
        self._assert_template(mock_args,
                              mock_return_value,
                              function_to_call=syslog_ng.modules,
                              expected_output=expected_output)

    def test_config_test_ok(self):
        mock_return_value = {"retcode": 0, "stderr": "", "stdout": "Syslog-ng startup text..."}
        mock_args = "syslog-ng --syntax-only"
        self._assert_template(mock_args,
                              mock_return_value,
                              function_to_call=syslog_ng.config_test,
                              expected_output=mock_return_value)

    def test_config_test_fails(self):
        mock_return_value = {"retcode": 1, 'stderr': "Syntax error...", "stdout": ""}
        mock_args = "syslog-ng --syntax-only"
        self._assert_template(mock_args,
                              mock_return_value,
                              function_to_call=syslog_ng.config_test,
                              expected_output=mock_return_value)

    def test_config_test_cfgfile(self):
        cfgfile = "/path/to/syslog-ng.conf"
        mock_return_value = {"retcode": 1, 'stderr': "Syntax error...", "stdout": ""}
        mock_args = "syslog-ng --syntax-only --cfgfile={0}".format(cfgfile)
        self._assert_template(mock_args,
                              mock_return_value,
                              function_to_call=syslog_ng.config_test,
                              function_args={"cfgfile": cfgfile},
                              expected_output=mock_return_value)

    def _assert_template(self,
                         mock_function_args,
                         mock_return_value,
                         function_to_call,
                         expected_output,
                         function_args=None):
        if function_args is None:
            function_args = {}

        installed = True
        if not salt.utils.which("syslog-ng"):
            installed = False
            if "syslog-ng-ctl" in mock_function_args:
                expected_output = _SYSLOG_NG_CTL_NOT_INSTALLED_RETURN_VALUE
            else:
                expected_output = _SYSLOG_NG_NOT_INSTALLED_RETURN_VALUE

        mock_function = MagicMock(return_value=mock_return_value)

        with patch.dict(syslog_ng.__salt__, {'cmd.run_all': mock_function}):
            got = function_to_call(**function_args)
            self.assertEqual(expected_output, got)

            if installed:
                self.assertTrue(mock_function.called)
                self.assertEqual(len(mock_function.call_args), 2)
                mock_param = mock_function.call_args
                self.assertTrue(mock_param[0][0].endswith(mock_function_args))


if __name__ == '__main__':
    from integration import run_tests

    run_tests(SyslogNGTestCase, needs_daemon=False)
