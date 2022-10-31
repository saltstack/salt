"""
Interact with Consul

https://www.consul.io

"""

import base64
import http.client
import logging
import urllib

import salt.utils.http
import salt.utils.json
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


# Don't shadow built-ins.
__func_alias__ = {"list_": "list"}

__virtualname__ = "consul"


def _get_config():
    """
    Retrieve Consul configuration
    """
    return __salt__["config.get"]("consul.url") or __salt__["config.get"]("consul:url")


def _get_token():
    """
    Retrieve Consul configuration
    """
    return __salt__["config.get"]("consul.token") or __salt__["config.get"](
        "consul:token"
    )


def _query(
    function,
    consul_url,
    token=None,
    method="GET",
    api_version="v1",
    data=None,
    query_params=None,
):
    """
    Consul object method function to construct and execute on the API URL.

    :param api_url:     The Consul api url.
    :param api_version  The Consul api version
    :param function:    The Consul api function to perform.
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method. This param is ignored for GET requests.
    :return:            The json response from the API call or False.
    """

    if not query_params:
        query_params = {}

    ret = {"data": "", "res": True}

    if not token:
        token = _get_token()

    headers = {"X-Consul-Token": token, "Content-Type": "application/json"}
    base_url = urllib.parse.urljoin(consul_url, "{}/".format(api_version))
    url = urllib.parse.urljoin(base_url, function, False)

    if method == "GET":
        data = None
    else:
        if data is not None:
            if type(data) != str:
                data = salt.utils.json.dumps(data)
        else:
            data = salt.utils.json.dumps({})

    result = salt.utils.http.query(
        url,
        method=method,
        params=query_params,
        data=data,
        decode=True,
        status=True,
        header_dict=headers,
        opts=__opts__,
    )

    if result.get("status", None) == http.client.OK:
        ret["data"] = result.get("dict", result)
        ret["res"] = True
    elif result.get("status", None) == http.client.NO_CONTENT:
        ret["data"] = "No content available."
        ret["res"] = False
    elif result.get("status", None) == http.client.NOT_FOUND:
        ret["data"] = "Key not found."
        ret["res"] = False
    elif result.get("error", None):
        ret["data"] = "An error occurred."
        ret["error"] = result["error"]
        ret["res"] = False
    else:
        if result:
            ret["data"] = result
            ret["res"] = True
        else:
            ret["res"] = False
    return ret


def list_(consul_url=None, token=None, key=None, **kwargs):
    """
    List keys in Consul

    :param consul_url: The Consul server URL.
    :param key: The key to use as the starting point for the list.
    :return: The list of keys.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.list
        salt '*' consul.list key='web'

    """
    ret = {}

    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    query_params = {}

    if "recurse" in kwargs:
        query_params["recurse"] = "True"

    # No key so recurse and show all values
    if not key:
        query_params["recurse"] = "True"
        function = "kv/"
    else:
        function = "kv/{}".format(key)

    query_params["keys"] = "True"
    query_params["separator"] = "/"
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def get(consul_url=None, key=None, token=None, recurse=False, decode=False, raw=False):
    """
    Get key from Consul

    :param consul_url: The Consul server URL.
    :param key: The key to use as the starting point for the list.
    :param recurse: Return values recursively beginning at the value of key.
    :param decode: By default values are stored as Base64 encoded values,
                   decode will return the whole key with the value decoded.
    :param raw: Simply return the decoded value of the key.
    :return: The keys in Consul.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.get key='web/key1'
        salt '*' consul.get key='web' recurse=True
        salt '*' consul.get key='web' recurse=True decode=True

    By default values stored in Consul are base64 encoded, passing the
    decode option will show them as the decoded values.

    .. code-block:: bash

        salt '*' consul.get key='web' recurse=True decode=True raw=True

    By default Consult will return other information about the key, the raw
    option will return only the raw value.

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not key:
        raise SaltInvocationError('Required argument "key" is missing.')

    query_params = {}
    function = "kv/{}".format(key)
    if recurse:
        query_params["recurse"] = "True"
    if raw:
        query_params["raw"] = True
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )

    if ret["res"]:
        if decode:
            for item in ret["data"]:
                if item["Value"] is not None:
                    item["Value"] = base64.b64decode(item["Value"])
                else:
                    item["Value"] = ""
    return ret


def put(consul_url=None, token=None, key=None, value=None, **kwargs):
    """
    Put values into Consul

    :param consul_url: The Consul server URL.
    :param key: The key to use as the starting point for the list.
    :param value: The value to set the key to.
    :param flags: This can be used to specify an unsigned value
                  between 0 and 2^64-1. Clients can choose to use
                  this however makes sense for their application.
    :param cas: This flag is used to turn the PUT into a
                Check-And-Set operation.
    :param acquire: This flag is used to turn the PUT into a
                    lock acquisition operation.
    :param release: This flag is used to turn the PUT into a
                    lock release operation.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.put key='web/key1' value="Hello there"

        salt '*' consul.put key='web/key1' value="Hello there" acquire='d5d371f4-c380-5280-12fd-8810be175592'

        salt '*' consul.put key='web/key1' value="Hello there" release='d5d371f4-c380-5280-12fd-8810be175592'

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not key:
        raise SaltInvocationError('Required argument "key" is missing.')

    # Invalid to specified these together
    conflicting_args = ["cas", "release", "acquire"]
    for _l1 in conflicting_args:
        for _l2 in conflicting_args:
            if _l1 in kwargs and _l2 in kwargs and _l1 != _l2:
                raise SaltInvocationError(
                    "Using arguments `{}` and `{}` together is invalid.".format(
                        _l1, _l2
                    )
                )

    query_params = {}

    available_sessions = session_list(consul_url=consul_url, return_list=True)
    _current = get(consul_url=consul_url, token=token, key=key)

    if "flags" in kwargs:
        if kwargs["flags"] >= 0 and kwargs["flags"] <= 2**64:
            query_params["flags"] = kwargs["flags"]

    if "cas" in kwargs:
        if _current["res"]:
            if kwargs["cas"] == 0:
                ret["message"] = "Key {} exists, index must be non-zero.".format(key)
                ret["res"] = False
                return ret

            if kwargs["cas"] != _current["data"]["ModifyIndex"]:
                ret["message"] = "Key {} exists, but indexes do not match.".format(key)
                ret["res"] = False
                return ret
            query_params["cas"] = kwargs["cas"]
        else:
            ret[
                "message"
            ] = "Key {} does not exists, CAS argument can not be used.".format(key)
            ret["res"] = False
            return ret

    if "acquire" in kwargs:
        if kwargs["acquire"] not in available_sessions:
            ret["message"] = "{} is not a valid session.".format(kwargs["acquire"])
            ret["res"] = False
            return ret

        query_params["acquire"] = kwargs["acquire"]

    if "release" in kwargs:
        if _current["res"]:
            if "Session" in _current["data"]:
                if _current["data"]["Session"] == kwargs["release"]:
                    query_params["release"] = kwargs["release"]
                else:
                    ret["message"] = "{} locked by another session.".format(key)
                    ret["res"] = False
                    return ret

            else:
                ret["message"] = "{} is not a valid session.".format(kwargs["acquire"])
                ret["res"] = False
        else:
            log.error("Key {0} does not exist. Skipping release.")

    data = value
    function = "kv/{}".format(key)
    method = "PUT"
    res = _query(
        consul_url=consul_url,
        token=token,
        function=function,
        method=method,
        data=data,
        query_params=query_params,
    )

    if res["res"]:
        ret["res"] = True
        ret["data"] = "Added key {} with value {}.".format(key, value)
    else:
        ret["res"] = False
        ret["data"] = "Unable to add key {} with value {}.".format(key, value)
        if "error" in res:
            ret["error"] = res["error"]
    return ret


def delete(consul_url=None, token=None, key=None, **kwargs):
    """
    Delete values from Consul

    :param consul_url: The Consul server URL.
    :param key: The key to use as the starting point for the list.
    :param recurse: Delete values recursively beginning at the value of key.
    :param cas: This flag is used to turn the DELETE into
                a Check-And-Set operation.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.delete key='web'
        salt '*' consul.delete key='web' recurse='True'

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not key:
        raise SaltInvocationError('Required argument "key" is missing.')

    query_params = {}

    if "recurse" in kwargs:
        query_params["recurse"] = True

    if "cas" in kwargs:
        if kwargs["cas"] > 0:
            query_params["cas"] = kwargs["cas"]
        else:
            ret["message"] = (
                "Check and Set Operation ",
                "value must be greater than 0.",
            )
            ret["res"] = False
            return ret

    function = "kv/{}".format(key)
    res = _query(
        consul_url=consul_url,
        token=token,
        function=function,
        method="DELETE",
        query_params=query_params,
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "Deleted key {}.".format(key)
    else:
        ret["res"] = False
        ret["message"] = "Unable to delete key {}.".format(key)
        if "error" in res:
            ret["error"] = res["error"]
    return ret


def agent_checks(consul_url=None, token=None):
    """
    Returns the checks the local agent is managing

    :param consul_url: The Consul server URL.
    :return: Returns the checks the local agent is managing

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_checks

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    function = "agent/checks"
    ret = _query(consul_url=consul_url, function=function, token=token, method="GET")
    return ret


def agent_services(consul_url=None, token=None):
    """
    Returns the services the local agent is managing

    :param consul_url: The Consul server URL.
    :return: Returns the services the local agent is managing

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_services

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    function = "agent/services"
    ret = _query(consul_url=consul_url, function=function, token=token, method="GET")
    return ret


def agent_members(consul_url=None, token=None, **kwargs):
    """
    Returns the members as seen by the local serf agent

    :param consul_url: The Consul server URL.
    :return: Returns the members as seen by the local serf agent

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_members

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "wan" in kwargs:
        query_params["wan"] = kwargs["wan"]

    function = "agent/members"
    ret = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        method="GET",
        query_params=query_params,
    )
    return ret


def agent_self(consul_url=None, token=None):
    """
    Returns the local node configuration

    :param consul_url: The Consul server URL.
    :return: Returns the local node configuration

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_self

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    function = "agent/self"
    ret = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        method="GET",
        query_params=query_params,
    )
    return ret


def agent_maintenance(consul_url=None, token=None, **kwargs):
    """
    Manages node maintenance mode

    :param consul_url: The Consul server URL.
    :param enable: The enable flag is required.
                   Acceptable values are either true
                   (to enter maintenance mode) or
                   false (to resume normal operation).
    :param reason: If provided, its value should be a
                   text string explaining the reason for
                   placing the node into maintenance mode.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_maintenance enable='False' reason='Upgrade in progress'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "enable" in kwargs:
        query_params["enable"] = kwargs["enable"]
    else:
        ret["message"] = 'Required parameter "enable" is missing.'
        ret["res"] = False
        return ret

    if "reason" in kwargs:
        query_params["reason"] = kwargs["reason"]

    function = "agent/maintenance"
    res = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        method="PUT",
        query_params=query_params,
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Agent maintenance mode {}ed.".format(kwargs["enable"])
    else:
        ret["res"] = True
        ret["message"] = "Unable to change maintenance mode for agent."
    return ret


def agent_join(consul_url=None, token=None, address=None, **kwargs):
    """
    Triggers the local agent to join a node

    :param consul_url: The Consul server URL.
    :param address: The address for the agent to connect to.
    :param wan: Causes the agent to attempt to join using the WAN pool.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_join address='192.168.1.1'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not address:
        raise SaltInvocationError('Required argument "address" is missing.')

    if "wan" in kwargs:
        query_params["wan"] = kwargs["wan"]

    function = "agent/join/{}".format(address)
    res = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        method="GET",
        query_params=query_params,
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Agent joined the cluster"
    else:
        ret["res"] = False
        ret["message"] = "Unable to join the cluster."
    return ret


def agent_leave(consul_url=None, token=None, node=None):
    """
    Used to instruct the agent to force a node into the left state.

    :param consul_url: The Consul server URL.
    :param node: The node the agent will force into left state
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_leave node='web1.example.com'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not node:
        raise SaltInvocationError('Required argument "node" is missing.')

    function = "agent/force-leave/{}".format(node)
    res = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        method="GET",
        query_params=query_params,
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Node {} put in leave state.".format(node)
    else:
        ret["res"] = False
        ret["message"] = "Unable to change state for {}.".format(node)
    return ret


def agent_check_register(consul_url=None, token=None, **kwargs):
    """
    The register endpoint is used to add a new check to the local agent.

    :param consul_url: The Consul server URL.
    :param name: The description of what the check is for.
    :param id: The unique name to use for the check, if not
               provided 'name' is used.
    :param notes: Human readable description of the check.
    :param script: If script is provided, the check type is
                   a script, and Consul will evaluate that script
                   based on the interval parameter.
    :param http: Check will perform an HTTP GET request against
                 the value of HTTP (expected to be a URL) based
                 on the interval parameter.
    :param ttl: If a TTL type is used, then the TTL update endpoint
                must be used periodically to update the state of the check.
    :param interval: Interval at which the check should run.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_register name='Memory Utilization' script='/usr/local/bin/check_mem.py' interval='15s'

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "name" in kwargs:
        data["Name"] = kwargs["name"]
    else:
        raise SaltInvocationError('Required argument "name" is missing.')

    if True not in [True for item in ("script", "http", "ttl") if item in kwargs]:
        ret["message"] = 'Required parameter "script" or "http" is missing.'
        ret["res"] = False
        return ret

    if "id" in kwargs:
        data["ID"] = kwargs["id"]

    if "notes" in kwargs:
        data["Notes"] = kwargs["notes"]

    if "script" in kwargs:
        if "interval" not in kwargs:
            ret["message"] = 'Required parameter "interval" is missing.'
            ret["res"] = False
            return ret
        data["Script"] = kwargs["script"]
        data["Interval"] = kwargs["interval"]

    if "http" in kwargs:
        if "interval" not in kwargs:
            ret["message"] = 'Required parameter "interval" is missing.'
            ret["res"] = False
            return ret
        data["HTTP"] = kwargs["http"]
        data["Interval"] = kwargs["interval"]

    if "ttl" in kwargs:
        data["TTL"] = kwargs["ttl"]

    function = "agent/check/register"
    res = _query(
        consul_url=consul_url, function=function, token=token, method="PUT", data=data
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "Check {} added to agent.".format(kwargs["name"])
    else:
        ret["res"] = False
        ret["message"] = "Unable to add check to agent."
    return ret


def agent_check_deregister(consul_url=None, token=None, checkid=None):
    """
    The agent will take care of deregistering the check from the Catalog.

    :param consul_url: The Consul server URL.
    :param checkid: The ID of the check to deregister from Consul.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_deregister checkid='Memory Utilization'

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not checkid:
        raise SaltInvocationError('Required argument "checkid" is missing.')

    function = "agent/check/deregister/{}".format(checkid)
    res = _query(consul_url=consul_url, function=function, token=token, method="GET")
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Check {} removed from agent.".format(checkid)
    else:
        ret["res"] = False
        ret["message"] = "Unable to remove check from agent."
    return ret


def agent_check_pass(consul_url=None, token=None, checkid=None, **kwargs):
    """
    This endpoint is used with a check that is of the TTL type. When this
    is called, the status of the check is set to passing and the TTL
    clock is reset.

    :param consul_url: The Consul server URL.
    :param checkid: The ID of the check to mark as passing.
    :param note: A human-readable message with the status of the check.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_pass checkid='redis_check1' note='Forcing check into passing state.'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not checkid:
        raise SaltInvocationError('Required argument "checkid" is missing.')

    if "note" in kwargs:
        query_params["note"] = kwargs["note"]

    function = "agent/check/pass/{}".format(checkid)
    res = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        query_params=query_params,
        method="GET",
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Check {} marked as passing.".format(checkid)
    else:
        ret["res"] = False
        ret["message"] = "Unable to update check {}.".format(checkid)
    return ret


def agent_check_warn(consul_url=None, token=None, checkid=None, **kwargs):
    """
    This endpoint is used with a check that is of the TTL type. When this
    is called, the status of the check is set to warning and the TTL
    clock is reset.

    :param consul_url: The Consul server URL.
    :param checkid: The ID of the check to deregister from Consul.
    :param note: A human-readable message with the status of the check.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_warn checkid='redis_check1' note='Forcing check into warning state.'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not checkid:
        raise SaltInvocationError('Required argument "checkid" is missing.')

    if "note" in kwargs:
        query_params["note"] = kwargs["note"]

    function = "agent/check/warn/{}".format(checkid)
    res = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        query_params=query_params,
        method="GET",
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Check {} marked as warning.".format(checkid)
    else:
        ret["res"] = False
        ret["message"] = "Unable to update check {}.".format(checkid)
    return ret


def agent_check_fail(consul_url=None, token=None, checkid=None, **kwargs):
    """
    This endpoint is used with a check that is of the TTL type. When this
    is called, the status of the check is set to critical and the
    TTL clock is reset.

    :param consul_url: The Consul server URL.
    :param checkid: The ID of the check to deregister from Consul.
    :param note: A human-readable message with the status of the check.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_fail checkid='redis_check1' note='Forcing check into critical state.'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not checkid:
        raise SaltInvocationError('Required argument "checkid" is missing.')

    if "note" in kwargs:
        query_params["note"] = kwargs["note"]

    function = "agent/check/fail/{}".format(checkid)
    res = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        query_params=query_params,
        method="GET",
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Check {} marked as critical.".format(checkid)
    else:
        ret["res"] = False
        ret["message"] = "Unable to update check {}.".format(checkid)
    return ret


def agent_service_register(consul_url=None, token=None, **kwargs):
    """
    The used to add a new service, with an optional
    health check, to the local agent.

    :param consul_url: The Consul server URL.
    :param name: A name describing the service.
    :param address: The address used by the service, defaults
                    to the address of the agent.
    :param port: The port used by the service.
    :param id: Unique ID to identify the service, if not
               provided the value of the name parameter is used.
    :param tags: Identifying tags for service, string or list.
    :param script: If script is provided, the check type is
                   a script, and Consul will evaluate that script
                   based on the interval parameter.
    :param http: Check will perform an HTTP GET request against
                 the value of HTTP (expected to be a URL) based
                 on the interval parameter.
    :param check_ttl: If a TTL type is used, then the TTL update
                      endpoint must be used periodically to update
                      the state of the check.
    :param check_interval: Interval at which the check should run.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_service_register name='redis' tags='["master", "v1"]' address="127.0.0.1" port="8080" check_script="/usr/local/bin/check_redis.py" interval="10s"

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    lc_kwargs = dict()
    for k, v in kwargs.items():
        lc_kwargs[k.lower()] = v

    if "name" in lc_kwargs:
        data["Name"] = lc_kwargs["name"]
    else:
        raise SaltInvocationError('Required argument "name" is missing.')

    if "address" in lc_kwargs:
        data["Address"] = lc_kwargs["address"]

    if "port" in lc_kwargs:
        data["Port"] = lc_kwargs["port"]

    if "id" in lc_kwargs:
        data["ID"] = lc_kwargs["id"]

    if "tags" in lc_kwargs:
        _tags = lc_kwargs["tags"]
        if not isinstance(_tags, list):
            _tags = [_tags]
        data["Tags"] = _tags

    if "enabletagoverride" in lc_kwargs:
        data["EnableTagOverride"] = lc_kwargs["enabletagoverride"]

    if "check" in lc_kwargs:
        dd = dict()
        for k, v in lc_kwargs["check"].items():
            dd[k.lower()] = v
        interval_required = False
        check_dd = dict()

        if "script" in dd:
            interval_required = True
            check_dd["Script"] = dd["script"]
        if "http" in dd:
            interval_required = True
            check_dd["HTTP"] = dd["http"]
        if "ttl" in dd:
            check_dd["TTL"] = dd["ttl"]
        if "interval" in dd:
            check_dd["Interval"] = dd["interval"]

        if interval_required:
            if "Interval" not in check_dd:
                ret["message"] = 'Required parameter "interval" is missing.'
                ret["res"] = False
                return ret
        else:
            if "Interval" in check_dd:
                del check_dd["Interval"]  # not required, so ignore it

        if check_dd:
            data["Check"] = check_dd  # if empty, ignore it

    function = "agent/service/register"
    res = _query(
        consul_url=consul_url, function=function, token=token, method="PUT", data=data
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Service {} registered on agent.".format(kwargs["name"])
    else:
        ret["res"] = False
        ret["message"] = "Unable to register service {}.".format(kwargs["name"])
    return ret


def agent_service_deregister(consul_url=None, token=None, serviceid=None):
    """
    Used to remove a service.

    :param consul_url: The Consul server URL.
    :param serviceid: A serviceid describing the service.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_service_deregister serviceid='redis'

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not serviceid:
        raise SaltInvocationError('Required argument "serviceid" is missing.')

    function = "agent/service/deregister/{}".format(serviceid)
    res = _query(
        consul_url=consul_url, function=function, token=token, method="PUT", data=data
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Service {} removed from agent.".format(serviceid)
    else:
        ret["res"] = False
        ret["message"] = "Unable to remove service {}.".format(serviceid)
    return ret


def agent_service_maintenance(consul_url=None, token=None, serviceid=None, **kwargs):
    """
    Used to place a service into maintenance mode.

    :param consul_url: The Consul server URL.
    :param serviceid: A name of the service.
    :param enable: Whether the service should be enabled or disabled.
    :param reason: A human readable message of why the service was
                   enabled or disabled.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_service_deregister serviceid='redis' enable='True' reason='Down for upgrade'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not serviceid:
        raise SaltInvocationError('Required argument "serviceid" is missing.')

    if "enable" in kwargs:
        query_params["enable"] = kwargs["enable"]
    else:
        ret["message"] = 'Required parameter "enable" is missing.'
        ret["res"] = False
        return ret

    if "reason" in kwargs:
        query_params["reason"] = kwargs["reason"]

    function = "agent/service/maintenance/{}".format(serviceid)
    res = _query(
        consul_url=consul_url, token=token, function=function, query_params=query_params
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "Service {} set in maintenance mode.".format(serviceid)
    else:
        ret["res"] = False
        ret["message"] = "Unable to set service {} to maintenance mode.".format(
            serviceid
        )
    return ret


def session_create(consul_url=None, token=None, **kwargs):
    """
    Used to create a session.

    :param consul_url: The Consul server URL.
    :param lockdelay: Duration string using a "s" suffix for seconds.
                      The default is 15s.
    :param node: Must refer to a node that is already registered,
                 if specified. By default, the agent's own node
                 name is used.
    :param name: A human-readable name for the session
    :param checks: A list of associated health checks. It is highly
                   recommended that, if you override this list, you
                   include the default "serfHealth".
    :param behavior: Can be set to either release or delete. This controls
                     the behavior when a session is invalidated. By default,
                     this is release, causing any locks that are held to be
                     released. Changing this to delete causes any locks that
                     are held to be deleted. delete is useful for creating
                     ephemeral key/value entries.
    :param ttl: Session is invalidated if it is not renewed before
                the TTL expires
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_create node='node1' name='my-session' behavior='delete' ttl='3600s'

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret
    data = {}

    if "lockdelay" in kwargs:
        data["LockDelay"] = kwargs["lockdelay"]

    if "node" in kwargs:
        data["Node"] = kwargs["node"]

    if "name" in kwargs:
        data["Name"] = kwargs["name"]
    else:
        raise SaltInvocationError('Required argument "name" is missing.')

    if "checks" in kwargs:
        data["Touch"] = kwargs["touch"]

    if "behavior" in kwargs:
        if not kwargs["behavior"] in ("delete", "release"):
            ret["message"] = ("Behavior must be ", "either delete or release.")
            ret["res"] = False
            return ret
        data["Behavior"] = kwargs["behavior"]

    if "ttl" in kwargs:
        _ttl = kwargs["ttl"]
        if str(_ttl).endswith("s"):
            _ttl = _ttl[:-1]

        if int(_ttl) < 0 or int(_ttl) > 3600:
            ret["message"] = ("TTL must be ", "between 0 and 3600.")
            ret["res"] = False
            return ret
        data["TTL"] = "{}s".format(_ttl)

    function = "session/create"
    res = _query(
        consul_url=consul_url, function=function, token=token, method="PUT", data=data
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "Created session {}.".format(kwargs["name"])
    else:
        ret["res"] = False
        ret["message"] = "Unable to create session {}.".format(kwargs["name"])
    return ret


def session_list(consul_url=None, token=None, return_list=False, **kwargs):
    """
    Used to list sessions.

    :param consul_url: The Consul server URL.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param return_list: By default, all information about the sessions is
                        returned, using the return_list parameter will return
                        a list of session IDs.
    :return: A list of all available sessions.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_list

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    query_params = {}

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "session/list"
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )

    if return_list:
        _list = []
        for item in ret["data"]:
            _list.append(item["ID"])
        return _list
    return ret


def session_destroy(consul_url=None, token=None, session=None, **kwargs):
    """
    Destroy session

    :param consul_url: The Consul server URL.
    :param session: The ID of the session to destroy.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_destroy session='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not session:
        raise SaltInvocationError('Required argument "session" is missing.')

    query_params = {}

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "session/destroy/{}".format(session)
    res = _query(
        consul_url=consul_url,
        function=function,
        token=token,
        method="PUT",
        query_params=query_params,
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Destroyed Session {}.".format(session)
    else:
        ret["res"] = False
        ret["message"] = "Unable to destroy session {}.".format(session)
    return ret


def session_info(consul_url=None, token=None, session=None, **kwargs):
    """
    Information about a session

    :param consul_url: The Consul server URL.
    :param session: The ID of the session to return information about.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_info session='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not session:
        raise SaltInvocationError('Required argument "session" is missing.')

    query_params = {}

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "session/info/{}".format(session)
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def catalog_register(consul_url=None, token=None, **kwargs):
    """
    Registers a new node, service, or check

    :param consul_url: The Consul server URL.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param node: The node to register.
    :param address: The address of the node.
    :param service: The service that will be registered.
    :param service_address: The address that the service listens on.
    :param service_port: The port for the service.
    :param service_id: A unique identifier for the service, if this is not
                       provided "name" will be used.
    :param service_tags: Any tags associated with the service.
    :param check: The name of the health check to register
    :param check_status: The initial status of the check,
                         must be one of unknown, passing, warning, or critical.
    :param check_service: The service that the check is performed against.
    :param check_id: Unique identifier for the service.
    :param check_notes: An opaque field that is meant to hold human-readable text.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_register node='node1' address='192.168.1.1' service='redis' service_address='127.0.0.1' service_port='8080' service_id='redis_server1'

    """
    ret = {}
    data = {}
    data["NodeMeta"] = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "datacenter" in kwargs:
        data["Datacenter"] = kwargs["datacenter"]

    if "node" in kwargs:
        data["Node"] = kwargs["node"]
    else:
        ret["message"] = "Required argument node argument is missing."
        ret["res"] = False
        return ret

    if "address" in kwargs:
        if isinstance(kwargs["address"], list):
            _address = kwargs["address"][0]
        else:
            _address = kwargs["address"]
        data["Address"] = _address
    else:
        ret["message"] = "Required argument address argument is missing."
        ret["res"] = False
        return ret

    if "ip_interfaces" in kwargs:
        data["TaggedAddresses"] = {}
        for k in kwargs["ip_interfaces"]:
            if kwargs["ip_interfaces"].get(k):
                data["TaggedAddresses"][k] = kwargs["ip_interfaces"][k][0]

    if "service" in kwargs:
        data["Service"] = {}
        data["Service"]["Service"] = kwargs["service"]

        if "service_address" in kwargs:
            data["Service"]["Address"] = kwargs["service_address"]

        if "service_port" in kwargs:
            data["Service"]["Port"] = kwargs["service_port"]

        if "service_id" in kwargs:
            data["Service"]["ID"] = kwargs["service_id"]

        if "service_tags" in kwargs:
            _tags = kwargs["service_tags"]
            if not isinstance(_tags, list):
                _tags = [_tags]
            data["Service"]["Tags"] = _tags

    if "cpu" in kwargs:
        data["NodeMeta"]["Cpu"] = kwargs["cpu"]

    if "num_cpus" in kwargs:
        data["NodeMeta"]["Cpu_num"] = kwargs["num_cpus"]

    if "mem" in kwargs:
        data["NodeMeta"]["Memory"] = kwargs["mem"]

    if "oscode" in kwargs:
        data["NodeMeta"]["Os"] = kwargs["oscode"]

    if "osarch" in kwargs:
        data["NodeMeta"]["Osarch"] = kwargs["osarch"]

    if "kernel" in kwargs:
        data["NodeMeta"]["Kernel"] = kwargs["kernel"]

    if "kernelrelease" in kwargs:
        data["NodeMeta"]["Kernelrelease"] = kwargs["kernelrelease"]

    if "localhost" in kwargs:
        data["NodeMeta"]["localhost"] = kwargs["localhost"]

    if "nodename" in kwargs:
        data["NodeMeta"]["nodename"] = kwargs["nodename"]

    if "os_family" in kwargs:
        data["NodeMeta"]["os_family"] = kwargs["os_family"]

    if "lsb_distrib_description" in kwargs:
        data["NodeMeta"]["lsb_distrib_description"] = kwargs["lsb_distrib_description"]

    if "master" in kwargs:
        data["NodeMeta"]["master"] = kwargs["master"]

    if "check" in kwargs:
        data["Check"] = {}
        data["Check"]["Name"] = kwargs["check"]

        if "check_status" in kwargs:
            if kwargs["check_status"] not in (
                "unknown",
                "passing",
                "warning",
                "critical",
            ):
                ret[
                    "message"
                ] = "Check status must be unknown, passing, warning, or critical."
                ret["res"] = False
                return ret
            data["Check"]["Status"] = kwargs["check_status"]

        if "check_service" in kwargs:
            data["Check"]["ServiceID"] = kwargs["check_service"]

        if "check_id" in kwargs:
            data["Check"]["CheckID"] = kwargs["check_id"]

        if "check_notes" in kwargs:
            data["Check"]["Notes"] = kwargs["check_notes"]

    function = "catalog/register"
    res = _query(
        consul_url=consul_url, function=function, token=token, method="PUT", data=data
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "Catalog registration for {} successful.".format(
            kwargs["node"]
        )
    else:
        ret["res"] = False
        ret["message"] = "Catalog registration for {} failed.".format(kwargs["node"])
    ret["data"] = data
    return ret


def catalog_deregister(consul_url=None, token=None, **kwargs):
    """
    Deregisters a node, service, or check

    :param consul_url: The Consul server URL.
    :param node: The node to deregister.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param checkid: The ID of the health check to deregister.
    :param serviceid: The ID of the service to deregister.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_register node='node1' serviceid='redis_server1' checkid='redis_check1'

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "datacenter" in kwargs:
        data["Datacenter"] = kwargs["datacenter"]

    if "node" in kwargs:
        data["Node"] = kwargs["node"]
    else:
        ret["message"] = "Node argument required."
        ret["res"] = False
        return ret

    if "checkid" in kwargs:
        data["CheckID"] = kwargs["checkid"]

    if "serviceid" in kwargs:
        data["ServiceID"] = kwargs["serviceid"]

    function = "catalog/deregister"
    res = _query(
        consul_url=consul_url, function=function, token=token, method="PUT", data=data
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "Catalog item {} removed.".format(kwargs["node"])
    else:
        ret["res"] = False
        ret["message"] = "Removing Catalog item {} failed.".format(kwargs["node"])
    return ret


def catalog_datacenters(consul_url=None, token=None):
    """
    Return list of available datacenters from catalog.

    :param consul_url: The Consul server URL.
    :return: The list of available datacenters.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_datacenters

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    function = "catalog/datacenters"
    ret = _query(consul_url=consul_url, function=function, token=token)
    return ret


def catalog_nodes(consul_url=None, token=None, **kwargs):
    """
    Return list of available nodes from catalog.

    :param consul_url: The Consul server URL.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: The list of available nodes.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_nodes

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "catalog/nodes"
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def catalog_services(consul_url=None, token=None, **kwargs):
    """
    Return list of available services rom catalog.

    :param consul_url: The Consul server URL.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: The list of available services.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_services

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "catalog/services"
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def catalog_service(consul_url=None, token=None, service=None, **kwargs):
    """
    Information about the registered service.

    :param consul_url: The Consul server URL.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param tag: Filter returned services with tag parameter.
    :return: Information about the requested service.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_service service='redis'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not service:
        raise SaltInvocationError('Required argument "service" is missing.')

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    if "tag" in kwargs:
        query_params["tag"] = kwargs["tag"]

    function = "catalog/service/{}".format(service)
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def catalog_node(consul_url=None, token=None, node=None, **kwargs):
    """
    Information about the registered node.

    :param consul_url: The Consul server URL.
    :param node: The node to request information about.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_service service='redis'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not node:
        raise SaltInvocationError('Required argument "node" is missing.')

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "catalog/node/{}".format(node)
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def health_node(consul_url=None, token=None, node=None, **kwargs):
    """
    Health information about the registered node.

    :param consul_url: The Consul server URL.
    :param node: The node to request health information about.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Health information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_node node='node1'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not node:
        raise SaltInvocationError('Required argument "node" is missing.')

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "health/node/{}".format(node)
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def health_checks(consul_url=None, token=None, service=None, **kwargs):
    """
    Health information about the registered service.

    :param consul_url: The Consul server URL.
    :param service: The service to request health information about.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Health information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_checks service='redis1'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not service:
        raise SaltInvocationError('Required argument "service" is missing.')

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    function = "health/checks/{}".format(service)
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def health_service(consul_url=None, token=None, service=None, **kwargs):
    """
    Health information about the registered service.

    :param consul_url: The Consul server URL.
    :param service: The service to request health information about.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param tag: Filter returned services with tag parameter.
    :param passing: Filter results to only nodes with all
                    checks in the passing state.
    :return: Health information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_service service='redis1'

        salt '*' consul.health_service service='redis1' passing='True'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not service:
        raise SaltInvocationError('Required argument "service" is missing.')

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    if "tag" in kwargs:
        query_params["tag"] = kwargs["tag"]

    if "passing" in kwargs:
        query_params["passing"] = kwargs["passing"]

    function = "health/service/{}".format(service)
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def health_state(consul_url=None, token=None, state=None, **kwargs):
    """
    Returns the checks in the state provided on the path.

    :param consul_url: The Consul server URL.
    :param state: The state to show checks for. The supported states
                  are any, unknown, passing, warning, or critical.
                  The any state is a wildcard that can be used to
                  return all checks.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: The checks in the provided state.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_state state='redis1'

        salt '*' consul.health_state service='redis1' passing='True'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not state:
        raise SaltInvocationError('Required argument "state" is missing.')

    if "dc" in kwargs:
        query_params["dc"] = kwargs["dc"]

    if state not in ("any", "unknown", "passing", "warning", "critical"):
        ret["message"] = "State must be any, unknown, passing, warning, or critical."
        ret["res"] = False
        return ret

    function = "health/state/{}".format(state)
    ret = _query(
        consul_url=consul_url, function=function, token=token, query_params=query_params
    )
    return ret


def status_leader(consul_url=None, token=None):
    """
    Returns the current Raft leader

    :param consul_url: The Consul server URL.
    :return: The address of the Raft leader.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.status_leader

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    function = "status/leader"
    ret = _query(consul_url=consul_url, function=function, token=token)
    return ret


def status_peers(consul_url, token=None):
    """
    Returns the current Raft peer set

    :param consul_url: The Consul server URL.
    :return: Retrieves the Raft peers for the
             datacenter in which the agent is running.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.status_peers

    """
    ret = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    function = "status/peers"
    ret = _query(consul_url=consul_url, function=function, token=token)
    return ret


def acl_create(consul_url=None, token=None, **kwargs):
    """
    Create a new ACL token.

    :param consul_url: The Consul server URL.
    :param name: Meaningful indicator of the ACL's purpose.
    :param type: Type is either client or management. A management
                 token is comparable to a root user and has the
                 ability to perform any action including creating,
                 modifying, and deleting ACLs.
    :param rules: The Consul server URL.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_create

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "id" in kwargs:
        data["id"] = kwargs["id"]

    if "name" in kwargs:
        data["Name"] = kwargs["name"]
    else:
        raise SaltInvocationError('Required argument "name" is missing.')

    if "type" in kwargs:
        data["Type"] = kwargs["type"]

    if "rules" in kwargs:
        data["Rules"] = kwargs["rules"]

    function = "acl/create"
    res = _query(
        consul_url=consul_url, token=token, data=data, method="PUT", function=function
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "ACL {} created.".format(kwargs["name"])
    else:
        ret["res"] = False
        ret["message"] = "Removing Catalog item {} failed.".format(kwargs["name"])
    return ret


def acl_update(consul_url=None, token=None, **kwargs):
    """
    Update an ACL token.

    :param consul_url: The Consul server URL.
    :param name: Meaningful indicator of the ACL's purpose.
    :param id: Unique identifier for the ACL to update.
    :param type: Type is either client or management. A management
                 token is comparable to a root user and has the
                 ability to perform any action including creating,
                 modifying, and deleting ACLs.
    :param rules: The Consul server URL.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_update

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "id" in kwargs:
        data["ID"] = kwargs["id"]
    else:
        ret["message"] = 'Required parameter "id" is missing.'
        ret["res"] = False
        return ret

    if "name" in kwargs:
        data["Name"] = kwargs["name"]
    else:
        raise SaltInvocationError('Required argument "name" is missing.')

    if "type" in kwargs:
        data["Type"] = kwargs["type"]

    if "rules" in kwargs:
        data["Rules"] = kwargs["rules"]

    function = "acl/update"
    res = _query(
        consul_url=consul_url, token=token, data=data, method="PUT", function=function
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "ACL {} created.".format(kwargs["name"])
    else:
        ret["res"] = False
        ret["message"] = "Updating ACL {} failed.".format(kwargs["name"])

    return ret


def acl_delete(consul_url=None, token=None, **kwargs):
    """
    Delete an ACL token.

    :param consul_url: The Consul server URL.
    :param id: Unique identifier for the ACL to update.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_delete id='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "id" not in kwargs:
        ret["message"] = 'Required parameter "id" is missing.'
        ret["res"] = False
        return ret

    function = "acl/destroy/{}".format(kwargs["id"])
    res = _query(
        consul_url=consul_url, token=token, data=data, method="PUT", function=function
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "ACL {} deleted.".format(kwargs["id"])
    else:
        ret["res"] = False
        ret["message"] = "Removing ACL {} failed.".format(kwargs["id"])

    return ret


def acl_info(consul_url=None, **kwargs):
    """
    Information about an ACL token.

    :param consul_url: The Consul server URL.
    :param id: Unique identifier for the ACL to update.
    :return: Information about the ACL requested.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_info id='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "id" not in kwargs:
        ret["message"] = 'Required parameter "id" is missing.'
        ret["res"] = False
        return ret

    function = "acl/info/{}".format(kwargs["id"])
    ret = _query(consul_url=consul_url, data=data, method="GET", function=function)
    return ret


def acl_clone(consul_url=None, token=None, **kwargs):
    """
    Information about an ACL token.

    :param consul_url: The Consul server URL.
    :param id: Unique identifier for the ACL to update.
    :return: Boolean, message of success or
             failure, and new ID of cloned ACL.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_info id='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "id" not in kwargs:
        ret["message"] = 'Required parameter "id" is missing.'
        ret["res"] = False
        return ret

    function = "acl/clone/{}".format(kwargs["id"])
    res = _query(
        consul_url=consul_url, token=token, data=data, method="PUT", function=function
    )
    if res["res"]:
        ret["res"] = True
        ret["message"] = "ACL {} cloned.".format(kwargs["name"])
        ret["ID"] = res["data"]
    else:
        ret["res"] = False
        ret["message"] = "Cloning ACL item {} failed.".format(kwargs["name"])
    return ret


def acl_list(consul_url=None, token=None, **kwargs):
    """
    List the ACL tokens.

    :param consul_url: The Consul server URL.
    :return: List of ACLs

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_list

    """
    ret = {}
    data = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    function = "acl/list"
    ret = _query(
        consul_url=consul_url, token=token, data=data, method="GET", function=function
    )
    return ret


def event_fire(consul_url=None, token=None, name=None, **kwargs):
    """
    List the ACL tokens.

    :param consul_url: The Consul server URL.
    :param name: The name of the event to fire.
    :param dc: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param node: Filter by node name.
    :param service: Filter by service name.
    :param tag: Filter by tag name.
    :return: List of ACLs

    CLI Example:

    .. code-block:: bash

        salt '*' consul.event_fire name='deploy'

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if not name:
        raise SaltInvocationError('Required argument "name" is missing.')

    if "dc" in kwargs:
        query_params = kwargs["dc"]

    if "node" in kwargs:
        query_params = kwargs["node"]

    if "service" in kwargs:
        query_params = kwargs["service"]

    if "tag" in kwargs:
        query_params = kwargs["tag"]

    function = "event/fire/{}".format(name)
    res = _query(
        consul_url=consul_url,
        token=token,
        query_params=query_params,
        method="PUT",
        function=function,
    )

    if res["res"]:
        ret["res"] = True
        ret["message"] = "Event {} fired.".format(name)
        ret["data"] = res["data"]
    else:
        ret["res"] = False
        ret["message"] = "Cloning ACL item {} failed.".format(kwargs["name"])
    return ret


def event_list(consul_url=None, token=None, **kwargs):
    """
    List the recent events.

    :param consul_url: The Consul server URL.
    :param name: The name of the event to fire.
    :return: List of ACLs

    CLI Example:

    .. code-block:: bash

        salt '*' consul.event_list

    """
    ret = {}
    query_params = {}
    if not consul_url:
        consul_url = _get_config()
        if not consul_url:
            log.error("No Consul URL found.")
            ret["message"] = "No Consul URL found."
            ret["res"] = False
            return ret

    if "name" in kwargs:
        query_params = kwargs["name"]
    else:
        raise SaltInvocationError('Required argument "name" is missing.')

    function = "event/list/"
    ret = _query(
        consul_url=consul_url, token=token, query_params=query_params, function=function
    )
    return ret
