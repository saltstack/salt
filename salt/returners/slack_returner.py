# -*- coding: utf-8 -*-
"""
Return salt data via slack

..  versionadded:: 2015.5.0

The following fields can be set in the minion conf file:

.. code-block:: yaml

    slack.channel (required)
    slack.api_key (required)
    slack.username (required)
    slack.as_user (required to see the profile picture of your bot)
    slack.profile (optional)
    slack.changes(optional, only show changes and failed states)
    slack.only_show_failed(optional, only show failed states)
    slack.yaml_format(optional, format the json in yaml format)


Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    slack.channel
    slack.api_key
    slack.username
    slack.as_user

Slack settings may also be configured as:

.. code-block:: yaml

    slack:
        channel: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        username: user
        as_user: true

    alternative.slack:
        room_id: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        from_name: user@email.com

    slack_profile:
        slack.api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        slack.from_name: user@email.com

    slack:
        profile: slack_profile
        channel: RoomName

    alternative.slack:
        profile: slack_profile
        channel: RoomName

To use the Slack returner, append '--return slack' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return slack --return_kwargs '{"channel": "#random"}'

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Python libs
import pprint

# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six.moves.http_client

# Import Salt Libs
import salt.returners
import salt.utils.slack
import salt.utils.yaml
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode

# pylint: enable=import-error,no-name-in-module,redefined-builtin


log = logging.getLogger(__name__)

__virtualname__ = "slack"


def _get_options(ret=None):
    """
    Get the slack options from salt.
    """

    defaults = {"channel": "#general"}

    attrs = {
        "slack_profile": "profile",
        "channel": "channel",
        "username": "username",
        "as_user": "as_user",
        "api_key": "api_key",
        "changes": "changes",
        "only_show_failed": "only_show_failed",
        "yaml_format": "yaml_format",
    }

    profile_attr = "slack_profile"

    profile_attrs = {
        "from_jid": "from_jid",
        "api_key": "api_key",
        "api_version": "api_key",
    }

    _options = salt.returners.get_returner_options(
        __virtualname__,
        ret,
        attrs,
        profile_attr=profile_attr,
        profile_attrs=profile_attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults,
    )
    return _options


def __virtual__():
    """
    Return virtual name of the module.

    :return: The virtual name of the module.
    """
    return __virtualname__


def _post_message(channel, message, username, as_user, api_key=None):
    """
    Send a message to a Slack room.
    :param channel:     The room name.
    :param message:     The message to send to the Slack room.
    :param username:    Specify who the message is from.
    :param as_user:     Sets the profile picture which have been added through Slack itself.
    :param api_key:     The Slack api key, if not specified in the configuration.
    :param api_version: The Slack api version, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.
    """

    parameters = dict()
    parameters["channel"] = channel
    parameters["username"] = username
    parameters["as_user"] = as_user
    parameters["text"] = "```" + message + "```"  # pre-formatted, fixed-width text

    # Slack wants the body on POST to be urlencoded.
    result = salt.utils.slack.query(
        function="message",
        api_key=api_key,
        method="POST",
        header_dict={"Content-Type": "application/x-www-form-urlencoded"},
        data=_urlencode(parameters),
    )

    log.debug("Slack message post result: %s", result)
    if result:
        return True
    else:
        return False


def returner(ret):
    """
    Send an slack message with the data
    """

    _options = _get_options(ret)

    channel = _options.get("channel")
    username = _options.get("username")
    as_user = _options.get("as_user")
    api_key = _options.get("api_key")
    changes = _options.get("changes")
    only_show_failed = _options.get("only_show_failed")
    yaml_format = _options.get("yaml_format")

    if not channel:
        log.error("slack.channel not defined in salt config")
        return

    if not username:
        log.error("slack.username not defined in salt config")
        return

    if not as_user:
        log.error("slack.as_user not defined in salt config")
        return

    if not api_key:
        log.error("slack.api_key not defined in salt config")
        return

    if only_show_failed and changes:
        log.error(
            "cannot define both slack.changes and slack.only_show_failed in salt config"
        )
        return

    returns = ret.get("return")
    if changes is True:
        returns = {
            (key, value)
            for key, value in returns.items()
            if value["result"] is not True or value["changes"]
        }

    if only_show_failed is True:
        returns = {
            (key, value)
            for key, value in returns.items()
            if value["result"] is not True
        }

    if yaml_format is True:
        returns = salt.utils.yaml.safe_dump(returns)
    else:
        returns = pprint.pformat(returns)

    message = (
        "id: {0}\r\n"
        "function: {1}\r\n"
        "function args: {2}\r\n"
        "jid: {3}\r\n"
        "return: {4}\r\n"
    ).format(
        ret.get("id"), ret.get("fun"), ret.get("fun_args"), ret.get("jid"), returns
    )

    slack = _post_message(channel, message, username, as_user, api_key)
    return slack
