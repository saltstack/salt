# -*- coding: utf-8 -*-
'''
Test module for syslog_ng
'''

# Import Salt Testing libs
import salt
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

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

_SYSLOG_NG_NOT_INSTALLED_RETURN_VALUE = {"retcode": -1, "stderr":
    "Unable to execute the command 'syslog-ng'. It is not in the PATH."}
_SYSLOG_NG_CTL_NOT_INSTALLED_RETURN_VALUE = {"retcode": -1, "stderr":
    "Unable to execute the command 'syslog-ng-ctl'. It is not in the PATH."}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SyslogNGTestCase(TestCase):
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
                         mock_funtion_args,
                         mock_return_value,
                         function_to_call,
                         expected_output,
                         function_args=None):
        if function_args is None:
            function_args = {}

        installed = True
        if not salt.utils.which("syslog-ng"):
            installed = False
            if "syslog-ng-ctl" in mock_funtion_args:
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
                self.assertTrue(mock_param[0][0].endswith(mock_funtion_args))


if __name__ == '__main__':
    from integration import run_tests

    run_tests(SyslogNGTestCase, needs_daemon=False)
