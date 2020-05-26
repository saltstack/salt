# -*- coding: utf-8 -*-
"""
IRC Bot engine

.. versionadded:: 2017.7.0

Example Configuration

.. code-block:: yaml

    engines:
      - ircbot:
          nick: <nick>
          username: <username>
          password: <password>
          host: chat.freenode.net
          port: 7000
          channels:
            - salt-test
            - '##something'
          use_ssl: True
          use_sasl: True
          disable_query: True
          allow_hosts:
            - salt/engineer/.*
          allow_nicks:
            - gtmanfred

Available commands on irc are:

ping
    return pong

echo <stuff>
    return <stuff> targeted at the user who sent the commands

event <tag> [<extra>, <data>]
    fire event on the master or minion event stream with the tag `salt/engines/ircbot/<tag>` and a data object with a
    list of everything else sent in the message

Example of usage

.. code-block:: text

    08:33:57 @gtmanfred > !ping
    08:33:57   gtmanbot > gtmanfred: pong
    08:34:02 @gtmanfred > !echo ping
    08:34:02   gtmanbot > ping
    08:34:17 @gtmanfred > !event test/tag/ircbot irc is useful
    08:34:17   gtmanbot > gtmanfred: TaDa!

.. code-block:: text

    [DEBUG   ] Sending event: tag = salt/engines/ircbot/test/tag/ircbot; data = {'_stamp': '2016-11-28T14:34:16.633623', 'data': ['irc', 'is', 'useful']}

"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libraries
import base64
import logging
import re
import socket
import ssl
from collections import namedtuple

import salt.ext.tornado.ioloop
import salt.ext.tornado.iostream

# Import salt libraries
import salt.utils.event

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


# Nothing listening here
Event = namedtuple("Event", "source code line")
PrivEvent = namedtuple("PrivEvent", "source nick user host code channel command line")


class IRCClient(object):
    def __init__(
        self,
        nick,
        host,
        port=6667,
        username=None,
        password=None,
        channels=None,
        use_ssl=False,
        use_sasl=False,
        char="!",
        allow_hosts=False,
        allow_nicks=False,
        disable_query=True,
    ):
        self.nick = nick
        self.host = host
        self.port = port
        self.username = username or nick
        self.password = password
        self.channels = channels or []
        self.ssl = use_ssl
        self.sasl = use_sasl
        self.char = char
        self.allow_hosts = allow_hosts
        self.allow_nicks = allow_nicks
        self.disable_query = disable_query
        self.io_loop = salt.ext.tornado.ioloop.IOLoop(make_current=False)
        self.io_loop.make_current()
        self._connect()

    def _connect(self):
        _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        if self.ssl is True:
            self._stream = salt.ext.tornado.iostream.SSLIOStream(
                _sock, ssl_options={"cert_reqs": ssl.CERT_NONE}
            )
        else:
            self._stream = salt.ext.tornado.iostream.IOStream(_sock)
        self._stream.set_close_callback(self.on_closed)
        self._stream.connect((self.host, self.port), self.on_connect)

    def read_messages(self):
        self._stream.read_until("\r\n", self._message)

    @staticmethod
    def _event(line):
        log.debug("Received: %s", line)
        search = re.match(
            "^(?:(?P<source>:[^ ]+) )?(?P<code>[^ ]+)(?: (?P<line>.*))?$", line
        )
        source, code, line = (
            search.group("source"),
            search.group("code"),
            search.group("line"),
        )
        return Event(source, code, line)

    def _allow_host(self, host):
        if isinstance(self.allow_hosts, bool):
            return self.allow_hosts
        else:
            return any([re.match(match, host) for match in self.allow_hosts])

    def _allow_nick(self, nick):
        if isinstance(self.allow_nicks, bool):
            return self.allow_nicks
        else:
            return any([re.match(match, nick) for match in self.allow_nicks])

    def _privmsg(self, event):
        search = re.match(
            "^:(?P<nick>[^!]+)!(?P<user>[^@]+)@(?P<host>.*)$", event.source
        )
        nick, user, host = (
            search.group("nick"),
            search.group("user"),
            search.group("host"),
        )
        search = re.match(
            "^(?P<channel>[^ ]+) :(?:{0}(?P<command>[^ ]+)(?: (?P<line>.*))?)?$".format(
                self.char
            ),
            event.line,
        )
        if search:
            channel, command, line = (
                search.group("channel"),
                search.group("command"),
                search.group("line"),
            )
            if self.disable_query is True and not channel.startswith("#"):
                return
            if channel == self.nick:
                channel = nick
            privevent = PrivEvent(
                event.source, nick, user, host, event.code, channel, command, line
            )
            if (self._allow_nick(nick) or self._allow_host(host)) and hasattr(
                self, "_command_{0}".format(command)
            ):
                getattr(self, "_command_{0}".format(command))(privevent)

    def _command_echo(self, event):
        message = "PRIVMSG {0} :{1}".format(event.channel, event.line)
        self.send_message(message)

    def _command_ping(self, event):
        message = "PRIVMSG {0} :{1}: pong".format(event.channel, event.nick)
        self.send_message(message)

    def _command_event(self, event):
        if __opts__.get("__role") == "master":
            fire_master = salt.utils.event.get_master_event(
                __opts__, __opts__["sock_dir"]
            ).fire_event
        else:
            fire_master = None

        def fire(tag, msg):
            """
            How to fire the event
            """
            if fire_master:
                fire_master(msg, tag)
            else:
                __salt__["event.send"](tag, msg)

        args = event.line.split(" ")
        tag = args[0]
        if len(args) > 1:
            payload = {"data": args[1:]}
        else:
            payload = {"data": []}

        fire("salt/engines/ircbot/" + tag, payload)
        message = "PRIVMSG {0} :{1}: TaDa!".format(event.channel, event.nick)
        self.send_message(message)

    def _message(self, raw):
        raw = raw.rstrip(b"\r\n").decode("utf-8")
        event = self._event(raw)

        if event.code == "PING":
            salt.ext.tornado.ioloop.IOLoop.current().spawn_callback(
                self.send_message, "PONG {0}".format(event.line)
            )
        elif event.code == "PRIVMSG":
            salt.ext.tornado.ioloop.IOLoop.current().spawn_callback(
                self._privmsg, event
            )
        self.read_messages()

    def join_channel(self, channel):
        if not channel.startswith("#"):
            channel = "#" + channel
        self.send_message("JOIN {0}".format(channel))

    def on_connect(self):
        logging.info("on_connect")
        if self.sasl is True:
            self.send_message("CAP REQ :sasl")
        self.send_message("NICK {0}".format(self.nick))
        self.send_message("USER saltstack 0 * :saltstack")
        if self.password:
            if self.sasl is True:
                authstring = base64.b64encode(
                    "{0}\x00{0}\x00{1}".format(self.username, self.password).encode()
                )
                self.send_message("AUTHENTICATE PLAIN")
                self.send_message("AUTHENTICATE {0}".format(authstring))
                self.send_message("CAP END")
            else:
                self.send_message(
                    "PRIVMSG NickServ :IDENTIFY {0} {1}".format(
                        self.username, self.password
                    )
                )
        for channel in self.channels:
            self.join_channel(channel)
        self.read_messages()

    def on_closed(self):
        logging.info("on_closed")

    def send_message(self, line):
        if isinstance(line, six.string_types):
            line = line.encode("utf-8")
        log.debug("Sending:  %s", line)
        self._stream.write(line + b"\r\n")


def start(
    nick,
    host,
    port=6667,
    username=None,
    password=None,
    channels=None,
    use_ssl=False,
    use_sasl=False,
    char="!",
    allow_hosts=False,
    allow_nicks=False,
    disable_query=True,
):
    """
    IRC Bot for interacting with salt.

    nick
        Nickname of the connected Bot.

    host
        irc server (example - chat.freenode.net).

    port
        irc port.  Default: 6667

    password
        password for authenticating.  If not provided, user will not authenticate on the irc server.

    channels
        channels to join.

    use_ssl
        connect to server using ssl. Default: False

    use_sasl
        authenticate using sasl, instead of messaging NickServ. Default: False

        .. note:: This will allow the bot user to be fully authenticated before joining any channels

    char
        command character to look for. Default: !

    allow_hosts
        hostmasks allowed to use commands on the bot.  Default: False
        True to allow all
        False to allow none
        List of regexes to allow matching

    allow_nicks
        Nicks that are allowed to use commands on the bot.  Default: False
        True to allow all
        False to allow none
        List of regexes to allow matching

    disable_query
        Disable commands from being sent through private queries.  Require they be sent to a channel, so that all
        communication can be controlled by access to the channel. Default: True

    .. warning:: Unauthenticated Access to event stream

        This engine sends events calls to the event stream without authenticating them in salt.  Authentication will
        need to be configured and enforced on the irc server or enforced in the irc channel.  The engine only accepts
        commands from channels, so non authenticated users could be banned or quieted in the channel.

        /mode +q $~a  # quiet all users who are not authenticated
        /mode +r      # do not allow unauthenticated users into the channel

        It would also be possible to add a password to the irc channel, or only allow invited users to join.
    """
    client = IRCClient(
        nick,
        host,
        port,
        username,
        password,
        channels or [],
        use_ssl,
        use_sasl,
        char,
        allow_hosts,
        allow_nicks,
        disable_query,
    )
    client.io_loop.start()
