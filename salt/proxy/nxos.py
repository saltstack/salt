r"""
Proxy Minion for Cisco NX-OS Switches

.. versionadded:: 2016.11.0

The Cisco NX-OS Proxy Minion is supported on NX-OS devices for the following connection types:
1) Connection Type SSH
2) Connection Type NX-API (If Supported By The Device and Image Version).

:maturity:   new
:platform:   nxos

SSH uses the built in SSHConnection module in :mod:`salt.utils.vt_helper <salt.utils.vt_helper>`

To configure the proxy minion for ssh:

.. code-block:: yaml

    proxy:
      proxytype: nxos
      connection: ssh
      host: 192.168.187.100
      username: admin
      password: admin
      prompt_name: nxos-switch
      ssh_args: '-o PubkeyAuthentication=no'
      key_accept: True

To configure the proxy minion for nxapi:

.. code-block:: yaml

    proxy:
      proxytype: nxos
      connection: nxapi
      host: 192.168.187.100
      username: admin
      password: admin
      transport: http
      port: 80
      verify: False
      save_config: False

proxytype:
    (REQUIRED) Use this proxy minion `nxos`

connection:
    (REQUIRED) connection transport type.
    Choices: `ssh, nxapi`
    Default: `ssh`

host:
    (REQUIRED) login ip address or dns hostname.

username:
    (REQUIRED) login username.

password:
    (REQUIRED) login password.

save_config:
    If True, 'copy running-config starting-config' is issues for every
    configuration command.
    If False, Running config is not saved to startup config
    Default: True

    The recommended approach is to use the `save_running_config` function
    instead of this option to improve performance.  The default behavior
    controlled by this option is preserved for backwards compatibility.

Connection SSH Args:

    prompt_name:
        (REQUIRED when `connection` is `ssh`)
        (REQUIRED, this or `prompt_regex` below, but not both)
        The name in the prompt on the switch.  Recommended to use your
        device's hostname.

    prompt_regex:
        (REQUIRED when `connection` is `ssh`)
        (REQUIRED, this or `prompt_name` above, but not both)
        A regular expression that matches the prompt on the switch
        and any other possible prompt at which you need the proxy minion
        to continue sending input.  This feature was specifically developed
        for situations where the switch may ask for confirmation.  `prompt_name`
        above would not match these, and so the session would timeout.

        Example:

        .. code-block:: yaml

            nxos-switch#.*|\(y\/n\)\?.*

        This should match

        .. code-block:: shell

            nxos-switch#

        or

        .. code-block:: shell

            Flash complete.  Reboot this switch (y/n)? [n]


        If neither `prompt_name` nor `prompt_regex` is specified the prompt will be
        defaulted to

        .. code-block:: shell

            .+#$

        which should match any number of characters followed by a `#` at the end
        of the line.  This may be far too liberal for most installations.

    ssh_args:
        Extra optional arguments used for connecting to switch.

    key_accept:
        Whether or not to accept the host key of the switch on initial login.
        Default: `False`

Connection NXAPI Args:

    transport:
        (REQUIRED) when `connection` is `nxapi`.
        Choices: `http, https`
        Default: `https`

    port:
        (REQUIRED) when `connection` is `nxapi`.
        Default: `80`

    verify:
        (REQUIRED) when `connection` is `nxapi`.
        Either a boolean, in which case it controls whether we verify the NX-API
        TLS certificate, or a string, in which case it must be a path to a CA bundle
        to use.
        Default: `True`

        When there is no certificate configuration on the device and this option is
        set as ``True`` (default), the commands will fail with the following error:
        ``SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:581)``.
        In this case, you either need to configure a proper certificate on the
        device (*recommended*), or bypass the checks setting this argument as ``False``
        with all the security risks considered.

        Check https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus3000/sw/programmability/6_x/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide_chapter_01.html
        to see how to properly configure the certificate.


The functions from the proxy minion can be run from the salt commandline using
the :mod:`salt.modules.nxos<salt.modules.nxos>` execution module.

.. note:
    If `multiprocessing: True` is set for the proxy minion config, each forked
    worker will open up a new connection to the Cisco NX OS Switch.  If you
    only want one consistent connection used for everything, use
    `multiprocessing: False`

"""

import copy
import logging
import multiprocessing
import re

import salt.utils.nxos
from salt.exceptions import CommandExecutionError, NxosCliError
from salt.utils.args import clean_kwargs
from salt.utils.vt import TerminalException
from salt.utils.vt_helper import SSHConnection

log = logging.getLogger(__file__)

__proxyenabled__ = ["nxos"]
__virtualname__ = "nxos"

# Globals used to maintain state for ssh and nxapi proxy minions
DEVICE_DETAILS = {"grains_cache": {}}
CONNECTION = "ssh"


def __virtual__():
    """
    Only return if all the modules are available
    """
    log.info("nxos proxy __virtual__() called...")

    return __virtualname__


# -----------------------------------------------------------------------------
# Device Connection Connection Agnostic Functions
# -----------------------------------------------------------------------------
def init(opts=None):
    """
    Required.
    Initialize device connection using ssh or nxapi connection type.
    """
    global CONNECTION
    if __opts__.get("proxy").get("connection") is not None:
        CONNECTION = __opts__.get("proxy").get("connection")

    if CONNECTION == "ssh":
        log.info("NXOS PROXY: Initialize ssh proxy connection")
        return _init_ssh(opts)
    elif CONNECTION == "nxapi":
        log.info("NXOS PROXY: Initialize nxapi proxy connection")
        return _init_nxapi(opts)
    else:
        log.error("Unknown Connection Type: %s", CONNECTION)
        return False


def initialized():
    """
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether the
    init() function has been called.
    """
    if CONNECTION == "ssh":
        return _initialized_ssh()
    elif CONNECTION == "nxapi":
        return _initialized_nxapi()


def ping():
    """
    Helper function for nxos execution module functions that need to
    ping the nxos device using the proxy minion.
    """
    if CONNECTION == "ssh":
        return _ping_ssh()
    elif CONNECTION == "nxapi":
        return _ping_nxapi()


def grains():
    """
    Helper function for nxos execution module functions that need to
    retrieve nxos grains using the proxy minion.
    """
    if not DEVICE_DETAILS["grains_cache"]:
        data = sendline("show version")
        if CONNECTION == "nxapi":
            data = data[0]
        ret = salt.utils.nxos.system_info(data)
        log.debug("System Info: %s", ret)
        DEVICE_DETAILS["grains_cache"].update(ret["nxos"])
    return {"nxos": DEVICE_DETAILS["grains_cache"]}


def grains_refresh():
    """
    Helper function for nxos execution module functions that need to
    refresh nxos grains using the proxy minion.
    """
    DEVICE_DETAILS["grains_cache"] = {}
    return grains()


def shutdown():
    """
    Not supported.  Only used as a place holder to satisfy shutdown function
    requirement.
    """
    if CONNECTION == "ssh":
        return _shutdown_ssh()
    elif CONNECTION == "nxapi":
        return _shutdown_nxapi()


def sendline(commands, method="cli_show_ascii", **kwargs):
    """
    Helper function for nxos execution module functions that need to
    send commands to an nxos device using the proxy minion.
    """
    try:
        if CONNECTION == "ssh":
            result = _sendline_ssh(commands, **kwargs)
        elif CONNECTION == "nxapi":
            result = _nxapi_request(commands, method, **kwargs)
    except (TerminalException, NxosCliError) as e:
        log.error(e)
        raise
    return result


def proxy_config(commands, save_config=None):
    """
    Helper function for nxos execution module functions that need to
    configure an nxos device using the proxy minion.
    """
    COPY_RS = "copy running-config startup-config"

    if save_config is None:
        save_config = DEVICE_DETAILS.get("save_config", True)
    if not isinstance(commands, list):
        commands = [commands]
    try:
        if CONNECTION == "ssh":
            _sendline_ssh("config terminal")
            prev_cmds = []
            for cmd in commands:
                prev_cmds.append(cmd)
                ret = _sendline_ssh(cmd)
            if save_config:
                _sendline_ssh(COPY_RS)
            if ret:
                log.error(prev_cmds)
        elif CONNECTION == "nxapi":
            ret = _nxapi_request(commands)
            if save_config:
                _nxapi_request(COPY_RS)
            for each in ret:
                if "Failure" in each:
                    log.error(each)
    except CommandExecutionError as e:
        log.error(e)
        raise
    return [commands, ret]


# -----------------------------------------------------------------------------
# SSH Transport Functions
# -----------------------------------------------------------------------------
def _init_ssh(opts=None):
    """
    Open a connection to the NX-OS switch over SSH.
    """
    if opts is None:
        opts = __opts__
    try:
        this_prompt = None
        if "prompt_regex" in opts["proxy"]:
            this_prompt = opts["proxy"]["prompt_regex"]
        elif "prompt_name" in opts["proxy"]:
            this_prompt = "{}.*#".format(opts["proxy"]["prompt_name"])
        else:
            log.warning("nxos proxy configuration does not specify a prompt match.")
            this_prompt = ".+#$"

        DEVICE_DETAILS[_worker_name()] = SSHConnection(
            host=opts["proxy"]["host"],
            username=opts["proxy"]["username"],
            password=opts["proxy"]["password"],
            key_accept=opts["proxy"].get("key_accept", False),
            ssh_args=opts["proxy"].get("ssh_args", ""),
            prompt=this_prompt,
        )
        out, err = DEVICE_DETAILS[_worker_name()].sendline("terminal length 0")
        log.info("SSH session establised for process %s", _worker_name())
    except Exception as ex:  # pylint: disable=broad-except
        log.error("Unable to connect to %s", opts["proxy"]["host"])
        log.error("Please check the following:\n")
        log.error(
            '-- Verify that "feature ssh" is enabled on your NX-OS device: %s',
            opts["proxy"]["host"],
        )
        log.error("-- Exception Generated: %s", ex)
        log.error(ex)
        raise
    DEVICE_DETAILS["initialized"] = True
    DEVICE_DETAILS["save_config"] = opts["proxy"].get("save_config", True)


def _initialized_ssh():
    return DEVICE_DETAILS.get("initialized", False)


def _ping_ssh():
    if _worker_name() not in DEVICE_DETAILS:
        try:
            _init_ssh()
        except Exception:  # pylint: disable=broad-except
            return False
    try:
        return DEVICE_DETAILS[_worker_name()].conn.isalive()
    except TerminalException as e:
        log.error(e)
        return False


def _shutdown_ssh():
    return "Shutdown of ssh proxy minion is not supported"


def _sendline_ssh(commands, timeout=None, **kwargs):
    if isinstance(commands, str):
        commands = [commands]
    command = " ; ".join(commands)
    if _ping_ssh() is False:
        _init_ssh()
    out, err = DEVICE_DETAILS[_worker_name()].sendline(command)
    _, out = out.split("\n", 1)
    out, _, _ = out.rpartition("\n")
    kwargs = clean_kwargs(**kwargs)
    _parse_output_for_errors(out, command, **kwargs)
    return out


def _parse_output_for_errors(data, command, error_pattern=None):
    """
    Helper method to parse command output for error information
    """
    if re.search("% Invalid", data):
        raise CommandExecutionError(
            {
                "rejected_input": command,
                "message": "CLI excution error",
                "code": "400",
                "cli_error": data.lstrip(),
            }
        )
    if error_pattern:
        if isinstance(error_pattern, str):
            error_pattern = [error_pattern]
        for re_line in error_pattern:
            if re.search(re_line, data):
                raise CommandExecutionError(
                    {
                        "rejected_input": command,
                        "message": "CLI excution error",
                        "code": "400",
                        "cli_error": data.lstrip(),
                    }
                )


def _worker_name():
    return multiprocessing.current_process().name


# -----------------------------------------------------------------------------
# NX-API Transport Functions
# -----------------------------------------------------------------------------
def _init_nxapi(opts):
    """
    Open a connection to the NX-OS switch over NX-API.

    As the communication is HTTP(S) based, there is no connection to maintain,
    however, in order to test the connectivity and make sure we are able to
    bring up this Minion, we are executing a very simple command (``show clock``)
    which doesn't come with much overhead and it's sufficient to confirm we are
    indeed able to connect to the NX-API endpoint as configured.
    """
    proxy_dict = opts.get("proxy", {})
    conn_args = copy.deepcopy(proxy_dict)
    conn_args.pop("proxytype", None)
    try:
        rpc_reply = __utils__["nxos.nxapi_request"]("show clock", **conn_args)
        # Execute a very simple command to confirm we are able to connect properly
        DEVICE_DETAILS["conn_args"] = conn_args
        DEVICE_DETAILS["initialized"] = True
        DEVICE_DETAILS["up"] = True
        DEVICE_DETAILS["save_config"] = opts["proxy"].get("save_config", True)
    except Exception as ex:
        log.error("Unable to connect to %s", conn_args["host"])
        log.error("Please check the following:\n")
        log.error(
            '-- Verify that "feature nxapi" is enabled on your NX-OS device: %s',
            conn_args["host"],
        )
        log.error(
            "-- Verify that nxapi settings on the NX-OS device and proxy minion config"
            " file match"
        )
        log.error("-- Exception Generated: %s", ex)
        raise
    log.info("nxapi DEVICE_DETAILS info: %s", DEVICE_DETAILS)
    return True


def _initialized_nxapi():
    return DEVICE_DETAILS.get("initialized", False)


def _ping_nxapi():
    return DEVICE_DETAILS.get("up", False)


def _shutdown_nxapi():
    return "Shutdown of nxapi proxy minion is not supported"


def _nxapi_request(commands, method="cli_conf", **kwargs):
    """
    Executes an nxapi_request request over NX-API.

    commands
        The exec or config commands to be sent.

    method: ``cli_show``
        ``cli_show_ascii``: Return raw test or unstructured output.
        ``cli_show``: Return structured output.
        ``cli_conf``: Send configuration commands to the device.
        Defaults to ``cli_conf``.
    """
    if CONNECTION == "ssh":
        return "_nxapi_request is not available for ssh proxy"
    conn_args = DEVICE_DETAILS["conn_args"]
    conn_args.update(kwargs)
    data = __utils__["nxos.nxapi_request"](commands, method=method, **conn_args)
    return data
