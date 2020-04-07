# -*- coding: utf-8 -*-
"""
Create an Event in VictorOps
============================

.. versionadded:: 2015.8.0

This state is useful for creating events on the
VictorOps service during state runs.

.. code-block:: yaml

    webserver-warning-message:
      victorops.create_event:
        - message_type: 'CRITICAL'
        - entity_id: 'webserver/diskspace'
        - state_message: 'Webserver diskspace is low.'
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if the victorops module is available in __salt__
    """
    return "victorops" if "victorops.create_event" in __salt__ else False


def create_event(name, message_type, routing_key="everyone", **kwargs):
    """
    Create an event on the VictorOps service

    .. code-block:: yaml

        webserver-warning-message:
          victorops.create_event:
            - message_type: 'CRITICAL'
            - entity_id: 'webserver/diskspace'
            - state_message: 'Webserver diskspace is low.'

        database-server-warning-message:
          victorops.create_event:
            - message_type: 'WARNING'
            - entity_id: 'db_server/load'
            - state_message: 'Database Server load is high.'
            - entity_is_host: True
            - entity_display_name: 'dbdserver.example.com'

    The following parameters are required:

    name
        This is a short description of the event.

    message_type
        One of the following values: INFO, WARNING, ACKNOWLEDGEMENT, CRITICAL, RECOVERY.

    The following parameters are optional:

        routing_key
            The key for where messages should be routed. By default, sent to 'everyone' route.

        entity_id
            The name of alerting entity. If not provided, a random name will be assigned.

        timestamp
            Timestamp of the alert in seconds since epoch. Defaults to the time the alert is received at VictorOps.

        timestamp_fmt
            The date format for the timestamp parameter.  Defaults to ''%Y-%m-%dT%H:%M:%S'.

        state_start_time
            The time this entity entered its current state (seconds since epoch). Defaults to the time alert is received.

        state_start_time_fmt
            The date format for the timestamp parameter. Defaults to '%Y-%m-%dT%H:%M:%S'.

        state_message
            Any additional status information from the alert item.

        entity_is_host
            Used within VictorOps to select the appropriate display format for the incident.

        entity_display_name
            Used within VictorOps to display a human-readable name for the entity.

        ack_message
            A user entered comment for the acknowledgment.

        ack_author
            The user that acknowledged the incident.

    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if __opts__["test"]:
        ret["comment"] = "Need to create event: {0}".format(name)
        return ret

    res = __salt__["victorops.create_event"](
        message_type=message_type, routing_key=routing_key, **kwargs
    )
    if res["result"] == "success":
        ret["result"] = True
        ret["comment"] = "Created event: {0} for entity {1}".format(
            name, res["entity_id"]
        )
    else:
        ret["result"] = False
        ret["comment"] = "Failed to create event: {0}".format(res["message"])
    return ret
