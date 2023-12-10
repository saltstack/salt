"""
tests.unit.proxy.test_cimc
~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the cimc proxy module
"""

import logging

import pytest

import salt.exceptions
import salt.proxy.cimc as cimc
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def http_query_response(*args, data=None, **kwargs):
    log.debug(
        "http_query_response side_effect; ARGS: %s // KWARGS: %s // DATA: %s",
        args,
        kwargs,
        data,
    )
    login_response = """\
    <aaaLogin
        response="yes"
        outCookie="real-cookie"
        outRefreshPeriod="600"
        outPriv="admin">
    </aaaLogin>"""
    logout_response = """\
    <aaaLogout
        cookie="real-cookie"
        response="yes"
        outStatus="success">
    </aaaLogout>
    """
    config_resolve_class_response = """\
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
    config_con_mo_response = """\
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

    if data.startswith("<aaaLogin"):
        response = login_response
    elif data.startswith("<aaaLogout"):
        response = logout_response
    elif data.startswith("<configResolveClass"):
        response = config_resolve_class_response
    elif data.startswith("<configConfMo"):
        response = config_con_mo_response
    else:
        response = ""
    return {"text": response, "status": 200}


@pytest.fixture
def configure_loader_modules():
    with patch.dict(cimc.DETAILS):
        yield {cimc: {"__pillar__": {}}}


@pytest.fixture(params=[None, True, False])
def verify_ssl(request):
    return request.param


@pytest.fixture
def opts(verify_ssl):
    return {
        "proxy": {
            "host": "TheHost",
            "username": "TheUsername",
            "password": "ThePassword",
            "verify_ssl": verify_ssl,
        }
    }


def _get_expected_verify_ssl(verify_ssl):
    expected = True if verify_ssl is None else verify_ssl

    log.debug(
        "verify_ssl: %s // expected verify_ssl: %s",
        verify_ssl,
        expected,
    )

    return expected


def test_init():
    # No host, returns False
    opts = {"proxy": {"username": "xxxx", "password": "xxx"}}
    ret = cimc.init(opts)
    assert not ret

    # No username , returns False
    opts = {"proxy": {"password": "xxx", "host": "cimc"}}
    ret = cimc.init(opts)
    assert not ret

    # No password, returns False
    opts = {"proxy": {"username": "xxxx", "host": "cimc"}}
    ret = cimc.init(opts)
    assert not ret

    opts = {"proxy": {"username": "xxxx", "password": "xxx", "host": "cimc"}}
    with patch.object(cimc, "logon", return_value="9zVG5U8DFZNsTR"):
        with patch.object(cimc, "get_config_resolver_class", return_value="True"):
            ret = cimc.init(opts)
            assert cimc.DETAILS["url"] == "https://cimc/nuova"
            assert cimc.DETAILS["username"] == "xxxx"
            assert cimc.DETAILS["password"] == "xxx"
            assert cimc.DETAILS["initialized"]


def test__validate_response_code():
    with pytest.raises(
        salt.exceptions.CommandExecutionError,
        match="Did not receive a valid response from host.",
    ):
        cimc._validate_response_code("404")

    with patch.object(cimc, "logout", return_value=True) as mock_logout:
        with pytest.raises(
            salt.exceptions.CommandExecutionError,
            match="Did not receive a valid response from host.",
        ):
            cimc._validate_response_code("404", "9zVG5U8DFZNsTR")
            mock_logout.assert_called_once_with("9zVG5U8DFZNsTR")


def test_init_with_ssl(verify_ssl, opts):
    http_query_mock = MagicMock(side_effect=http_query_response)
    expected_verify_ssl_value = _get_expected_verify_ssl(verify_ssl)

    with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
        cimc.init(opts)

    for idx, call in enumerate(http_query_mock.mock_calls, 1):
        condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
        condition_error = "{} != {}; Call(number={}): {}".format(
            idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
        )
        assert condition, condition_error


def test_logon(opts, verify_ssl):
    http_query_mock = MagicMock(side_effect=http_query_response)
    expected_verify_ssl_value = _get_expected_verify_ssl(verify_ssl)

    # Let's init the proxy and ignore it's actions, this test is not about them
    with patch(
        "salt.proxy.cimc.get_config_resolver_class",
        MagicMock(return_value=True),
    ):
        cimc.init(opts)

    with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
        cimc.logon()

    for idx, call in enumerate(http_query_mock.mock_calls, 1):
        condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
        condition_error = "{} != {}; Call(number={}): {}".format(
            idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
        )
        assert condition, condition_error


def test_logout(opts, verify_ssl):
    http_query_mock = MagicMock(side_effect=http_query_response)
    expected_verify_ssl_value = _get_expected_verify_ssl(verify_ssl)

    # Let's init the proxy and ignore it's actions, this test is not about them
    with patch(
        "salt.proxy.cimc.get_config_resolver_class",
        MagicMock(return_value=True),
    ):
        cimc.init(opts)

    with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
        cimc.logout()

    for idx, call in enumerate(http_query_mock.mock_calls, 1):
        condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
        condition_error = "{} != {}; Call(number={}): {}".format(
            idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
        )
        assert condition, condition_error


def test_grains(opts, verify_ssl):
    http_query_mock = MagicMock(side_effect=http_query_response)
    expected_verify_ssl_value = _get_expected_verify_ssl(verify_ssl)

    # Let's init the proxy and ignore it's actions, this test is not about them
    with patch(
        "salt.proxy.cimc.get_config_resolver_class",
        MagicMock(return_value=True),
    ):
        cimc.init(opts)

    with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
        cimc.grains()

    for idx, call in enumerate(http_query_mock.mock_calls, 1):
        condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
        condition_error = "{} != {}; Call(number={}): {}".format(
            idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
        )
        assert condition, condition_error


def test_grains_refresh(opts, verify_ssl):
    http_query_mock = MagicMock(side_effect=http_query_response)
    expected_verify_ssl_value = _get_expected_verify_ssl(verify_ssl)

    # Let's init the proxy and ignore it's actions, this test is not about them
    with patch(
        "salt.proxy.cimc.get_config_resolver_class",
        MagicMock(return_value=True),
    ):
        cimc.init(opts)

    with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
        cimc.grains_refresh()

    for idx, call in enumerate(http_query_mock.mock_calls, 1):
        condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
        condition_error = "{} != {}; Call(number={}): {}".format(
            idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
        )
        assert condition, condition_error


def test_ping(opts, verify_ssl):
    http_query_mock = MagicMock(side_effect=http_query_response)
    expected_verify_ssl_value = _get_expected_verify_ssl(verify_ssl)

    # Let's init the proxy and ignore it's actions, this test is not about them
    with patch(
        "salt.proxy.cimc.get_config_resolver_class",
        MagicMock(return_value=True),
    ):
        cimc.init(opts)

    with patch.dict(cimc.__utils__, {"http.query": http_query_mock}):
        cimc.ping()

    for idx, call in enumerate(http_query_mock.mock_calls, 1):
        condition = call.kwargs["verify_ssl"] is expected_verify_ssl_value
        condition_error = "{} != {}; Call(number={}): {}".format(
            idx, call, call.kwargs["verify_ssl"], expected_verify_ssl_value
        )
        assert condition, condition_error


def test_set_config_modify(opts, verify_ssl):
    http_query_mock = MagicMock(side_effect=http_query_response)
    expected_verify_ssl_value = _get_expected_verify_ssl(verify_ssl)

    # Let's init the proxy and ignore it's actions, this test is not about them
    with patch(
        "salt.proxy.cimc.get_config_resolver_class",
        MagicMock(return_value=True),
    ):
        cimc.init(opts)

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
        assert condition, condition_error
