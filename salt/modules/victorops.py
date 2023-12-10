"""
Support for VictorOps

.. versionadded:: 2015.8.0

Requires an ``api_key`` in ``/etc/salt/minion``:

.. code-block:: yaml

    victorops:
      api_key: '280d4699-a817-4719-ba6f-ca56e573e44f'
"""


import datetime
import logging
import time

import salt.utils.http
import salt.utils.json
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

_api_key_missing_error = "No VictorOps api key found."


def __virtual__():
    """
    Only load the module if apache is installed
    """
    if not __salt__["config.get"]("victorops.api_key") and not __salt__["config.get"](
        "victorops:api_key"
    ):
        return (False, _api_key_missing_error)
    return True


def _query(
    action=None, routing_key=None, args=None, method="GET", header_dict=None, data=None
):
    """
    Make a web call to VictorOps
    """
    api_key = __salt__["config.get"]("victorops.api_key") or __salt__["config.get"](
        "victorops:api_key"
    )

    path = "https://alert.victorops.com/integrations/generic/20131114/"

    if action:
        path += "{}/".format(action)

    if api_key:
        path += "{}/".format(api_key)

    if routing_key:
        path += routing_key

    log.debug("VictorOps URL: %s", path)

    if not isinstance(args, dict):
        args = {}

    if header_dict is None:
        header_dict = {"Content-type": "application/json"}

    if method != "POST":
        header_dict["Accept"] = "application/json"

    decode = True
    if method == "DELETE":
        decode = False

    result = salt.utils.http.query(
        path,
        method,
        params=args,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type="json",
        text=True,
        status=True,
        cookies=True,
        persist_session=True,
        opts=__opts__,
    )
    if "error" in result:
        log.error(result["error"])
        return [result["status"], result["error"]]

    return [result["status"], result.get("dict", {})]


def create_event(message_type=None, routing_key="everybody", **kwargs):
    """
    Create an event in VictorOps. Designed for use in states.

    The following parameters are required:

    :param message_type:            One of the following values: INFO, WARNING, ACKNOWLEDGEMENT, CRITICAL, RECOVERY.

    The following parameters are optional:

    :param routing_key:             The key for where messages should be routed. By default, sent to
                                    'everyone' route.

    :param entity_id:               The name of alerting entity. If not provided, a random name will be assigned.

    :param timestamp:               Timestamp of the alert in seconds since epoch. Defaults to the
                                    time the alert is received at VictorOps.

    :param timestamp_fmt            The date format for the timestamp parameter.

    :param state_start_time:        The time this entity entered its current state
                                    (seconds since epoch). Defaults to the time alert is received.

    :param state_start_time_fmt:    The date format for the timestamp parameter.

    :param state_message:           Any additional status information from the alert item.

    :param entity_is_host:          Used within VictorOps to select the appropriate
                                    display format for the incident.

    :param entity_display_name:     Used within VictorOps to display a human-readable name for the entity.

    :param ack_message:             A user entered comment for the acknowledgment.

    :param ack_author:              The user that acknowledged the incident.

    :return:                        A dictionary with result, entity_id, and message if result was failure.

    CLI Example:

    .. code-block:: yaml

        salt myminion victorops.create_event message_type='CRITICAL' routing_key='everyone' \
                 entity_id='hostname/diskspace'

        salt myminion victorops.create_event message_type='ACKNOWLEDGEMENT' routing_key='everyone' \
                 entity_id='hostname/diskspace' ack_message='Acknowledged' ack_author='username'

        salt myminion victorops.create_event message_type='RECOVERY' routing_key='everyone' \
                 entity_id='hostname/diskspace'

    The following parameters are required:
        message_type

    """

    keyword_args = {
        "entity_id": str,
        "state_message": str,
        "entity_is_host": bool,
        "entity_display_name": str,
        "ack_message": str,
        "ack_author": str,
    }

    data = {}

    if not message_type:
        raise SaltInvocationError('Required argument "message_type" is missing.')

    if message_type.upper() not in [
        "INFO",
        "WARNING",
        "ACKNOWLEDGEMENT",
        "CRITICAL",
        "RECOVERY",
    ]:
        raise SaltInvocationError(
            '"message_type" must be INFO, WARNING, ACKNOWLEDGEMENT, CRITICAL, or'
            " RECOVERY."
        )

    data["message_type"] = message_type

    data["monitoring_tool"] = "SaltStack"

    if "timestamp" in kwargs:
        timestamp_fmt = kwargs.get("timestamp_fmt", "%Y-%m-%dT%H:%M:%S")

        try:
            timestamp = datetime.datetime.strptime(kwargs["timestamp"], timestamp_fmt)
            data["timestamp"] = int(time.mktime(timestamp.timetuple()))
        except (TypeError, ValueError):
            raise SaltInvocationError(
                "Date string could not be parsed: {}, {}".format(
                    kwargs["timestamp"], timestamp_fmt
                )
            )

    if "state_start_time" in kwargs:
        state_start_time_fmt = kwargs.get("state_start_time_fmt", "%Y-%m-%dT%H:%M:%S")

        try:
            state_start_time = datetime.datetime.strptime(
                kwargs["state_start_time"], state_start_time_fmt
            )
            data["state_start_time"] = int(time.mktime(state_start_time.timetuple()))
        except (TypeError, ValueError):
            raise SaltInvocationError(
                "Date string could not be parsed: {}, {}".format(
                    kwargs["state_start_time"], state_start_time_fmt
                )
            )

    for kwarg in keyword_args:
        if kwarg in kwargs:
            if isinstance(kwargs[kwarg], keyword_args[kwarg]):
                data[kwarg] = kwargs[kwarg]
            else:
                # Should this faile on the wrong type.
                log.error("Wrong type, skipping %s", kwarg)

    status, result = _query(
        action="alert",
        routing_key=routing_key,
        data=salt.utils.json.dumps(data),
        method="POST",
    )
    return result
