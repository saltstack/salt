"""
Junos Syslog Engine
==========================

.. versionadded:: 2017.7.0


:depends: pyparsing, twisted


An engine that listens to syslog message from Junos devices,
extract event information and generate message on SaltStack bus.

The event topic sent to salt is dynamically generated according to the topic title
specified by the user. The incoming event data (from the junos device) consists
of the following fields:

1.   hostname
2.   hostip
3.   daemon
4.   event
5.   severity
6.   priority
7.   timestamp
8.   message
9.   pid
10.   raw (the raw event data forwarded from the device)

The topic title can consist of any of the combination of above fields,
but the topic has to start with 'jnpr/syslog'.
So, we can have different combinations:

 - jnpr/syslog/hostip/daemon/event
 - jnpr/syslog/daemon/severity

The corresponding dynamic topic sent on salt event bus would look something like:

 - jnpr/syslog/1.1.1.1/mgd/UI_COMMIT_COMPLETED
 - jnpr/syslog/sshd/7

The default topic title is 'jnpr/syslog/hostname/event'.

The user can choose the type of data they wants of the event bus.
Like, if one wants only events pertaining to a particular daemon, they can
specify that in the configuration file:

.. code-block:: yaml

    daemon: mgd

One can even have a list of daemons like:

.. code-block:: yaml

    daemon:
      - mgd
      - sshd

Example configuration (to be written in master config file)

.. code-block:: yaml

    engines:
      - junos_syslog:
          port: 9999
          topic: jnpr/syslog/hostip/daemon/event
          daemon:
            - mgd
            - sshd

For junos_syslog engine to receive events, syslog must be set on the junos device.
This can be done via following configuration:

.. code-block:: bash

    set system syslog host <ip-of-the-salt-device> port 516 any any

Below is a sample syslog event which is received from the junos device:

.. code-block:: bash

    '<30>May 29 05:18:12 bng-ui-vm-9 mspd[1492]: No chassis configuration found'

The source for parsing the syslog messages is taken from:
https://gist.github.com/leandrosilva/3651640#file-xlog-py
"""

import logging
import re
import time

import salt.utils.event as event

try:
    from pyparsing import (
        Combine,
        LineEnd,
        Optional,
        Regex,
        StringEnd,
        Suppress,
        Word,
        alphas,
        delimitedList,
        nums,
        string,
    )
    from twisted.internet import reactor, threads  # pylint: disable=no-name-in-module
    from twisted.internet.protocol import (  # pylint: disable=no-name-in-module
        DatagramProtocol,
    )

    HAS_TWISTED_AND_PYPARSING = True
except ImportError:
    HAS_TWISTED_AND_PYPARSING = False

    # Fallback class
    class DatagramProtocol:
        pass


# logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

__virtualname__ = "junos_syslog"


def __virtual__():
    """
    Load only if twisted and pyparsing libs are present.
    """
    if not HAS_TWISTED_AND_PYPARSING:
        return (
            False,
            "junos_syslog could not be loaded."
            " Make sure you have twisted and pyparsing python libraries.",
        )
    return True


class _Parser:
    def __init__(self):
        ints = Word(nums)
        EOL = LineEnd().suppress()

        # ip address of device
        ipAddress = Optional(delimitedList(ints, ".", combine=True) + Suppress(":"))

        # priority
        priority = Suppress("<") + ints + Suppress(">")

        # timestamp
        month = Word(string.ascii_uppercase, string.ascii_lowercase, exact=3)
        day = ints
        hour = Combine(ints + ":" + ints + ":" + ints)

        timestamp = month + day + hour

        # hostname
        hostname = Word(alphas + nums + "_" + "-" + ".")

        # daemon
        daemon = (
            Word(alphas + nums + "/" + "-" + "_" + ".")
            + Optional(Suppress("[") + ints + Suppress("]"))
            + Suppress(":")
        )

        # message
        message = Regex(".*")

        # pattern build
        self.__pattern = (
            ipAddress + priority + timestamp + hostname + daemon + message + StringEnd()
            | EOL
        )

        self.__pattern_without_daemon = (
            ipAddress + priority + timestamp + hostname + message + StringEnd() | EOL
        )

    def parse(self, line):
        try:
            parsed = self.__pattern.parseString(line)
        except Exception:  # pylint: disable=broad-except
            try:
                parsed = self.__pattern_without_daemon.parseString(line)
            except Exception:  # pylint: disable=broad-except
                return
        if len(parsed) == 6:
            payload = {}
            payload["priority"] = int(parsed[0])
            payload["severity"] = payload["priority"] & 0x07
            payload["facility"] = payload["priority"] >> 3
            payload["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[4]
            payload["daemon"] = "unknown"
            payload["message"] = parsed[5]
            payload["event"] = "SYSTEM"
            payload["raw"] = line
            return payload
        elif len(parsed) == 7:
            payload = {}
            payload["priority"] = int(parsed[0])
            payload["severity"] = payload["priority"] & 0x07
            payload["facility"] = payload["priority"] >> 3
            payload["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[4]
            payload["daemon"] = parsed[5]
            payload["message"] = parsed[6]
            payload["event"] = "SYSTEM"
            obj = re.match(r"(\w+): (.*)", payload["message"])
            if obj:
                payload["message"] = obj.group(2)
            payload["raw"] = line
            return payload
        elif len(parsed) == 8:
            payload = {}
            payload["priority"] = int(parsed[0])
            payload["severity"] = payload["priority"] & 0x07
            payload["facility"] = payload["priority"] >> 3
            payload["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[4]
            payload["daemon"] = parsed[5]
            payload["pid"] = parsed[6]
            payload["message"] = parsed[7]
            payload["event"] = "SYSTEM"
            obj = re.match(r"(\w+): (.*)", payload["message"])
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
            payload["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            payload["hostname"] = parsed[5]
            payload["daemon"] = parsed[6]
            payload["pid"] = parsed[7]
            payload["message"] = parsed[8]
            payload["event"] = "SYSTEM"
            obj = re.match(r"(\w+): (.*)", payload["message"])
            if obj:
                payload["event"] = obj.group(1)
                payload["message"] = obj.group(2)
            payload["raw"] = line
            return payload


class _SyslogServerFactory(DatagramProtocol):
    def __init__(self, options):
        self.options = options
        self.obj = _Parser()
        data = [
            "hostip",
            "priority",
            "severity",
            "facility",
            "timestamp",
            "hostname",
            "daemon",
            "pid",
            "message",
            "event",
        ]
        if "topic" in self.options:
            # self.title = 'jnpr/syslog'
            # To remove the stray '/', if not removed splitting the topic
            # won't work properly. Eg: '/jnpr/syslog/event' won't be split
            # properly if the starting '/' is not stripped
            self.options["topic"] = options["topic"].strip("/")
            topics = options["topic"].split("/")
            self.title = topics
            if len(topics) < 2 or topics[0] != "jnpr" or topics[1] != "syslog":
                log.debug(
                    "The topic specified in configuration should start with "
                    '"jnpr/syslog". Using the default topic.'
                )
                self.title = ["jnpr", "syslog", "hostname", "event"]
            else:
                for i in range(2, len(topics)):
                    if topics[i] not in data:
                        log.debug(
                            "Please check the topic specified. Only the following "
                            "keywords can be specified in the topic: hostip, priority, "
                            "severity, facility, timestamp, hostname, daemon, pid, "
                            "message, event. Using the default topic."
                        )
                        self.title = ["jnpr", "syslog", "hostname", "event"]
                        break
            # We are done processing the topic. All other arguments are the
            # filters given by the user. While processing the filters we don't
            # explicitly ignore the 'topic', but delete it here itself.
            del self.options["topic"]
        else:
            self.title = ["jnpr", "syslog", "hostname", "event"]

    def parseData(self, data, host, port, options):
        """
        This function will parse the raw syslog data, dynamically create the
        topic according to the topic specified by the user (if specified) and
        decide whether to send the syslog data as an event on the master bus,
        based on the constraints given by the user.

        :param data: The raw syslog event data which is to be parsed.
        :param host: The IP of the host from where syslog is forwarded.
        :param port: Port of the junos device from which the data is sent
        :param options: kwargs provided by the user in the configuration file.
        :return: The result dictionary which contains the data and the topic,
                 if the event is to be sent on the bus.

        """
        data = self.obj.parse(data.decode())
        data["hostip"] = host
        log.debug(
            "Junos Syslog - received %s from %s, sent from port %s", data, host, port
        )

        send_this_event = True
        for key in options:
            if key in data:
                if isinstance(options[key], (str, int)):
                    if str(options[key]) != str(data[key]):
                        send_this_event = False
                        break
                elif isinstance(options[key], list):
                    for opt in options[key]:
                        if str(opt) == str(data[key]):
                            break
                    else:
                        send_this_event = False
                        break
                else:
                    raise Exception("Arguments in config not specified properly")
            else:
                raise Exception(
                    "Please check the arguments given to junos engine in the "
                    "configuration file"
                )

        if send_this_event:
            if "event" in data:
                topic = "jnpr/syslog"

                for i in range(2, len(self.title)):
                    topic += "/" + str(data[self.title[i]])
                    log.debug(
                        "Junos Syslog - sending this event on the bus: %s from %s",
                        data,
                        host,
                    )
                result = {"send": True, "data": data, "topic": topic}
                return result
            else:
                raise Exception("The incoming event data could not be parsed properly.")
        else:
            result = {"send": False}
            return result

    def send_event_to_salt(self, result):
        """
        This function identifies whether the engine is running on the master
        or the minion and sends the data to the master event bus accordingly.

        :param result: It's a dictionary which has the final data and topic.

        """
        if result["send"]:
            data = result["data"]
            topic = result["topic"]
            # If the engine is run on master, get the event bus and send the
            # parsed event.
            if __opts__["__role"] == "master":
                event.get_master_event(__opts__, __opts__["sock_dir"]).fire_event(
                    data, topic
                )
            # If the engine is run on minion, use the fire_master execution
            # module to send event on the master bus.
            else:
                __salt__["event.fire_master"](data=data, tag=topic)

    def handle_error(self, err_msg):
        """
        Log the error messages.
        """
        log.error(err_msg.getErrorMessage)

    def datagramReceived(self, data, connection_details):
        (host, port) = connection_details
        d = threads.deferToThread(self.parseData, data, host, port, self.options)
        d.addCallbacks(self.send_event_to_salt, self.handle_error)


def start(port=516, **kwargs):

    log.info("Starting junos syslog engine (port %s)", port)
    reactor.listenUDP(port, _SyslogServerFactory(kwargs))
    reactor.run()
