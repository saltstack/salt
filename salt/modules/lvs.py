"""
Support for LVS (Linux Virtual Server)
"""

import salt.utils.decorators as decorators
import salt.utils.path
from salt.exceptions import SaltException

__func_alias__ = {"list_": "list"}


# Cache the output of running which('ipvsadm')
@decorators.memoize
def __detect_os():
    return salt.utils.path.which("ipvsadm")


def __virtual__():
    """
    Only load if ipvsadm command exists on the system.
    """
    if not __detect_os():
        return (
            False,
            "The lvs execution module cannot be loaded: the ipvsadm binary is not in"
            " the path.",
        )

    return "lvs"


def _build_cmd(**kwargs):
    """

    Build a well-formatted ipvsadm command based on kwargs.
    """
    cmd = ""

    if "service_address" in kwargs:
        if kwargs["service_address"]:
            if "protocol" in kwargs:
                if kwargs["protocol"] == "tcp":
                    cmd += " -t {}".format(kwargs["service_address"])
                elif kwargs["protocol"] == "udp":
                    cmd += " -u {}".format(kwargs["service_address"])
                elif kwargs["protocol"] == "fwmark":
                    cmd += " -f {}".format(kwargs["service_address"])
                else:
                    raise SaltException(
                        "Error: Only support tcp, udp and fwmark service protocol"
                    )
                del kwargs["protocol"]
            else:
                raise SaltException("Error: protocol should specified")
            if "scheduler" in kwargs:
                if kwargs["scheduler"]:
                    cmd += " -s {}".format(kwargs["scheduler"])
                    del kwargs["scheduler"]
        else:
            raise SaltException("Error: service_address should specified")
        del kwargs["service_address"]

    if "server_address" in kwargs:
        if kwargs["server_address"]:
            cmd += " -r {}".format(kwargs["server_address"])
            if "packet_forward_method" in kwargs and kwargs["packet_forward_method"]:
                if kwargs["packet_forward_method"] == "dr":
                    cmd += " -g"
                elif kwargs["packet_forward_method"] == "tunnel":
                    cmd += " -i"
                elif kwargs["packet_forward_method"] == "nat":
                    cmd += " -m"
                else:
                    raise SaltException("Error: only support dr, tunnel and nat")
                del kwargs["packet_forward_method"]
            if "weight" in kwargs and kwargs["weight"]:
                cmd += " -w {}".format(kwargs["weight"])
                del kwargs["weight"]
        else:
            raise SaltException("Error: server_address should specified")
        del kwargs["server_address"]

    return cmd


def add_service(protocol=None, service_address=None, scheduler="wlc"):
    """
    Add a virtual service.

    protocol
        The service protocol(only support tcp, udp and fwmark service).

    service_address
        The LVS service address.

    scheduler
        Algorithm for allocating TCP connections and UDP datagrams to real servers.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.add_service tcp 1.1.1.1:80 rr
    """

    cmd = "{} -A {}".format(
        __detect_os(),
        _build_cmd(
            protocol=protocol, service_address=service_address, scheduler=scheduler
        ),
    )
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def edit_service(protocol=None, service_address=None, scheduler=None):
    """
    Edit the virtual service.

    protocol
        The service protocol(only support tcp, udp and fwmark service).

    service_address
        The LVS service address.

    scheduler
        Algorithm for allocating TCP connections and UDP datagrams to real servers.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.edit_service tcp 1.1.1.1:80 rr
    """

    cmd = "{} -E {}".format(
        __detect_os(),
        _build_cmd(
            protocol=protocol, service_address=service_address, scheduler=scheduler
        ),
    )
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def delete_service(protocol=None, service_address=None):
    """

    Delete the virtual service.

    protocol
        The service protocol(only support tcp, udp and fwmark service).

    service_address
        The LVS service address.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.delete_service tcp 1.1.1.1:80
    """

    cmd = "{} -D {}".format(
        __detect_os(), _build_cmd(protocol=protocol, service_address=service_address)
    )
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def add_server(
    protocol=None,
    service_address=None,
    server_address=None,
    packet_forward_method="dr",
    weight=1,
    **kwargs
):
    """

    Add a real server to a virtual service.

    protocol
        The service protocol(only support ``tcp``, ``udp`` and ``fwmark`` service).

    service_address
        The LVS service address.

    server_address
        The real server address.

    packet_forward_method
        The LVS packet forwarding method(``dr`` for direct routing, ``tunnel`` for tunneling, ``nat`` for network access translation).

    weight
        The capacity  of a server relative to the others in the pool.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.add_server tcp 1.1.1.1:80 192.168.0.11:8080 nat 1
    """

    cmd = "{} -a {}".format(
        __detect_os(),
        _build_cmd(
            protocol=protocol,
            service_address=service_address,
            server_address=server_address,
            packet_forward_method=packet_forward_method,
            weight=weight,
            **kwargs
        ),
    )
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def edit_server(
    protocol=None,
    service_address=None,
    server_address=None,
    packet_forward_method=None,
    weight=None,
    **kwargs
):
    """

    Edit a real server to a virtual service.

    protocol
        The service protocol(only support ``tcp``, ``udp`` and ``fwmark`` service).

    service_address
        The LVS service address.

    server_address
        The real server address.

    packet_forward_method
        The LVS packet forwarding method(``dr`` for direct routing, ``tunnel`` for tunneling, ``nat`` for network access translation).

    weight
        The capacity  of a server relative to the others in the pool.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.edit_server tcp 1.1.1.1:80 192.168.0.11:8080 nat 1
    """

    cmd = "{} -e {}".format(
        __detect_os(),
        _build_cmd(
            protocol=protocol,
            service_address=service_address,
            server_address=server_address,
            packet_forward_method=packet_forward_method,
            weight=weight,
            **kwargs
        ),
    )
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def delete_server(protocol=None, service_address=None, server_address=None):
    """

    Delete the realserver from the virtual service.

    protocol
        The service protocol(only support ``tcp``, ``udp`` and ``fwmark`` service).

    service_address
        The LVS service address.

    server_address
        The real server address.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.delete_server tcp 1.1.1.1:80 192.168.0.11:8080
    """

    cmd = "{} -d {}".format(
        __detect_os(),
        _build_cmd(
            protocol=protocol,
            service_address=service_address,
            server_address=server_address,
        ),
    )
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def clear():
    """

    Clear the virtual server table

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.clear
    """

    cmd = "{} -C".format(__detect_os())

    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def get_rules():
    """

    Get the virtual server rules

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.get_rules
    """

    cmd = "{} -S -n".format(__detect_os())

    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def list_(protocol=None, service_address=None):
    """

    List the virtual server table if service_address is not specified. If a service_address is selected, list this service only.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.list
    """

    if service_address:
        cmd = "{} -L {} -n".format(
            __detect_os(),
            _build_cmd(protocol=protocol, service_address=service_address),
        )
    else:
        cmd = "{} -L -n".format(__detect_os())
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = out["stdout"].strip()

    return ret


def zero(protocol=None, service_address=None):
    """

    Zero the packet, byte and rate counters in a service or all services.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.zero
    """

    if service_address:
        cmd = "{} -Z {}".format(
            __detect_os(),
            _build_cmd(protocol=protocol, service_address=service_address),
        )
    else:
        cmd = "{} -Z".format(__detect_os())
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    # A non-zero return code means fail
    if out["retcode"]:
        ret = out["stderr"].strip()
    else:
        ret = True
    return ret


def check_service(protocol=None, service_address=None, **kwargs):
    """

    Check the virtual service exists.

    CLI Example:

    .. code-block:: bash

        salt '*' lvs.check_service tcp 1.1.1.1:80
    """

    cmd = "{}".format(
        _build_cmd(protocol=protocol, service_address=service_address, **kwargs)
    )
    # Exact match
    if not kwargs:
        cmd += " "

    all_rules = get_rules()
    out = all_rules.find(cmd)

    if out != -1:
        ret = True
    else:
        ret = "Error: service not exists"
    return ret


def check_server(protocol=None, service_address=None, server_address=None, **kwargs):
    """

    Check the real server exists in the specified service.

    CLI Example:

    .. code-block:: bash

         salt '*' lvs.check_server tcp 1.1.1.1:80 192.168.0.11:8080
    """

    cmd = "{}".format(
        _build_cmd(
            protocol=protocol,
            service_address=service_address,
            server_address=server_address,
            **kwargs
        )
    )
    # Exact match
    if not kwargs:
        cmd += " "

    all_rules = get_rules()
    out = all_rules.find(cmd)

    if out != -1:
        ret = True
    else:
        ret = "Error: server not exists"
    return ret
