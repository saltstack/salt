"""
tests.unit.proxy.test_cimc
~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the cimc proxy module
"""

import logging

import salt.exceptions
import salt.proxy.cimc as cimc
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


LOGIN_RESPONSE = """\
<aaaLogin
    response="yes"
    outCookie="real-cookie"
       outRefreshPeriod="600"
       outPriv="admin">
</aaaLogin>"""
LOGOUT_RESPONSE = """\
<aaaLogout
    cookie="real-cookie"
    response="yes"
    outStatus="success">
</aaaLogout>
"""
CONFIG_RESOLVE_CLASS_RESPONSE = """\
<configResolveClass
    cookie="real-cookie"
    response="yes"
    classId="computeRackUnit">
    <outConfig>
        <computeRackUnit
            dn="sys/rack-unit-1"
            adminPower="policy"
            availableMemory="16384"
            model="R210-2121605W"
            memorySpeed="1067"
            name="UCS C210 M2"
            numOfAdaptors="2"
            numOfCores="8"
            numOfCoresEnabled="8"
            numOfCpus="2"
            numOfEthHostIfs="5"
            numOfFcHostIfs="2"
            numOfThreads="16"
            operPower="on"
            originalUuid="00C9DE3C-370D-DF11-1186-6DD1393A608B"
            presence="equipped"
            serverID="1"
            serial="QCI140205Z2"
            totalMemory="16384"
            usrLbl="C210 Row-B Rack-10"
            uuid="00C9DE3C-370D-DF11-1186-6DD1393A608B"
            vendor="Cisco Systems Inc" >
        </computeRackUnit>
    </outConfig>
</configResolveClass>
"""
CONFIG_CON_MO_RESPONSE = """\
<configConfMo
    dn="sys/rack-unit-1/locator-led"
    cookie="real-cookie"
    response="yes">
    <outConfig>
        <equipmentLocatorLed
            dn="sys/rack-unit-1/locator-led"
            adminState="inactive"
            color="unknown"
            id="1"
            name=""
            operState="off">
        </equipmentLocatorLed>
    </outConfig>
</configConfMo>
"""


def http_query_response(*args, data=None, **kwargs):
    log.debug(
        "http_query_response side_effect; ARGS: %s // KWARGS: %s // DATA: %s",
        args,
        kwargs,
        data,
    )
    if data.startswith("<aaaLogin"):
        response = LOGIN_RESPONSE
    elif data.startswith("<aaaLogout"):
        response = LOGOUT_RESPONSE
    elif data.startswith("<configResolveClass"):
        response = CONFIG_RESOLVE_CLASS_RESPONSE
    elif data.startswith("<configConfMo"):
        response = CONFIG_CON_MO_RESPONSE
    else:
        response = ""
    return {"text": response, "status": 200}


class CIMCProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {cimc: {"DETAILS": {}, "__pillar__": {}}}

    def setUp(self):
        self.opts = {"proxy": {"username": "xxxx", "password": "xxx", "host": "cimc"}}
        self.addCleanup(delattr, self, "opts")

    def test_init(self):
        # No host, returns False
        opts = {"proxy": {"username": "xxxx", "password": "xxx"}}
        ret = cimc.init(opts)
        self.assertFalse(ret)

        # No username , returns False
        opts = {"proxy": {"password": "xxx", "host": "cimc"}}
        ret = cimc.init(opts)
        self.assertFalse(ret)

        # No password, returns False
        opts = {"proxy": {"username": "xxxx", "host": "cimc"}}
        ret = cimc.init(opts)
        self.assertFalse(ret)

        with patch.object(cimc, "logon", return_value="9zVG5U8DFZNsTR") as mock_logon:
            with patch.object(
                cimc, "get_config_resolver_class", return_value="True"
            ) as mock_logon:
                ret = cimc.init(self.opts)
                self.assertEqual(cimc.DETAILS["url"], "https://cimc/nuova")
                self.assertEqual(cimc.DETAILS["username"], "xxxx")
                self.assertEqual(cimc.DETAILS["password"], "xxx")
                self.assertTrue(cimc.DETAILS["initialized"])

    def test__validate_response_code(self):
        with self.assertRaisesRegex(
            salt.exceptions.CommandExecutionError,
            "Did not receive a valid response from host.",
        ):
            cimc._validate_response_code("404")

        with patch.object(cimc, "logout", return_value=True) as mock_logout:
            with self.assertRaisesRegex(
                salt.exceptions.CommandExecutionError,
                "Did not receive a valid response from host.",
            ):
                cimc._validate_response_code("404", "9zVG5U8DFZNsTR")
                mock_logout.assert_called_once_with("9zVG5U8DFZNsTR")


class ValidateSSLTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {cimc: {}}

    def setUp(self):
        cimc.DETAILS.clear()

    def test_init(self):
        verify_ssl_values = (None, True, False)
        for verify_ssl_value in verify_ssl_values:
            cimc.DETAILS.clear()
            opts = {
                "proxy": {
                    "host": "TheHost",
                    "username": "TheUsername",
                    "password": "ThePassword",
                    "verify_ssl": verify_ssl_value,
                }
            }
            http_query_mock = MagicMock(side_effect=http_query_response)
            if verify_ssl_value is None:
                expected_verify_ssl_value = True
            else:
                expected_verify_ssl_value = verify_ssl_value

            log.debug(
                "verify_ssl: %s // expected verify_ssl: %s",
                verify_ssl_value,
                expected_verify_ssl_value,
            )

            with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
                cimc.init(opts)

            for idx, call in enumerate(http_query_mock.mock_calls, 1):
                condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
                condition_error = "{} != {}; Call(number={}): {}".format(
                    idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
                )
                self.assertTrue(condition, msg=condition_error)

    def test_logon(self):
        verify_ssl_values = (None, True, False)
        for verify_ssl_value in verify_ssl_values:
            cimc.DETAILS.clear()
            opts = {
                "proxy": {
                    "host": "TheHost",
                    "username": "TheUsername",
                    "password": "ThePassword",
                    "verify_ssl": verify_ssl_value,
                }
            }
            http_query_mock = MagicMock(side_effect=http_query_response)
            if verify_ssl_value is None:
                expected_verify_ssl_value = True
            else:
                expected_verify_ssl_value = verify_ssl_value

            # Let's init the proxy and ignore it's actions, this test is not about them
            with patch(
                "salt.proxy.cimc.get_config_resolver_class",
                MagicMock(return_value=True),
            ):
                cimc.init(opts)

            log.debug(
                "verify_ssl: %s // expected verify_ssl: %s",
                verify_ssl_value,
                expected_verify_ssl_value,
            )

            with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
                cimc.logon()

            for idx, call in enumerate(http_query_mock.mock_calls, 1):
                condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
                condition_error = "{} != {}; Call(number={}): {}".format(
                    idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
                )
                self.assertTrue(condition, msg=condition_error)

    def test_logout(self):
        verify_ssl_values = (None, True, False)
        for verify_ssl_value in verify_ssl_values:
            cimc.DETAILS.clear()
            opts = {
                "proxy": {
                    "host": "TheHost",
                    "username": "TheUsername",
                    "password": "ThePassword",
                    "verify_ssl": verify_ssl_value,
                }
            }
            http_query_mock = MagicMock(side_effect=http_query_response)
            if verify_ssl_value is None:
                expected_verify_ssl_value = True
            else:
                expected_verify_ssl_value = verify_ssl_value

            # Let's init the proxy and ignore it's actions, this test is not about them
            with patch(
                "salt.proxy.cimc.get_config_resolver_class",
                MagicMock(return_value=True),
            ):
                cimc.init(opts)

            log.debug(
                "verify_ssl: %s // expected verify_ssl: %s",
                verify_ssl_value,
                expected_verify_ssl_value,
            )

            with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
                cimc.logout()

            for idx, call in enumerate(http_query_mock.mock_calls, 1):
                condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
                condition_error = "{} != {}; Call(number={}): {}".format(
                    idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
                )
                self.assertTrue(condition, msg=condition_error)

    def test_grains(self):
        verify_ssl_values = (None, True, False)
        for verify_ssl_value in verify_ssl_values:
            cimc.DETAILS.clear()
            opts = {
                "proxy": {
                    "host": "TheHost",
                    "username": "TheUsername",
                    "password": "ThePassword",
                    "verify_ssl": verify_ssl_value,
                }
            }
            http_query_mock = MagicMock(side_effect=http_query_response)
            if verify_ssl_value is None:
                expected_verify_ssl_value = True
            else:
                expected_verify_ssl_value = verify_ssl_value

            # Let's init the proxy and ignore it's actions, this test is not about them
            with patch(
                "salt.proxy.cimc.get_config_resolver_class",
                MagicMock(return_value=True),
            ):
                cimc.init(opts)

            log.debug(
                "verify_ssl: %s // expected verify_ssl: %s",
                verify_ssl_value,
                expected_verify_ssl_value,
            )

            with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
                cimc.grains()

            for idx, call in enumerate(http_query_mock.mock_calls, 1):
                condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
                condition_error = "{} != {}; Call(number={}): {}".format(
                    idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
                )
                self.assertTrue(condition, msg=condition_error)

    def test_grains_refresh(self):
        verify_ssl_values = (None, True, False)
        for verify_ssl_value in verify_ssl_values:
            cimc.DETAILS.clear()
            opts = {
                "proxy": {
                    "host": "TheHost",
                    "username": "TheUsername",
                    "password": "ThePassword",
                    "verify_ssl": verify_ssl_value,
                }
            }
            http_query_mock = MagicMock(side_effect=http_query_response)
            if verify_ssl_value is None:
                expected_verify_ssl_value = True
            else:
                expected_verify_ssl_value = verify_ssl_value

            # Let's init the proxy and ignore it's actions, this test is not about them
            with patch(
                "salt.proxy.cimc.get_config_resolver_class",
                MagicMock(return_value=True),
            ):
                cimc.init(opts)

            log.debug(
                "verify_ssl: %s // expected verify_ssl: %s",
                verify_ssl_value,
                expected_verify_ssl_value,
            )

            with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
                cimc.grains_refresh()

            for idx, call in enumerate(http_query_mock.mock_calls, 1):
                condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
                condition_error = "{} != {}; Call(number={}): {}".format(
                    idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
                )
                self.assertTrue(condition, msg=condition_error)

    def test_ping(self):
        verify_ssl_values = (None, True, False)
        for verify_ssl_value in verify_ssl_values:
            cimc.DETAILS.clear()
            opts = {
                "proxy": {
                    "host": "TheHost",
                    "username": "TheUsername",
                    "password": "ThePassword",
                    "verify_ssl": verify_ssl_value,
                }
            }
            http_query_mock = MagicMock(side_effect=http_query_response)
            if verify_ssl_value is None:
                expected_verify_ssl_value = True
            else:
                expected_verify_ssl_value = verify_ssl_value

            # Let's init the proxy and ignore it's actions, this test is not about them
            with patch(
                "salt.proxy.cimc.get_config_resolver_class",
                MagicMock(return_value=True),
            ):
                cimc.init(opts)

            log.debug(
                "verify_ssl: %s // expected verify_ssl: %s",
                verify_ssl_value,
                expected_verify_ssl_value,
            )

            with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
                cimc.ping()

            for idx, call in enumerate(http_query_mock.mock_calls, 1):
                condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
                condition_error = "{} != {}; Call(number={}): {}".format(
                    idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
                )
                self.assertTrue(condition, msg=condition_error)

    def test_set_config_modify(self):
        verify_ssl_values = (None, True, False)
        for verify_ssl_value in verify_ssl_values:
            cimc.DETAILS.clear()
            opts = {
                "proxy": {
                    "host": "TheHost",
                    "username": "TheUsername",
                    "password": "ThePassword",
                    "verify_ssl": verify_ssl_value,
                }
            }
            http_query_mock = MagicMock(side_effect=http_query_response)
            if verify_ssl_value is None:
                expected_verify_ssl_value = True
            else:
                expected_verify_ssl_value = verify_ssl_value

            # Let's init the proxy and ignore it's actions, this test is not about them
            with patch(
                "salt.proxy.cimc.get_config_resolver_class",
                MagicMock(return_value=True),
            ):
                cimc.init(opts)

            log.debug(
                "verify_ssl: %s // expected verify_ssl: %s",
                verify_ssl_value,
                expected_verify_ssl_value,
            )

            with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
                cimc.set_config_modify(
                    dn="sys/rack-unit-1/locator-led",
                    inconfig=(
                        "<inConfig><equipmentLocatorLed adminState='on'"
                        " dn='sys/rack-unit-1/locator-led'></equipmentLocatorLed></inConfig>"
                    ),
                )

            for idx, call in enumerate(http_query_mock.mock_calls, 1):
                condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
                condition_error = "{} != {}; Call(number={}): {}".format(
                    idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
                )
                self.assertTrue(condition, msg=condition_error)
