# -*- coding: utf-8 -*-
'''
Junos Syslog Engine
===================

.. versionadded:: Nitrogen

An engine that listen to syslog message from Junos devices,
extract event information and generate message on SaltStack bus.

:configuration:
  Example configuration
    engines:
      - junos_syslog:
          port: 516

For junos_syslog engine to receive events syslog must be set on junos device.
This can be done via following configuration:
    set system syslog host <ip-of-the-salt-device> port 516 any any

Here is a sample syslog event which is received from the junos device:
    ' <30>May 29 05:18:12 bng-ui-vm-92 mspd[1492]: No chassis configuration found '

The source for parsing the syslog messages is taken from:
    https://gist.github.com/leandrosilva/3651640#file-xlog-py
'''

# Import Python libs
from __future__ import absolute_import
import re
from time import strftime
import logging

# Import Salt libs
import salt.utils.event

try:
    from twisted.internet.protocol import DatagramProtocol
    from twisted.internet import reactor
    from pyparsing import Word, alphas, Suppress, Combine, nums, string, Optional, \
        Regex, Literal, OneOrMore, LineEnd, LineStart, StringEnd, delimitedList
    HAS_TWISTED_AND_PYPARSING = True
except ImportError:
    HAS_TWISTED_AND_PYPARSING = False

# logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

__virtualname__ = 'junos_syslog'


def __virtual__():
    '''
    Load only if twisted and pyparsing libs are present.
    '''
    if not HAS_TWISTED_AND_PYPARSING:
        return (False, 'junos_syslog could not be loaded. \
            Make sure you have twisted and pyparsing python libraries.')
    return True


class Parser(object):

    def __init__(self):
        ints = Word(nums)
        word = Word(alphas)
        EOL = LineEnd().suppress()
        SOL = LineStart().leaveWhitespace()
        blankline = SOL + LineEnd()

        # ip address of device
        ipAddress = Optional(
            delimitedList(
                ints,
                ".",
                combine=True) + Suppress(
            ":"))

        # Received message
        rec_msg = Suppress(OneOrMore(word)) + Suppress(Literal("'"))

        # priority
        priority = Suppress("<") + ints + Suppress(">")

        # timestamp
        month = Word(string.uppercase, string.lowercase, exact=3)
        day = ints
        hour = Combine(ints + ":" + ints + ":" + ints)

        timestamp = month + day + hour

        # hostname
        hostname = Word(alphas + nums + "_" + "-" + ".")

        # appname
        appname = Word(alphas + "/" + "-" + "_" + ".") + Optional(
            Suppress("[") + ints + Suppress("]")) + Suppress(":")

        # message
        message = Regex(".*")

        # pattern build
        self.__pattern = ipAddress + priority + timestamp + \
            hostname + appname + message + StringEnd() | EOL

        self.__pattern_without_appname = ipAddress + priority + \
            timestamp + hostname + message + StringEnd() | EOL

    def parse(self, line):
        try:
            parsed = self.__pattern.parseString(line)
        except Exception:
            try:
                parsed = self.__pattern_without_appname.parseString(line)
            except Exception:
                return
        if len(parsed) == 6:
            payload = {}
            payload["priority"] = int(parsed[0])
            payload["severity"] = payload["priority"] & 0x07
            payload["facility"] = payload["priority"] >> 3
            payload["timestamp"] = strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[4]
            payload["message"] = parsed[5]
            payload["event"] = 'SYSTEM'
            return payload
        elif len(parsed) == 7:
            payload = {}
            payload["priority"] = int(parsed[0])
            payload["severity"] = payload["priority"] & 0x07
            payload["facility"] = payload["priority"] >> 3
            payload["timestamp"] = strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[4]
            payload["appname"] = parsed[5]
            payload["message"] = parsed[6]
            payload["event"] = 'SYSTEM'
            obj = re.match(r'(\w+): (.*)', payload["message"])
            if obj:
                payload["message"] = obj.group(2)
            payload["raw"] = line
            return payload
        elif len(parsed) == 8:
            payload = {}
            payload["priority"] = int(parsed[0])
            payload["severity"] = payload["priority"] & 0x07
            payload["facility"] = payload["priority"] >> 3
            payload["timestamp"] = strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[4]
            payload["appname"] = parsed[5]
            payload["pid"] = parsed[6]
            payload["message"] = parsed[7]
            payload["event"] = 'SYSTEM'
            obj = re.match(r'(\w+): (.*)', payload["message"])
            if obj:
                payload["event"] = obj.group(1)
                payload["message"] = obj.group(2)
            payload["raw"] = line
            return payload
        elif len(parsed) == 9:
            payload = {}
            payload["hostip"] = parsed[0]
            payload["priority"] = int(parsed[1])
            payload["severity"] = payload["priority"] & 0x07
            payload["facility"] = payload["priority"] >> 3
            payload["timestamp"] = strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[5]
            payload["appname"] = parsed[6]
            payload["pid"] = parsed[7]
            payload["message"] = parsed[8]
            payload["event"] = 'SYSTEM'
            obj = re.match(r'(\w+): (.*)', payload["message"])
            if obj:
                payload["event"] = obj.group(1)
                payload["message"] = obj.group(2)
            payload["raw"] = line
            return payload


class Echo(DatagramProtocol):  # pylint: disable=W0232

    def datagramReceived(self, data, connection_details):
        (host, port) = connection_details
        obj = Parser()
        data = obj.parse(data)
        log.debug('Junos Syslog - received {0} from {1}:{2}'.format(data, host, port))

        if data is not None and data['event']:
            topic = 'jnpr/event/{0}/{1}'.format(
                data['hostname'], data['event'])
            data['port'] = port

            salt.utils.event.get_master_event(
                __opts__,
                __opts__['sock_dir']).fire_event(data, topic)
            # Do nothing if the syslog do not contain events


def start(port=516):
    log.info('Starting junos syslog engine (port {0})'.format(port))
    reactor.listenUDP(port, Echo())
    reactor.run()
