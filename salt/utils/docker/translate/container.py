# -*- coding: utf-8 -*-
"""
Functions to translate input for container creation
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt libs
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import helpers
from . import helpers

ALIASES = {
    "cmd": "command",
    "cpuset": "cpuset_cpus",
    "dns_option": "dns_opt",
    "env": "environment",
    "expose": "ports",
    "interactive": "stdin_open",
    "ipc": "ipc_mode",
    "label": "labels",
    "memory": "mem_limit",
    "memory_swap": "memswap_limit",
    "publish": "port_bindings",
    "publish_all": "publish_all_ports",
    "restart": "restart_policy",
    "rm": "auto_remove",
    "sysctl": "sysctls",
    "security_opts": "security_opt",
    "ulimit": "ulimits",
    "user_ns_mode": "userns_mode",
    "volume": "volumes",
    "workdir": "working_dir",
}
ALIASES_REVMAP = dict([(y, x) for x, y in six.iteritems(ALIASES)])


def _merge_keys(kwargs):
    """
    The log_config is a mixture of the CLI options --log-driver and --log-opt
    (which we support in Salt as log_driver and log_opt, respectively), but it
    must be submitted to the host config in the format {'Type': log_driver,
    'Config': log_opt}. So, we need to construct this argument to be passed to
    the API from those two arguments.
    """
    log_driver = kwargs.pop("log_driver", helpers.NOTSET)
    log_opt = kwargs.pop("log_opt", helpers.NOTSET)
    if "log_config" not in kwargs:
        if log_driver is not helpers.NOTSET or log_opt is not helpers.NOTSET:
            kwargs["log_config"] = {
                "Type": log_driver if log_driver is not helpers.NOTSET else "none",
                "Config": log_opt if log_opt is not helpers.NOTSET else {},
            }


def _post_processing(kwargs, skip_translate, invalid):
    """
    Additional container-specific post-translation processing
    """
    # Don't allow conflicting options to be set
    if kwargs.get("port_bindings") is not None and kwargs.get("publish_all_ports"):
        kwargs.pop("port_bindings")
        invalid["port_bindings"] = "Cannot be used when publish_all_ports=True"
    if kwargs.get("hostname") is not None and kwargs.get("network_mode") == "host":
        kwargs.pop("hostname")
        invalid["hostname"] = "Cannot be used when network_mode=True"

    # Make sure volumes and ports are defined to match the binds and port_bindings
    if kwargs.get("binds") is not None and (
        skip_translate is True
        or all(x not in skip_translate for x in ("binds", "volume", "volumes"))
    ):
        # Make sure that all volumes defined in "binds" are included in the
        # "volumes" param.
        auto_volumes = []
        if isinstance(kwargs["binds"], dict):
            for val in six.itervalues(kwargs["binds"]):
                try:
                    if "bind" in val:
                        auto_volumes.append(val["bind"])
                except TypeError:
                    continue
        else:
            if isinstance(kwargs["binds"], list):
                auto_volume_defs = kwargs["binds"]
            else:
                try:
                    auto_volume_defs = helpers.split(kwargs["binds"])
                except AttributeError:
                    auto_volume_defs = []
            for val in auto_volume_defs:
                try:
                    auto_volumes.append(helpers.split(val, ":")[1])
                except IndexError:
                    continue
        if auto_volumes:
            actual_volumes = kwargs.setdefault("volumes", [])
            actual_volumes.extend([x for x in auto_volumes if x not in actual_volumes])
            # Sort list to make unit tests more reliable
            actual_volumes.sort()

    if kwargs.get("port_bindings") is not None and all(
        x not in skip_translate for x in ("port_bindings", "expose", "ports")
    ):
        # Make sure that all ports defined in "port_bindings" are included in
        # the "ports" param.
        ports_to_bind = list(kwargs["port_bindings"])
        if ports_to_bind:
            ports_to_open = set(kwargs.get("ports", []))
            ports_to_open.update([helpers.get_port_def(x) for x in ports_to_bind])
            kwargs["ports"] = list(ports_to_open)

    if "ports" in kwargs and all(x not in skip_translate for x in ("expose", "ports")):
        # TCP ports should only be passed as the port number. Normalize the
        # input so a port definition of 80/tcp becomes just 80 instead of
        # (80, 'tcp').
        for index, _ in enumerate(kwargs["ports"]):
            try:
                if kwargs["ports"][index][1] == "tcp":
                    kwargs["ports"][index] = ports_to_open[index][0]
            except TypeError:
                continue


# Functions below must match names of docker-py arguments
def auto_remove(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def binds(val, **kwargs):  # pylint: disable=unused-argument
    """
    On the CLI, these are passed as multiple instances of a given CLI option.
    In Salt, we accept these as a comma-delimited list but the API expects a
    Python list.
    """
    if not isinstance(val, dict):
        if not isinstance(val, list):
            try:
                val = helpers.split(val)
            except AttributeError:
                raise SaltInvocationError(
                    "'{0}' is not a dictionary or list of bind "
                    "definitions".format(val)
                )
    return val


def blkio_weight(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def blkio_weight_device(val, **kwargs):  # pylint: disable=unused-argument
    """
    CLI input is a list of PATH:WEIGHT pairs, but the API expects a list of
    dictionaries in the format [{'Path': path, 'Weight': weight}]
    """
    val = helpers.map_vals(val, "Path", "Weight")
    for idx in range(len(val)):
        try:
            val[idx]["Weight"] = int(val[idx]["Weight"])
        except (TypeError, ValueError):
            raise SaltInvocationError(
                "Weight '{Weight}' for path '{Path}' is not an "
                "integer".format(**val[idx])
            )
    return val


def cap_add(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def cap_drop(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def command(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_command(val)


def cpuset_cpus(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def cpuset_mems(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def cpu_group(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def cpu_period(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def cpu_shares(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def detach(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def device_read_bps(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_device_rates(val, numeric_rate=False)


def device_read_iops(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_device_rates(val, numeric_rate=True)


def device_write_bps(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_device_rates(val, numeric_rate=False)


def device_write_iops(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_device_rates(val, numeric_rate=True)


def devices(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def dns_opt(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def dns_search(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def dns(val, **kwargs):
    val = helpers.translate_stringlist(val)
    if kwargs.get("validate_ip_addrs", True):
        for item in val:
            helpers.validate_ip(item)
    return val


def domainname(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def entrypoint(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_command(val)


def environment(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_key_val(val, delimiter="=")


def extra_hosts(val, **kwargs):
    val = helpers.translate_key_val(val, delimiter=":")
    if kwargs.get("validate_ip_addrs", True):
        for key in val:
            helpers.validate_ip(val[key])
    return val


def group_add(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def host_config(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_dict(val)


def hostname(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def ipc_mode(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def isolation(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def labels(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_labels(val)


def links(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_key_val(val, delimiter=":")


def log_driver(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def log_opt(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_key_val(val, delimiter="=")


def lxc_conf(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_key_val(val, delimiter="=")


def mac_address(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def mem_limit(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bytes(val)


def mem_swappiness(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def memswap_limit(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bytes(val)


def name(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def network_disabled(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def network_mode(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def oom_kill_disable(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def oom_score_adj(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def pid_mode(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def pids_limit(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def port_bindings(val, **kwargs):
    """
    On the CLI, these are passed as multiple instances of a given CLI option.
    In Salt, we accept these as a comma-delimited list but the API expects a
    Python dictionary mapping ports to their bindings. The format the API
    expects is complicated depending on whether or not the external port maps
    to a different internal port, or if the port binding is for UDP instead of
    TCP (the default). For reference, see the "Port bindings" section in the
    docker-py documentation at the following URL:
    http://docker-py.readthedocs.io/en/stable/api.html
    """
    validate_ip_addrs = kwargs.get("validate_ip_addrs", True)
    if not isinstance(val, dict):
        if not isinstance(val, list):
            try:
                val = helpers.split(val)
            except AttributeError:
                val = helpers.split(six.text_type(val))

        for idx in range(len(val)):
            if not isinstance(val[idx], six.string_types):
                val[idx] = six.text_type(val[idx])

        def _format_port(port_num, proto):
            return (
                six.text_type(port_num) + "/udp" if proto.lower() == "udp" else port_num
            )

        bindings = {}
        for binding in val:
            bind_parts = helpers.split(binding, ":")
            num_bind_parts = len(bind_parts)
            if num_bind_parts == 1:
                # Single port or port range being passed through (no
                # special mapping)
                container_port = six.text_type(bind_parts[0])
                if container_port == "":
                    raise SaltInvocationError("Empty port binding definition found")
                container_port, _, proto = container_port.partition("/")
                try:
                    start, end = helpers.get_port_range(container_port)
                except ValueError as exc:
                    # Using __str__() to avoid deprecation warning for using
                    # the message attribute of the ValueError.
                    raise SaltInvocationError(exc.__str__())
                bind_vals = [
                    (_format_port(port_num, proto), None)
                    for port_num in range(start, end + 1)
                ]
            elif num_bind_parts == 2:
                if bind_parts[0] == "":
                    raise SaltInvocationError(
                        "Empty host port in port binding definition "
                        "'{0}'".format(binding)
                    )
                if bind_parts[1] == "":
                    raise SaltInvocationError(
                        "Empty container port in port binding definition "
                        "'{0}'".format(binding)
                    )
                container_port, _, proto = bind_parts[1].partition("/")
                try:
                    cport_start, cport_end = helpers.get_port_range(container_port)
                    hport_start, hport_end = helpers.get_port_range(bind_parts[0])
                except ValueError as exc:
                    # Using __str__() to avoid deprecation warning for
                    # using the message attribute of the ValueError.
                    raise SaltInvocationError(exc.__str__())
                if (hport_end - hport_start) != (cport_end - cport_start):
                    # Port range is mismatched
                    raise SaltInvocationError(
                        "Host port range ({0}) does not have the same "
                        "number of ports as the container port range "
                        "({1})".format(bind_parts[0], container_port)
                    )
                cport_list = list(range(cport_start, cport_end + 1))
                hport_list = list(range(hport_start, hport_end + 1))
                bind_vals = [
                    (_format_port(cport_list[x], proto), hport_list[x])
                    for x in range(len(cport_list))
                ]
            elif num_bind_parts == 3:
                host_ip, host_port = bind_parts[0:2]
                if validate_ip_addrs:
                    helpers.validate_ip(host_ip)
                container_port, _, proto = bind_parts[2].partition("/")
                try:
                    cport_start, cport_end = helpers.get_port_range(container_port)
                except ValueError as exc:
                    # Using __str__() to avoid deprecation warning for
                    # using the message attribute of the ValueError.
                    raise SaltInvocationError(exc.__str__())
                cport_list = list(range(cport_start, cport_end + 1))
                if host_port == "":
                    hport_list = [None] * len(cport_list)
                else:
                    try:
                        hport_start, hport_end = helpers.get_port_range(host_port)
                    except ValueError as exc:
                        # Using __str__() to avoid deprecation warning for
                        # using the message attribute of the ValueError.
                        raise SaltInvocationError(exc.__str__())
                    hport_list = list(range(hport_start, hport_end + 1))

                    if (hport_end - hport_start) != (cport_end - cport_start):
                        # Port range is mismatched
                        raise SaltInvocationError(
                            "Host port range ({0}) does not have the same "
                            "number of ports as the container port range "
                            "({1})".format(host_port, container_port)
                        )

                bind_vals = [
                    (
                        _format_port(val, proto),
                        (host_ip,)
                        if hport_list[idx] is None
                        else (host_ip, hport_list[idx]),
                    )
                    for idx, val in enumerate(cport_list)
                ]
            else:
                raise SaltInvocationError(
                    "'{0}' is an invalid port binding definition (at most "
                    "3 components are allowed, found {1})".format(
                        binding, num_bind_parts
                    )
                )

            for cport, bind_def in bind_vals:
                if cport not in bindings:
                    bindings[cport] = bind_def
                else:
                    if isinstance(bindings[cport], list):
                        # Append to existing list of bindings for this
                        # container port.
                        bindings[cport].append(bind_def)
                    else:
                        bindings[cport] = [bindings[cport], bind_def]
                    for idx in range(len(bindings[cport])):
                        if bindings[cport][idx] is None:
                            # Now that we are adding multiple
                            # bindings
                            try:
                                # Convert 1234/udp to 1234
                                bindings[cport][idx] = int(cport.split("/")[0])
                            except AttributeError:
                                # Port was tcp, the AttributeError
                                # signifies that the split failed
                                # because the port number was
                                # already defined as an integer.
                                # Just use the cport.
                                bindings[cport][idx] = cport
        val = bindings
    return val


def ports(val, **kwargs):  # pylint: disable=unused-argument
    """
    Like cap_add, cap_drop, etc., this option can be specified multiple times,
    and each time can be a port number or port range. Ultimately, the API
    expects a list, but elements in the list are ints when the port is TCP, and
    a tuple (port_num, 'udp') when the port is UDP.
    """
    if not isinstance(val, list):
        try:
            val = helpers.split(val)
        except AttributeError:
            if isinstance(val, six.integer_types):
                val = [val]
            else:
                raise SaltInvocationError(
                    "'{0}' is not a valid port definition".format(val)
                )
    new_ports = set()
    for item in val:
        if isinstance(item, six.integer_types):
            new_ports.add(item)
            continue
        try:
            item, _, proto = item.partition("/")
        except AttributeError:
            raise SaltInvocationError(
                "'{0}' is not a valid port definition".format(item)
            )
        try:
            range_start, range_end = helpers.get_port_range(item)
        except ValueError as exc:
            # Using __str__() to avoid deprecation warning for using
            # the "message" attribute of the ValueError.
            raise SaltInvocationError(exc.__str__())
        new_ports.update(
            [helpers.get_port_def(x, proto) for x in range(range_start, range_end + 1)]
        )
    return list(new_ports)


def privileged(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def publish_all_ports(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def read_only(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def restart_policy(val, **kwargs):  # pylint: disable=unused-argument
    """
    CLI input is in the format NAME[:RETRY_COUNT] but the API expects {'Name':
    name, 'MaximumRetryCount': retry_count}. We will use the 'fill' kwarg here
    to make sure the mapped result uses '0' for the count if this optional
    value was omitted.
    """
    val = helpers.map_vals(val, "Name", "MaximumRetryCount", fill="0")
    # map_vals() converts the input into a list of dicts, but the API
    # wants just a dict, so extract the value from the single-element
    # list. If there was more than one element in the list, then
    # invalid input was passed (i.e. a comma-separated list, when what
    # we wanted was a single value).
    if len(val) != 1:
        raise SaltInvocationError("Only one policy is permitted")
    val = val[0]
    try:
        # The count needs to be an integer
        val["MaximumRetryCount"] = int(val["MaximumRetryCount"])
    except (TypeError, ValueError):
        # Non-numeric retry count passed
        raise SaltInvocationError(
            "Retry count '{0}' is non-numeric".format(val["MaximumRetryCount"])
        )
    return val


def security_opt(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def shm_size(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bytes(val)


def stdin_open(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def stop_signal(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def stop_timeout(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_int(val)


def storage_opt(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_key_val(val, delimiter="=")


def sysctls(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_key_val(val, delimiter="=")


def tmpfs(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_dict(val)


def tty(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def ulimits(val, **kwargs):  # pylint: disable=unused-argument
    val = helpers.translate_stringlist(val)
    for idx in range(len(val)):
        if not isinstance(val[idx], dict):
            try:
                ulimit_name, limits = helpers.split(val[idx], "=", 1)
                comps = helpers.split(limits, ":", 1)
            except (AttributeError, ValueError):
                raise SaltInvocationError(
                    "Ulimit definition '{0}' is not in the format "
                    "type=soft_limit[:hard_limit]".format(val[idx])
                )
            if len(comps) == 1:
                comps *= 2
            soft_limit, hard_limit = comps
            try:
                val[idx] = {
                    "Name": ulimit_name,
                    "Soft": int(soft_limit),
                    "Hard": int(hard_limit),
                }
            except (TypeError, ValueError):
                raise SaltInvocationError(
                    "Limit '{0}' contains non-numeric value(s)".format(val[idx])
                )
    return val


def user(val, **kwargs):  # pylint: disable=unused-argument
    """
    This can be either a string or a numeric uid
    """
    if not isinstance(val, six.integer_types):
        # Try to convert to integer. This will fail if the value is a
        # username. This is OK, as we check below to make sure that the
        # value is either a string or integer. Trying to convert to an
        # integer first though will allow us to catch the edge case in
        # which a quoted uid is passed (e.g. '1000').
        try:
            val = int(val)
        except (TypeError, ValueError):
            pass
    if not isinstance(val, (six.integer_types, six.string_types)):
        raise SaltInvocationError("Value must be a username or uid")
    elif isinstance(val, six.integer_types) and val < 0:
        raise SaltInvocationError("'{0}' is an invalid uid".format(val))
    return val


def userns_mode(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def volume_driver(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def volumes(val, **kwargs):  # pylint: disable=unused-argument
    """
    Should be a list of absolute paths
    """
    val = helpers.translate_stringlist(val)
    for item in val:
        if not os.path.isabs(item):
            raise SaltInvocationError("'{0}' is not an absolute path".format(item))
    return val


def volumes_from(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_stringlist(val)


def working_dir(val, **kwargs):  # pylint: disable=unused-argument
    """
    Must be an absolute path
    """
    try:
        is_abs = os.path.isabs(val)
    except AttributeError:
        is_abs = False
    if not is_abs:
        raise SaltInvocationError("'{0}' is not an absolute path".format(val))
    return val
