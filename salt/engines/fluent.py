"""
An engine that reads messages from the salt event bus and pushes
them onto a fluent endpoint.

.. versionadded:: 3000

:Configuration:

All arguments are optional

    Example configuration of default settings

    .. code-block:: yaml

        engines:
          - fluent:
              host: localhost
              port: 24224
              app: engine

    Example fluentd configuration

    .. code-block:: none

        <source>
            @type forward
            port 24224
        </source>

        <match saltstack.**>
            @type file
            path /var/log/td-agent/saltstack
        </match>

:depends: fluent-logger
"""

import logging

import salt.utils.event

try:
    from fluent import event, sender
except ImportError:
    sender = None

log = logging.getLogger(__name__)

__virtualname__ = "fluent"


def __virtual__():
    return (
        __virtualname__
        if sender is not None
        else (False, "fluent-logger not installed")
    )


def start(host="localhost", port=24224, app="engine"):
    """
    Listen to salt events and forward them to fluent

    args:
        host (str): Host running fluentd agent. Default is localhost
        port (int): Port of fluentd agent. Default is 24224
        app (str): Text sent as fluentd tag. Default is "engine". This text is appended
                   to "saltstack." to form a fluentd tag, ex: "saltstack.engine"
    """
    SENDER_NAME = "saltstack"

    sender.setup(SENDER_NAME, host=host, port=port)

    if __opts__.get("id").endswith("_master"):
        event_bus = salt.utils.event.get_master_event(
            __opts__, __opts__["sock_dir"], listen=True
        )
    else:
        event_bus = salt.utils.event.get_event(
            "minion",
            opts=__opts__,
            sock_dir=__opts__["sock_dir"],
            listen=True,
        )
    log.info("Fluent engine started")

    with event_bus:
        while True:
            salt_event = event_bus.get_event_block()
            if salt_event:
                event.Event(app, salt_event)
