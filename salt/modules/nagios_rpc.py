"""
Check Host & Service status from Nagios via JSON RPC.

.. versionadded:: 2015.8.0

"""


import http.client
import logging

import salt.utils.http
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if requests is successfully imported
    """
    return "nagios_rpc"


def _config():
    """
    Get configuration items for URL, Username and Password
    """
    status_url = __salt__["config.get"]("nagios.status_url") or __salt__["config.get"](
        "nagios:status_url"
    )
    if not status_url:
        raise CommandExecutionError("Missing Nagios URL in the configuration.")

    username = __salt__["config.get"]("nagios.username") or __salt__["config.get"](
        "nagios:username"
    )
    password = __salt__["config.get"]("nagios.password") or __salt__["config.get"](
        "nagios:password"
    )
    return {"url": status_url, "username": username, "password": password}


def _status_query(query, hostname, enumerate=None, service=None):
    """
    Send query along to Nagios.
    """
    config = _config()

    data = None
    params = {
        "hostname": hostname,
        "query": query,
    }

    ret = {"result": False}

    if enumerate:
        params["formatoptions"] = "enumerate"
    if service:
        params["servicedescription"] = service

    if config["username"] and config["password"] is not None:
        auth = (
            config["username"],
            config["password"],
        )
    else:
        auth = None

    try:
        result = salt.utils.http.query(
            config["url"],
            method="GET",
            params=params,
            decode=True,
            data=data,
            text=True,
            status=True,
            header_dict={},
            auth=auth,
            backend="requests",
            opts=__opts__,
        )
    except ValueError:
        ret["error"] = "Please ensure Nagios is running."
        ret["result"] = False
        return ret

    if result.get("status", None) == http.client.OK:
        try:
            ret["json_data"] = result["dict"]
            ret["result"] = True
        except ValueError:
            ret["error"] = "Please ensure Nagios is running."
    elif result.get("status", None) == http.client.UNAUTHORIZED:
        ret["error"] = "Authentication failed. Please check the configuration."
    elif result.get("status", None) == http.client.NOT_FOUND:
        ret["error"] = "URL {} was not found.".format(config["url"])
    else:
        ret["error"] = "Results: {}".format(result.text)

    return ret


def host_status(hostname=None, **kwargs):
    """
    Check status of a particular host By default
    statuses are returned in a numeric format.

    Parameters:

    hostname
        The hostname to check the status of the service in Nagios.

    numeric
        Turn to false in order to return status in text format
        ('OK' instead of 0, 'Warning' instead of 1 etc)

    :return: status:     'OK', 'Warning', 'Critical' or 'Unknown'

    CLI Example:

    .. code-block:: bash

        salt '*' nagios_rpc.host_status hostname=webserver.domain.com
        salt '*' nagios_rpc.host_status hostname=webserver.domain.com numeric=False
    """

    if not hostname:
        raise CommandExecutionError("Missing hostname parameter")

    target = "host"
    numeric = kwargs.get("numeric")
    data = _status_query(target, hostname, enumerate=numeric)

    ret = {"result": data["result"]}
    if ret["result"]:
        ret["status"] = (
            data.get("json_data", {})
            .get("data", {})
            .get(target, {})
            .get("status", not numeric and "Unknown" or 2)
        )
    else:
        ret["error"] = data["error"]
    return ret


def service_status(hostname=None, service=None, **kwargs):
    """
    Check status of a particular service on a host on it in Nagios.
    By default statuses are returned in a numeric format.

    Parameters:

    hostname
        The hostname to check the status of the service in Nagios.

    service
        The service to check the status of in Nagios.

    numeric
        Turn to false in order to return status in text format
        ('OK' instead of 0, 'Warning' instead of 1 etc)

    :return: status:     'OK', 'Warning', 'Critical' or 'Unknown'

    CLI Example:

    .. code-block:: bash

        salt '*' nagios_rpc.service_status hostname=webserver.domain.com service='HTTP'
        salt '*' nagios_rpc.service_status hostname=webserver.domain.com service='HTTP' numeric=False
    """

    if not hostname:
        raise CommandExecutionError("Missing hostname parameter")

    if not service:
        raise CommandExecutionError("Missing service parameter")

    target = "service"
    numeric = kwargs.get("numeric")
    data = _status_query(target, hostname, service=service, enumerate=numeric)

    ret = {"result": data["result"]}
    if ret["result"]:
        ret["status"] = (
            data.get("json_data", {})
            .get("data", {})
            .get(target, {})
            .get("status", not numeric and "Unknown" or 2)
        )
    else:
        ret["error"] = data["error"]
    return ret
