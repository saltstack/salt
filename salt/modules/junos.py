"""
Module to interact with Junos devices.

:maturity: new
:dependencies: junos-eznc, jxmlease

.. note::

    Those who wish to use junos-eznc (PyEZ) version >= 2.1.0, must
    use the latest salt code from github until the next release.

Refer to :mod:`junos <salt.proxy.junos>` for information on connecting to junos proxy.

"""

import copy
import json
import logging
import os
import re
from functools import wraps

import yaml

import salt.utils.args
import salt.utils.files
import salt.utils.json
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree


# Juniper interface libraries
# https://github.com/Juniper/py-junos-eznc
try:
    # pylint: disable=W0611
    import jnpr.junos.cfg
    import jnpr.junos.op as tables_dir
    import jnpr.junos.utils
    import jxmlease
    import yamlordereddictloader
    from jnpr.junos import Device
    from jnpr.junos.exception import (
        ConnectClosedError,
        LockError,
        RpcTimeoutError,
        UnlockError,
    )
    from jnpr.junos.factory.cfgtable import CfgTable
    from jnpr.junos.factory.factory_loader import FactoryLoader
    from jnpr.junos.factory.optable import OpTable
    from jnpr.junos.utils.config import Config
    from jnpr.junos.utils.scp import SCP
    from jnpr.junos.utils.sw import SW

    # pylint: enable=W0611
    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "junos"

__proxyenabled__ = ["junos"]


def __virtual__():
    """
    We need the Junos adapter libraries for this
    module to work.  We also need a proxymodule entry in __opts__
    in the opts dictionary
    """
    if HAS_JUNOS and "proxy" in __opts__:
        return __virtualname__
    else:
        return (
            False,
            "The junos or dependent module could not be loaded: "
            "junos-eznc or jxmlease or yamlordereddictloader or "
            "proxy could not be loaded.",
        )


class HandleFileCopy:
    """
    To figure out proper path either from proxy local file system
    or proxy cache or on master. If required, then only copy from
    master to proxy

    """

    def __init__(self, path, **kwargs):
        self._file_path = path
        self._cached_folder = None
        self._cached_file = None
        self._kwargs = kwargs

    def __enter__(self):
        if self._file_path.startswith("salt://"):
            # check if file exists in cache
            local_cache_path = __salt__["cp.is_cached"](self._file_path)
            if local_cache_path:
                master_hash = __salt__["cp.hash_file"](self._file_path)
                proxy_hash = __salt__["file.get_hash"](local_cache_path)
                # check if hash is same, else copy newly
                if master_hash.get("hsum") == proxy_hash:
                    self._cached_file = salt.utils.files.mkstemp()
                    # local copy is a template, hence need to render
                    with salt.utils.files.fopen(self._cached_file, "w") as fp:
                        template_string = __salt__["slsutil.renderer"](
                            path=local_cache_path,
                            default_renderer="jinja",
                            **self._kwargs,
                        )
                        fp.write(template_string)
                    return self._cached_file

            # continue for else part
            self._cached_file = salt.utils.files.mkstemp()
            __salt__["cp.get_template"](
                self._file_path, self._cached_file, **self._kwargs
            )
            if self._cached_file != "":
                return self._cached_file
        else:
            # check for local location of file
            if __salt__["file.file_exists"](self._file_path):
                self._cached_file = salt.utils.files.mkstemp()
                with salt.utils.files.fopen(self._cached_file, "w") as fp:
                    template_string = __salt__["slsutil.renderer"](
                        path=self._file_path, default_renderer="jinja", **self._kwargs
                    )
                    fp.write(template_string)
                return self._cached_file

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self._cached_file is not None:
            salt.utils.files.safe_rm(self._cached_file)
            log.debug("Deleted cached file: %s", self._cached_file)
        if self._cached_folder is not None:
            __salt__["file.rmdir"](self._cached_folder)
            log.debug("Deleted cached folder: %s", self._cached_folder)


def _timeout_decorator(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "dev_timeout" in kwargs or "timeout" in kwargs:
            ldev_timeout = max(kwargs.pop("dev_timeout", 0), kwargs.pop("timeout", 0))
            conn = __proxy__["junos.conn"]()
            restore_timeout = conn.timeout
            conn.timeout = ldev_timeout
            try:
                result = function(*args, **kwargs)
                conn.timeout = restore_timeout
                return result
            except Exception:  # pylint: disable=broad-except
                conn.timeout = restore_timeout
                raise
        else:
            return function(*args, **kwargs)

    return wrapper


def _timeout_decorator_cleankwargs(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "dev_timeout" in kwargs or "timeout" in kwargs:
            ldev_timeout = max(kwargs.pop("dev_timeout", 0), kwargs.pop("timeout", 0))
            conn = __proxy__["junos.conn"]()
            restore_timeout = conn.timeout
            conn.timeout = ldev_timeout
            try:
                restore_kwargs = False
                del_list = []
                op = {}
                op.update(kwargs)
                for keychk in kwargs:
                    if keychk.startswith("__pub"):
                        del_list.append(keychk)
                if del_list:
                    restore_kwargs = True
                    for delkey in del_list:
                        kwargs.pop(delkey)

                result = function(*args, **kwargs)
                if restore_kwargs:
                    kwargs.update(op)

                conn.timeout = restore_timeout
                return result
            except Exception:  # pylint: disable=broad-except
                conn.timeout = restore_timeout
                raise
        else:
            restore_kwargs = False
            del_list = []
            op = {}
            op.update(kwargs)
            for keychk in kwargs:
                if keychk.startswith("__pub"):
                    del_list.append(keychk)
            if del_list:
                restore_kwargs = True
                for delkey in del_list:
                    kwargs.pop(delkey)

            ret = function(*args, **kwargs)
            if restore_kwargs:
                kwargs.update(op)

            return ret

    return wrapper


def _restart_connection():
    minion_id = __opts__.get("proxyid", "") or __opts__.get("id", "")
    log.info(
        "Junos exception occurred %s (junos proxy) is down. Restarting.", minion_id
    )
    __salt__["event.fire_master"](
        {}, "junos/proxy/{}/stop".format(__opts__["proxy"]["host"])
    )
    __proxy__["junos.shutdown"](__opts__)  # safely close connection
    __proxy__["junos.init"](__opts__)  # reopen connection
    log.debug("Junos exception occurred, restarted %s (junos proxy)!", minion_id)


@_timeout_decorator_cleankwargs
def facts_refresh():
    """
    Reload the facts dictionary from the device. Usually only needed if,
    the device configuration is changed by some other actor.
    This function will also refresh the facts stored in the salt grains.

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.facts_refresh
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    try:
        conn.facts_refresh()
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Execution failed due to "{exception}"'
        ret["out"] = False
        _restart_connection()
        return ret

    ret["facts"] = __proxy__["junos.get_serialized_facts"]()

    try:
        __salt__["saltutil.sync_grains"]()
    except Exception as exception:  # pylint: disable=broad-except
        log.error('Grains could not be updated due to "%s"', exception)

    return ret


def facts():
    """
    Displays the facts gathered during the connection.
    These facts are also stored in Salt grains.

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.facts
    """
    ret = {}
    try:
        ret["facts"] = __proxy__["junos.get_serialized_facts"]()
        ret["out"] = True
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Could not display facts due to "{exception}"'
        ret["out"] = False
        _restart_connection()

    return ret


@_timeout_decorator
def rpc(cmd=None, dest=None, **kwargs):
    """
    This function executes the RPC provided as arguments on the junos device.
    The returned data can be stored in a file.

    cmd
        The RPC to be executed

    dest
        Destination file where the RPC output is stored. Note that the file
        will be stored on the proxy minion. To push the files to the master use
        :py:func:`cp.push <salt.modules.cp.push>`.

    format : xml
        The format in which the RPC reply is received from the device

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds)

    filter
        Used with the ``get-config`` RPC to get specific configuration

    terse : False
        Amount of information you want

    interface_name
      Name of the interface to query

    CLI Example:

    .. code-block:: bash

        salt 'device' junos.rpc get_config dest=/var/log/config.txt format=text filter='<configuration><system/></configuration>'
        salt 'device' junos.rpc get-interface-information dest=/home/user/interface.xml interface_name='lo0' terse=True
        salt 'device' junos.rpc get-chassis-inventory
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True

    op = dict()
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    elif "__pub_schedule" in kwargs:
        for key, value in kwargs.items():
            if not key.startswith("__pub_"):
                op[key] = value
    else:
        op.update(kwargs)

    if cmd is None:
        ret["message"] = "Please provide the rpc to execute."
        ret["out"] = False
        return ret

    format_ = op.pop("format", "xml")
    # dest becomes part of op via __pub_arg if not None
    # rpc commands objecting to dest as part of op
    op.pop("dest", dest)

    if cmd in ["get-config", "get_config"]:
        filter_reply = None
        if "filter" in op:
            try:
                filter_reply = etree.XML(op["filter"])
            except etree.XMLSyntaxError as ex:
                ret["message"] = f"Invalid filter: {ex}"
                ret["out"] = False
                return ret

            del op["filter"]

        op.update({"format": format_})
        try:
            reply = getattr(conn.rpc, cmd.replace("-", "_"))(filter_reply, options=op)
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = f'RPC execution failed due to "{exception}"'
            ret["out"] = False
            _restart_connection()
            return ret
    else:
        if "filter" in op:
            log.warning('Filter ignored as it is only used with "get-config" rpc')

        if "dest" in op:
            log.warning("dest in op, rpc may reject this for cmd '%s'", cmd)

        try:
            reply = getattr(conn.rpc, cmd.replace("-", "_"))({"format": format_}, **op)
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = f'RPC execution failed due to "{exception}"'
            ret["out"] = False
            _restart_connection()
            return ret

    if format_ == "text":
        ret["rpc_reply"] = reply.text
    elif format_ == "json":
        ret["rpc_reply"] = reply
    else:
        ret["rpc_reply"] = jxmlease.parse(etree.tostring(reply))

    if dest:
        if format_ == "text":
            write_response = reply.text
        elif format_ == "json":
            write_response = salt.utils.json.dumps(reply, indent=1)
        else:
            write_response = etree.tostring(reply)
        with salt.utils.files.fopen(dest, "w") as fp:
            fp.write(salt.utils.stringutils.to_str(write_response))

    return ret


@_timeout_decorator
def set_hostname(hostname=None, **kwargs):
    """
    Set the device's hostname

    hostname
        The name to be set

    comment
        Provide a comment to the commit

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds)

    confirm
      Provide time in minutes for commit confirmation. If this option is
      specified, the commit will be rolled back in the specified amount of time
      unless the commit is confirmed.

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.set_hostname salt-device
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    if hostname is None:
        ret["message"] = "Please provide the hostname."
        ret["out"] = False
        return ret

    op = dict()
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    # Added to recent versions of JunOs
    # Use text format instead
    set_string = f"set system host-name {hostname}"
    try:
        conn.cu.load(set_string, format="set")
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Could not load configuration due to error "{}"'.format(
            exception
        )
        ret["out"] = False
        _restart_connection()
        return ret

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Could not commit check due to error "{exception}"'
        ret["out"] = False
        _restart_connection()
        return ret

    if commit_ok:
        try:
            conn.cu.commit(**op)
            ret["message"] = "Successfully changed hostname."
            ret["out"] = True
        except Exception as exception:  # pylint: disable=broad-except
            ret["out"] = False
            ret["message"] = (
                'Successfully loaded host-name but commit failed with "{}"'.format(
                    exception
                )
            )
            _restart_connection()
            return ret
    else:
        ret["out"] = False
        ret["message"] = "Successfully loaded host-name but pre-commit check failed."
        try:
            conn.cu.rollback()
        except Exception as exception:  # pylint: disable=broad-except
            ret["out"] = False
            ret["message"] = (
                'Successfully loaded host-name but rollback before exit failed "{}"'.format(
                    exception
                )
            )
            _restart_connection()

    return ret


@_timeout_decorator
def commit(**kwargs):
    """
    To commit the changes loaded in the candidate configuration.

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds)

    comment
      Provide a comment for the commit

    confirm
      Provide time in minutes for commit confirmation. If this option is
      specified, the commit will be rolled back in the specified amount of time
      unless the commit is confirmed.

    sync : False
      When ``True``, on dual control plane systems, requests that the candidate
      configuration on one control plane be copied to the other control plane,
      checked for correct syntax, and committed on both Routing Engines.

    force_sync : False
      When ``True``, on dual control plane systems, force the candidate
      configuration on one control plane to be copied to the other control
      plane.

    full
      When ``True``, requires all the daemons to check and evaluate the new
      configuration.

    detail
      When ``True``, return commit detail

    CLI Examples:

    .. code-block:: bash

        salt 'device_name' junos.commit comment='Commiting via saltstack' detail=True
        salt 'device_name' junos.commit dev_timeout=60 confirm=10
        salt 'device_name' junos.commit sync=True dev_timeout=90
    """

    conn = __proxy__["junos.conn"]()
    ret = {}
    op = dict()
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    op["detail"] = op.get("detail", False)

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Could not perform commit check due to "{exception}"'
        ret["out"] = False
        _restart_connection()
        return ret

    if commit_ok:
        try:
            commit = conn.cu.commit(**op)
            ret["out"] = True
            if commit:
                if op["detail"]:
                    ret["message"] = jxmlease.parse(etree.tostring(commit))
                else:
                    ret["message"] = "Commit Successful."
            else:
                ret["message"] = "Commit failed."
                ret["out"] = False
        except Exception as exception:  # pylint: disable=broad-except
            ret["out"] = False
            ret["message"] = (
                'Commit check succeeded but actual commit failed with "{}"'.format(
                    exception
                )
            )
            _restart_connection()
    else:
        ret["out"] = False
        ret["message"] = "Pre-commit check failed."
        try:
            conn.cu.rollback()
        except Exception as exception:  # pylint: disable=broad-except
            ret["out"] = False
            ret["message"] = (
                'Pre-commit check failed, and exception during rollback "{}"'.format(
                    exception
                )
            )
            _restart_connection()

    return ret


@_timeout_decorator
def rollback(**kwargs):
    """
    Roll back the last committed configuration changes and commit

    id : 0
        The rollback ID value (0-49)

    d_id : 0
        The rollback ID value (0-49)

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds)

    comment
      Provide a comment for the commit

    confirm
      Provide time in minutes for commit confirmation. If this option is
      specified, the commit will be rolled back in the specified amount of time
      unless the commit is confirmed.

    diffs_file
      Path to the file where the diff (difference in old configuration and the
      committed configuration) will be stored. Note that the file will be
      stored on the proxy minion. To push the files to the master use
      :py:func:`cp.push <salt.modules.cp.push>`.

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.rollback 10

    NOTE: Because of historical reasons and the internals of the Salt state
    compiler, there are three possible sources of the rollback ID--the
    positional argument, and the `id` and `d_id` kwargs.  The precedence of
    the arguments are `id` (positional), `id` (kwarg), `d_id` (kwarg).  In
    other words, if all three are passed, only the positional argument
    will be used.  A warning is logged if more than one is passed.
    """
    ids_passed = 0
    id_ = 0
    if "d_id" in kwargs:
        id_ = kwargs.pop("d_id")
        ids_passed = ids_passed + 1
    if "id" in kwargs:
        id_ = kwargs.pop("id", 0)
        ids_passed = ids_passed + 1

    if ids_passed > 1:
        log.warning(
            "junos.rollback called with more than one possible ID. "
            "Use only one of the positional argument, `id`, or `d_id` kwargs"
        )

    ret = {}
    conn = __proxy__["junos.conn"]()

    op = dict()
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    try:
        ret["out"] = conn.cu.rollback(id_)
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Rollback failed due to "{exception}"'
        ret["out"] = False
        _restart_connection()
        return ret

    if ret["out"]:
        ret["message"] = "Rollback successful"
    else:
        ret["message"] = "Rollback failed"
        return ret

    if "diffs_file" in op and op["diffs_file"] is not None:
        diff = conn.cu.diff()
        if diff is not None:
            with salt.utils.files.fopen(op["diffs_file"], "w") as fp:
                fp.write(salt.utils.stringutils.to_str(diff))
        else:
            log.info(
                "No diff between current configuration and "
                "rollbacked configuration, so no diff file created"
            )

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Could not commit check due to "{exception}"'
        ret["out"] = False
        _restart_connection()
        return ret

    if commit_ok:
        try:
            conn.cu.commit(**op)
            ret["out"] = True
        except Exception as exception:  # pylint: disable=broad-except
            ret["out"] = False
            ret["message"] = (
                'Rollback successful but commit failed with error "{}"'.format(
                    exception
                )
            )
            _restart_connection()
            return ret
    else:
        ret["message"] = "Rollback successful but pre-commit check failed."
        ret["out"] = False

    return ret


@_timeout_decorator
def diff(**kwargs):
    """
    Returns the difference between the candidate and the current configuration

    id : 0
        The rollback ID value (0-49)

    d_id : 0
        The rollback ID value (0-49)

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.diff d_id=3

    NOTE: Because of historical reasons and the internals of the Salt state
    compiler, there are three possible sources of the rollback ID--the
    positional argument, and the `id` and `d_id` kwargs.  The precedence of
    the arguments are `id` (positional), `id` (kwarg), `d_id` (kwarg).  In
    other words, if all three are passed, only the positional argument
    will be used.  A warning is logged if more than one is passed.
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    ids_passed = 0
    id_ = 0
    if "d_id" in kwargs:
        id_ = kwargs.pop("d_id")
        ids_passed = ids_passed + 1
    if "id" in kwargs:
        id_ = kwargs.pop("id", 0)
        ids_passed = ids_passed + 1
    if ids_passed > 1:
        log.warning(
            "junos.rollback called with more than one possible ID. "
            "Use only one of the positional argument, `id`, or `d_id` kwargs"
        )

    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    try:
        ret["message"] = conn.cu.diff(rb_id=id_)
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Could not get diff with error "{exception}"'
        ret["out"] = False
        _restart_connection()

    return ret


@_timeout_decorator
def ping(dest_ip=None, **kwargs):
    """
    Send a ping RPC to a device

    dest_ip
      The IP of the device to ping

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds)

    rapid : False
        When ``True``, executes ping at 100pps instead of 1pps

    ttl
        Maximum number of IP routers (IP hops) allowed between source and
        destination

    routing_instance
      Name of the routing instance to use to send the ping

    interface
      Interface used to send traffic

    count : 5
      Number of packets to send

    CLI Examples:

    .. code-block:: bash

        salt 'device_name' junos.ping '8.8.8.8' count=5
        salt 'device_name' junos.ping '8.8.8.8' ttl=1 rapid=True
    """
    conn = __proxy__["junos.conn"]()
    ret = {}

    if dest_ip is None:
        ret["message"] = "Please specify the destination ip to ping."
        ret["out"] = False
        return ret

    op = {"host": dest_ip}
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    op["count"] = str(op.pop("count", 5))
    if "ttl" in op:
        op["ttl"] = str(op["ttl"])

    ret["out"] = True
    try:
        ret["message"] = jxmlease.parse(etree.tostring(conn.rpc.ping(**op)))
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Execution failed due to "{exception}"'
        ret["out"] = False
        _restart_connection()

    return ret


@_timeout_decorator
def cli(command=None, **kwargs):
    """
    Executes the CLI commands and returns the output in specified format. \
    (default is text) The output can also be stored in a file.

    command (required)
        The command to execute on the Junos CLI

    format : text
        Format in which to get the CLI output (either ``text`` or ``xml``)

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds)

    dest
        Destination file where the RPC output is stored. Note that the file
        will be stored on the proxy minion. To push the files to the master use
        :py:func:`cp.push <salt.modules.cp.push>`.

    CLI Examples:

    .. code-block:: bash

        salt 'device_name' junos.cli 'show system commit'
        salt 'device_name' junos.cli 'show system alarms' format=xml dest=/home/user/cli_output.txt
    """
    conn = __proxy__["junos.conn"]()

    format_ = kwargs.pop("format", "text")
    if not format_:
        format_ = "text"

    ret = {}
    if command is None:
        ret["message"] = "Please provide the CLI command to be executed."
        ret["out"] = False
        return ret

    op = dict()
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    try:
        result = conn.cli(command, format_, warning=False)
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Execution failed due to "{exception}"'
        ret["out"] = False
        _restart_connection()
        return ret

    if format_ == "text":
        ret["message"] = result
    else:
        result = etree.tostring(result)
        ret["message"] = jxmlease.parse(result)

    if "dest" in op and op["dest"] is not None:
        try:
            with salt.utils.files.fopen(op["dest"], "w") as fp:
                fp.write(salt.utils.stringutils.to_str(result))
        except OSError:
            ret["message"] = 'Unable to open "{}" to write'.format(op["dest"])
            ret["out"] = False
            return ret

    ret["out"] = True
    return ret


@_timeout_decorator
def shutdown(**kwargs):
    """
    Shut down (power off) or reboot a device running Junos OS. This includes
    all Routing Engines in a Virtual Chassis or a dual Routing Engine system.

      .. note::
          One of ``shutdown`` or ``reboot`` must be set to ``True`` or no
          action will be taken.

    shutdown : False
      Set this to ``True`` if you want to shutdown the machine. This is a
      safety mechanism so that the user does not accidentally shutdown the
      junos device.

    reboot : False
      If ``True``, reboot instead of shutting down

    at
      Used when rebooting, to specify the date and time the reboot should take
      place. The value of this option must match the JunOS CLI reboot syntax.

    in_min
        Used when shutting down. Specify the delay (in minutes) before the
        device will be shut down.

    CLI Examples:

    .. code-block:: bash

        salt 'device_name' junos.shutdown reboot=True
        salt 'device_name' junos.shutdown shutdown=True in_min=10
        salt 'device_name' junos.shutdown shutdown=True
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    sw = SW(conn)

    op = {}
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)
    if "shutdown" not in op and "reboot" not in op:
        ret["message"] = "Provide either one of the arguments: shutdown or reboot."
        ret["out"] = False
        return ret

    try:
        if "reboot" in op and op["reboot"]:
            shut = sw.reboot
        elif "shutdown" in op and op["shutdown"]:
            shut = sw.poweroff
        else:
            ret["message"] = "Nothing to be done."
            ret["out"] = False
            return ret

        if "in_min" in op:
            shut(in_min=op["in_min"])
        elif "at" in op:
            shut(at=op["at"])
        else:
            shut()
        ret["message"] = "Successfully powered off/rebooted."
        ret["out"] = True
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Could not poweroff/reboot because "{exception}"'
        ret["out"] = False
        _restart_connection()

    return ret


@_timeout_decorator
def install_config(path=None, **kwargs):
    """
    Installs the given configuration file into the candidate configuration.
    Commits the changes if the commit checks or throws an error.

    path (required)
        Path where the configuration/template file is present. If the file has
        a ``.conf`` extension, the content is treated as text format. If the
        file has a ``.xml`` extension, the content is treated as XML format. If
        the file has a ``.set`` extension, the content is treated as Junos OS
        ``set`` commands.

    mode : exclusive
        The mode in which the configuration is locked. Can be one of
        ``private``, ``dynamic``, ``batch``, ``exclusive``, ``ephemeral``

    dev_timeout : 30
        Set NETCONF RPC timeout. Can be used for commands which take a while to
        execute.

    overwrite : False
        Set to ``True`` if you want this file is to completely replace the
        configuration file. Sets action to override

        .. note:: This option cannot be used if **format** is "set".

    replace : False
        Specify whether the configuration file uses ``replace:`` statements. If
        ``True``, only those statements under the ``replace`` tag will be
        changed.

    merge : False
        If set to ``True`` will set the load-config action to merge.
        the default load-config action is 'replace' for xml/json/text config

    format
        Determines the format of the contents

    update : False
        Compare a complete loaded configuration against the candidate
        configuration. For each hierarchy level or configuration object that is
        different in the two configurations, the version in the loaded
        configuration replaces the version in the candidate configuration. When
        the configuration is later committed, only system processes that are
        affected by the changed configuration elements parse the new
        configuration. This action is supported from PyEZ 2.1.

    comment
      Provide a comment for the commit

    confirm
      Provide time in minutes for commit confirmation. If this option is
      specified, the commit will be rolled back in the specified amount of time
      unless the commit is confirmed.

    diffs_file
      Path to the file where the diff (difference in old configuration and the
      committed configuration) will be stored. Note that the file will be
      stored on the proxy minion. To push the files to the master use:

        py:func:`cp.push <salt.modules.cp.push>`.

    template_vars
      Variables to be passed into the template processing engine in addition to
      those present in pillar, the minion configuration, grains, etc.  You may
      reference these variables in your template like so:

      .. code-block:: jinja

          {{ template_vars["var_name"] }}

    CLI Examples:

    .. code-block:: bash

        salt 'device_name' junos.install_config 'salt://production/network/routers/config.set'
        salt 'device_name' junos.install_config 'salt://templates/replace_config.conf' replace=True comment='Committed via SaltStack'
        salt 'device_name' junos.install_config 'salt://my_new_configuration.conf' dev_timeout=300 diffs_file='/salt/confs/old_config.conf' overwrite=True
        salt 'device_name' junos.install_config 'salt://syslog_template.conf' template_vars='{"syslog_host": "10.180.222.7"}'
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True

    if path is None:
        ret["message"] = (
            "Please provide the salt path where the configuration is present"
        )
        ret["out"] = False
        return ret

    op = {}
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    test = op.pop("test", False)

    kwargs = {}
    if "template_vars" in op:
        kwargs.update({"template_vars": op["template_vars"]})

    with HandleFileCopy(path, **kwargs) as template_cached_path:
        if template_cached_path is None:
            ret["message"] = "Invalid file path."
            ret["out"] = False
            return ret

        if os.path.getsize(template_cached_path) == 0:
            ret["message"] = "Template failed to render"
            ret["out"] = False
            return ret

        write_diff = ""
        if "diffs_file" in op and op["diffs_file"] is not None:
            write_diff = op["diffs_file"]
            del op["diffs_file"]

        op["path"] = template_cached_path

        if "format" not in op:
            if path.endswith("set"):
                template_format = "set"
            elif path.endswith("xml"):
                template_format = "xml"
            elif path.endswith("json"):
                template_format = "json"
            else:
                template_format = "text"

            op["format"] = template_format

        if "replace" in op and op["replace"]:
            op["merge"] = False
            del op["replace"]
        elif "overwrite" in op and op["overwrite"]:
            op["overwrite"] = True
        elif "overwrite" in op and not op["overwrite"]:
            op["merge"] = True
            del op["overwrite"]

        db_mode = op.pop("mode", "exclusive")
        if write_diff and db_mode in ["dynamic", "ephemeral"]:
            ret["message"] = (
                "Write diff is not supported with dynamic/ephemeral configuration mode"
            )
            ret["out"] = False
            return ret

        config_params = {}
        if "ephemeral_instance" in op:
            config_params["ephemeral_instance"] = op.pop("ephemeral_instance")
        try:
            with Config(conn, mode=db_mode, **config_params) as cu:
                try:
                    cu.load(**op)
                except Exception as exception:  # pylint: disable=broad-except
                    ret["message"] = (
                        f'Could not load configuration due to : "{exception}"'
                    )
                    ret["format"] = op["format"]
                    ret["out"] = False
                    _restart_connection()
                    return ret

                config_diff = None
                if db_mode in ["dynamic", "ephemeral"]:
                    log.warning("diff is not supported for dynamic and ephemeral")
                else:
                    config_diff = cu.diff()
                    if config_diff is None:
                        ret["message"] = "Configuration already applied!"
                        ret["out"] = True
                        return ret

                commit_params = {}
                if "confirm" in op:
                    commit_params["confirm"] = op["confirm"]
                if "comment" in op:
                    commit_params["comment"] = op["comment"]

                # Assume commit_check succeeds and initialize variable check
                check = True
                if db_mode in ["dynamic", "ephemeral"]:
                    log.warning("commit check not supported for dynamic and ephemeral")
                else:
                    try:
                        check = cu.commit_check()
                    except Exception as exception:  # pylint: disable=broad-except
                        ret["message"] = (
                            'Commit check threw the following exception: "{}"'.format(
                                exception
                            )
                        )
                        ret["out"] = False
                        _restart_connection()
                        return ret

                if check and not test:
                    try:
                        cu.commit(**commit_params)
                        ret["message"] = "Successfully loaded and committed!"
                    except Exception as exception:  # pylint: disable=broad-except
                        ret["message"] = (
                            'Commit check successful but commit failed with "{}"'.format(
                                exception
                            )
                        )
                        ret["out"] = False
                        _restart_connection()
                        return ret

                elif not check:
                    try:
                        cu.rollback()
                        ret["message"] = (
                            "Loaded configuration but commit check failed, hence"
                            " rolling back configuration."
                        )
                    except Exception as exception:  # pylint: disable=broad-except
                        ret["message"] = (
                            "Loaded configuration but commit check failed, and"
                            ' exception occurred during rolling back configuration "{}"'.format(
                                exception
                            )
                        )
                        _restart_connection()

                    ret["out"] = False
                else:
                    try:
                        cu.rollback()
                        ret["message"] = (
                            "Commit check passed, but skipping commit for dry-run and"
                            " rolling back configuration."
                        )
                        ret["out"] = True
                    except Exception as exception:  # pylint: disable=broad-except
                        ret["message"] = (
                            "Commit check passed, but skipping commit for dry-run and"
                            ' while rolling back configuration exception occurred "{}"'.format(
                                exception
                            )
                        )
                        ret["out"] = False
                        _restart_connection()

                try:
                    if write_diff and config_diff is not None:
                        with salt.utils.files.fopen(write_diff, "w") as fp:
                            fp.write(salt.utils.stringutils.to_str(config_diff))
                except Exception as exception:  # pylint: disable=broad-except
                    ret["message"] = (
                        f"Could not write into diffs_file due to: '{exception}'"
                    )
                    ret["out"] = False

        except ValueError as ex:
            message = f"install_config failed due to: {ex}"
            log.error(message)
            ret["message"] = message
            ret["out"] = False
        except LockError as ex:
            log.error("Configuration database is locked")
            ret["message"] = ex.message
            ret["out"] = False
        except RpcTimeoutError as ex:
            message = f"install_config failed due to timeout error : {ex}"
            log.error(message)
            ret["message"] = message
            ret["out"] = False
        except Exception as exc:  # pylint: disable=broad-except
            ret["message"] = f"install_config failed due to exception: '{exc}'"
            ret["out"] = False

        return ret


@_timeout_decorator_cleankwargs
def zeroize():
    """
    Resets the device to default factory settings

    .. note::
        In case of non-root user, proxy_reconnect will not be able
        to re-connect to the device as zeroize will delete the local
        user's configuration.
        For more details on zeroize functionality, please refer
        https://www.juniper.net/documentation/en_US/junos/topics/reference/command-summary/request-system-zeroize.html

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.zeroize
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    try:
        conn.cli("request system zeroize")
        ret["message"] = "Completed zeroize and rebooted"
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f'Could not zeroize due to : "{exception}"'
        ret["out"] = False
        _restart_connection()

    return ret


@_timeout_decorator
def install_os(path=None, **kwargs):
    """
    Installs the given image on the device. After the installation is complete
    the device is rebooted, if reboot=True is given as a keyworded argument.

    path (required)
        Path where the image file is present on the proxy minion

    remote_path : /var/tmp
        If the value of path  is a file path on the local
        (Salt host's) filesystem, then the image is copied from the local
        filesystem to the :remote_path: directory on the target Junos
        device. The default is ``/var/tmp``. If the value of :path: or
        is a URL, then the value of :remote_path: is unused.

    dev_timeout : 1800
        The NETCONF RPC timeout (in seconds). This argument was added since most of
        the time the "package add" RPC takes a significant amount of time.
        So this :timeout: value will be used in the context of the SW installation
        process.  Defaults to 30 minutes (30*60=1800 seconds)

    timeout : 1800
        Alias to dev_timeout for backward compatibility

    reboot : False
        Whether to reboot after installation

    no_copy : False
        If ``True`` the software package will not be SCP’d to the device

    bool validate:
        When ``True`` this method will perform a config validation against
        the new image

    bool issu: False
        When ``True`` allows unified in-service software upgrade
        (ISSU) feature enables you to upgrade between two different Junos OS
        releases with no disruption on the control plane and with minimal
        disruption of traffic.

    bool nssu: False
        When ``True`` allows nonstop software upgrade (NSSU)
        enables you to upgrade the software running on a Juniper Networks
        EX Series Virtual Chassis or a Juniper Networks EX Series Ethernet
        Switch with redundant Routing Engines with a single command and
        minimal disruption to network traffic.

    bool all_re: True
        When True (default), executes the software install on all Routing Engines of the Junos
        device. When False, execute the software install only on the current Routing Engine.

        .. versionadded:: 3001

    .. note::
        Any additional keyword arguments specified are passed down to PyEZ sw.install() as is.
        Please refer to below URl for PyEZ sw.install() documentation:
        https://pyez.readthedocs.io/en/latest/jnpr.junos.utils.html#jnpr.junos.utils.sw.SW.install

    CLI Examples:

    .. code-block:: bash

        salt 'device_name' junos.install_os 'salt://images/junos_image.tgz' reboot=True
        salt 'device_name' junos.install_os 'salt://junos_16_1.tgz' dev_timeout=300
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True

    op = {}
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    # timeout value is not honoured by sw.install if not passed as argument
    # currently, timeout is set to be maximum of default 1800 and user passed timeout value
    # For info: https://github.com/Juniper/salt/issues/116
    dev_timeout = max(op.pop("dev_timeout", 0), op.pop("timeout", 0))
    timeout = max(1800, conn.timeout, dev_timeout)

    # Reboot should not be passed as a keyword argument to install(),
    # Please refer to https://github.com/Juniper/salt/issues/115 for more details
    reboot = op.pop("reboot", False)
    no_copy_ = op.get("no_copy", False)

    if path is None:
        ret["message"] = (
            "Please provide the salt path where the junos image is present."
        )
        ret["out"] = False
        return ret

    if reboot:
        #  flag reboot active, disables proxy_reconnect since it's probing
        # of connection interferes with the reboot, especially with a
        # package install (time taken to xfer package and install)
        __proxy__["junos.reboot_active"]()

    install_status = False
    if not no_copy_:
        with HandleFileCopy(path) as image_path:
            if image_path is None:
                ret["message"] = "Invalid path. Please provide a valid image path"
                ret["out"] = False
                __proxy__["junos.reboot_clear"]()
                return ret
            if salt.utils.platform.is_junos():
                # If its native minion running on Junos, pyez dont need to SCP file
                # hence setting no_copy as True, HandleFileCopy already copied file
                # from master to Junos
                tmp_absfile = image_path
                op["no_copy"] = True
                op["remote_path"] = os.path.dirname(tmp_absfile)
                image_path = os.path.basename(tmp_absfile)
            try:
                install_status, install_message = conn.sw.install(
                    image_path, progress=True, timeout=timeout, **op
                )
            except Exception as exception:  # pylint: disable=broad-except
                ret["message"] = f'Installation failed due to: "{exception}"'
                ret["out"] = False
                __proxy__["junos.reboot_clear"]()
                _restart_connection()
                return ret
    else:
        try:
            install_status, install_message = conn.sw.install(
                path, progress=True, timeout=timeout, **op
            )
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = f'Installation failed due to: "{exception}"'
            ret["out"] = False
            __proxy__["junos.reboot_clear"]()
            _restart_connection()
            return ret

    if install_status is True:
        ret["out"] = True
        ret["message"] = "Installed the os."
    else:
        ret["message"] = f"Installation failed. Reason: {install_message}"
        ret["out"] = False
        __proxy__["junos.reboot_clear"]()
        return ret

    # Handle reboot, after the install has finished
    if reboot is True:
        reboot_kwargs = {}
        if "vmhost" in op and op.get("vmhost") is True:
            reboot_kwargs["vmhost"] = True
        if "all_re" in op:
            reboot_kwargs["all_re"] = op.get("all_re")
        try:
            __proxy__["junos.reboot_active"]()
            conn.sw.reboot(**reboot_kwargs)
        except Exception as exception:  # pylint: disable=broad-except
            __proxy__["junos.reboot_clear"]()
            ret["message"] = (
                'Installation successful but reboot failed due to : "{}"'.format(
                    exception
                )
            )
            ret["out"] = False
            _restart_connection()
            return ret

        __proxy__["junos.reboot_clear"]()
        ret["out"] = True
        ret["message"] = "Successfully installed and rebooted!"

    return ret


@_timeout_decorator_cleankwargs
def file_copy(src, dest):
    """
    Copies the file from the local device to the junos device

    .. note::
        This function does not work on Juniper native minions

    src
        The source path where the file is kept.

    dest
        The destination path on the where the file will be copied

    .. versionadded:: 3001

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.file_copy /home/m2/info.txt info_copy.txt
    """
    if salt.utils.platform.is_junos():
        return {
            "success": False,
            "message": "This method is unsupported on the current operating system!",
        }

    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True

    with HandleFileCopy(src) as fp:
        if fp is None:
            ret["message"] = f"Invalid source file path {src}"
            ret["out"] = False
            return ret

        try:
            with SCP(conn, progress=True) as scp:
                scp.put(fp, dest)
            ret["message"] = f"Successfully copied file from {src} to {dest}"
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = f'Could not copy file : "{exception}"'
            ret["out"] = False

        return ret


@_timeout_decorator_cleankwargs
def lock():
    """
    Attempts an exclusive lock on the candidate configuration. This
    is a non-blocking call.

    .. note::
        When locking, it is important to remember to call
        :py:func:`junos.unlock <salt.modules.junos.unlock>` once finished. If
        locking during orchestration, remember to include a step in the
        orchestration job to unlock.

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.lock
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    try:
        conn.cu.lock()
        ret["message"] = "Successfully locked the configuration."
    except RpcTimeoutError as exception:
        ret["message"] = f'Could not gain lock due to : "{exception}"'
        ret["out"] = False
        _restart_connection()

    except LockError as exception:
        ret["message"] = f'Could not gain lock due to : "{exception}"'
        ret["out"] = False

    return ret


@_timeout_decorator_cleankwargs
def unlock():
    """
    Unlocks the candidate configuration.

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.unlock
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    try:
        conn.cu.unlock()
        ret["message"] = "Successfully unlocked the configuration."
    except RpcTimeoutError as exception:
        ret["message"] = 'Could not unlock configuration due to : "{}"'.format(
            exception
        )
        ret["out"] = False
        _restart_connection()

    except UnlockError as exception:
        ret["message"] = 'Could not unlock configuration due to : "{}"'.format(
            exception
        )
        ret["out"] = False

    return ret


@_timeout_decorator
def load(path=None, **kwargs):
    """
    Loads the configuration from the file provided onto the device.

    path (required)
        Path where the configuration/template file is present. If the file has
        a ``.conf`` extension, the content is treated as text format. If the
        file has a ``.xml`` extension, the content is treated as XML format. If
        the file has a ``.set`` extension, the content is treated as Junos OS
        ``set`` commands.

    overwrite : False
        Set to ``True`` if you want this file is to completely replace the
        configuration file. Sets action to override

        .. note:: This option cannot be used if **format** is "set".

    replace : False
        Specify whether the configuration file uses ``replace:`` statements. If
        ``True``, only those statements under the ``replace`` tag will be
        changed.

    merge : False
        If set to ``True`` will set the load-config action to merge.
        the default load-config action is 'replace' for xml/json/text config

    update : False
        Compare a complete loaded configuration against the candidate
        configuration. For each hierarchy level or configuration object that is
        different in the two configurations, the version in the loaded
        configuration replaces the version in the candidate configuration. When
        the configuration is later committed, only system processes that are
        affected by the changed configuration elements parse the new
        configuration. This action is supported from PyEZ 2.1.

    format
        Determines the format of the contents

    template_vars
      Variables to be passed into the template processing engine in addition to
      those present in pillar, the minion configuration, grains, etc.  You may
      reference these variables in your template like so:

      .. code-block:: jinja

          {{ template_vars["var_name"] }}

    CLI Examples:

    .. code-block:: bash

        salt 'device_name' junos.load 'salt://production/network/routers/config.set'

        salt 'device_name' junos.load 'salt://templates/replace_config.conf' replace=True

        salt 'device_name' junos.load 'salt://my_new_configuration.conf' overwrite=True

        salt 'device_name' junos.load 'salt://syslog_template.conf' template_vars='{"syslog_host": "10.180.222.7"}'
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True

    if path is None:
        ret["message"] = (
            "Please provide the salt path where the configuration is present"
        )
        ret["out"] = False
        return ret

    op = {}
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    kwargs = {}
    if "template_vars" in op:
        kwargs.update({"template_vars": op["template_vars"]})

    with HandleFileCopy(path, **kwargs) as template_cached_path:
        if template_cached_path is None:
            ret["message"] = "Invalid file path."
            ret["out"] = False
            return ret

        if os.path.getsize(template_cached_path) == 0:
            ret["message"] = "Template failed to render"
            ret["out"] = False
            return ret

        op["path"] = template_cached_path

        if "format" not in op:
            if path.endswith("set"):
                template_format = "set"
            elif path.endswith("xml"):
                template_format = "xml"
            elif path.endswith("json"):
                template_format = "json"
            else:
                template_format = "text"

            op["format"] = template_format

        # Currently, four config_actions are supported: overwrite, replace, update, merge
        # Allow only one config_action, providing multiple config_action value is not allowed
        actions = [
            item
            for item in ("overwrite", "replace", "update", "merge")
            if op.get(item, False)
        ]
        if len(list(actions)) > 1:
            ret["message"] = "Only one config_action is allowed. Provided: {}".format(
                actions
            )
            ret["out"] = False
            return ret

        if "replace" in op and op["replace"]:
            op["merge"] = False
            del op["replace"]
        elif "overwrite" in op and op["overwrite"]:
            op["overwrite"] = True
        elif "merge" in op and op["merge"]:
            op["merge"] = True
        elif "overwrite" in op and not op["overwrite"]:
            op["merge"] = True
            del op["overwrite"]

        try:
            conn.cu.load(**op)
            ret["message"] = "Successfully loaded the configuration."
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = 'Could not load configuration due to : "{}"'.format(
                exception
            )
            ret["format"] = op["format"]
            ret["out"] = False
            _restart_connection()
            return ret

        return ret


@_timeout_decorator_cleankwargs
def commit_check():
    """
    Perform a commit check on the configuration

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.commit_check
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    try:
        conn.cu.commit_check()
        ret["message"] = "Commit check succeeded."
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = f"Commit check failed with {exception}"
        ret["out"] = False
        _restart_connection()

    return ret


@_timeout_decorator_cleankwargs
def get_table(
    table,
    table_file,
    path=None,
    target=None,
    key=None,
    key_items=None,
    filters=None,
    table_args=None,
):
    """
    .. versionadded:: 3001

    Retrieve data from a Junos device using Tables/Views

    table (required)
        Name of PyEZ Table

    table_file (required)
        YAML file that has the table specified in table parameter

    path:
        Path of location of the YAML file.
        defaults to op directory in jnpr.junos.op

    target:
        if command need to run on FPC, can specify fpc target

    key:
        To overwrite key provided in YAML

    key_items:
        To select only given key items

    filters:
        To select only filter for the dictionary from columns

    table_args:
        key/value pair which should render Jinja template command
        or are passed as args to rpc call in op table

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.get_table RouteTable routes.yml
        salt 'device_name' junos.get_table EthPortTable ethport.yml table_args='{"interface_name": "ge-3/2/2"}'
        salt 'device_name' junos.get_table EthPortTable ethport.yml salt://tables
    """

    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    ret["hostname"] = conn._hostname
    ret["tablename"] = table
    get_kvargs = {}
    if target is not None:
        get_kvargs["target"] = target
    if key is not None:
        get_kvargs["key"] = key
    if key_items is not None:
        get_kvargs["key_items"] = key_items
    if filters is not None:
        get_kvargs["filters"] = filters
    if table_args is not None and isinstance(table_args, dict):
        get_kvargs["args"] = table_args
    pyez_tables_path = os.path.dirname(os.path.abspath(tables_dir.__file__))
    try:
        if path is not None:
            file_path = os.path.join(path, f"{table_file}")
        else:
            file_path = os.path.join(pyez_tables_path, f"{table_file}")

        with HandleFileCopy(file_path) as file_loc:
            if file_loc is None:
                ret["message"] = "Given table file {} cannot be located".format(
                    table_file
                )
                ret["out"] = False
                return ret
            try:
                with salt.utils.files.fopen(file_loc) as fp:
                    ret["table"] = yaml.load(
                        fp.read(), Loader=yamlordereddictloader.Loader
                    )
                    globals().update(FactoryLoader().load(ret["table"]))
            except OSError as err:
                ret["message"] = (
                    "Uncaught exception during YAML Load - please report: {}".format(
                        str(err)
                    )
                )
                ret["out"] = False
                return ret
            try:
                data = globals()[table](conn)
                data.get(**get_kvargs)
            except KeyError as err:
                ret["message"] = (
                    "Uncaught exception during get API call - please report: {}".format(
                        str(err)
                    )
                )
                ret["out"] = False
                return ret
            except ConnectClosedError:
                ret["message"] = (
                    "Got ConnectClosedError exception. Connection lost with {}".format(
                        conn
                    )
                )
                ret["out"] = False
                _restart_connection()
                return ret
            ret["reply"] = json.loads(data.to_json())
            if data.__class__.__bases__[0] in [OpTable, CfgTable]:
                # Sets key value if not present in YAML. To be used by returner
                if ret["table"][table].get("key") is None:
                    ret["table"][table]["key"] = data.ITEM_NAME_XPATH
                # If key is provided from salt state file.
                if key is not None:
                    ret["table"][table]["key"] = data.KEY
                if table_args is not None:
                    args = copy.copy(data.GET_ARGS)
                    args.update(table_args)
                    ret["table"][table]["args"] = args
            else:
                if target is not None:
                    ret["table"][table]["target"] = data.TARGET
                if key is not None:
                    ret["table"][table]["key"] = data.KEY
                if key_items is not None:
                    ret["table"][table]["key_items"] = data.KEY_ITEMS
                if table_args is not None:
                    args = copy.copy(data.CMD_ARGS)
                    args.update(table_args)
                    ret["table"][table]["args"] = args
                    ret["table"][table]["command"] = data.GET_CMD
    except ConnectClosedError:
        ret["message"] = (
            "Got ConnectClosedError exception. Connection lost with {}".format(
                str(conn)
            )
        )
        ret["out"] = False
        _restart_connection()
        return ret
    except Exception as err:  # pylint: disable=broad-except
        ret["message"] = f"Uncaught exception - please report: {str(err)}"
        ret["out"] = False
        _restart_connection()
        return ret
    return ret


def _recursive_dict(node):
    """
    Convert an lxml.etree node tree into a dict.
    """
    result = {}

    for element in node.iterchildren():
        # Remove namespace prefix
        key = element.tag.split("}")[1] if "}" in element.tag else element.tag

        # Process element as tree element if the inner XML contains non-whitespace content
        if element.text and element.text.strip():
            value = element.text
        else:
            value = _recursive_dict(element)
        if key in result:

            if type(result[key]) is list:
                result[key].append(value)
            else:
                tempvalue = result[key].copy()
                result[key] = [tempvalue, value]
        else:
            result[key] = value
    return result


@_timeout_decorator
def rpc_file_list(path, **kwargs):
    """
    Use the Junos RPC interface to get a list of files and return
    them as a structure dictionary.

    .. versionadded:: 3003

    CLI Example:

    .. code-block:: bash

        salt junos-router junos.rpc_file_list /var/local/salt/etc

        junos-router:
            files:
                directory:
                    directory-name:
                        /var/local/salt/etc
                    file-information:
                        |_
                          file-directory:
                              file-name:
                                  pki
                        |_
                          file-name:
                              proxy
                        |_
                          file-directory:
                              file-name:
                                  proxy.d
                total-file-blocks:
                    10
                total-files:
                    1
        success:
            True

    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    conn = __proxy__["junos.conn"]()
    if conn._conn is None:
        return False

    results = conn.rpc.file_list(path=path)

    ret = {}
    ret["files"] = _recursive_dict(results)
    ret["success"] = True

    return ret


def _strip_newlines(str):
    stripped = str.replace("\n", "")
    return stripped


def _make_source_list(dir):

    dir_list = []
    if not dir:
        return
    base = rpc_file_list(dir)["files"]["directory"]

    # No files in this directory
    if "file-information" not in base:
        if "directory_name" not in base:
            return None
        return [os.path.join(_strip_newlines(base.get("directory-name", None))) + "/"]

    if isinstance(base["file-information"], dict):
        dirname = os.path.join(
            dir, _strip_newlines(base["file-information"]["file-name"])
        )
        if "file-directory" in base["file-information"]:
            new_list = _make_source_list(os.path.join(dir, dirname))
            return new_list
        else:
            return [dirname]
    for entry in base["file-information"]:
        if "file-directory" in entry:
            new_list = _make_source_list(
                os.path.join(dir, _strip_newlines(entry["file-name"]))
            )
            if new_list:
                dir_list.extend(new_list)
        else:
            dir_list.append(os.path.join(dir, _strip_newlines(entry["file-name"])))

    return dir_list


@_timeout_decorator
def file_compare(file1, file2, **kwargs):  # pragma: no cover
    """
    Compare two files and return a dictionary indicating if they
    are different.

    Dictionary includes `success` key.  If False, one or more files do not
    exist or some other error occurred.

    Under the hood, this uses the junos CLI command `file compare files ...`

    .. note::
        This function only works on Juniper native minions

    .. versionadded:: 3003

    CLI Example:

    .. code-block:: bash

        salt junos-router junos.file_compare /var/tmp/backup1/cmt.script /var/tmp/backup2/cmt.script

        junos-router:
            identical:
                False
            success:
                True

    """
    if not salt.utils.platform.is_junos():
        return {
            "success": False,
            "message": "This method is unsupported on the current operating system!",
        }

    ret = {"message": "", "identical": False, "success": True}

    junos_cli = salt.utils.path.which("cli")
    if not junos_cli:
        return {"success": False, "message": "Cannot find Junos cli command"}

    cliret = __salt__["cmd.run"](f"{junos_cli} file compare files {file1} {file2} ")
    clilines = cliret.splitlines()

    for r in clilines:
        if r.strip() != "":
            if "No such file" in r:
                ret["identical"] = False
                ret["success"] = False
                return ret

            ret["identical"] = False
            ret["success"] = True
            return ret

    ret["identical"] = True
    ret["success"] = True
    return ret


@_timeout_decorator
def fsentry_exists(dir, **kwargs):  # pragma: no cover
    """
    Returns a dictionary indicating if `dir` refers to a file
    or a non-file (generally a directory) in the file system,
    or if there is no file by that name.

    .. note::
        This function only works on Juniper native minions

    .. versionadded:: 3003

    CLI Example:

    .. code-block:: bash

        salt junos-router junos.fsentry_exists /var/log

        junos-router:
            is_dir:
                True
            exists:
                True

    """
    if not salt.utils.platform.is_junos():
        return {
            "success": False,
            "message": "This method is unsupported on the current operating system!",
        }

    junos_cli = salt.utils.path.which("cli")
    if not junos_cli:
        return {"success": False, "message": "Cannot find Junos cli command"}

    ret = __salt__["cmd.run"](f"{junos_cli} file show {dir}")
    retlines = ret.splitlines()
    exists = True
    is_dir = False
    status = {"is_dir": False, "exists": True}
    for r in retlines:
        if "could not resolve" in r or "error: Could not connect" in r:
            status["is_dir"] = False
            status["exists"] = False
        if "is not a regular file" in r:
            status["is_dir"] = True
            status["exists"] = True

    return status


def _find_routing_engines():
    junos_cli = salt.utils.path.which("cli")
    if not junos_cli:
        return {"success": False, "message": "Cannot find Junos cli command"}

    re_check = __salt__["cmd.run"](f"{junos_cli} show chassis routing-engine")
    engine_present = True
    engine = {}

    # for l in re_check.splitlines():
    #     if 'error: Unrecognized command' in l:
    #         engine_present = False

    # if not engine_present:
    #     return {'success': False,
    #             'message': 'Device does not have multiple routing engines'}

    current_engine = None
    status = None
    for l in re_check.splitlines():
        if "Slot" in l:
            mat = re.search(".*(\\d+):.*", l)
            if mat:
                current_engine = "re" + str(mat.group(1)) + ":"
        if "Current state" in l:
            if "Master" in l:
                status = "Master"
            if "Disabled" in l:
                status = "Disabled"
            if "Backup" in l:
                status = "Backup"

        if current_engine and status:
            engine[current_engine] = status
            current_engine = None
            status = None

    if not engine:
        return {
            "success": False,
            "message": "Junos cli command returned no information",
        }

    engine["success"] = True
    return engine


@_timeout_decorator
def routing_engine(**kwargs):
    """
    Returns a dictionary containing the routing engines on the device and
    their status (Master, Disabled, Backup).

    Under the hood parses the result of `show chassis routing-engine`

    .. versionadded:: 3003

    CLI Example:

    .. code-block:: bash

        salt junos-router junos.routing_engine

        junos-router:
            backup:
              - re1:
            master:
              re0:
            success:
              True

    Returns `success: False` if the device does not appear to have multiple routing engines.

    """
    engine_status = _find_routing_engines()
    if not engine_status["success"]:
        return {"success": False}

    master = None
    backup = []
    for k, v in engine_status.items():
        if v == "Master":
            master = k
        if v == "Backup" or v == "Disabled":
            backup.append(k)

    if master:
        ret = {"master": master, "backup": backup, "success": True}
    else:
        ret = {"master": master, "backup": backup, "success": False}
    log.debug(ret)
    return ret


@_timeout_decorator
def dir_copy(source, dest, force=False, **kwargs):  # pragma: no cover
    """
    Copy a directory and recursively its contents from source to dest.

    .. note::
        This function only works on the Juniper native minion

    Parameters:

    source : Directory to use as the source

    dest : Directory in which to place the source and its contents.

    force : This function will not copy identical files unless `force` is `True`

    .. versionadded:: 3003

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.dir_copy /etc/salt/pki re1:/

    This will take the `pki` directory, its absolute path and copy it and its
    contents to routing engine 1 root directory. The result will be
    `re1:/etc/salt/pki/<files and dirs in /etc/salt/pki`.

    """
    if not salt.utils.platform.is_junos():
        return {
            "success": False,
            "message": "This method is unsupported on the current operating system!",
        }

    junos_cli = salt.utils.path.which("cli")
    if not junos_cli:
        return {"success": False, "message": "Cannot find Junos cli command"}

    ret = {}
    ret_messages = ""
    if not source.startswith("/"):
        ret["message"] = "Source directory must be a fully qualified path."
        ret["success"] = False
        return ret

    if not (dest.endswith(":") or dest.startswith("/")):
        ret["message"] = (
            "Destination must be a routing engine reference (e.g. re1:) or a fully"
            " qualified path."
        )
        ret["success"] = False
        return ret

    check_source = fsentry_exists(source)
    if not check_source["exists"]:
        ret["message"] = "Source does not exist"
        ret["success"] = False
        return ret

    if not check_source["is_dir"]:
        ret["message"] = "Source is not a directory."
        ret["success"] = False
        return ret

    filelist = _make_source_list(source)
    dirops = []
    for f in filelist:
        splitpath = os.path.split(f)[0]
        fullpath = "/"
        for component in splitpath.split("/"):
            fullpath = os.path.join(fullpath, component)
            if fullpath not in dirops:
                dirops.append(fullpath)

    for d in dirops:
        target = dest + d
        status = fsentry_exists(target)
        if not status["exists"]:
            ret = __salt__["cmd.run"](f"{junos_cli} file make-directory {target}")
            ret = ret_messages + ret
        else:
            ret_messages = ret_messages + "Directory " + target + " already exists.\n"
    for f in filelist:
        if not f.endswith("/"):
            target = dest + f
            comp_result = file_compare(f, target)

            if not comp_result["identical"] or force:
                ret = __salt__["cmd.run"](f"{junos_cli} file copy {f} {target}")
                ret = ret_messages + ret
            else:
                ret_messages = (
                    ret_messages
                    + f"Files {f} and {target} are identical, not copying.\n"
                )

    return ret_messages
