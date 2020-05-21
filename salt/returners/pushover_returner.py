# -*- coding: utf-8 -*-
"""
Return salt data via pushover (http://www.pushover.net)

.. versionadded:: 2016.3.0

The following fields can be set in the minion conf file::

    pushover.user (required)
    pushover.token (required)
    pushover.title (optional)
    pushover.device (optional)
    pushover.priority (optional)
    pushover.expire (optional)
    pushover.retry (optional)
    pushover.profile (optional)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    alternative.pushover.user
    alternative.pushover.token
    alternative.pushover.title
    alternative.pushover.device
    alternative.pushover.priority
    alternative.pushover.expire
    alternative.pushover.retry

PushOver settings may also be configured as::

    pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        title: Salt Returner
        device: phone
        priority: -1
        expire: 3600
        retry: 5

    alternative.pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        title: Salt Returner
        device: phone
        priority: 1
        expire: 4800
        retry: 2

    pushover_profile:
        pushover.token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

    pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        profile: pushover_profile

    alternative.pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        profile: pushover_profile

  To use the PushOver returner, append '--return pushover' to the salt command. ex:

  .. code-block:: bash

    salt '*' test.ping --return pushover

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return pushover --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return pushover --return_kwargs '{"title": "Salt is awesome!"}'

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Python libs
import pprint

# Import Salt Libs
import salt.returners
import salt.utils.pushover
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode

# pylint: enable=import-error,no-name-in-module,redefined-builtin


log = logging.getLogger(__name__)

__virtualname__ = "pushover"


def _get_options(ret=None):
    """
    Get the pushover options from salt.
    """

    defaults = {"priority": "0"}

    attrs = {
        "pushover_profile": "profile",
        "user": "user",
        "device": "device",
        "token": "token",
        "priority": "priority",
        "title": "title",
        "api_version": "api_version",
        "expire": "expire",
        "retry": "retry",
        "sound": "sound",
    }

    profile_attr = "pushover_profile"

    profile_attrs = {
        "user": "user",
        "device": "device",
        "token": "token",
        "priority": "priority",
        "title": "title",
        "api_version": "api_version",
        "expire": "expire",
        "retry": "retry",
        "sound": "sound",
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


def _post_message(
    user,
    device,
    message,
    title,
    priority,
    expire,
    retry,
    sound,
    api_version=1,
    token=None,
):
    """
    Send a message to a Pushover user or group.
    :param user:        The user or group to send to, must be key of user or group not email address.
    :param message:     The message to send to the PushOver user or group.
    :param title:       Specify who the message is from.
    :param priority     The priority of the message, defaults to 0.
    :param api_version: The PushOver API version, if not specified in the configuration.
    :param notify:      Whether to notify the room, default: False.
    :param token:       The PushOver token, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.
    """

    user_validate = salt.utils.pushover.validate_user(user, device, token)
    if not user_validate["result"]:
        return user_validate

    parameters = dict()
    parameters["user"] = user
    parameters["device"] = device
    parameters["token"] = token
    parameters["title"] = title
    parameters["priority"] = priority
    parameters["expire"] = expire
    parameters["retry"] = retry
    parameters["message"] = message

    if sound:
        sound_validate = salt.utils.pushover.validate_sound(sound, token)
        if sound_validate["res"]:
            parameters["sound"] = sound

    result = salt.utils.pushover.query(
        function="message",
        method="POST",
        header_dict={"Content-Type": "application/x-www-form-urlencoded"},
        data=_urlencode(parameters),
        opts=__opts__,
    )

    return result


def returner(ret):
    """
    Send an PushOver message with the data
    """

    _options = _get_options(ret)

    user = _options.get("user")
    device = _options.get("device")
    token = _options.get("token")
    title = _options.get("title")
    priority = _options.get("priority")
    expire = _options.get("expire")
    retry = _options.get("retry")
    sound = _options.get("sound")

    if not token:
        raise SaltInvocationError("Pushover token is unavailable.")

    if not user:
        raise SaltInvocationError("Pushover user key is unavailable.")

    if priority and priority == 2:
        if not expire and not retry:
            raise SaltInvocationError(
                "Priority 2 requires pushover.expire and pushover.retry options."
            )

    message = (
        "id: {0}\r\n"
        "function: {1}\r\n"
        "function args: {2}\r\n"
        "jid: {3}\r\n"
        "return: {4}\r\n"
    ).format(
        ret.get("id"),
        ret.get("fun"),
        ret.get("fun_args"),
        ret.get("jid"),
        pprint.pformat(ret.get("return")),
    )

    result = _post_message(
        user=user,
        device=device,
        message=message,
        title=title,
        priority=priority,
        expire=expire,
        retry=retry,
        sound=sound,
        token=token,
    )

    log.debug("pushover result %s", result)
    if not result["res"]:
        log.info("Error: %s", result["message"])
    return
