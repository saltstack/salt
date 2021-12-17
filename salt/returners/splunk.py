"""

Send json response data to Splunk via the HTTP Event Collector
Requires the following config values to be specified in config or pillar:

.. code-block:: yaml

    splunk_http_forwarder:
      token: <splunk_http_forwarder_token>
      indexer: <hostname/IP of Splunk indexer>
      sourcetype: <Destination sourcetype for data>
      index: <Destination index for data>
      verify_ssl: true

Run a test by using ``salt-call test.ping --return splunk``

Written by Scott Pack (github.com/scottjpack)

"""

import logging
import socket
import time

import requests
import salt.utils.json

_max_content_bytes = 100000
http_event_collector_debug = False

log = logging.getLogger(__name__)

__virtualname__ = "splunk"


def __virtual__():
    """
    Return virtual name of the module.
    :return: The virtual name of the module.
    """
    return __virtualname__


def returner(ret):
    """
    Send a message to Splunk via the HTTP Event Collector
    """
    return _send_splunk(ret)


def _get_options():
    try:
        token = __salt__["config.get"]("splunk_http_forwarder:token")
        indexer = __salt__["config.get"]("splunk_http_forwarder:indexer")
        sourcetype = __salt__["config.get"]("splunk_http_forwarder:sourcetype")
        index = __salt__["config.get"]("splunk_http_forwarder:index")
        verify_ssl = __salt__["config.get"](
            "splunk_http_forwarder:verify_ssl", default=True
        )
    except Exception:  # pylint: disable=broad-except
        log.error("Splunk HTTP Forwarder parameters not present in config.")
        return None
    splunk_opts = {
        "token": token,
        "indexer": indexer,
        "sourcetype": sourcetype,
        "index": index,
        "verify_ssl": verify_ssl,
    }
    return splunk_opts


def _send_splunk(event, index_override=None, sourcetype_override=None):
    """
    Send the results to Splunk.
    Requires the Splunk HTTP Event Collector running on port 8088.
    This is available on Splunk Enterprise version 6.3 or higher.

    """
    # Get Splunk Options
    opts = _get_options()
    log.info(
        "Options: %s",
        salt.utils.json.dumps(opts),
    )
    http_event_collector_key = opts["token"]
    http_event_collector_host = opts["indexer"]
    http_event_collector_verify_ssl = opts["verify_ssl"]
    # Set up the collector
    splunk_event = http_event_collector(
        http_event_collector_key,
        http_event_collector_host,
        verify_ssl=http_event_collector_verify_ssl,
    )
    # init the payload
    payload = {}

    # Set up the event metadata
    if index_override is None:
        payload.update({"index": opts["index"]})
    else:
        payload.update({"index": index_override})
    if sourcetype_override is None:
        payload.update({"sourcetype": opts["sourcetype"]})
    else:
        payload.update({"index": sourcetype_override})

    # Add the event
    payload.update({"event": event})
    log.info(
        "Payload: %s",
        salt.utils.json.dumps(payload),
    )
    # Fire it off
    splunk_event.sendEvent(payload)
    return True


# Thanks to George Starcher for the http_event_collector class (https://github.com/georgestarcher/)


class http_event_collector:
    def __init__(
        self,
        token,
        http_event_server,
        host="",
        http_event_port="8088",
        http_event_server_ssl=True,
        max_bytes=_max_content_bytes,
        verify_ssl=True,
    ):
        self.token = token
        self.batchEvents = []
        self.maxByteLength = max_bytes
        self.currentByteLength = 0
        self.verify_ssl = verify_ssl

        # Set host to specified value or default to localhostname if no value provided
        if host:
            self.host = host
        else:
            self.host = socket.gethostname()

        # Build and set server_uri for http event collector
        # Defaults to SSL if flag not passed
        # Defaults to port 8088 if port not passed

        if http_event_server_ssl:
            buildURI = ["https://"]
        else:
            buildURI = ["http://"]
        for i in [http_event_server, ":", http_event_port, "/services/collector/event"]:
            buildURI.append(i)
        self.server_uri = "".join(buildURI)

        if http_event_collector_debug:
            log.debug(self.token)
            log.debug(self.server_uri)

    def sendEvent(self, payload, eventtime=""):
        # Method to immediately send an event to the http event collector

        headers = {"Authorization": "Splunk " + self.token}

        # If eventtime in epoch not passed as optional argument use current system time in epoch
        if not eventtime:
            eventtime = str(int(time.time()))

        # Fill in local hostname if not manually populated
        if "host" not in payload:
            payload.update({"host": self.host})

        # Update time value on payload if need to use system time
        data = {"time": eventtime}
        data.update(payload)

        # send event to http event collector
        r = requests.post(
            self.server_uri,
            data=salt.utils.json.dumps(data),
            headers=headers,
            verify=self.verify_ssl,
        )

        # Print debug info if flag set
        if http_event_collector_debug:
            log.debug(r.text)
            log.debug(data)

    def batchEvent(self, payload, eventtime=""):
        # Method to store the event in a batch to flush later

        # Fill in local hostname if not manually populated
        if "host" not in payload:
            payload.update({"host": self.host})

        serialized_payload = salt.utils.json.dumps(payload)
        payloadLength = len(serialized_payload)

        if (self.currentByteLength + payloadLength) > self.maxByteLength:
            self.flushBatch()
            # Print debug info if flag set
            if http_event_collector_debug:
                log.debug("auto flushing")
        else:
            self.currentByteLength = self.currentByteLength + payloadLength

        # If eventtime in epoch not passed as optional argument use current system time in epoch
        if not eventtime:
            eventtime = str(int(time.time()))

        # Update time value on payload if need to use system time
        data = {"time": eventtime}
        data.update(payload)

        self.batchEvents.append(serialized_payload)

    def flushBatch(self):
        # Method to flush the batch list of events

        if len(self.batchEvents) > 0:
            headers = {"Authorization": "Splunk " + self.token}
            r = requests.post(
                self.server_uri,
                data=" ".join(self.batchEvents),
                headers=headers,
                verify=self.verify_ssl,
            )
            self.batchEvents = []
            self.currentByteLength = 0
