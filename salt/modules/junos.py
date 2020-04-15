# -*- coding: utf-8 -*-
"""
Module to interact with Junos devices.

:maturity: new
:dependencies: junos-eznc, jxmlease

.. note::

    Those who wish to use junos-eznc (PyEZ) version >= 2.1.0, must
    use the latest salt code from github until the next release.

Refer to :mod:`junos <salt.proxy.junos>` for information on connecting to junos proxy.

"""

# Import Python libraries
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
from functools import wraps

# Import Salt libs
import salt.utils.args
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
from salt.ext import six

try:
    from lxml import etree
except ImportError:
    from salt._compat import ElementTree as etree


# Juniper interface libraries
# https://github.com/Juniper/py-junos-eznc
try:
    # pylint: disable=W0611
    from jnpr.junos import Device
    from jnpr.junos.utils.config import Config
    from jnpr.junos.utils.sw import SW
    from jnpr.junos.utils.scp import SCP
    import jnpr.junos.utils
    import jnpr.junos.cfg
    import jxmlease

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
            "The junos module could not be loaded: "
            "junos-eznc or jxmlease or proxy could not be loaded.",
        )


def timeoutDecorator(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "dev_timeout" in kwargs:
            conn = __proxy__["junos.conn"]()
            restore_timeout = conn.timeout
            conn.timeout = kwargs.pop("dev_timeout", None)
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
        ret["message"] = 'Execution failed due to "{0}"'.format(exception)
        ret["out"] = False
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
        ret["message"] = 'Could not display facts due to "{0}"'.format(exception)
        ret["out"] = False
    return ret


@timeoutDecorator
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

        salt 'device' junos.rpc get_config /var/log/config.txt format=text filter='<configuration><system/></configuration>'
        salt 'device' junos.rpc get-interface-information /home/user/interface.xml interface_name='lo0' terse=True
        salt 'device' junos.rpc get-chassis-inventory
    """

    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True

    if cmd is None:
        ret["message"] = "Please provide the rpc to execute."
        ret["out"] = False
        return ret

    format_ = kwargs.pop("format", "xml")
    if not format_:
        format_ = "xml"

    op = dict()
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    elif "__pub_schedule" in kwargs:
        for key, value in six.iteritems(kwargs):
            if not key.startswith("__pub_"):
                op[key] = value
    else:
        op.update(kwargs)

    if cmd in ["get-config", "get_config"]:
        filter_reply = None
        if "filter" in op:
            filter_reply = etree.XML(op["filter"])
            del op["filter"]

        op.update({"format": format_})
        try:
            reply = getattr(conn.rpc, cmd.replace("-", "_"))(filter_reply, options=op)
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = 'RPC execution failed due to "{0}"'.format(exception)
            ret["out"] = False
            return ret
    else:
        if "filter" in op:
            log.warning('Filter ignored as it is only used with "get-config" rpc')
        try:
            reply = getattr(conn.rpc, cmd.replace("-", "_"))({"format": format_}, **op)
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = 'RPC execution failed due to "{0}"'.format(exception)
            ret["out"] = False
            return ret

    if format_ == "text":
        # Earlier it was ret['message']
        ret["rpc_reply"] = reply.text
    elif format_ == "json":
        # Earlier it was ret['message']
        ret["rpc_reply"] = reply
    else:
        # Earlier it was ret['message']
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


@timeoutDecorator
def set_hostname(hostname=None, **kwargs):
    """
    Set the device's hostname

    hostname
        The name to be set

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds)

    comment
        Provide a comment to the commit

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
    set_string = "set system host-name {0}".format(hostname)
    try:
        conn.cu.load(set_string, format="set")
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Could not load configuration due to error "{0}"'.format(
            exception
        )
        ret["out"] = False
        return ret

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Could not commit check due to error "{0}"'.format(exception)
        ret["out"] = False
        return ret

    if commit_ok:
        try:
            conn.cu.commit(**op)
            ret["message"] = "Successfully changed hostname."
            ret["out"] = True
        except Exception as exception:  # pylint: disable=broad-except
            ret["out"] = False
            ret[
                "message"
            ] = 'Successfully loaded host-name but commit failed with "{0}"'.format(
                exception
            )
            return ret
    else:
        ret["out"] = False
        ret["message"] = "Successfully loaded host-name but pre-commit check failed."
        conn.cu.rollback()
    return ret


@timeoutDecorator
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
        ret["message"] = 'Could not perform commit check due to "{0}"'.format(exception)
        ret["out"] = False
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
            ret[
                "message"
            ] = 'Commit check succeeded but actual commit failed with "{0}"'.format(
                exception
            )
    else:
        ret["out"] = False
        ret["message"] = "Pre-commit check failed."
        conn.cu.rollback()
    return ret


@timeoutDecorator
def rollback(**kwargs):
    """
    Roll back the last committed configuration changes and commit

    id : 0
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
    """
    id_ = kwargs.pop("id", 0)

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
        ret["message"] = 'Rollback failed due to "{0}"'.format(exception)
        ret["out"] = False
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
                "No diff between current configuration and \
                rollbacked configuration, so no diff file created"
            )

    try:
        commit_ok = conn.cu.commit_check()
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Could not commit check due to "{0}"'.format(exception)
        ret["out"] = False
        return ret

    if commit_ok:
        try:
            conn.cu.commit(**op)
            ret["out"] = True
        except Exception as exception:  # pylint: disable=broad-except
            ret["out"] = False
            ret[
                "message"
            ] = 'Rollback successful but commit failed with error "{0}"'.format(
                exception
            )
            return ret
    else:
        ret["message"] = "Rollback succesfull but pre-commit check failed."
        ret["out"] = False
    return ret


def diff(**kwargs):
    """
    Returns the difference between the candidate and the current configuration

    id : 0
        The rollback ID value (0-49)

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.diff 3
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    id_ = kwargs.pop("id", 0)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True
    try:
        ret["message"] = conn.cu.diff(rb_id=id_)
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Could not get diff with error "{0}"'.format(exception)
        ret["out"] = False

    return ret


@timeoutDecorator
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

    op["count"] = six.text_type(op.pop("count", 5))
    if "ttl" in op:
        op["ttl"] = six.text_type(op["ttl"])

    ret["out"] = True
    try:
        ret["message"] = jxmlease.parse(etree.tostring(conn.rpc.ping(**op)))
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Execution failed due to "{0}"'.format(exception)
        ret["out"] = False
    return ret


@timeoutDecorator
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
        salt 'device_name' junos.cli 'show version' dev_timeout=40
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
        ret["message"] = 'Execution failed due to "{0}"'.format(exception)
        ret["out"] = False
        return ret

    if format_ == "text":
        ret["message"] = result
    else:
        result = etree.tostring(result)
        ret["message"] = jxmlease.parse(result)

    if "dest" in op and op["dest"] is not None:
        with salt.utils.files.fopen(op["dest"], "w") as fp:
            fp.write(salt.utils.stringutils.to_str(result))

    ret["out"] = True
    return ret


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
        ret["message"] = 'Could not poweroff/reboot beacause "{0}"'.format(exception)
        ret["out"] = False
    return ret


@timeoutDecorator
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
        ``private``, ``dynamic``, ``batch``, ``exclusive``.

    dev_timeout : 30
        Set NETCONF RPC timeout. Can be used for commands which take a while to
        execute.

    overwrite : False
        Set to ``True`` if you want this file is to completely replace the
        configuration file.

    replace : False
        Specify whether the configuration file uses ``replace:`` statements. If
        ``True``, only those statements under the ``replace`` tag will be
        changed.

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
      stored on the proxy minion. To push the files to the master use
      :py:func:`cp.push <salt.modules.cp.push>`.

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
        ret[
            "message"
        ] = "Please provide the salt path where the configuration is present"
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
    template_vars = {}
    if "template_vars" in op:
        template_vars = op["template_vars"]

    template_cached_path = salt.utils.files.mkstemp()
    __salt__["cp.get_template"](path, template_cached_path, template_vars=template_vars)

    if not os.path.isfile(template_cached_path):
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
    with Config(conn, mode=db_mode) as cu:
        try:
            cu.load(**op)

        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = 'Could not load configuration due to : "{0}"'.format(
                exception
            )
            ret["format"] = op["format"]
            ret["out"] = False
            return ret

        finally:
            salt.utils.files.safe_rm(template_cached_path)

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

        try:
            check = cu.commit_check()
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = 'Commit check threw the following exception: "{0}"'.format(
                exception
            )

            ret["out"] = False
            return ret

        if check and not test:
            try:
                cu.commit(**commit_params)
                ret["message"] = "Successfully loaded and committed!"
            except Exception as exception:  # pylint: disable=broad-except
                ret[
                    "message"
                ] = 'Commit check successful but commit failed with "{0}"'.format(
                    exception
                )
                ret["out"] = False
                return ret
        elif not check:
            cu.rollback()
            ret[
                "message"
            ] = "Loaded configuration but commit check failed, hence rolling back configuration."
            ret["out"] = False
        else:
            cu.rollback()
            ret[
                "message"
            ] = "Commit check passed, but skipping commit for dry-run and rolling back configuration."
            ret["out"] = True

        try:
            if write_diff and config_diff is not None:
                with salt.utils.files.fopen(write_diff, "w") as fp:
                    fp.write(salt.utils.stringutils.to_str(config_diff))
        except Exception as exception:  # pylint: disable=broad-except
            ret["message"] = 'Could not write into diffs_file due to: "{0}"'.format(
                exception
            )
            ret["out"] = False

    return ret


def zeroize():
    """
    Resets the device to default factory settings

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
        ret["message"] = 'Could not zeroize due to : "{0}"'.format(exception)
        ret["out"] = False

    return ret


@timeoutDecorator
def install_os(path=None, **kwargs):
    """
    Installs the given image on the device. After the installation is complete\
     the device is rebooted,
    if reboot=True is given as a keyworded argument.

    path (required)
        Path where the image file is present on the proxy minion

    remote_path :
        If the value of path  is a file path on the local
        (Salt host's) filesystem, then the image is copied from the local
        filesystem to the :remote_path: directory on the target Junos
        device. The default is ``/var/tmp``. If the value of :path: or
        is a URL, then the value of :remote_path: is unused.

    dev_timeout : 30
        The NETCONF RPC timeout (in seconds). This argument was added since most of
        the time the "package add" RPC takes a significant amount of time.  The default
        RPC timeout is 30 seconds.  So this :timeout: value will be
        used in the context of the SW installation process.  Defaults to
        30 minutes (30*60=1800)

    reboot : False
        Whether to reboot after installation

    no_copy : False
        If ``True`` the software package will not be SCP’d to the device

    bool validate:
        When ``True`` this method will perform a config validation against
        the new image

    bool issu:
        When ``True`` allows unified in-service software upgrade
        (ISSU) feature enables you to upgrade between two different Junos OS
        releases with no disruption on the control plane and with minimal
        disruption of traffic.

    bool nssu:
        When ``True`` allows nonstop software upgrade (NSSU)
        enables you to upgrade the software running on a Juniper Networks
        EX Series Virtual Chassis or a Juniper Networks EX Series Ethernet
        Switch with redundant Routing Engines with a single command and
        minimal disruption to network traffic.

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

    no_copy_ = op.get("no_copy", False)

    if path is None:
        ret[
            "message"
        ] = "Please provide the salt path where the junos image is present."
        ret["out"] = False
        return ret

    if not no_copy_:
        image_cached_path = salt.utils.files.mkstemp()
        __salt__["cp.get_file"](path, image_cached_path)

        if not os.path.isfile(image_cached_path):
            ret["message"] = "Invalid image path."
            ret["out"] = False
            return ret

        if os.path.getsize(image_cached_path) == 0:
            ret["message"] = "Failed to copy image"
            ret["out"] = False
            return ret
        path = image_cached_path

    try:
        conn.sw.install(path, progress=True, **op)
        ret["message"] = "Installed the os."
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Installation failed due to: "{0}"'.format(exception)
        ret["out"] = False
        return ret
    finally:
        if not no_copy_:
            salt.utils.files.safe_rm(image_cached_path)

    if "reboot" in op and op["reboot"] is True:
        try:
            conn.sw.reboot()
        except Exception as exception:  # pylint: disable=broad-except
            ret[
                "message"
            ] = 'Installation successful but reboot failed due to : "{0}"'.format(
                exception
            )
            ret["out"] = False
            return ret
        ret["message"] = "Successfully installed and rebooted!"
    return ret


def file_copy(src=None, dest=None):
    """
    Copies the file from the local device to the junos device

    src
        The source path where the file is kept.

    dest
        The destination path on the where the file will be copied

    CLI Example:

    .. code-block:: bash

        salt 'device_name' junos.file_copy /home/m2/info.txt info_copy.txt
    """
    conn = __proxy__["junos.conn"]()
    ret = {}
    ret["out"] = True

    if src is None:
        ret["message"] = "Please provide the absolute path of the file to be copied."
        ret["out"] = False
        return ret
    if not os.path.isfile(src):
        ret["message"] = "Invalid source file path"
        ret["out"] = False
        return ret

    if dest is None:
        ret[
            "message"
        ] = "Please provide the absolute path of the destination where the file is to be copied."
        ret["out"] = False
        return ret

    try:
        with SCP(conn, progress=True) as scp:
            scp.put(src, dest)
        ret["message"] = "Successfully copied file from {0} to {1}".format(src, dest)
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Could not copy file : "{0}"'.format(exception)
        ret["out"] = False
    return ret


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
    except jnpr.junos.exception.LockError as exception:
        ret["message"] = 'Could not gain lock due to : "{0}"'.format(exception)
        ret["out"] = False

    return ret


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
    except jnpr.junos.exception.UnlockError as exception:
        ret["message"] = 'Could not unlock configuration due to : "{0}"'.format(
            exception
        )
        ret["out"] = False

    return ret


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
        configuration file.

    replace : False
        Specify whether the configuration file uses ``replace:`` statements. If
        ``True``, only those statements under the ``replace`` tag will be
        changed.

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
        ret[
            "message"
        ] = "Please provide the salt path where the configuration is present"
        ret["out"] = False
        return ret

    op = {}
    if "__pub_arg" in kwargs:
        if kwargs["__pub_arg"]:
            if isinstance(kwargs["__pub_arg"][-1], dict):
                op.update(kwargs["__pub_arg"][-1])
    else:
        op.update(kwargs)

    template_vars = {}
    if "template_vars" in op:
        template_vars = op["template_vars"]

    template_cached_path = salt.utils.files.mkstemp()
    __salt__["cp.get_template"](path, template_cached_path, template_vars=template_vars)

    if not os.path.isfile(template_cached_path):
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

    try:
        conn.cu.load(**op)
        ret["message"] = "Successfully loaded the configuration."
    except Exception as exception:  # pylint: disable=broad-except
        ret["message"] = 'Could not load configuration due to : "{0}"'.format(exception)
        ret["format"] = op["format"]
        ret["out"] = False
        return ret
    finally:
        salt.utils.files.safe_rm(template_cached_path)

    return ret


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
        ret["message"] = "Commit check failed with {0}".format(exception)
        ret["out"] = False

    return ret
