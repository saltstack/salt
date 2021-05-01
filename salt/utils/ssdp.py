#
# Author: Bo Maryniuk <bo@suse.de>, Zane Mingee <zmingee@gmail.com>
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

import asyncio
import copy
import datetime
import itertools
import logging
import random
import socket
import time

import salt.utils.json
import salt.utils.network
import salt.utils.stringutils


class BaseSSDPException(Exception):
    message = None

    def __init__(self, message=None):
        super().__init__(message or self.message)


class InvalidIPAddress(BaseSSDPException):
    """Invalid interface IP address"""

    message = "Invalid IP Address"


class InvalidMessage(BaseSSDPException):
    """Invalid message"""

    message = "Invalid message"


class InvalidSignature(BaseSSDPException):
    """Invalid message signature"""

    message = "Invalid signature"


class InvalidTimestamp(BaseSSDPException):
    """Invalid message timestamp"""

    message = "Invalid timestamp"


class SSDPBase:
    """
    Salt Service Discovery Protocol base class.
    """

    log = logging.getLogger(__name__)

    # Fields
    SIGNATURE = "signature"
    ANSWER = "answer"
    PORT = "port"
    INTERFACE_IP = "interface_ip"
    TIMEOUT = "timeout"

    # Default values
    DEFAULTS = {
        SIGNATURE: "__salt_master_service",
        ANSWER: {},
        PORT: 4520,
        INTERFACE_IP: "0.0.0.0",
        TIMEOUT: 3,
    }

    def __init__(self, **config):
        self._config = copy.deepcopy(config)


class SSDPProtocol(SSDPBase, asyncio.DatagramProtocol):
    """
    :py:class:`asyncio.DatagramProtocol` implementing the Salt Service
    Discovery Protocol.
    """

    def __init__(self, **config):
        super().__init__(**config)
        self.signature = self._config.get(self.SIGNATURE, self.DEFAULTS[self.SIGNATURE])
        self.answer = self._config.get(self.ANSWER, self.DEFAULTS[self.ANSWER])
        self.hidden = True
        self.transport = None

    def _validate_message(self, message):
        """
        Validate broadcast message

        :param str message: broadcast message
        :return:
        """
        if not message.startswith(self.signature):
            raise InvalidSignature

        try:
            timestamp = float(message[len(self.signature) :])
        except (TypeError, ValueError) as err:
            raise InvalidTimestamp from err

        if datetime.datetime.fromtimestamp(timestamp) < (
            datetime.datetime.now() - datetime.timedelta(seconds=20)
        ):
            raise InvalidTimestamp

    def connection_made(self, transport):
        """
        Handle connection

        :param transport: socket connection transport
        :type transport: :py:class:`asyncio.DatagramProtocol`
        :return:
        """
        self.transport = transport

    def _sendto(self, data, addr=None, attempts=10):
        """
        On multi-master environments, running on the same machine, transport
        sending to the destination can be allowed only at once.  Since every
        machine will immediately respond, high chance to get sending fired at
        the same time, which will result to a PermissionError at socket level.
        We are attempting to send it in a different time.

        :param bytes data: data to send to peer
        :param addr: IP address and port of peer
        :return:
        """
        tries = 0
        slp_time = lambda: 0.5 / random.randint(10, 30)
        slp = slp_time()
        while tries < attempts:
            try:
                self.transport.sendto(data, addr=addr)
                self.log.debug("Service discovery message sent successfully")
                return
            except AttributeError as ex:
                self.log.error("Permission error: %s", ex)
                time.sleep(slp)
                tries += 1
                slp += slp_time()

    def datagram_received(self, data, addr):
        """
        Process datagram

        :param data: bytes object containing the incoming data
        :param addr: address of the peer sending the data
        :return:
        """
        message = salt.utils.stringutils.to_unicode(data)

        try:
            self._validate_message(message)
        except BaseSSDPException as err:
            self.log.error(
                "Service discovery message validation failed: %s:%s - %s",
                *addr,
                err.message
            )
            if not self.hidden:
                self._sendto("{}:E:{}".format(self.signature, err.message), addr)
            return

        self.log.debug("Service discovery received message: %s:%s - %s", *addr, message)

        resp = "{}:@:{}".format(self.signature, salt.utils.json.dumps(self.answer))

        self._sendto(salt.utils.stringutils.to_bytes(resp), addr)


class SSDPDiscoveryServer(SSDPBase):
    """
    Service discovery publisher
    """

    def __init__(self, **config):
        super().__init__(**config)
        self.answer = self._config.get(self.ANSWER, {})
        self.timeout = self._config.get(self.TIMEOUT, self.DEFAULTS[self.TIMEOUT])
        self.interface_ip = self._config.get(
            self.INTERFACE_IP, self.DEFAULTS[self.INTERFACE_IP]
        )
        self.port = self._config.get(self.PORT, self.DEFAULTS[self.PORT])

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(self.timeout)

        if not salt.utils.network.is_ipv4(self.interface_ip):
            self.log.error(
                "Service discovery interface IP family must be IPv4 for broadcast support"
            )
            raise InvalidIPAddress
        if salt.utils.network.is_ip_filter(self.interface_ip, "public"):
            self.log.error(
                "Service discovery interface IP must not be public or global"
            )
            raise InvalidIPAddress
        if salt.utils.network.is_ip_filter(self.interface_ip, "loopback"):
            self.log.warning("Service discovery will listen on loopback interface")
            self.answer.update({"master": self.interface_ip})
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self._socket.bind((self.interface_ip, self.port))
        elif self.interface_ip == "0.0.0.0":
            self.log.warning("Service discovery will listen on all interfaces")
            self._socket.bind(("", self.port))
        else:
            self.answer.update({"master": self.interface_ip})
            interfaces = iter(
                interface["inet"]
                for (name, interface) in salt.utils.network.interfaces().items()
                if interface["up"]
            )
            addresses = {
                address["address"]: address.get("broadcast")
                for address in itertools.chain.from_iterable(interfaces)
            }

            if addresses.get(self.interface_ip):
                broadcast_ip = addresses[self.interface_ip]
                self._socket.bind((broadcast_ip, self.port))
            else:
                self.log.error("Interface IP not found or does not support broadcast")
                raise InvalidIPAddress

    def run(self):
        """
        Run service discovery publisher

        :return:
        """
        self.log.info(
            "Start service discovery publisher: udp://%s:%s",
            self.interface_ip,
            self.port,
        )

        loop = asyncio.get_event_loop()
        coro = loop.create_datagram_endpoint(
            lambda: SSDPProtocol(answer=self.answer), sock=self._socket
        )
        transport, protocol = loop.run_until_complete(coro)

        try:
            loop.run_forever()
        finally:
            self.log.info("Stop service discovery publisher")
            transport.close()
            loop.close()


class SSDPDiscoveryClient(SSDPBase):
    """
    Service discovery client
    """

    def __init__(self, **config):
        super().__init__(**config)
        self.signature = self._config.get(self.SIGNATURE, self.DEFAULTS[self.SIGNATURE])
        self.timeout = self._config.get(self.TIMEOUT, self.DEFAULTS[self.TIMEOUT])
        self.interface_ip = (
            self._config.get(self.INTERFACE_IP) or self.DEFAULTS[self.INTERFACE_IP]
        )
        self.port = self._config.get(self.PORT, self.DEFAULTS[self.PORT])

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(self.timeout)

        self.broadcast_ip = None
        self.broadcast_ips = None
        if not salt.utils.network.is_ipv4(self.interface_ip):
            self.log.error(
                "Service discovery interface IP family must be IPv4 for broadcast support"
            )
            raise InvalidIPAddress
        if salt.utils.network.is_ip_filter(self.interface_ip, "public"):
            self.log.error(
                "Service discovery interface IP must not be public or global"
            )
            raise InvalidIPAddress
        if salt.utils.network.is_ip_filter(self.interface_ip, "loopback"):
            self.log.warning("Service discovery will broadcast on loopback interface")
            self.broadcast_ip = self.interface_ip
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        else:
            interfaces = iter(
                interface["inet"]
                for (name, interface) in salt.utils.network.interfaces().items()
                if interface["up"]
            )
            addresses = [
                (address["address"], address["broadcast"])
                for address in itertools.chain.from_iterable(interfaces)
                if address.get("broadcast")
            ]

            if self.interface_ip == "0.0.0.0":
                self.log.warning("Service discovery will broadcast on all interfaces")
                self.broadcast_ips = [
                    address[1]
                    for address in addresses
                    if not salt.utils.network.is_ip_filter(address[0], "public")
                ]
            else:
                self.broadcast_ip = next(
                    (
                        address[1]
                        for address in addresses
                        if address[0] == self.interface_ip
                    ),
                    None,
                )

        if not (self.broadcast_ip or self.broadcast_ips):
            self.log.error("Interface IP not found or does not support broadcast")
            raise InvalidIPAddress

    def _validate_message(self, message):
        """
        Validate broadcast response message

        :param str message: response message
        :return:
        """
        if not message.startswith(self.signature):
            raise InvalidSignature

        if ":E:" in message:
            err = message.split(":E:")[-1]
            if err == "Invalid timestamp":
                raise InvalidTimestamp

            raise InvalidMessage(err)

    def _query(self):
        """
        Send broadcast datagram

        :return:
        """
        query = salt.utils.stringutils.to_bytes(
            "{}{}".format(self.signature, time.time())
        )

        if self.broadcast_ip is None:
            for broadcast_ip in self.broadcast_ips:
                self.log.debug("Send query: %s:%s - %s", broadcast_ip, self.port, query)
                self._socket.sendto(query, (broadcast_ip, self.port))
        else:
            self.log.debug(
                "Send query: %s:%s - %s", self.broadcast_ip, self.port, query
            )
            self._socket.sendto(query, (self.broadcast_ip, self.port))

        response = {}
        while True:
            buffer = bytearray(1024)
            try:
                nbytes, addr = self._socket.recvfrom_into(buffer, 1024)
            except socket.timeout:
                if not response:
                    self.log.error("Service discovery did not find master")
                    raise TimeoutError
                break
            except Exception:  # pylint: disable=broad-except
                self.log.exception("Unknown error occurred")
                break
            else:
                if not nbytes:
                    break
                if addr[0] not in response:
                    response[addr[0]] = []
                response[addr[0]].append(
                    salt.utils.stringutils.to_str(buffer.rstrip(b"\x00"))
                )

        return response

    def discover(self):
        """
        Discover service discovery publishers

        :return: Discovered masters
        :rtype: dict
        """
        masters = {}
        self.log.debug("Start service discovery")
        response = self._query()

        for addr, datagrams in response.items():
            for data in datagrams:
                message = salt.utils.stringutils.to_unicode(data)

                try:
                    self._validate_message(message)
                except InvalidTimestamp as err:
                    self.log.error("Service discovery timestamp is invalid: %s", addr)
                    continue
                except BaseSSDPException as err:
                    self.log.error(
                        "Service discovery message validation failed: %s - %s",
                        addr,
                        err.message,
                    )
                    continue

                if addr not in masters:
                    masters[addr] = []
                masters[addr].append(salt.utils.json.loads(message.split(":@:")[-1]))

        return masters
