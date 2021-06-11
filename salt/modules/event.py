"""
Use the :ref:`Salt Event System <events>` to fire events from the
master to the minion and vice-versa.
"""


import logging
import os
import sys
import traceback
from collections.abc import Mapping

import salt.crypt
import salt.payload
import salt.transport.client
import salt.utils.event
import salt.utils.zeromq

__proxyenabled__ = ["*"]
log = logging.getLogger(__name__)


def _dict_subset(keys, master_dict):
    """
    Return a dictionary of only the subset of keys/values specified in keys
    """
    return {k: v for k, v in master_dict.items() if k in keys}


def fire_master(data, tag, preload=None):
    """
    Fire an event off up to the master server

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire_master '{"data":"my event data"}' 'tag'
    """
    if (
        __opts__.get("local", None) or __opts__.get("file_client", None) == "local"
    ) and not __opts__.get("use_master_when_local", False):
        #  We can't send an event if we're in masterless mode
        log.warning("Local mode detected. Event with tag %s will NOT be sent.", tag)
        return False

    if preload or __opts__.get("__cli") == "salt-call":
        # If preload is specified, we must send a raw event (this is
        # slower because it has to independently authenticate)
        if "master_uri" not in __opts__:
            __opts__["master_uri"] = "tcp://{ip}:{port}".format(
                ip=salt.utils.zeromq.ip_bracket(__opts__["interface"]),
                port=__opts__.get("ret_port", "4506"),  # TODO, no fallback
            )
        masters = list()
        ret = True
        if "master_uri_list" in __opts__:
            for master_uri in __opts__["master_uri_list"]:
                masters.append(master_uri)
        else:
            masters.append(__opts__["master_uri"])
        auth = salt.crypt.SAuth(__opts__)
        load = {
            "id": __opts__["id"],
            "tag": tag,
            "data": data,
            "tok": auth.gen_token(b"salt"),
            "cmd": "_minion_event",
        }

        if isinstance(preload, dict):
            load.update(preload)

        for master in masters:
            with salt.transport.client.ReqChannel.factory(
                __opts__, master_uri=master
            ) as channel:
                try:
                    channel.send(load)
                    # channel.send was successful.
                    # Ensure ret is True.
                    ret = True
                except Exception:  # pylint: disable=broad-except
                    ret = False
        return ret
    else:
        # Usually, we can send the event via the minion, which is faster
        # because it is already authenticated
        try:
            return salt.utils.event.MinionEvent(__opts__, listen=False).fire_event(
                {"data": data, "tag": tag, "events": None, "pretag": None},
                "fire_master",
            )
        except Exception:  # pylint: disable=broad-except
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            log.debug(lines)
            return False


def fire(data, tag):
    """
    Fire an event on the local minion event bus. Data must be formed as a dict.

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire '{"data":"my event data"}' 'tag'
    """
    try:
        with salt.utils.event.get_event(
            "minion",  # was __opts__['id']
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
            opts=__opts__,
            listen=False,
        ) as event:
            return event.fire_event(data, tag)
    except Exception:  # pylint: disable=broad-except
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        log.debug(lines)
        return False


def send(
    tag,
    data=None,
    preload=None,
    with_env=False,
    with_grains=False,
    with_pillar=False,
    with_env_opts=False,
    **kwargs
):
    """
    Send an event to the Salt Master

    .. versionadded:: 2014.7.0

    :param tag: A tag to give the event.
        Use slashes to create a namespace for related events. E.g.,
        ``myco/build/buildserver1/start``, ``myco/build/buildserver1/success``,
        ``myco/build/buildserver1/failure``.

    :param data: A dictionary of data to send in the event.
        This is free-form. Send any data points that are needed for whoever is
        consuming the event. Arguments on the CLI are interpreted as YAML so
        complex data structures are possible.

    :param with_env: Include environment variables from the current shell
        environment in the event data as ``environ``.. This is a short-hand for
        working with systems that seed the environment with relevant data such
        as Jenkins.
    :type with_env: Specify ``True`` to include all environment variables, or
        specify a list of strings of variable names to include.

    :param with_grains: Include grains from the current minion in the event
        data as ``grains``.
    :type with_grains: Specify ``True`` to include all grains, or specify a
        list of strings of grain names to include.

    :param with_pillar: Include Pillar values from the current minion in the
        event data as ``pillar``. Remember Pillar data is often sensitive data
        so be careful. This is useful for passing ephemeral Pillar values
        through an event. Such as passing the ``pillar={}`` kwarg in
        :py:func:`state.sls <salt.modules.state.sls>` from the Master, through
        an event on the Minion, then back to the Master.
    :type with_pillar: Specify ``True`` to include all Pillar values, or
        specify a list of strings of Pillar keys to include. It is a
        best-practice to only specify a relevant subset of Pillar data.

    :param with_env_opts: Include ``saltenv`` and ``pillarenv`` set on minion
        at the moment when event is send into event data.
    :type with_env_opts: Specify ``True`` to include ``saltenv`` and
        ``pillarenv`` values or ``False`` to omit them.

    :param kwargs: Any additional keyword arguments passed to this function
        will be interpreted as key-value pairs and included in the event data.
        This provides a convenient alternative to YAML for simple values.

    CLI Example:

    .. code-block:: bash

        salt-call event.send myco/mytag foo=Foo bar=Bar
        salt-call event.send 'myco/mytag' '{foo: Foo, bar: Bar}'

    A convenient way to allow Jenkins to execute ``salt-call`` is via sudo. The
    following rule in sudoers will allow the ``jenkins`` user to run only the
    following command.

    ``/etc/sudoers`` (allow preserving the environment):

    .. code-block:: text

        jenkins ALL=(ALL) NOPASSWD:SETENV: /usr/bin/salt-call event.send*

    Call Jenkins via sudo (preserve the environment):

    .. code-block:: bash

        sudo -E salt-call event.send myco/jenkins/build/success with_env=[BUILD_ID, BUILD_URL, GIT_BRANCH, GIT_COMMIT]

    """
    data_dict = {}

    if with_env:
        if isinstance(with_env, list):
            data_dict["environ"] = _dict_subset(with_env, dict(os.environ))
        else:
            data_dict["environ"] = dict(os.environ)

    if with_grains:
        if isinstance(with_grains, list):
            data_dict["grains"] = _dict_subset(with_grains, __grains__)
        else:
            data_dict["grains"] = __grains__

    if with_pillar:
        if isinstance(with_pillar, list):
            data_dict["pillar"] = _dict_subset(with_pillar, __pillar__)
        else:
            data_dict["pillar"] = __pillar__

    if with_env_opts:
        data_dict["saltenv"] = __opts__.get("saltenv", "base")
        data_dict["pillarenv"] = __opts__.get("pillarenv")

    if kwargs:
        data_dict.update(kwargs)

    # Allow values in the ``data`` arg to override any of the above values.
    if isinstance(data, Mapping):
        data_dict.update(data)

    if (
        __opts__.get("local")
        or __opts__.get("file_client") == "local"
        or __opts__.get("master_type") == "disable"
    ) and not __opts__.get("use_master_when_local"):
        return fire(data_dict, tag)
    else:
        return fire_master(data_dict, tag, preload=preload)
