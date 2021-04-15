"""
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
"""

import datetime
import socket

import salt.utils.json
import salt.utils.ssdp as ssdp
import salt.utils.stringutils
from tests.support.mock import MagicMock, PropertyMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import pytest
except ImportError:
    pytest = None


class Mocks:
    def get_socket_mock(self, expected_ip, expected_hostname):
        """
        Get a mock of a socket
        :return:
        """
        sck = MagicMock()
        sck.getsockname = MagicMock(return_value=(expected_ip, 123456))

        sock_mock = MagicMock()
        sock_mock.timeout = socket.timeout
        sock_mock.socket = MagicMock(return_value=sck)
        sock_mock.gethostname = MagicMock(return_value=expected_hostname)
        sock_mock.gethostbyname = MagicMock(return_value=expected_ip)
        type(sock_mock).SOL_SOCKET = PropertyMock(return_value=socket.SOL_SOCKET)
        type(sock_mock).SO_REUSEPORT = PropertyMock(return_value=socket.SO_REUSEPORT)
        type(sock_mock).SO_BROADCAST = PropertyMock(return_value=socket.SO_BROADCAST)

        return sock_mock

    def get_ssdp_protocol(self, expected_ip=None, expected_hostname=None, **config):
        if expected_ip is None:
            expected_ip = "127.0.0.1"
        if expected_hostname is None:
            expected_hostname = "localhost"
        sock_mock = self.get_socket_mock(expected_ip, expected_hostname)
        with patch("salt.utils.ssdp.socket", sock_mock):
            protocol = ssdp.SSDPProtocol(**config)
        return protocol

    def get_ssdp_discovery_client(
        self, expected_ip=None, expected_hostname=None, **config
    ):
        if expected_ip is None:
            expected_ip = "127.0.0.1"
        if expected_hostname is None:
            expected_hostname = "localhost"
        sock_mock = self.get_socket_mock(expected_ip, expected_hostname)
        with patch("salt.utils.ssdp.socket", sock_mock):
            protocol = ssdp.SSDPDiscoveryClient(**config)
        return protocol

    def get_ssdp_discovery_server(
        self, expected_ip=None, expected_hostname=None, **config
    ):
        if expected_ip is None:
            expected_ip = "127.0.0.1"
        if expected_hostname is None:
            expected_hostname = "localhost"
        sock_mock = self.get_socket_mock(expected_ip, expected_hostname)
        with patch("salt.utils.ssdp.socket", sock_mock):
            protocol = ssdp.SSDPDiscoveryServer(**config)
        return protocol

    def get_network_interfaces_mock(self):
        return MagicMock(
            return_value={
                "lo": {
                    "hwaddr": "00:00:00:00:00:00",
                    "inet": [
                        {
                            "address": "127.0.0.1",
                            "broadcast": None,
                            "label": "lo",
                            "netmask": "255.0.0.0",
                        }
                    ],
                    "inet6": [{"address": "::1", "prefixlen": "128", "scope": "host"}],
                    "up": True,
                },
                "eth0": {
                    "hwaddr": "00:00:00:00:00:00",
                    "inet": [
                        {
                            "address": "10.0.0.10",
                            "broadcast": "10.0.0.255",
                            "label": "eth0",
                            "netmask": "255.255.255.0",
                        }
                    ],
                    "inet6": [
                        {
                            "address": "fd00:1234:5678:1::1",
                            "prefixlen": "64",
                            "scope": "link",
                        }
                    ],
                    "up": True,
                },
            }
        )


@skipIf(pytest is None, "PyTest is missing")
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
        raise AttributeError("attribute error: {}. {}".format(args, kwargs))

    def test_base_protocol_settings(self):
        """
        Tests default constants data.
        :return:
        """
        base = ssdp.SSDPBase()
        v_keys = ["signature", "answer", "port", "interface_ip", "timeout"]
        v_vals = ["__salt_master_service", {}, 4520, "0.0.0.0", 3]
        for key in v_keys:
            assert key in base.DEFAULTS

        for key in base.DEFAULTS:
            assert key in v_keys

        for key, value in zip(v_keys, v_vals):
            assert base.DEFAULTS[key] == value


@skipIf(pytest is None, "PyTest is missing")
class SSDPProtocolTestCase(TestCase, Mocks):
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
        protocol = self.get_ssdp_protocol(expected_ip=expected_ip, **config)
        for attr in [ssdp.SSDPBase.SIGNATURE, ssdp.SSDPBase.ANSWER]:
            assert hasattr(protocol, attr)
            assert getattr(protocol, attr) == config[attr]
        assert protocol.hidden

    def test_transport_sendto_success(self):
        """
        Test transport send_to.

        :return:
        """
        transport = MagicMock()
        log = MagicMock()
        protocol = self.get_ssdp_protocol()
        with patch.object(protocol, "transport", transport), patch.object(
            protocol, "log", log
        ):
            data = {"some": "data"}
            addr = "10.10.10.10"
            protocol._sendto(data=data, addr=addr)
            assert protocol.transport.sendto.called
            assert protocol.transport.sendto.mock_calls[0][1][0]["some"] == "data"
            assert protocol.transport.sendto.mock_calls[0][2]["addr"] == "10.10.10.10"
            assert protocol.log.debug.called
            assert (
                protocol.log.debug.mock_calls[0][1][0]
                == "Service discovery message sent successfully"
            )

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
            protocol = self.get_ssdp_protocol()
            with patch.object(protocol, "transport", transport), patch.object(
                protocol, "log", log
            ):
                data = {"some": "data"}
                addr = "10.10.10.10"
                protocol._sendto(data=data, addr=addr)
                assert protocol.transport.sendto.called
                assert ssdp.time.sleep.called
                assert (
                    ssdp.time.sleep.call_args[0][0] > 0
                    and ssdp.time.sleep.call_args[0][0] < 0.5
                )
                assert protocol.log.error.called
                assert "Permission error" in protocol.log.error.mock_calls[0][1][0]

    def test_datagram_signature_bad(self):
        """
        Test datagram_received on bad signature

        :return:
        """
        protocol = self.get_ssdp_protocol()
        data = "nonsense"
        addr = "10.10.10.10", "foo.suse.de"

        with patch.object(protocol, "log", MagicMock()):
            protocol.datagram_received(data=data, addr=addr)
            assert protocol.log.error.called
            assert "Invalid signature" in protocol.log.error.call_args[0][-1]
            assert protocol.log.error.call_args[0][1] == addr[0]
            assert protocol.log.error.call_args[0][2] == addr[1]

    def test_datagram_signature_wrong_timestamp_quiet(self):
        """
        Test datagram receives a wrong timestamp (no reply).

        :return:
        """
        protocol = self.get_ssdp_protocol()
        data = "{}nonsense".format(ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE])
        addr = "10.10.10.10", "foo.suse.de"
        with patch.object(protocol, "log", MagicMock()), patch.object(
            protocol, "_sendto", MagicMock()
        ):
            protocol.datagram_received(data=data, addr=addr)
            assert protocol.log.error.called
            assert "Invalid timestamp" in protocol.log.error.call_args[0][-1]
            assert not protocol._sendto.called

    def test_datagram_signature_wrong_timestamp_reply(self):
        """
        Test datagram receives a wrong timestamp.

        :return:
        """
        protocol = self.get_ssdp_protocol()
        protocol.hidden = False
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = "{}nonsense".format(signature)
        addr = "10.10.10.10", "foo.suse.de"
        with patch.object(protocol, "log", MagicMock()), patch.object(
            protocol, "_sendto", MagicMock()
        ):
            protocol.datagram_received(data=data, addr=addr)
            assert protocol.log.error.called
            assert "Invalid timestamp" in protocol.log.error.call_args[0][-1]
            assert protocol._sendto.called
            assert (
                "{}:E:Invalid timestamp".format(signature)
                == protocol._sendto.call_args[0][0]
            )

    def test_datagram_signature_outdated_timestamp_quiet(self):
        """
        Test if datagram processing reacts on outdated message (more than 20 seconds). Quiet mode.
        :return:
        """
        protocol = self.get_ssdp_protocol()
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = "{}{}".format(signature, "1516623820")
        addr = "10.10.10.10", "foo.suse.de"

        ahead_dt = datetime.datetime.fromtimestamp(1516623841)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(protocol, "log", MagicMock()), patch.object(
            protocol, "_sendto"
        ), patch("salt.utils.ssdp.datetime.datetime", MagicMock()), patch(
            "salt.utils.ssdp.datetime.datetime.now", MagicMock(return_value=ahead_dt)
        ), patch(
            "salt.utils.ssdp.datetime.datetime.fromtimestamp",
            MagicMock(return_value=curnt_dt),
        ), patch(
            "salt.utils.ssdp.datetime.timedelta", MagicMock(return_value=delta)
        ):
            protocol.datagram_received(data=data, addr=addr)
            assert protocol.log.error.called
            assert "Invalid timestamp" in protocol.log.error.call_args[0][-1]
            assert not protocol._sendto.called

    def test_datagram_signature_outdated_timestamp_reply(self):
        """
        Test if datagram processing reacts on outdated message (more than 20 seconds). Reply mode.
        :return:
        """
        protocol = self.get_ssdp_protocol()
        protocol.hidden = False
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = "{}{}".format(signature, "1516623820")
        addr = "10.10.10.10", "foo.suse.de"

        ahead_dt = datetime.datetime.fromtimestamp(1516623841)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(protocol, "log", MagicMock()), patch.object(
            protocol, "_sendto"
        ), patch("salt.utils.ssdp.datetime.datetime", MagicMock()), patch(
            "salt.utils.ssdp.datetime.datetime.now", MagicMock(return_value=ahead_dt)
        ), patch(
            "salt.utils.ssdp.datetime.datetime.fromtimestamp",
            MagicMock(return_value=curnt_dt),
        ), patch(
            "salt.utils.ssdp.datetime.timedelta", MagicMock(return_value=delta)
        ):
            protocol.datagram_received(data=data, addr=addr)
            assert protocol.log.error.called
            assert "Invalid timestamp" in protocol.log.error.call_args[0][-1]
            assert protocol._sendto.called
            assert (
                "{}:E:Invalid timestamp".format(signature)
                == protocol._sendto.call_args[0][0]
            )

    def test_datagram_signature_correct_timestamp_reply(self):
        """
        Test if datagram processing sends out correct reply within 20 seconds.
        :return:
        """
        protocol = self.get_ssdp_protocol()
        protocol.hidden = False
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        data = "{}{}".format(signature, "1516623820")
        addr = "10.10.10.10", "foo.suse.de"

        ahead_dt = datetime.datetime.fromtimestamp(1516623840)
        curnt_dt = datetime.datetime.fromtimestamp(1516623820)
        delta = datetime.timedelta(0, 20)
        with patch.object(protocol, "log", MagicMock()), patch.object(
            protocol, "_sendto"
        ), patch("salt.utils.ssdp.datetime.datetime", MagicMock()), patch(
            "salt.utils.ssdp.datetime.datetime.now", MagicMock(return_value=ahead_dt)
        ), patch(
            "salt.utils.ssdp.datetime.datetime.fromtimestamp",
            MagicMock(return_value=curnt_dt),
        ), patch(
            "salt.utils.ssdp.datetime.timedelta", MagicMock(return_value=delta)
        ):
            protocol.datagram_received(data=data, addr=addr)
            assert protocol.log.debug.called
            assert (
                "Service discovery received message: %s:%s - %s"
                in protocol.log.debug.call_args[0][0]
            )
            assert protocol._sendto.called
            assert protocol._sendto.call_args[0][0] == salt.utils.stringutils.to_bytes(
                "{}:@:{{}}".format(signature)
            )


@skipIf(pytest is None, "PyTest is missing")
class SSDPServerTestCase(TestCase, Mocks):
    """
    Server-related test cases
    """

    def test_config_detached_default(self):
        """
        Test if configuration is not a reference.
        :return:
        """
        config = {ssdp.SSDPBase.TIMEOUT: 15, ssdp.SSDPBase.PORT: 5555}

        server = self.get_ssdp_discovery_server(**config)
        assert (
            getattr(server, ssdp.SSDPBase.TIMEOUT, None)
            == config[ssdp.SSDPBase.TIMEOUT]
        )
        assert getattr(server, ssdp.SSDPBase.PORT, None) == config[ssdp.SSDPBase.PORT]
        assert (
            getattr(server, ssdp.SSDPBase.INTERFACE_IP, None)
            == ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.INTERFACE_IP]
        )
        assert "master" not in getattr(server, ssdp.SSDPBase.ANSWER, {})
        assert server._socket.bind.called
        assert server._socket.bind.call_args[0][0][0] == ""

    def test_config_detached_ipv6(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "::1"}

        with pytest.raises(ssdp.InvalidIPAddress):
            server = self.get_ssdp_discovery_server(**config)

    def test_config_detached_public(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "1.0.0.1"}

        with pytest.raises(ssdp.InvalidIPAddress):
            server = self.get_ssdp_discovery_server(**config)

    def test_config_detached_loopback(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "127.0.0.1"}

        server = self.get_ssdp_discovery_server(**config)
        assert getattr(server, ssdp.SSDPBase.INTERFACE_IP, None) == "127.0.0.1"
        assert getattr(server, ssdp.SSDPBase.ANSWER, {}).get("master") == "127.0.0.1"
        assert server._socket.bind.called
        assert server._socket.bind.call_args[0][0][0] == "127.0.0.1"

    def test_config_detached_private(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "10.0.0.10"}

        interfaces = self.get_network_interfaces_mock()

        with patch("salt.utils.network.interfaces", interfaces):
            server = self.get_ssdp_discovery_server(**config)
            assert getattr(server, ssdp.SSDPBase.INTERFACE_IP, None) == "10.0.0.10"
            assert (
                getattr(server, ssdp.SSDPBase.ANSWER, {}).get("master") == "10.0.0.10"
            )
            assert server._socket.bind.called
            assert server._socket.bind.call_args[0][0][0] == "10.0.0.255"

    def test_config_detached_private_fail(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "192.168.0.10"}

        interfaces = self.get_network_interfaces_mock()

        with patch("salt.utils.network.interfaces", interfaces):
            with pytest.raises(ssdp.InvalidIPAddress):
                server = self.get_ssdp_discovery_server(**config)

    def test_run(self):
        """
        Test server runner.
        :return:
        """
        config = {ssdp.SSDPBase.TIMEOUT: 15, ssdp.SSDPBase.PORT: 5555}

        with patch("salt.utils.ssdp.SSDPProtocol", MagicMock()):
            server = self.get_ssdp_discovery_server(**config)
            server.create_datagram_endpoint = MagicMock()
            server.log = MagicMock()

            transport = MagicMock()
            protocol = MagicMock()
            loop = MagicMock()
            loop.run_until_complete = MagicMock(return_value=(transport, protocol))

            asyncio_mod = MagicMock()
            asyncio_mod.get_event_loop = MagicMock(return_value=loop)

            with patch("salt.utils.ssdp.asyncio", asyncio_mod):
                server.run()

                assert asyncio_mod.get_event_loop.called
                assert asyncio_mod.get_event_loop().run_until_complete.called
                assert asyncio_mod.get_event_loop().create_datagram_endpoint.called
                assert asyncio_mod.get_event_loop().run_forever.called
                assert transport.close.called
                assert loop.close.called
                assert server.log.info.called
                assert (
                    server.log.info.call_args[0][0]
                    == "Stop service discovery publisher"
                )

                assert server._socket.setsockopt.called
                assert server._socket.setsockopt.call_args[0] == (
                    socket.SOL_SOCKET,
                    socket.SO_BROADCAST,
                    1,
                )
                assert server._socket.settimeout.called
                assert (
                    server._socket.settimeout.call_args[0][0]
                    == config[ssdp.SSDPBase.TIMEOUT]
                )
                assert server._socket.bind.called
                assert server._socket.bind.call_args[0][0] == (
                    "",
                    config[ssdp.SSDPBase.PORT],
                )


@skipIf(pytest is None, "PyTest is missing")
class SSDPClientTestCase(TestCase, Mocks):
    """
    Client-related test cases
    """

    class Resource:
        """
        Fake network reader
        """

        def __init__(self):
            self.datagrams = []

        def recvfrom_into(self, *args, **kwargs):
            if not self.datagrams:
                raise socket.timeout
            message, addr = self.datagrams.pop(0)
            args[0][0 : len(message)] = salt.utils.stringutils.to_bytes(message)
            return len(message), addr

    def test_config_detached_default(self):
        """
        Test if the configuration is passed.
        :return:
        """
        config = {
            ssdp.SSDPBase.TIMEOUT: 15,
            ssdp.SSDPBase.PORT: 5555,
        }

        interfaces = self.get_network_interfaces_mock()

        with patch("salt.utils.network.interfaces", interfaces):
            client = self.get_ssdp_discovery_client(**config)

        assert (
            getattr(client, ssdp.SSDPBase.TIMEOUT, None)
            == config[ssdp.SSDPBase.TIMEOUT]
        )
        assert getattr(client, ssdp.SSDPBase.PORT, None) == config[ssdp.SSDPBase.PORT]

        assert client._socket.setsockopt.called
        assert client._socket.setsockopt.call_args[0] == (
            socket.SOL_SOCKET,
            socket.SO_BROADCAST,
            1,
        )
        assert client._socket.settimeout.called
        assert (
            client._socket.settimeout.call_args[0][0] == config[ssdp.SSDPBase.TIMEOUT]
        )

        assert client.interface_ip == ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.INTERFACE_IP]
        assert client.broadcast_ip is None
        assert len(client.broadcast_ips) == 1
        assert client.broadcast_ips[0] == interfaces()["eth0"]["inet"][0]["broadcast"]

    def test_config_detached_ipv6(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "::1"}

        with pytest.raises(ssdp.InvalidIPAddress):
            client = self.get_ssdp_discovery_client(**config)

    def test_config_detached_public(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "1.0.0.1"}

        with pytest.raises(ssdp.InvalidIPAddress):
            client = self.get_ssdp_discovery_client(**config)

    def test_config_detached_loopback(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "127.0.0.1"}

        client = self.get_ssdp_discovery_client(**config)
        assert getattr(client, ssdp.SSDPBase.INTERFACE_IP, None) == "127.0.0.1"
        assert client.broadcast_ip == "127.0.0.1"
        assert client.broadcast_ips is None
        assert client._socket.setsockopt.called
        assert client._socket.setsockopt.call_args[0] == (
            socket.SOL_SOCKET,
            socket.SO_REUSEPORT,
            1,
        )

    def test_config_detached_private(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "10.0.0.10"}

        interfaces = self.get_network_interfaces_mock()

        with patch("salt.utils.network.interfaces", interfaces):
            client = self.get_ssdp_discovery_client(**config)
            assert getattr(client, ssdp.SSDPBase.INTERFACE_IP, None) == "10.0.0.10"
            assert client.broadcast_ip == interfaces()["eth0"]["inet"][0]["broadcast"]
            assert client.broadcast_ips is None

    def test_config_detached_private_fail(self):
        config = {ssdp.SSDPBase.INTERFACE_IP: "192.168.0.10"}

        interfaces = self.get_network_interfaces_mock()

        with patch("salt.utils.network.interfaces", interfaces):
            with pytest.raises(ssdp.InvalidIPAddress):
                client = self.get_ssdp_discovery_client(**config)

    def test_query(self):
        """
        Test if client queries the broadcast
        :return:
        """
        config = {
            ssdp.SSDPBase.SIGNATURE: "SUSE Enterprise Server",
            ssdp.SSDPBase.PORT: 5555,
        }

        _interfaces = self.get_network_interfaces_mock()
        _socket = self.get_socket_mock(
            _interfaces()["eth0"]["inet"][0]["address"], "localhost"
        )

        with patch("salt.utils.ssdp.socket", _socket), patch(
            "salt.utils.network.interfaces", _interfaces
        ):
            client = ssdp.SSDPDiscoveryClient(**config)
            client._query()
            assert client._socket.sendto.called
            assert client._socket.sendto.call_count == 1
            message, target = client._socket.sendto.call_args[0]
            assert salt.utils.stringutils.to_unicode(message).startswith(
                config[ssdp.SSDPBase.SIGNATURE]
            )
            assert target[0] == _interfaces()["eth0"]["inet"][0]["broadcast"]
            assert target[1] == config[ssdp.SSDPBase.PORT]

    def test_discover_default(self):
        """
        Test getting map of the available masters on the network
        :return:
        """
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        port = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.PORT]
        message = "{}:@:{{}}".format(signature)

        resource = SSDPClientTestCase.Resource()
        resource.datagrams.append(
            (
                message.format(salt.utils.json.dumps({"master": "10.0.0.2"})),
                ("10.0.0.2", port),
            )
        )
        resource.datagrams.append(
            (
                message.format(
                    salt.utils.json.dumps({"master": "10.0.0.2", "sentinel": True})
                ),
                ("10.0.0.2", port),
            )
        )
        resource.datagrams.append(
            (
                message.format(salt.utils.json.dumps({"master": "10.1.0.2"})),
                ("10.1.0.2", port),
            )
        )

        _interfaces = self.get_network_interfaces_mock()
        _socket = self.get_socket_mock(
            _interfaces()["eth0"]["inet"][0]["address"], "localhost"
        )

        response = {}
        with patch("salt.utils.ssdp.socket", _socket), patch(
            "salt.utils.network.interfaces", _interfaces
        ):
            client = ssdp.SSDPDiscoveryClient()
            client.log = MagicMock()
            client._socket.recvfrom_into = resource.recvfrom_into

            response = client.discover()
            assert "10.0.0.2" in response
            assert response["10.0.0.2"] == [
                {"master": "10.0.0.2"},
                {"master": "10.0.0.2", "sentinel": True},
            ]
            assert "10.1.0.2" in response
            assert response["10.1.0.2"] == [{"master": "10.1.0.2"}]

    def test_discover_no_masters(self):
        """
        Test discover available master on the network (none found).
        :return:
        """

        client = self.get_ssdp_discovery_client()
        client._socket.recvfrom_into = MagicMock(side_effect=socket.timeout("sentinel"))
        client.log = MagicMock()

        with pytest.raises(TimeoutError):
            client.discover()

        assert client.log.error.called
        assert (
            client.log.error.call_args[0][0] == "Service discovery did not find master"
        )

    def test_discover_general_error(self):
        """
        Test discover available master on the network (erroneous found)
        :return:
        """
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        port = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.PORT]
        message = "{}:E:{{}}".format(signature)

        resource = SSDPClientTestCase.Resource()
        resource.datagrams.append((message.format("sentinel"), ("10.0.0.2", port)))

        _interfaces = self.get_network_interfaces_mock()
        _socket = self.get_socket_mock(
            _interfaces()["eth0"]["inet"][0]["address"], "localhost"
        )

        with patch("salt.utils.ssdp.socket", _socket), patch(
            "salt.utils.network.interfaces", _interfaces
        ):
            client = ssdp.SSDPDiscoveryClient()
            client.log = MagicMock()
            client._socket.recvfrom_into = resource.recvfrom_into
            client.discover()
            assert len(client.log.error.mock_calls) == 1
            assert (
                "Service discovery message validation failed"
                in client.log.error.call_args[0][0]
            )
            assert client.log.error.call_args[0][1] == "10.0.0.2"
            assert client.log.error.call_args[0][2] == "Invalid message"

    def test_discover_timestamp_error(self):
        """
        Test discover available master on the network (outdated timestamp)
        :return:
        """
        signature = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.SIGNATURE]
        port = ssdp.SSDPBase.DEFAULTS[ssdp.SSDPBase.PORT]
        message = "{}:E:{{}}".format(signature)

        resource = SSDPClientTestCase.Resource()
        resource.datagrams.append(
            (message.format("Invalid timestamp"), ("10.0.0.2", port))
        )

        _interfaces = self.get_network_interfaces_mock()
        _socket = self.get_socket_mock(
            _interfaces()["eth0"]["inet"][0]["address"], "localhost"
        )

        with patch("salt.utils.ssdp.socket", _socket), patch(
            "salt.utils.network.interfaces", _interfaces
        ):
            client = ssdp.SSDPDiscoveryClient()
            client.log = MagicMock()
            client._socket.recvfrom_into = resource.recvfrom_into
            client.discover()
            assert len(client.log.error.mock_calls) == 1
            assert (
                "Service discovery timestamp is invalid"
                in client.log.error.call_args[0][0]
            )
            assert client.log.error.call_args[0][1] == "10.0.0.2"
