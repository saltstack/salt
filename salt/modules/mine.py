"""
The function cache system allows for data to be stored on the master so it can be easily read by other minions
"""

import logging
import time
import traceback

import salt.crypt
import salt.payload
import salt.transport.client
import salt.utils.args
import salt.utils.dictupdate
import salt.utils.event
import salt.utils.functools
import salt.utils.mine
import salt.utils.minions
import salt.utils.network
from salt.exceptions import SaltClientError

MINE_INTERNAL_KEYWORDS = frozenset(
    [
        "__pub_user",
        "__pub_arg",
        "__pub_fun",
        "__pub_jid",
        "__pub_tgt",
        "__pub_tgt_type",
        "__pub_ret",
    ]
)

__proxyenabled__ = ["*"]

log = logging.getLogger(__name__)


def _auth():
    """
    Return the auth object
    """
    if "auth" not in __context__:
        try:
            __context__["auth"] = salt.crypt.SAuth(__opts__)
        except SaltClientError:
            log.error(
                "Could not authenticate with master. Mine data will not be transmitted."
            )
    return __context__["auth"]


def _mine_function_available(func):
    if func not in __salt__:
        log.error("Function %s in mine_functions not available", func)
        return False
    return True


def _mine_send(load, opts):
    eventer = salt.utils.event.MinionEvent(opts, listen=False)
    event_ret = eventer.fire_event(load, "_minion_mine")
    # We need to pause here to allow for the decoupled nature of
    # events time to allow the mine to propagate
    time.sleep(0.5)
    return event_ret


def _mine_get(load, opts):
    if opts.get("transport", "") in ("zeromq", "tcp"):
        try:
            load["tok"] = _auth().gen_token(b"salt")
        except AttributeError:
            log.error(
                "Mine could not authenticate with master. Mine could not be retrieved."
            )
            return False
    with salt.transport.client.ReqChannel.factory(opts) as channel:
        return channel.send(load)


def _mine_store(mine_data, clear=False):
    """
    Helper function to store the provided mine data.
    This will store either locally in the cache (for masterless setups), or in
    the master's cache.

    :param dict mine_data: Dictionary with function_name: function_data to store.
    :param bool clear: Whether or not to clear (`True`) the mine data for the
        function names present in ``mine_data``, or update it (`False`).
    """
    # Store in the salt-minion's local cache
    if __opts__["file_client"] == "local":
        if not clear:
            old = __salt__["data.get"]("mine_cache")
            if isinstance(old, dict):
                old.update(mine_data)
                mine_data = old
        return __salt__["data.update"]("mine_cache", mine_data)
    # Store on the salt master
    load = {
        "cmd": "_mine",
        "data": mine_data,
        "id": __opts__["id"],
        "clear": clear,
    }
    return _mine_send(load, __opts__)


def update(clear=False, mine_functions=None):
    """
    Call the configured functions and send the data back up to the master.
    The functions to be called are merged from the master config, pillar and
    minion config under the option `mine_functions`:

    .. code-block:: yaml

        mine_functions:
          network.ip_addrs:
            - eth0
          disk.usage: []

    This function accepts the following arguments:

    :param bool clear: Default: ``False``
        Specifies whether updating will clear the existing values (``True``), or
        whether it will update them (``False``).

    :param dict mine_functions:
        Update (or clear, see ``clear``) the mine data on these functions only.
        This will need to have the structure as defined on
        https://docs.saltproject.io/en/latest/topics/mine/index.html#mine-functions

        This feature can be used when updating the mine for functions
        that require a refresh at different intervals than the rest of
        the functions specified under `mine_functions` in the
        minion/master config or pillar.
        A potential use would be together with the `scheduler`, for example:

        .. code-block:: yaml

            schedule:
              lldp_mine_update:
                function: mine.update
                kwargs:
                    mine_functions:
                      net.lldp: []
                hours: 12

        In the example above, the mine for `net.lldp` would be refreshed
        every 12 hours, while  `network.ip_addrs` would continue to be updated
        as specified in `mine_interval`.

    The function cache will be populated with information from executing these
    functions

    CLI Example:

    .. code-block:: bash

        salt '*' mine.update
    """
    if not mine_functions:
        mine_functions = __salt__["config.merge"]("mine_functions", {})
        # If we don't have any mine functions configured, then we should just bail out
        if not mine_functions:
            return
    elif isinstance(mine_functions, list):
        mine_functions = {fun: {} for fun in mine_functions}
    elif isinstance(mine_functions, dict):
        pass
    else:
        return

    mine_data = {}
    for function_alias, function_data in mine_functions.items():
        (
            function_name,
            function_args,
            function_kwargs,
            minion_acl,
        ) = salt.utils.mine.parse_function_definition(function_data)
        if not _mine_function_available(function_name or function_alias):
            continue
        try:
            res = salt.utils.functools.call_function(
                __salt__[function_name or function_alias],
                *function_args,
                **function_kwargs
            )
        except Exception:  # pylint: disable=broad-except
            trace = traceback.format_exc()
            log.error(
                "Function %s in mine.update failed to execute",
                function_name or function_alias,
            )
            log.debug("Error: %s", trace)
            continue
        if minion_acl.get("allow_tgt"):
            mine_data[function_alias] = salt.utils.mine.wrap_acl_structure(
                res, **minion_acl
            )
        else:
            mine_data[function_alias] = res
    return _mine_store(mine_data, clear)


def send(name, *args, **kwargs):
    """
    Send a specific function and its result to the salt mine.
    This gets stored in either the local cache, or the salt master's cache.

    :param str name: Name of the function to add to the mine.

    The following pameters are extracted from kwargs if present:

    :param str mine_function: The name of the execution_module.function to run
        and whose value will be stored in the salt mine. Defaults to ``name``.
    :param str allow_tgt: Targeting specification for ACL. Specifies which minions
        are allowed to access this function. Please note both your master and
        minion need to be on, at least, version 3000 for this to work properly.

    :param str allow_tgt_type: Type of the targeting specification. This value will
        be ignored if ``allow_tgt`` is not specified. Please note both your
        master and minion need to be on, at least, version 3000 for this to work
        properly.

    Remaining args and kwargs will be passed on to the function to run.

    :rtype: bool
    :return: Whether executing the function and storing the information was successful.

    .. versionchanged:: 3000

        Added ``allow_tgt``- and ``allow_tgt_type``-parameters to specify which
        minions are allowed to access this function.
        See :ref:`targeting` for more information about targeting.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.send network.ip_addrs eth0
        salt '*' mine.send eth0_ip_addrs mine_function=network.ip_addrs eth0
        salt '*' mine.send eth0_ip_addrs mine_function=network.ip_addrs eth0 allow_tgt='G@grain:value' allow_tgt_type=compound
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    mine_function = kwargs.pop("mine_function", None)
    allow_tgt = kwargs.pop("allow_tgt", None)
    allow_tgt_type = kwargs.pop("allow_tgt_type", None)
    mine_data = {}
    try:
        res = salt.utils.functools.call_function(
            __salt__[mine_function or name], *args, **kwargs
        )
    except Exception as exc:  # pylint: disable=broad-except
        trace = traceback.format_exc()
        log.error("Function %s in mine.send failed to execute", mine_function or name)
        log.debug("Error: %s", trace)
        return False

    if allow_tgt:
        mine_data[name] = salt.utils.mine.wrap_acl_structure(
            res, allow_tgt=allow_tgt, allow_tgt_type=allow_tgt_type
        )
    else:
        mine_data[name] = res
    return _mine_store(mine_data)


def get(tgt, fun, tgt_type="glob", exclude_minion=False):
    """
    Get data from the mine.

    :param str tgt: Target whose mine data to get.
    :param fun: Function to get the mine data of. You can specify multiple functions
        to retrieve using either a list or a comma-separated string of functions.
    :type fun: str or list
    :param str tgt_type: Default ``glob``. Target type to use with ``tgt``.
        See :ref:`targeting` for more information.
        Note that all pillar matches, whether using the compound matching system or
        the pillar matching system, will be exact matches, with globbing disabled.
    :param bool exclude_minion: Excludes the current minion from the result set.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.get '*' network.interfaces
        salt '*' mine.get 'os:Fedora' network.interfaces grain
        salt '*' mine.get 'G@os:Fedora and S@192.168.5.0/24' network.ipaddrs compound

    .. seealso:: Retrieving Mine data from Pillar and Orchestrate

        This execution module is intended to be executed on minions.
        Master-side operations such as Pillar or Orchestrate that require Mine
        data should use the :py:mod:`Mine Runner module <salt.runners.mine>`
        instead; it can be invoked from a Pillar SLS file using the
        :py:func:`saltutil.runner <salt.modules.saltutil.runner>` module. For
        example:

        .. code-block:: jinja

            {% set minion_ips = salt.saltutil.runner('mine.get',
                tgt='*',
                fun='network.ip_addrs',
                tgt_type='glob') %}
    """
    # Load from local minion's cache
    if __opts__["file_client"] == "local":
        ret = {}
        is_target = {
            "glob": __salt__["match.glob"],
            "pcre": __salt__["match.pcre"],
            "list": __salt__["match.list"],
            "grain": __salt__["match.grain"],
            "grain_pcre": __salt__["match.grain_pcre"],
            "ipcidr": __salt__["match.ipcidr"],
            "compound": __salt__["match.compound"],
            "pillar": __salt__["match.pillar"],
            "pillar_pcre": __salt__["match.pillar_pcre"],
        }[tgt_type](tgt)
        if not is_target:
            return ret

        data = __salt__["data.get"]("mine_cache")
        if not isinstance(data, dict):
            return ret

        if isinstance(fun, str):
            functions = list(set(fun.split(",")))
            _ret_dict = len(functions) > 1
        elif isinstance(fun, list):
            functions = fun
            _ret_dict = True
        else:
            return ret

        for function in functions:
            if function not in data:
                continue
            # If this is a mine item with minion_side_ACL, get its data
            if salt.utils.mine.MINE_ITEM_ACL_ID in data[function]:
                res = data[function][salt.utils.mine.MINE_ITEM_ACL_DATA]
            else:
                # Backwards compatibility with non-ACL mine data.
                res = data[function]
            if _ret_dict:
                ret.setdefault(function, {})[__opts__["id"]] = res
            else:
                ret[__opts__["id"]] = res
        return ret

    # Load from master
    load = {
        "cmd": "_mine_get",
        "id": __opts__["id"],
        "tgt": tgt,
        "fun": fun,
        "tgt_type": tgt_type,
    }
    ret = _mine_get(load, __opts__)
    if exclude_minion and __opts__["id"] in ret:
        del ret[__opts__["id"]]
    return ret


def delete(fun):
    """
    Remove specific function contents of minion.

    :param str fun: The name of the function.
    :rtype: bool
    :return: True on success.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.delete 'network.interfaces'
    """
    if __opts__["file_client"] == "local":
        data = __salt__["data.get"]("mine_cache")
        if isinstance(data, dict) and fun in data:
            del data[fun]
        return __salt__["data.update"]("mine_cache", data)
    load = {
        "cmd": "_mine_delete",
        "id": __opts__["id"],
        "fun": fun,
    }
    return _mine_send(load, __opts__)


def flush():
    """
    Remove all mine contents of minion.

    :rtype: bool
    :return: True on success

    CLI Example:

    .. code-block:: bash

        salt '*' mine.flush
    """
    if __opts__["file_client"] == "local":
        return __salt__["data.update"]("mine_cache", {})
    load = {
        "cmd": "_mine_flush",
        "id": __opts__["id"],
    }
    return _mine_send(load, __opts__)


def get_docker(interfaces=None, cidrs=None, with_container_id=False):
    """
    .. versionchanged:: 2017.7.8,2018.3.3
        When :conf_minion:`docker.update_mine` is set to ``False`` for a given
        minion, no mine data will be populated for that minion, and thus none
        will be returned for it.
    .. versionchanged:: 2019.2.0
        :conf_minion:`docker.update_mine` now defaults to ``False``

    Get all mine data for :py:func:`docker.ps <salt.modules.dockermod.ps_>` and
    run an aggregation routine. The ``interfaces`` parameter allows for
    specifying the network interfaces from which to select IP addresses. The
    ``cidrs`` parameter allows for specifying a list of subnets which the IP
    address must match.

    with_container_id
        Boolean, to expose container_id in the list of results

        .. versionadded:: 2015.8.2

    CLI Example:

    .. code-block:: bash

        salt '*' mine.get_docker
        salt '*' mine.get_docker interfaces='eth0'
        salt '*' mine.get_docker interfaces='["eth0", "eth1"]'
        salt '*' mine.get_docker cidrs='107.170.147.0/24'
        salt '*' mine.get_docker cidrs='["107.170.147.0/24", "172.17.42.0/24"]'
        salt '*' mine.get_docker interfaces='["eth0", "eth1"]' cidrs='["107.170.147.0/24", "172.17.42.0/24"]'
    """
    # Enforce that interface and cidr are lists
    if interfaces:
        interface_ = []
        interface_.extend(interfaces if isinstance(interfaces, list) else [interfaces])
        interfaces = interface_
    if cidrs:
        cidr_ = []
        cidr_.extend(cidrs if isinstance(cidrs, list) else [cidrs])
        cidrs = cidr_

    # Get docker info
    cmd = "docker.ps"
    docker_hosts = get("*", cmd)

    proxy_lists = {}

    # Process docker info
    for containers in docker_hosts.values():
        host = containers.pop("host")
        host_ips = []

        # Prepare host_ips list
        if not interfaces:
            for info in host["interfaces"].values():
                if "inet" in info:
                    for ip_ in info["inet"]:
                        host_ips.append(ip_["address"])
        else:
            for interface in interfaces:
                if interface in host["interfaces"]:
                    if "inet" in host["interfaces"][interface]:
                        for item in host["interfaces"][interface]["inet"]:
                            host_ips.append(item["address"])
        host_ips = list(set(host_ips))

        # Filter out ips from host_ips with cidrs
        if cidrs:
            good_ips = []
            for cidr in cidrs:
                for ip_ in host_ips:
                    if salt.utils.network.in_subnet(cidr, [ip_]):
                        good_ips.append(ip_)
            host_ips = list(set(good_ips))

        # Process each container
        for container in containers.values():
            container_id = container["Info"]["Id"]
            if container["Image"] not in proxy_lists:
                proxy_lists[container["Image"]] = {}
            for dock_port in container["Ports"]:
                # IP exists only if port is exposed
                ip_address = dock_port.get("IP")
                # If port is 0.0.0.0, then we must get the docker host IP
                if ip_address == "0.0.0.0":
                    for ip_ in host_ips:
                        containers = (
                            proxy_lists[container["Image"]]
                            .setdefault("ipv4", {})
                            .setdefault(dock_port["PrivatePort"], [])
                        )
                        container_network_footprint = "{}:{}".format(
                            ip_, dock_port["PublicPort"]
                        )
                        if with_container_id:
                            value = (container_network_footprint, container_id)
                        else:
                            value = container_network_footprint
                        if value not in containers:
                            containers.append(value)
                elif ip_address:
                    containers = (
                        proxy_lists[container["Image"]]
                        .setdefault("ipv4", {})
                        .setdefault(dock_port["PrivatePort"], [])
                    )
                    container_network_footprint = "{}:{}".format(
                        dock_port["IP"], dock_port["PublicPort"]
                    )
                    if with_container_id:
                        value = (container_network_footprint, container_id)
                    else:
                        value = container_network_footprint
                    if value not in containers:
                        containers.append(value)

    return proxy_lists


def valid():
    """
    List valid entries in mine configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.valid
    """
    mine_functions = __salt__["config.merge"]("mine_functions", {})
    # If we don't have any mine functions configured, then we should just bail out
    if not mine_functions:
        return

    mine_data = {}
    for function_alias, function_data in mine_functions.items():
        (
            function_name,
            function_args,
            function_kwargs,
            minion_acl,
        ) = salt.utils.mine.parse_function_definition(function_data)
        if not _mine_function_available(function_name or function_alias):
            continue
        if function_name:
            mine_data[function_alias] = {
                function_name: function_args
                + [{key: value} for key, value in function_kwargs.items()]
            }
        else:
            mine_data[function_alias] = function_data
    return mine_data
