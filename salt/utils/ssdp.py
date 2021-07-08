#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Salt Service Discovery Protocol.
JSON-based service discovery protocol, used by minions to find running Master.
"""

import copy
import datetime
import logging
import random
import socket
import time

import salt.utils.json
import salt.utils.stringutils

try:
    from salt.utils.odict import OrderedDict
except ImportError:
    from collections import OrderedDict

_json = salt.utils.json.import_json()
if not hasattr(_json, "dumps"):
    _json = None

try:
    import asyncio

    asyncio.ported = False
except ImportError:
    try:
        # Python 2 doesn't have asyncio
        import trollius as asyncio

        asyncio.ported = True
    except ImportError:
        asyncio = None


class TimeOutException(Exception):
    pass


class TimeStampException(Exception):
    pass


class SSDPBase:
    """
    Salt Service Discovery Protocol.
    """

    log = logging.getLogger(__name__)

    # Fields
    SIGNATURE = "signature"
    ANSWER = "answer"
    PORT = "port"
    LISTEN_IP = "listen_ip"
    TIMEOUT = "timeout"

    # Default values
    DEFAULTS = {
        SIGNATURE: "__salt_master_service",
        PORT: 4520,
        LISTEN_IP: "0.0.0.0",
        TIMEOUT: 3,
        ANSWER: {},
    }

    @staticmethod
    def _is_available():
        """
        Return True if the USSDP dependencies are satisfied.
        :return:
        """
        return bool(asyncio and _json)

    @staticmethod
    def get_self_ip():
        """
        Find out localhost outside IP.

        :return:
        """
        sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sck.connect(("1.255.255.255", 1))  # Does not needs to be reachable
            ip_addr = sck.getsockname()[0]
        except Exception:  # pylint: disable=broad-except
            ip_addr = socket.gethostbyname(socket.gethostname())
        finally:
            sck.close()
        return ip_addr


class SSDPFactory(SSDPBase):
    """
    Socket protocol factory.
    """

    def __init__(self, **config):
        """
        Initialize

        :param config:
        """
        for attr in (self.SIGNATURE, self.ANSWER):
            setattr(self, attr, config.get(attr, self.DEFAULTS[attr]))
        self.disable_hidden = False
        self.transport = None
        self.my_ip = socket.gethostbyname(socket.gethostname())

    def __call__(self, *args, **kwargs):
        """
        Return instance on Factory call.
        :param args:
        :param kwargs:
        :return:
        """
        return self

    def connection_made(self, transport):
        """
        On connection.

        :param transport:
        :return:
        """
        self.transport = transport

    def _sendto(self, data, addr=None, attempts=10):
        """
        On multi-master environments, running on the same machine,
        transport sending to the destination can be allowed only at once.
        Since every machine will immediately respond, high chance to
        get sending fired at the same time, which will result to a PermissionError
        at socket level. We are attempting to send it in a different time.

        :param data:
        :param addr:
        :return:
        """
        tries = 0
        slp_time = lambda: 0.5 / random.randint(10, 30)
        slp = slp_time()
        while tries < attempts:
            try:
                self.transport.sendto(data, addr=addr)
                self.log.debug("Sent successfully")
                return
            except AttributeError as ex:
                self.log.debug("Permission error: %s", ex)
                time.sleep(slp)
                tries += 1
                slp += slp_time()

    def datagram_received(self, data, addr):
        """
        On datagram receive.

        :param data:
        :param addr:
        :return:
        """
        message = salt.utils.stringutils.to_unicode(data)
        if message.startswith(self.signature):
            try:
                timestamp = float(message[len(self.signature) :])
            except (TypeError, ValueError):
                self.log.debug(
                    "Received invalid timestamp in package from %s:%s", *addr
                )
                if self.disable_hidden:
                    self._sendto(
                        "{}:E:{}".format(self.signature, "Invalid timestamp"), addr
                    )
                return

            if datetime.datetime.fromtimestamp(timestamp) < (
                datetime.datetime.now() - datetime.timedelta(seconds=20)
            ):
                if self.disable_hidden:
                    self._sendto(
                        "{}:E:{}".format(self.signature, "Timestamp is too old"), addr
                    )
                self.log.debug("Received outdated package from %s:%s", *addr)
                return

            self.log.debug('Received "%s" from %s:%s', message, *addr)
            self._sendto(
                salt.utils.stringutils.to_bytes(
                    "{}:@:{}".format(
                        self.signature,
                        salt.utils.json.dumps(self.answer, _json_module=_json),
                    )
                ),
                addr,
            )
        else:
            if self.disable_hidden:
                self._sendto(
                    salt.utils.stringutils.to_bytes(
                        "{}:E:{}".format(self.signature, "Invalid packet signature"),
                        addr,
                    )
                )
            self.log.debug("Received bad signature from %s:%s", *addr)


class SSDPDiscoveryServer(SSDPBase):
    """
    Discovery service publisher.

    """

    @staticmethod
    def is_available():
        """
        Return availability of the Server.
        :return:
        """
        return SSDPBase._is_available()

    def __init__(self, **config):
        """
        Initialize.

        :param config:
        """
        self._config = copy.deepcopy(config)
        if self.ANSWER not in self._config:
            self._config[self.ANSWER] = {}
        self._config[self.ANSWER].update({"master": self.get_self_ip()})

    @staticmethod
    def create_datagram_endpoint(
        loop,
        protocol_factory,
        local_addr=None,
        remote_addr=None,
        family=0,
        proto=0,
        flags=0,
    ):
        """
        Create datagram connection.

        Based on code from Python 3.5 version, this method is used
        only in Python 2.7+ versions, since Trollius library did not
        ported UDP packets broadcast.
        """
        if not (local_addr or remote_addr):
            if not family:
                raise ValueError("unexpected address family")
            addr_pairs_info = (((family, proto), (None, None)),)
        else:
            addr_infos = OrderedDict()
            for idx, addr in ((0, local_addr), (1, remote_addr)):
                if addr is not None:
                    assert (
                        isinstance(addr, tuple) and len(addr) == 2
                    ), "2-tuple is expected"
                    infos = yield asyncio.coroutines.From(
                        loop.getaddrinfo(
                            *addr,
                            family=family,
                            type=socket.SOCK_DGRAM,
                            proto=proto,
                            flags=flags
                        )
                    )
                    if not infos:
                        raise OSError("getaddrinfo() returned empty list")
                    for fam, _, pro, _, address in infos:
                        key = (fam, pro)
                        if key not in addr_infos:
                            addr_infos[key] = [None, None]
                        addr_infos[key][idx] = address
            addr_pairs_info = [
                (key, addr_pair)
                for key, addr_pair in addr_infos.items()
                if not (
                    (local_addr and addr_pair[0] is None)
                    or (remote_addr and addr_pair[1] is None)
                )
            ]
            if not addr_pairs_info:
                raise ValueError("can not get address information")
        exceptions = []
        for ((family, proto), (local_address, remote_address)) in addr_pairs_info:
            sock = r_addr = None
            try:
                sock = socket.socket(family=family, type=socket.SOCK_DGRAM, proto=proto)
                for opt in [socket.SO_REUSEADDR, socket.SO_BROADCAST]:
                    sock.setsockopt(socket.SOL_SOCKET, opt, 1)
                sock.setblocking(False)
                if local_addr:
                    sock.bind(local_address)
                if remote_addr:
                    yield asyncio.coroutines.From(
                        loop.sock_connect(sock, remote_address)
                    )
                    r_addr = remote_address
            except OSError as exc:
                if sock is not None:
                    sock.close()
                exceptions.append(exc)
            except Exception:  # pylint: disable=broad-except
                if sock is not None:
                    sock.close()
                raise
            else:
                break
        else:
            raise exceptions[0]

        protocol = protocol_factory()
        waiter = asyncio.futures.Future(loop=loop)
        transport = loop._make_datagram_transport(sock, protocol, r_addr, waiter)
        try:
            yield asyncio.coroutines.From(waiter)
        except Exception:  # pylint: disable=broad-except
            transport.close()
            raise
        raise asyncio.coroutines.Return(transport, protocol)

    def run(self):
        """
        Run server.
        :return:
        """
        listen_ip = self._config.get(self.LISTEN_IP, self.DEFAULTS[self.LISTEN_IP])
        port = self._config.get(self.PORT, self.DEFAULTS[self.PORT])
        self.log.info(
            "Starting service discovery listener on udp://%s:%s", listen_ip, port
        )
        loop = asyncio.get_event_loop()
        protocol = SSDPFactory(answer=self._config[self.ANSWER])
        if asyncio.ported:
            transport, protocol = loop.run_until_complete(
                SSDPDiscoveryServer.create_datagram_endpoint(
                    loop, protocol, local_addr=(listen_ip, port)
                )
            )
        else:
            transport, protocol = loop.run_until_complete(
                loop.create_datagram_endpoint(
                    protocol, local_addr=(listen_ip, port), allow_broadcast=True
                )
            )
        try:
            loop.run_forever()
        finally:
            self.log.info("Stopping service discovery listener.")
            transport.close()
            loop.close()


class SSDPDiscoveryClient(SSDPBase):
    """
    Class to discover Salt Master via UDP broadcast.
    """

    @staticmethod
    def is_available():
        """
        Return availability of the Client
        :return:
        """
        return SSDPBase._is_available()

    def __init__(self, **config):
        """
        Initialize
        """
        self._config = config
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(
            self._config.get(self.TIMEOUT, self.DEFAULTS[self.TIMEOUT])
        )

        for attr in [self.SIGNATURE, self.TIMEOUT, self.PORT]:
            setattr(self, attr, self._config.get(attr, self.DEFAULTS[attr]))

    def _query(self):
        """
        Query the broadcast for defined services.
        :return:
        """
        query = salt.utils.stringutils.to_bytes(
            "{}{}".format(self.signature, time.time())
        )
        self._socket.sendto(query, ("<broadcast>", self.port))

        return query

    def _collect_masters_map(self, response):
        """
        Collect masters map from the network.
        :return:
        """
        while True:
            try:
                data, addr = self._socket.recvfrom(0x400)
                if data:
                    if addr not in response:
                        response[addr] = []
                    response[addr].append(data)
                else:
                    break
            except Exception as err:  # pylint: disable=broad-except
                self.log.error("Discovery master collection failure: %s", err)
                break

    def discover(self):
        """
        Gather the information of currently declared servers.

        :return:
        """
        response = {}
        masters = {}
        self.log.info("Looking for a server discovery")
        self._query()
        self._collect_masters_map(response)
        if not response:
            msg = "No master has been discovered."
            self.log.info(msg)
        else:
            for addr, descriptions in response.items():
                for (
                    data
                ) in descriptions:  # Several masters can run at the same machine.
                    msg = salt.utils.stringutils.to_unicode(data)
                    if msg.startswith(self.signature):
                        msg = msg.split(self.signature)[-1]
                        self.log.debug(
                            "Service announcement at '%s:%s'. Response: '%s'",
                            addr[0],
                            addr[1],
                            msg,
                        )
                        if ":E:" in msg:
                            err = msg.split(":E:")[-1]
                            self.log.error(
                                "Error response from the service publisher at %s: %s",
                                addr,
                                err,
                            )
                            if "timestamp" in err:
                                self.log.error(
                                    "Publisher sent shifted timestamp from %s", addr
                                )
                        else:
                            if addr not in masters:
                                masters[addr] = []
                            masters[addr].append(
                                salt.utils.json.loads(
                                    msg.split(":@:")[-1], _json_module=_json
                                )
                            )
        return masters
