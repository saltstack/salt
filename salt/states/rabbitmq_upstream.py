# -*- coding: utf-8 -*-
"""
Manage RabbitMQ Upstreams
=========================

Example:

.. code-block:: yaml

    rabbit_upstream:
      rabbitmq_upstream.present:
      - name: upstream_1
      - uri: amqp://my_user:my_password@rabbitmq_host
      - trust_user_id: True
      - ack_mode: on-confirm
      - max_hops: 1

.. versionadded:: 3000
"""

# Import python libs
from __future__ import absolute_import

import json
import logging

# Import salt libs
import salt.utils.data
import salt.utils.dictdiffer
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if the appropriate rabbitmq module functions are loaded.
    """
    requirements = [
        "rabbitmq.list_upstreams",
        "rabbitmq.upstream_exists",
        "rabbitmq.set_upstream",
        "rabbitmq.delete_upstream",
    ]
    return all(req in __salt__ for req in requirements)


def present(
    name,
    uri,
    prefetch_count=None,
    reconnect_delay=None,
    ack_mode=None,
    trust_user_id=None,
    exchange=None,
    max_hops=None,
    expires=None,
    message_ttl=None,
    ha_policy=None,
    queue=None,
    runas=None,
):
    """
    Ensure the RabbitMQ upstream exists.

    :param str name: The name of the upstream connection
    :param str uri: The URI to connect to. If upstream is a cluster and can have
        several URIs, you can enter them here separated by spaces.
        Examples:
        - amqp://user:password@server_name
        - amqp://user:password@server_name/vhost
        When connecting with SSL, several URI-parameters need also be specified:
        - cacertfile = /path/to/cacert.pem
        - certfile = /path/to/cert.pem
        - keyfile = /part/to/key.pem
        - verity = verify_peer
        - fail_if_no_peer_cert = true | false
        - auth_mechanism = external
        Example:
        - amqp://user:password@server_name?cacertfile=/path/to/cacert.pem&\
            certfile=/path/to/cert.pem&keyfile=/path/to/key.pem&verify=verify_peer
        - amqp://server-name?cacertfile=/path/to/cacert.pem&certfile=/path/to/cert.pem&\
            keyfile=/path/to/key.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external
    :param int prefetch_count: Maximum number of unacknowledged messages that may
        be in flight over a federation link at one time. Default: 1000
    :param int reconnect_delay: Time in seconds to wait after a network link
        goes down before attempting reconnection. Default: 5
    :param str ack_mode: The following values are allowed:
        on-confirm: Messages are acknowledged to the upstream broker after they
        have been confirmed downstream. Handles network errors and broker failures
        without losing messages. The slowest option, and the default.
        on-publish: Messages are acknowledged to the upstream broker after they
        have been published downstream. Handles network errors without losing
        messages, but may lose messages in the event of broker failures.
        no-ack: Message acknowledgements are not used. The fastest option, but
        you may lose messages in the event of network or broker failures.
    :param bool trust_user_id: Set ``True`` to preserve the "user-id" field across
        a federation link, even if the user-id does not match that used to republish
        the message. Set to ``False`` to clear the "user-id" field when messages
        are federated. Only set this to ``True`` if you trust the upstream broker
        not to forge user-ids.
    :param str exchange: The name of the upstream exchange. Default is to use the
        same name as the federated exchange.
    :param int max_hops: Maximum number of federation links that messages can
        traverse before being dropped. Defaults to 1 if not set.
    :param int expires: Time in milliseconds that the upstream should remember
        about this node for. After this time all upstream state will be removed.
        Set to ``None`` (Default) to mean "forever".
    :param int message_ttl: Time in milliseconds that undelivered messages should
        be held upstream when there is a network outage or backlog.
        Set to ``None`` (default) to mean "forever".
    :param str ha_policy: Determines the "x-ha-policy"-argument for the upstream
        queue for a federated exchange. Default is "none" meaning the queue is
        not HA.
    :param str queue: The name of the upstream queue. Default is to use the same
        name as the federated queue.

    .. versionadded:: 3000

    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    action = None

    try:
        current_upstreams = __salt__["rabbitmq.list_upstreams"](runas=runas)
    except CommandExecutionError as err:
        ret["comment"] = "Error: {0}".format(err)
        return ret
    new_config = salt.utils.data.filter_falsey(
        {
            "uri": uri,
            "prefetch-count": prefetch_count,
            "reconnect-delay": reconnect_delay,
            "ack-mode": ack_mode,
            "trust-user-id": trust_user_id,
            "exchange": exchange,
            "max-hops": max_hops,
            "expires": expires,
            "message-ttl": message_ttl,
            "ha-policy": ha_policy,
            "queue": queue,
        }
    )

    if name in current_upstreams:
        current_config = json.loads(current_upstreams.get(name, ""))
        diff_config = salt.utils.dictdiffer.deep_diff(current_config, new_config)
        if diff_config:
            action = "update"
        else:
            ret["result"] = True
            ret["comment"] = 'Upstream "{}" already present as specified.'.format(name)
    else:
        action = "create"
        diff_config = {"old": None, "new": new_config}

    if action:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = 'Upstream "{}" would have been {}d.'.format(name, action)
        else:
            try:
                res = __salt__["rabbitmq.set_upstream"](
                    name,
                    uri,
                    prefetch_count=prefetch_count,
                    reconnect_delay=reconnect_delay,
                    ack_mode=ack_mode,
                    trust_user_id=trust_user_id,
                    exchange=exchange,
                    max_hops=max_hops,
                    expires=expires,
                    message_ttl=message_ttl,
                    ha_policy=ha_policy,
                    queue=queue,
                    runas=runas,
                )
                ret["result"] = res
                ret["comment"] = 'Upstream "{}" {}d.'.format(name, action)
                ret["changes"] = diff_config
            except CommandExecutionError as exp:
                ret["comment"] = "Error trying to {} upstream: {}".format(action, exp)
    return ret


def absent(name, runas=None):
    """
    Ensure the named upstream is absent.

    :param str name: The name of the upstream to remove
    :param str runas: User to run the command

    .. versionadded:: 3000
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    try:
        upstream_exists = __salt__["rabbitmq.upstream_exists"](name, runas=runas)
    except CommandExecutionError as err:
        ret["comment"] = "Error: {0}".format(err)
        return ret

    if upstream_exists:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = 'Upstream "{}" would have been deleted.'.format(name)
        else:
            try:
                res = __salt__["rabbitmq.delete_upstream"](name, runas=runas)
                if res:
                    ret["result"] = True
                    ret["comment"] = 'Upstream "{}" has been deleted.'.format(name)
                    ret["changes"] = {"old": name, "new": None}
            except CommandExecutionError as err:
                ret["comment"] = "Error: {0}".format(err)
    else:
        ret["result"] = True
        ret["comment"] = 'The upstream "{}" is already absent.'.format(name)
    return ret
