"""
An engine that sends events to the Logentries logging service.

:maintainer:  Jimmy Tang (jimmy_tang@rapid7.com)
:maturity:    New
:depends:     ssl, certifi
:platform:    all

.. versionadded:: 2016.3.0

To enable this engine the master and/or minion will need the following
python libraries

    ssl
    certifi

If you are running a new enough version of python then the ssl library
will be present already.

You will also need the following values configured in the minion or
master config.

:configuration:

    Example configuration

    .. code-block:: yaml

        engines:
          - logentries:
              endpoint: data.logentries.com
              port: 10000
              token: 057af3e2-1c05-47c5-882a-5cd644655dbf

The 'token' can be obtained from the Logentries service.

To test this engine

    .. code-block:: bash

         salt '*' test.ping cmd.run uptime

"""

import logging
import random
import socket
import time
import uuid

import salt.utils.event
import salt.utils.json

try:
    import certifi

    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False

# This is here for older python installs, it is needed to setup an encrypted tcp connection
try:
    import ssl

    HAS_SSL = True
except ImportError:  # for systems without TLS support.
    HAS_SSL = False


log = logging.getLogger(__name__)


def __virtual__():
    return True if HAS_CERTIFI and HAS_SSL else False


class PlainTextSocketAppender:
    def __init__(
        self, verbose=True, LE_API="data.logentries.com", LE_PORT=80, LE_TLS_PORT=443
    ):

        self.LE_API = LE_API
        self.LE_PORT = LE_PORT
        self.LE_TLS_PORT = LE_TLS_PORT
        self.MIN_DELAY = 0.1
        self.MAX_DELAY = 10
        # Error message displayed when an incorrect Token has been detected
        self.INVALID_TOKEN = (
            "\n\nIt appears the LOGENTRIES_TOKEN "
            "parameter you entered is incorrect!\n\n"
        )
        # Encoded unicode line separator
        self.LINE_SEP = salt.utils.stringutils.to_str("\u2028")

        self.verbose = verbose
        self._conn = None

    def open_connection(self):
        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._conn.connect((self.LE_API, self.LE_PORT))

    def reopen_connection(self):
        self.close_connection()

        root_delay = self.MIN_DELAY
        while True:
            try:
                self.open_connection()
                return
            except Exception:  # pylint: disable=broad-except
                if self.verbose:
                    log.warning("Unable to connect to Logentries")

            root_delay *= 2
            if root_delay > self.MAX_DELAY:
                root_delay = self.MAX_DELAY

            wait_for = root_delay + random.uniform(0, root_delay)

            try:
                time.sleep(wait_for)
            except KeyboardInterrupt:  # pylint: disable=try-except-raise
                raise

    def close_connection(self):
        if self._conn is not None:
            self._conn.close()

    def put(self, data):
        # Replace newlines with Unicode line separator for multi-line events
        multiline = data.replace("\n", self.LINE_SEP) + str(
            "\n"
        )  # future lint: disable=blacklisted-function
        # Send data, reconnect if needed
        while True:
            try:
                self._conn.send(multiline)
            except OSError:
                self.reopen_connection()
                continue
            break

        self.close_connection()


try:
    import ssl

    HAS_SSL = True
except ImportError:  # for systems without TLS support.
    SocketAppender = PlainTextSocketAppender
    HAS_SSL = False
else:

    class TLSSocketAppender(PlainTextSocketAppender):
        def open_connection(self):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = ssl.wrap_socket(
                sock=sock,
                keyfile=None,
                certfile=None,
                server_side=False,
                cert_reqs=ssl.CERT_REQUIRED,
                ssl_version=getattr(ssl, "PROTOCOL_TLSv1_2", ssl.PROTOCOL_TLSv1),
                ca_certs=certifi.where(),
                do_handshake_on_connect=True,
                suppress_ragged_eofs=True,
            )
            sock.connect((self.LE_API, self.LE_TLS_PORT))
            self._conn = sock

    SocketAppender = TLSSocketAppender


def event_bus_context(opts):
    if opts.get("id").endswith("_master"):
        event_bus = salt.utils.event.get_master_event(
            opts, opts["sock_dir"], listen=True
        )
    else:
        event_bus = salt.utils.event.get_event(
            "minion",
            transport=opts["transport"],
            opts=opts,
            sock_dir=opts["sock_dir"],
            listen=True,
        )
    return event_bus


def start(
    endpoint="data.logentries.com",
    port=10000,
    token=None,
    tag="salt/engines/logentries",
):
    """
    Listen to salt events and forward them to Logentries
    """
    with event_bus_context(__opts__) as event_bus:
        log.debug("Logentries engine started")
        try:
            val = uuid.UUID(token)
        except ValueError:
            log.warning("Not a valid logentries token")

        appender = SocketAppender(verbose=False, LE_API=endpoint, LE_PORT=port)
        appender.reopen_connection()

        while True:
            event = event_bus.get_event()
            if event:
                # future lint: disable=blacklisted-function
                msg = " ".join(
                    (
                        salt.utils.stringutils.to_str(token),
                        salt.utils.stringutils.to_str(tag),
                        salt.utils.json.dumps(event),
                    )
                )
                # future lint: enable=blacklisted-function
                appender.put(msg)

        appender.close_connection()
