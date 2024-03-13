"""
Module providing a simple management interface to a marathon cluster.

Currently this only works when run through a proxy minion.

.. versionadded:: 2015.8.2
"""

import logging

import salt.utils.http
import salt.utils.json
import salt.utils.platform
from salt.exceptions import get_error_message

__proxyenabled__ = ["marathon"]
log = logging.getLogger(__file__)


def __virtual__():
    # only valid in proxy minions for now
    if salt.utils.platform.is_proxy() and "proxy" in __opts__:
        return True
    return (
        False,
        "The marathon execution module cannot be loaded: this only works on "
        "proxy minions.",
    )


def _base_url():
    """
    Return the proxy configured base url.
    """
    base_url = "http://locahost:8080"
    if "proxy" in __opts__:
        base_url = __opts__["proxy"].get("base_url", base_url)
    return base_url


def _app_id(app_id):
    """
    Make sure the app_id is in the correct format.
    """
    if app_id[0] != "/":
        app_id = f"/{app_id}"
    return app_id


def apps():
    """
    Return a list of the currently installed app ids.

    CLI Example:

    .. code-block:: bash

        salt marathon-minion-id marathon.apps
    """
    response = salt.utils.http.query(
        f"{_base_url()}/v2/apps",
        decode_type="json",
        decode=True,
    )
    return {"apps": [app["id"] for app in response["dict"]["apps"]]}


def has_app(id):
    """
    Return whether the given app id is currently configured.

    CLI Example:

    .. code-block:: bash

        salt marathon-minion-id marathon.has_app my-app
    """
    return _app_id(id) in apps()["apps"]


def app(id):
    """
    Return the current server configuration for the specified app.

    CLI Example:

    .. code-block:: bash

        salt marathon-minion-id marathon.app my-app
    """
    response = salt.utils.http.query(
        f"{_base_url()}/v2/apps/{id}",
        decode_type="json",
        decode=True,
    )
    return response["dict"]


def update_app(id, config):
    """
    Update the specified app with the given configuration.

    CLI Example:

    .. code-block:: bash

        salt marathon-minion-id marathon.update_app my-app '<config yaml>'
    """
    if "id" not in config:
        config["id"] = id
    config.pop("version", None)
    # mirror marathon-ui handling for uris deprecation (see
    # mesosphere/marathon-ui#594 for more details)
    config.pop("fetch", None)
    data = salt.utils.json.dumps(config)
    try:
        response = salt.utils.http.query(
            f"{_base_url()}/v2/apps/{id}?force=true",
            method="PUT",
            decode_type="json",
            decode=True,
            data=data,
            header_dict={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        log.debug("update response: %s", response)
        return response["dict"]
    except Exception as ex:  # pylint: disable=broad-except
        log.error("unable to update marathon app: %s", get_error_message(ex))
        return {"exception": {"message": get_error_message(ex)}}


def rm_app(id):
    """
    Remove the specified app from the server.

    CLI Example:

    .. code-block:: bash

        salt marathon-minion-id marathon.rm_app my-app
    """
    response = salt.utils.http.query(
        f"{_base_url()}/v2/apps/{id}",
        method="DELETE",
        decode_type="json",
        decode=True,
    )
    return response["dict"]


def info():
    """
    Return configuration and status information about the marathon instance.

    CLI Example:

    .. code-block:: bash

        salt marathon-minion-id marathon.info
    """
    response = salt.utils.http.query(
        f"{_base_url()}/v2/info",
        decode_type="json",
        decode=True,
    )
    return response["dict"]


def restart_app(id, restart=False, force=True):
    """
    Restart the current server configuration for the specified app.

    :param restart: Restart the app
    :param force: Override the current deployment

    CLI Example:

    .. code-block:: bash

        salt marathon-minion-id marathon.restart_app my-app

    By default, this will only check if the app exists in marathon. It does
    not check if there are any tasks associated with it or if the app is suspended.

    .. code-block:: bash

        salt marathon-minion-id marathon.restart_app my-app true true

    The restart option needs to be set to True to actually issue a rolling
    restart to marathon.

    The force option tells marathon to ignore the current app deployment if
    there is one.
    """
    ret = {"restarted": None}
    if not restart:
        ret["restarted"] = False
        return ret
    try:
        response = salt.utils.http.query(
            f"{_base_url()}/v2/apps/{_app_id(id)}/restart?force={force}",
            method="POST",
            decode_type="json",
            decode=True,
            header_dict={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        log.debug("restart response: %s", response)

        ret["restarted"] = True
        ret.update(response["dict"])
        return ret
    except Exception as ex:  # pylint: disable=broad-except
        log.error("unable to restart marathon app: %s", ex.message)
        return {"exception": {"message": ex.message}}
