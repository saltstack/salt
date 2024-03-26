"""
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
"""

import datetime

import salt.utils.ssdp as ssdp
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class Mocks:
    def get_socket_mock(self, expected_ip, expected_hostname):
        """
        Get a mock of a socket
        :return:
        """
        sck = MagicMock()
        sck.getsockname = MagicMock(return_value=(expected_ip, 123456))

        sock_mock = MagicMock()
        sock_mock.socket = MagicMock(return_value=sck)
        sock_mock.gethostname = MagicMock(return_value=expected_hostname)
        sock_mock.gethostbyname = MagicMock(return_value=expected_ip)

        return sock_mock

    def get_ssdp_factory(self, expected_ip=None, expected_hostname=None, **config):
        if expected_ip is None:
            expected_ip = "127.0.0.1"
        if expected_hostname is None:
            expected_hostname = "localhost"
        sock_mock = self.get_socket_mock(expected_ip, expected_hostname)
        with patch("salt.utils.ssdp.socket", sock_mock):
            factory = ssdp.SSDPFactory(**config)
        return factory

    def get_ssdp_discovery_client(
        self, expected_ip=None, expected_hostname=None, **config
    ):
        if expected_ip is None:
            expected_ip = "127.0.0.1"
        if expected_hostname is None:
            expected_hostname = "localhost"
        sock_mock = self.get_socket_mock(expected_ip, expected_hostname)
        with patch("salt.utils.ssdp.socket", sock_mock):
            factory = ssdp.SSDPDiscoveryClient(**config)
        return factory

    def get_ssdp_discovery_server(
        self, expected_ip=None, expected_hostname=None, **config
    ):
        if expected_ip is None:
            expected_ip = "127.0.0.1"
        if expected_hostname is None:
            expected_hostname = "localhost"
        sock_mock = self.get_socket_mock(expected_ip, expected_hostname)
        with patch("salt.utils.ssdp.socket", sock_mock):
            factory = ssdp.SSDPDiscoveryServer(**config)
        return factory


class SSDPBaseTestCase(TestCase, Mocks):
    """
    TestCase for SSDP-related parts.
    """

    @staticmethod
    def exception_generic(*args, **kwargs):
        """
        Side effect
        :return:
        """
        raise Exception("some network error")

    @staticmethod
    def exception_attr_error(*args, **kwargs):
        """
        Side effect
        :return:
        """
        raise AttributeError(f"attribute error: {args}. {kwargs}")

    @patch("salt.utils.ssdp._json", None)
    @patch("salt.utils.ssdp.asyncio", None)
    def test_base_avail(self):
        """
        Test SSDP base class availability method.
        :return:
        """
        base = ssdp.SSDPBase()
        assert not base._is_available()

        with patch("salt.utils.ssdp._json", True):
            assert not base._is_available()

        with patch("salt.utils.ssdp.asyncio", True):
            assert not base._is_available()

        with patch("salt.utils.ssdp._json", True), patch(
            "salt.utils.ssdp.asyncio", True
        ):
            assert base._is_available()

    def test_base_protocol_settings(self):
        """
        Tests default constants data.
        :return:
        """
        base = ssdp.SSDPBase()
        v_keys = ["signature", "answer", "port", "listen_ip", "timeout"]
        v_vals = ["__salt_master_service", {}, 4520, "0.0.0.0", 3]
        for key in v_keys:
            assert key in base.DEFAULTS

        for key in base.DEFAULTS:
            assert key in v_keys

        for key, value in zip(v_keys, v_vals):
            assert base.DEFAULTS[key] == value

    def test_base_self_ip(self):
        """
        Test getting self IP method.

        :return:
        """
        base = ssdp.SSDPBase()
        expected_ip = "192.168.1.10"
        expected_host = "oxygen"
        sock_mock = self.get_socket_mock(expected_ip, expected_host)

        with patch("salt.utils.ssdp.socket", sock_mock):
            assert base.get_self_ip() == expected_ip

        sock_mock.socket().getsockname.side_effect = SSDPBaseTestCase.exception_generic
        with patch("salt.utils.ssdp.socket", sock_mock):
            assert base.get_self_ip() == expected_ip


class SSDPFactoryTestCase(TestCase, Mocks):
    """
    Test socket protocol
    """

    def test_attr_check(self):
        """
        Tests attributes are set to the base class

        :return:
        """
        config = {
            ssdp.SSDPBase.SIGNATURE: "-signature-",
            ssdp.SSDPBase.ANSWER: {"this-is": "the-answer"},
        }
        expected_ip = "10.10.10.10"
        factory = self.get_ssdp_factory(expected_ip=expected_ip, **config)
        for attr in [ssdp.SSDPBase.SIGNATURE, ssdp.SSDPBase.ANSWER]:
            assert hasattr(factory, attr)
            assert getattr(factory, attr) == config[attr]
        assert not factory.disable_hidden
        assert factory.my_ip == expected_ip

    def test_transport_sendto_success(self):
        """
        Test transport send_to.

        :return:
        """
        transport = MagicMock()
        log = MagicMock()
        factory = self.get_ssdp_factory()
        with patch.object(factory, "transport", transport), patch.object(
            factory, "log", log
        ):
            data = {"some": "data"}
            addr = "10.10.10.10"
            factory._sendto(data=data, addr=addr)
            assert factory.transport.sendto.called
            assert factory.transport.sendto.mock_calls[0][1][0]["some"] == "data"
            assert factory.transport.sendto.mock_calls[0][2]["addr"] == "10.10.10.10"
            assert factory.log.debug.called
            assert factory.log.debug.mock_calls[0][1][0] == "Sent successfully"

    def test_transport_sendto_retry(self):
        """
        Test transport send_to.

        :return:
        """
        with patch("salt.utils.ssdp.time.sleep", MagicMock()):
            transport = MagicMock()
            transport.sendto = MagicMock(
                side_effect=SSDPBaseTestCase.exception_attr_error
            )
            log = MagicMock()
            factory = self.get_ssdp_factory()
            with patch.object(factory, "transport", transport), patch.object(
                factory, "log", log
            ):
                data = {"some": "data"}
                addr = "10.10.10.10"
                factory._sendto(data=data, addr=addr)
                assert factory.transport.sendto.called
                assert ssdp.time.sleep.called
                assert (
                    ssdp.time.sleep.call_args[0][0] > 0
                    and ssdp.time.sleep.call_args[0][0] < 0.5
                )
                assert factory.log.debug.called
                assert "Permission error" in factory.log.debug.mock_calls[0][1][0]

    def test_datagram_signature_bad(self):
        """
        Test datagram_received on bad signature

        :return:
        """
        factory = self.get_ssdp_factory()
        data = "nonsense"
        addr = "10.10.10.10", "foo.suse.de"

        with patch.object(factory, "log", MagicMock()):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert "Received bad signature from" in factory.log.debug.call_args[0][0]
            assert factory.log.debug.call_args[0][1] == addr[0]
            assert factory.log.debug.call_args[0][2] == addr[1]

    def test_datagram_signature_wrong_timestamp_quiet(self):
        """
        Test datagram receives a wrong timestamp (no reply).

        :return:
        """
        factory = self.get_ssdp_factory()
        data = f"{ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]}nonsense"
        addr = "10.10.10.10", "foo.suse.de"
        with patch.object(factory, "log", MagicMock()), patch.object(
            factory, "_sendto", MagicMock()
        ):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert (
                "Received invalid timestamp in package"
                in factory.log.debug.call_args[0][0]
            )
            assert not factory._sendto.called

    def test_datagram_signature_wrong_timestamp_reply(self):
        """
        Test datagram receives a wrong timestamp.

        :return:
        """
        factory = self.get_ssdp_factory()
        factory.disable_hidden = True
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = f"{signature}nonsense"
        addr = "10.10.10.10", "foo.suse.de"
        with patch.object(factory, "log", MagicMock()), patch.object(
            factory, "_sendto", MagicMock()
        ):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert (
                "Received invalid timestamp in package"
                in factory.log.debug.call_args[0][0]
            )
            assert factory._sendto.called
            assert f"{signature}:E:Invalid timestamp" == factory._sendto.call_args[0][0]

    def test_datagram_signature_outdated_timestamp_quiet(self):
        """
        Test if datagram processing reacts on outdated message (more than 20 seconds). Quiet mode.
        :return:
        """
        factory = self.get_ssdp_factory()
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = "{}{}".format(signature, "1516623820")
        addr = "10.10.10.10", "foo.suse.de"

        ahead_dt = datetime.datetime.fromtimestamp(1516623841)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(factory, "log", MagicMock()), patch.object(
            factory, "_sendto"
        ), patch("salt.utils.ssdp.datetime.datetime", MagicMock()), patch(
            "salt.utils.ssdp.datetime.datetime.now", MagicMock(return_value=ahead_dt)
        ), patch(
            "salt.utils.ssdp.datetime.datetime.fromtimestamp",
            MagicMock(return_value=curnt_dt),
        ), patch(
            "salt.utils.ssdp.datetime.timedelta", MagicMock(return_value=delta)
        ):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert not factory.disable_hidden
            assert not factory._sendto.called
            assert "Received outdated package" in factory.log.debug.call_args[0][0]

    def test_datagram_signature_outdated_timestamp_reply(self):
        """
        Test if datagram processing reacts on outdated message (more than 20 seconds). Reply mode.
        :return:
        """
        factory = self.get_ssdp_factory()
        factory.disable_hidden = True
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = "{}{}".format(signature, "1516623820")
        addr = "10.10.10.10", "foo.suse.de"

        ahead_dt = datetime.datetime.fromtimestamp(1516623841)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(factory, "log", MagicMock()), patch.object(
            factory, "_sendto"
        ), patch("salt.utils.ssdp.datetime.datetime", MagicMock()), patch(
            "salt.utils.ssdp.datetime.datetime.now", MagicMock(return_value=ahead_dt)
        ), patch(
            "salt.utils.ssdp.datetime.datetime.fromtimestamp",
            MagicMock(return_value=curnt_dt),
        ), patch(
            "salt.utils.ssdp.datetime.timedelta", MagicMock(return_value=delta)
        ):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert factory.disable_hidden
            assert factory._sendto.called
            assert (
                factory._sendto.call_args[0][0] == f"{signature}:E:Timestamp is too old"
            )
            assert "Received outdated package" in factory.log.debug.call_args[0][0]

    def test_datagram_signature_correct_timestamp_reply(self):
        """
        Test if datagram processing sends out correct reply within 20 seconds.
        :return:
        """
        factory = self.get_ssdp_factory()
        factory.disable_hidden = True
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = "{}{}".format(signature, "1516623820")
        addr = "10.10.10.10", "foo.suse.de"

        ahead_dt = datetime.datetime.fromtimestamp(1516623840)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(factory, "log", MagicMock()), patch.object(
            factory, "_sendto"
        ), patch("salt.utils.ssdp.datetime.datetime", MagicMock()), patch(
            "salt.utils.ssdp.datetime.datetime.now", MagicMock(return_value=ahead_dt)
        ), patch(
            "salt.utils.ssdp.datetime.datetime.fromtimestamp",
            MagicMock(return_value=curnt_dt),
        ), patch(
            "salt.utils.ssdp.datetime.timedelta", MagicMock(return_value=delta)
        ):
            factory.datagram_received(data=data, addr=addr)
            assert factory.log.debug.called
            assert factory.disable_hidden
            assert factory._sendto.called
            assert factory._sendto.call_args[0][0] == salt.utils.stringutils.to_bytes(
                f"{signature}:@:{{}}"
            )
            assert 'Received "%s" from %s:%s' in factory.log.debug.call_args[0][0]


class SSDPServerTestCase(TestCase, Mocks):
    """
    Server-related test cases
    """

    def test_config_detached(self):
        """
        Test if configuration is not a reference.
        :return:
        """
        old_ip = "10.10.10.10"
        new_ip = "20.20.20.20"
        config = {"answer": {"master": old_ip}}
        with patch(
            "salt.utils.ssdp.SSDPDiscoveryServer.get_self_ip",
            MagicMock(return_value=new_ip),
        ):
            srv = ssdp.SSDPDiscoveryServer(**config)
            assert srv._config["answer"]["master"] == new_ip
            assert config["answer"]["master"] == old_ip

    def test_run(self):
        """
        Test server runner.
        :return:
        """
        with patch("salt.utils.ssdp.SSDPFactory", MagicMock()):
            config = {
                "answer": {"master": "10.10.10.10"},
                ssdp.SSDPBase.LISTEN_IP: "10.10.10.10",
                ssdp.SSDPBase.PORT: 12345,
            }
            srv = self.get_ssdp_discovery_server(**config)
            srv.create_datagram_endpoint = MagicMock()
            srv.log = MagicMock()

            trnsp = MagicMock()
            proto = MagicMock()
            loop = MagicMock()
            loop.run_until_complete = MagicMock(return_value=(trnsp, proto))

            io = MagicMock()
            io.ported = False
            io.get_event_loop = MagicMock(return_value=loop)

            with patch("salt.utils.ssdp.asyncio", io):
                srv.run()
                cde_args = io.get_event_loop().create_datagram_endpoint.call_args[1]
                cfg_ip_addr, cfg_port = cde_args["local_addr"]

                assert io.get_event_loop.called
                assert io.get_event_loop().run_until_complete.called
                assert io.get_event_loop().create_datagram_endpoint.called
                assert io.get_event_loop().run_forever.called
                assert trnsp.close.called
                assert loop.close.called
                assert srv.log.info.called
                assert (
                    srv.log.info.call_args[0][0]
                    == "Stopping service discovery listener."
                )
                assert "allow_broadcast" in cde_args
                assert cde_args["allow_broadcast"]
                assert "local_addr" in cde_args
                assert (
                    not cfg_ip_addr == ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.LISTEN_IP]
                    and cfg_ip_addr == "10.10.10.10"
                )
                assert (
                    not cfg_port == ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.PORT]
                    and cfg_port == 12345
                )


class SSDPClientTestCase(TestCase, Mocks):
    """
    Client-related test cases
    """

    class Resource:
        """
        Fake network reader
        """

        def __init__(self):
            self.pool = [
                ("some", "10.10.10.10"),
                ("data", "20.20.20.20"),
                ("data", "10.10.10.10"),
                (None, None),
            ]

        def read(self, *args, **kwargs):
            return self.pool.pop(0)

    def test_config_passed(self):
        """
        Test if the configuration is passed.
        :return:
        """
        config = {
            ssdp.SSDPBase.SIGNATURE: "SUSE Enterprise Server",
            ssdp.SSDPBase.TIMEOUT: 5,
            ssdp.SSDPBase.PORT: 12345,
        }
        clnt = self.get_ssdp_discovery_client(**config)
        assert clnt._config[ssdp.SSDPBase.SIGNATURE] == config[ssdp.SSDPBase.SIGNATURE]
        assert clnt._config[ssdp.SSDPBase.PORT] == config[ssdp.SSDPBase.PORT]
        assert clnt._config[ssdp.SSDPBase.TIMEOUT] == config[ssdp.SSDPBase.TIMEOUT]

    def test_config_detached(self):
        """
        Test if the passed configuration is not a reference.
        :return:
        """
        config = {
            ssdp.SSDPBase.SIGNATURE: "SUSE Enterprise Server",
        }
        clnt = self.get_ssdp_discovery_client(**config)
        clnt._config["foo"] = "bar"
        assert "foo" in clnt._config
        assert "foo" not in config

    def test_query(self):
        """
        Test if client queries the broadcast
        :return:
        """
        config = {
            ssdp.SSDPBase.SIGNATURE: "SUSE Enterprise Server",
            ssdp.SSDPBase.PORT: 4000,
        }
        f_time = 1111
        _socket = MagicMock()
        with patch("salt.utils.ssdp.socket", _socket), patch(
            "salt.utils.ssdp.time.time", MagicMock(return_value=f_time)
        ):
            clnt = ssdp.SSDPDiscoveryClient(**config)
            clnt._query()
            assert clnt._socket.sendto.called
            message, target = clnt._socket.sendto.call_args[0]
            assert message == salt.utils.stringutils.to_bytes(
                f"{config[ssdp.SSDPBase.SIGNATURE]}{f_time}"
            )
            assert target[0] == "<broadcast>"
            assert target[1] == config[ssdp.SSDPBase.PORT]

    def test_get_masters_map(self):
        """
        Test getting map of the available masters on the network
        :return:
        """
        _socket = MagicMock()
        response = {}
        with patch("salt.utils.ssdp.socket", _socket):
            clnt = ssdp.SSDPDiscoveryClient()
            clnt._socket.recvfrom = SSDPClientTestCase.Resource().read
            clnt.log = MagicMock()
            clnt._collect_masters_map(response=response)
            assert "10.10.10.10" in response
            assert "20.20.20.20" in response
            assert response["10.10.10.10"] == ["some", "data"]
            assert response["20.20.20.20"] == ["data"]

    def test_get_masters_map_error_handling(self):
        """
        Test getting map handles timeout network exception
        :return:
        """
        _socket = MagicMock()
        response = {}
        error_msg = "fake testing timeout just had happened"
        with patch("salt.utils.ssdp.socket", _socket):
            clnt = ssdp.SSDPDiscoveryClient()
            clnt._socket.recvfrom = MagicMock(side_effect=Exception(error_msg))
            clnt.log = MagicMock()
            clnt._collect_masters_map(response=response)
            assert clnt.log.error.called
            assert (
                "Discovery master collection failure" in clnt.log.error.call_args[0][0]
            )
            assert error_msg == str(clnt.log.error.call_args[0][1])
            assert not response

    def test_discover_no_masters(self):
        """
        Test discover available master on the network (none found).
        :return:
        """

        clnt = self.get_ssdp_discovery_client()
        clnt._query = MagicMock()
        clnt._collect_masters_map = MagicMock()
        clnt.log = MagicMock()
        clnt.discover()

        assert clnt.log.info.called
        assert clnt.log.info.call_args[0][0] == "No master has been discovered."

    def test_discover_general_error(self):
        """
        Test discover available master on the network (erroneous found)
        :return:
        """

        _socket = MagicMock()
        error = "Admins on strike due to broken coffee machine"
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        fake_resource = SSDPClientTestCase.Resource()
        fake_resource.pool = [
            (f"{signature}:E:{error}", "10.10.10.10"),
            (None, None),
        ]

        with patch("salt.utils.ssdp.socket", _socket):
            clnt = ssdp.SSDPDiscoveryClient()
            clnt._socket.recvfrom = fake_resource.read
            clnt._query = MagicMock()
            clnt.log = MagicMock()
            clnt.discover()
            assert len(clnt.log.error.mock_calls) == 1
            assert (
                "Error response from the service publisher"
                in clnt.log.error.call_args[0][0]
            )
            assert "10.10.10.10" == clnt.log.error.call_args[0][1]
            assert clnt.log.error.call_args[1] == {}
            assert clnt.log.error.call_args[0][2] == error

    def test_discover_timestamp_error(self):
        """
        Test discover available master on the network (outdated timestamp)
        :return:
        """

        _socket = MagicMock()
        error = (
            "We only support a 1200 bps connection. Routing timestamp problems on"
            " neural net."
        )
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        fake_resource = SSDPClientTestCase.Resource()
        fake_resource.pool = [
            (f"{signature}:E:{error}", "10.10.10.10"),
            (None, None),
        ]

        with patch("salt.utils.ssdp.socket", _socket):
            clnt = ssdp.SSDPDiscoveryClient()
            clnt._socket.recvfrom = fake_resource.read
            clnt._query = MagicMock()
            clnt.log = MagicMock()
            clnt.discover()
            assert len(clnt.log.error.mock_calls) == 2
            assert (
                "Error response from the service publisher"
                in clnt.log.error.mock_calls[0][1][0]
            )
            assert clnt.log.error.mock_calls[0][1][2] == error
            assert clnt.log.error.mock_calls[0][2] == {}
            assert (
                "Publisher sent shifted timestamp" in clnt.log.error.mock_calls[1][1][0]
            )
            assert (
                clnt.log.error.mock_calls[1][1][1]
                == clnt.log.error.mock_calls[0][1][1]
                == "10.10.10.10"
            )
