"""
Utils for the NAPALM modules and proxy.

.. seealso::

    - :mod:`NAPALM grains: select network devices based on their characteristics <salt.grains.napalm>`
    - :mod:`NET module: network basic features <salt.modules.napalm_network>`
    - :mod:`NTP operational and configuration management module <salt.modules.napalm_ntp>`
    - :mod:`BGP operational and configuration management module <salt.modules.napalm_bgp>`
    - :mod:`Routes details <salt.modules.napalm_route>`
    - :mod:`SNMP configuration module <salt.modules.napalm_snmp>`
    - :mod:`Users configuration management <salt.modules.napalm_users>`

.. versionadded:: 2017.7.0
"""


import copy
import importlib
import logging
import traceback
from functools import wraps

import salt.output
import salt.utils.args
import salt.utils.platform

try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=unused-import,no-name-in-module
    import napalm
    import napalm.base as napalm_base

    # pylint: enable=unused-import,no-name-in-module
    HAS_NAPALM = True
    try:
        NAPALM_MAJOR = int(napalm.__version__.split(".")[0])
    except AttributeError:
        NAPALM_MAJOR = 0
except ImportError:
    HAS_NAPALM = False

try:
    # try importing ConnectionClosedException
    # from napalm-base
    # this exception has been introduced only in version 0.24.0
    from napalm.base.exceptions import ConnectionClosedException

    HAS_CONN_CLOSED_EXC_CLASS = True
except ImportError:
    HAS_CONN_CLOSED_EXC_CLASS = False

log = logging.getLogger(__file__)


def is_proxy(opts):
    """
    Is this a NAPALM proxy?
    """
    return (
        salt.utils.platform.is_proxy()
        and opts.get("proxy", {}).get("proxytype") == "napalm"
    )


def is_always_alive(opts):
    """
    Is always alive required?
    """
    return opts.get("proxy", {}).get("always_alive", True)


def not_always_alive(opts):
    """
    Should this proxy be always alive?
    """
    return (is_proxy(opts) and not is_always_alive(opts)) or is_minion(opts)


def is_minion(opts):
    """
    Is this a NAPALM straight minion?
    """
    return not salt.utils.platform.is_proxy() and "napalm" in opts


def virtual(opts, virtualname, filename):
    """
    Returns the __virtual__.
    """
    if (HAS_NAPALM and NAPALM_MAJOR >= 2) and (is_proxy(opts) or is_minion(opts)):
        return virtualname
    else:
        return (
            False,
            '"{vname}"" {filename} cannot be loaded: '
            "NAPALM is not installed: ``pip install napalm``".format(
                vname=virtualname, filename="({filename})".format(filename=filename)
            ),
        )


def call(napalm_device, method, *args, **kwargs):
    """
    Calls arbitrary methods from the network driver instance.
    Please check the readthedocs_ page for the updated list of getters.

    .. _readthedocs: http://napalm.readthedocs.org/en/latest/support/index.html#getters-support-matrix

    method
        Specifies the name of the method to be called.

    *args
        Arguments.

    **kwargs
        More arguments.

    :return: A dictionary with three keys:

        * result (True/False): if the operation succeeded
        * out (object): returns the object as-is from the call
        * comment (string): provides more details in case the call failed
        * traceback (string): complete traceback in case of exception. \
        Please submit an issue including this traceback \
        on the `correct driver repo`_ and make sure to read the FAQ_

    .. _`correct driver repo`: https://github.com/napalm-automation/napalm/issues/new
    .. FAQ_: https://github.com/napalm-automation/napalm#faq

    Example:

    .. code-block:: python

        salt.utils.napalm.call(
            napalm_object,
            'cli',
            [
                'show version',
                'show chassis fan'
            ]
        )
    """
    result = False
    out = None
    opts = napalm_device.get("__opts__", {})
    retry = kwargs.pop("__retry", True)  # retry executing the task?
    force_reconnect = kwargs.get("force_reconnect", False)
    if force_reconnect:
        log.debug("Forced reconnection initiated")
        log.debug("The current opts (under the proxy key):")
        log.debug(opts["proxy"])
        opts["proxy"].update(**kwargs)
        log.debug("Updated to:")
        log.debug(opts["proxy"])
        napalm_device = get_device(opts)
    try:
        if not napalm_device.get("UP", False):
            raise Exception("not connected")
        # if connected will try to execute desired command
        kwargs_copy = {}
        kwargs_copy.update(kwargs)
        for karg, warg in kwargs_copy.items():
            # lets clear None arguments
            # to not be sent to NAPALM methods
            if warg is None:
                kwargs.pop(karg)
        out = getattr(napalm_device.get("DRIVER"), method)(*args, **kwargs)
        # calls the method with the specified parameters
        result = True
    except Exception as error:  # pylint: disable=broad-except
        # either not connected
        # either unable to execute the command
        hostname = napalm_device.get("HOSTNAME", "[unspecified hostname]")
        err_tb = (
            traceback.format_exc()
        )  # let's get the full traceback and display for debugging reasons.
        if isinstance(error, NotImplementedError):
            comment = (
                "{method} is not implemented for the NAPALM {driver} driver!".format(
                    method=method, driver=napalm_device.get("DRIVER_NAME")
                )
            )
        elif (
            retry
            and HAS_CONN_CLOSED_EXC_CLASS
            and isinstance(error, ConnectionClosedException)
        ):
            # Received disconection whilst executing the operation.
            # Instructed to retry (default behaviour)
            #   thus trying to re-establish the connection
            #   and re-execute the command
            #   if any of the operations (close, open, call) will rise again ConnectionClosedException
            #   it will fail loudly.
            kwargs["__retry"] = False  # do not attempt re-executing
            comment = "Disconnected from {device}. Trying to reconnect.".format(
                device=hostname
            )
            log.error(err_tb)
            log.error(comment)
            log.debug("Clearing the connection with %s", hostname)
            call(napalm_device, "close", __retry=False)  # safely close the connection
            # Make sure we don't leave any TCP connection open behind
            #   if we fail to close properly, we might not be able to access the
            log.debug("Re-opening the connection with %s", hostname)
            call(napalm_device, "open", __retry=False)
            log.debug("Connection re-opened with %s", hostname)
            log.debug("Re-executing %s", method)
            return call(napalm_device, method, *args, **kwargs)
            # If still not able to reconnect and execute the task,
            #   the proxy keepalive feature (if enabled) will attempt
            #   to reconnect.
            # If the device is using a SSH-based connection, the failure
            #   will also notify the paramiko transport and the `is_alive` flag
            #   is going to be set correctly.
            # More background: the network device may decide to disconnect,
            #   although the SSH session itself is alive and usable, the reason
            #   being the lack of activity on the CLI.
            #   Paramiko's keepalive doesn't help in this case, as the ServerAliveInterval
            #   are targeting the transport layer, whilst the device takes the decision
            #   when there isn't any activity on the CLI, thus at the application layer.
            #   Moreover, the disconnect is silent and paramiko's is_alive flag will
            #   continue to return True, although the connection is already unusable.
            #   For more info, see https://github.com/paramiko/paramiko/issues/813.
            #   But after a command fails, the `is_alive` flag becomes aware of these
            #   changes and will return False from there on. And this is how the
            #   Salt proxy keepalive helps: immediately after the first failure, it
            #   will know the state of the connection and will try reconnecting.
        else:
            comment = (
                'Cannot execute "{method}" on {device}{port} as {user}. Reason:'
                " {error}!".format(
                    device=napalm_device.get("HOSTNAME", "[unspecified hostname]"),
                    port=(
                        ":{port}".format(
                            port=napalm_device.get("OPTIONAL_ARGS", {}).get("port")
                        )
                        if napalm_device.get("OPTIONAL_ARGS", {}).get("port")
                        else ""
                    ),
                    user=napalm_device.get("USERNAME", ""),
                    method=method,
                    error=error,
                )
            )
        log.error(comment)
        log.error(err_tb)
        return {"out": {}, "result": False, "comment": comment, "traceback": err_tb}
    finally:
        if opts and not_always_alive(opts) and napalm_device.get("CLOSE", True):
            # either running in a not-always-alive proxy
            # either running in a regular minion
            # close the connection when the call is over
            # unless the CLOSE is explicitly set as False
            napalm_device["DRIVER"].close()
    return {"out": out, "result": result, "comment": ""}


def get_device_opts(opts, salt_obj=None):
    """
    Returns the options of the napalm device.
    :pram: opts
    :return: the network device opts
    """
    network_device = {}
    # by default, look in the proxy config details
    device_dict = opts.get("proxy", {}) if is_proxy(opts) else opts.get("napalm", {})
    if opts.get("proxy") or opts.get("napalm"):
        opts["multiprocessing"] = device_dict.get("multiprocessing", False)
        # Most NAPALM drivers are SSH-based, so multiprocessing should default to False.
        # But the user can be allows one to have a different value for the multiprocessing, which will
        #   override the opts.
    if not device_dict:
        # still not able to setup
        log.error(
            "Incorrect minion config. Please specify at least the napalm driver name!"
        )
    # either under the proxy hier, either under the napalm in the config file
    network_device["HOSTNAME"] = (
        device_dict.get("host")
        or device_dict.get("hostname")
        or device_dict.get("fqdn")
        or device_dict.get("ip")
    )
    network_device["USERNAME"] = device_dict.get("username") or device_dict.get("user")
    network_device["DRIVER_NAME"] = device_dict.get("driver") or device_dict.get("os")
    network_device["PASSWORD"] = (
        device_dict.get("passwd")
        or device_dict.get("password")
        or device_dict.get("pass")
        or ""
    )
    network_device["TIMEOUT"] = device_dict.get("timeout", 60)
    network_device["OPTIONAL_ARGS"] = device_dict.get("optional_args", {})
    network_device["ALWAYS_ALIVE"] = device_dict.get("always_alive", True)
    network_device["PROVIDER"] = device_dict.get("provider")
    network_device["UP"] = False
    # get driver object form NAPALM
    if "config_lock" not in network_device["OPTIONAL_ARGS"]:
        network_device["OPTIONAL_ARGS"]["config_lock"] = False
    if (
        network_device["ALWAYS_ALIVE"]
        and "keepalive" not in network_device["OPTIONAL_ARGS"]
    ):
        network_device["OPTIONAL_ARGS"]["keepalive"] = 5  # 5 seconds keepalive
    return network_device


def get_device(opts, salt_obj=None):
    """
    Initialise the connection with the network device through NAPALM.
    :param: opts
    :return: the network device object
    """
    log.debug("Setting up NAPALM connection")
    network_device = get_device_opts(opts, salt_obj=salt_obj)
    provider_lib = napalm_base
    if network_device.get("PROVIDER"):
        # In case the user requires a different provider library,
        #   other than napalm-base.
        # For example, if napalm-base does not satisfy the requirements
        #   and needs to be enahanced with more specific features,
        #   we may need to define a custom library on top of napalm-base
        #   with the constraint that it still needs to provide the
        #   `get_network_driver` function. However, even this can be
        #   extended later, if really needed.
        # Configuration example:
        #   provider: napalm_base_example
        try:
            provider_lib = importlib.import_module(network_device.get("PROVIDER"))
        except ImportError as ierr:
            log.error(
                "Unable to import %s", network_device.get("PROVIDER"), exc_info=True
            )
            log.error("Falling back to napalm-base")
    _driver_ = provider_lib.get_network_driver(network_device.get("DRIVER_NAME"))
    try:
        network_device["DRIVER"] = _driver_(
            network_device.get("HOSTNAME", ""),
            network_device.get("USERNAME", ""),
            network_device.get("PASSWORD", ""),
            timeout=network_device["TIMEOUT"],
            optional_args=network_device["OPTIONAL_ARGS"],
        )
        network_device.get("DRIVER").open()
        # no exception raised here, means connection established
        network_device["UP"] = True
    except napalm_base.exceptions.ConnectionException as error:
        base_err_msg = "Cannot connect to {hostname}{port} as {username}.".format(
            hostname=network_device.get("HOSTNAME", "[unspecified hostname]"),
            port=(
                ":{port}".format(
                    port=network_device.get("OPTIONAL_ARGS", {}).get("port")
                )
                if network_device.get("OPTIONAL_ARGS", {}).get("port")
                else ""
            ),
            username=network_device.get("USERNAME", ""),
        )
        log.error(base_err_msg)
        log.error("Please check error: %s", error)
        raise napalm_base.exceptions.ConnectionException(base_err_msg)
    return network_device


def proxy_napalm_wrap(func):
    """
    This decorator is used to make the execution module functions
    available outside a proxy minion, or when running inside a proxy
    minion. If we are running in a proxy, retrieve the connection details
    from the __proxy__ injected variable.  If we are not, then
    use the connection information from the opts.
    :param func:
    :return:
    """

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        wrapped_global_namespace = func.__globals__
        # get __opts__ and __proxy__ from func_globals
        proxy = wrapped_global_namespace.get("__proxy__")
        opts = copy.deepcopy(wrapped_global_namespace.get("__opts__"))
        # in any case, will inject the `napalm_device` global
        # the execution modules will make use of this variable from now on
        # previously they were accessing the device properties through the __proxy__ object
        always_alive = opts.get("proxy", {}).get("always_alive", True)
        # force_reconnect is a magic keyword arg that allows one to establish
        # a separate connection to the network device running under an always
        # alive Proxy Minion, using new credentials (overriding the ones
        # configured in the opts / pillar.
        force_reconnect = kwargs.get("force_reconnect", False)
        if force_reconnect:
            log.debug("Usage of reconnect force detected")
            log.debug("Opts before merging")
            log.debug(opts["proxy"])
            opts["proxy"].update(**kwargs)
            log.debug("Opts after merging")
            log.debug(opts["proxy"])
        if is_proxy(opts) and always_alive:
            # if it is running in a NAPALM Proxy and it's using the default
            # always alive behaviour, will get the cached copy of the network
            # device object which should preserve the connection.
            if force_reconnect:
                wrapped_global_namespace["napalm_device"] = get_device(opts)
            else:
                wrapped_global_namespace["napalm_device"] = proxy["napalm.get_device"]()
        elif is_proxy(opts) and not always_alive:
            # if still proxy, but the user does not want the SSH session always alive
            # get a new device instance
            # which establishes a new connection
            # which is closed just before the call() function defined above returns
            if "inherit_napalm_device" not in kwargs or (
                "inherit_napalm_device" in kwargs
                and not kwargs["inherit_napalm_device"]
            ):
                # try to open a new connection
                # but only if the function does not inherit the napalm driver
                # for configuration management this is very important,
                # in order to make sure we are editing the same session.
                try:
                    wrapped_global_namespace["napalm_device"] = get_device(opts)
                except napalm_base.exceptions.ConnectionException as nce:
                    log.error(nce)
                    return "{base_msg}. See log for details.".format(
                        base_msg=str(nce.msg)
                    )
            else:
                # in case the `inherit_napalm_device` is set
                # and it also has a non-empty value,
                # the global var `napalm_device` will be overridden.
                # this is extremely important for configuration-related features
                # as all actions must be issued within the same configuration session
                # otherwise we risk to open multiple sessions
                wrapped_global_namespace["napalm_device"] = kwargs[
                    "inherit_napalm_device"
                ]
        else:
            # if not a NAPLAM proxy
            # thus it is running on a regular minion, directly on the network device
            # or another flavour of Minion from where we can invoke arbitrary
            # NAPALM commands
            # get __salt__ from func_globals
            log.debug("Not running in a NAPALM Proxy Minion")
            _salt_obj = wrapped_global_namespace.get("__salt__")
            napalm_opts = _salt_obj["config.get"]("napalm", {})
            napalm_inventory = _salt_obj["config.get"]("napalm_inventory", {})
            log.debug("NAPALM opts found in the Minion config")
            log.debug(napalm_opts)
            clean_kwargs = salt.utils.args.clean_kwargs(**kwargs)
            napalm_opts.update(clean_kwargs)  # no need for deeper merge
            log.debug("Merging the found opts with the CLI args")
            log.debug(napalm_opts)
            host = (
                napalm_opts.get("host")
                or napalm_opts.get("hostname")
                or napalm_opts.get("fqdn")
                or napalm_opts.get("ip")
            )
            if (
                host
                and napalm_inventory
                and isinstance(napalm_inventory, dict)
                and host in napalm_inventory
            ):
                inventory_opts = napalm_inventory[host]
                log.debug("Found %s in the NAPALM inventory:", host)
                log.debug(inventory_opts)
                napalm_opts.update(inventory_opts)
                log.debug(
                    "Merging the config for %s with the details found in the napalm"
                    " inventory:",
                    host,
                )
                log.debug(napalm_opts)
            opts = copy.deepcopy(opts)  # make sure we don't override the original
            # opts, but just inject the CLI args from the kwargs to into the
            # object manipulated by ``get_device_opts`` to extract the
            # connection details, then use then to establish the connection.
            opts["napalm"] = napalm_opts
            if "inherit_napalm_device" not in kwargs or (
                "inherit_napalm_device" in kwargs
                and not kwargs["inherit_napalm_device"]
            ):
                # try to open a new connection
                # but only if the function does not inherit the napalm driver
                # for configuration management this is very important,
                # in order to make sure we are editing the same session.
                try:
                    wrapped_global_namespace["napalm_device"] = get_device(
                        opts, salt_obj=_salt_obj
                    )
                except napalm_base.exceptions.ConnectionException as nce:
                    log.error(nce)
                    return "{base_msg}. See log for details.".format(
                        base_msg=str(nce.msg)
                    )
            else:
                # in case the `inherit_napalm_device` is set
                # and it also has a non-empty value,
                # the global var `napalm_device` will be overridden.
                # this is extremely important for configuration-related features
                # as all actions must be issued within the same configuration session
                # otherwise we risk to open multiple sessions
                wrapped_global_namespace["napalm_device"] = kwargs[
                    "inherit_napalm_device"
                ]
        if not_always_alive(opts):
            # inject the __opts__ only when not always alive
            # otherwise, we don't want to overload the always-alive proxies
            wrapped_global_namespace["napalm_device"]["__opts__"] = opts
        ret = func(*args, **kwargs)
        if force_reconnect:
            log.debug("That was a forced reconnect, gracefully clearing up")
            device = wrapped_global_namespace["napalm_device"]
            closing = call(device, "close", __retry=False)
        return ret

    return func_wrapper


def default_ret(name):
    """
    Return the default dict of the state output.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    return ret


def loaded_ret(ret, loaded, test, debug, compliance_report=False, opts=None):
    """
    Return the final state output.
    ret
        The initial state output structure.
    loaded
        The loaded dictionary.
    """
    # Always get the comment
    changes = {}
    ret["comment"] = loaded["comment"]
    if "diff" in loaded:
        changes["diff"] = loaded["diff"]
    if "commit_id" in loaded:
        changes["commit_id"] = loaded["commit_id"]
    if "compliance_report" in loaded:
        if compliance_report:
            changes["compliance_report"] = loaded["compliance_report"]
    if debug and "loaded_config" in loaded:
        changes["loaded_config"] = loaded["loaded_config"]
    if changes.get("diff"):
        ret["comment"] = "{comment_base}\n\nConfiguration diff:\n\n{diff}".format(
            comment_base=ret["comment"], diff=changes["diff"]
        )
    if changes.get("loaded_config"):
        ret["comment"] = "{comment_base}\n\nLoaded config:\n\n{loaded_cfg}".format(
            comment_base=ret["comment"], loaded_cfg=changes["loaded_config"]
        )
    if changes.get("compliance_report"):
        ret["comment"] = "{comment_base}\n\nCompliance report:\n\n{compliance}".format(
            comment_base=ret["comment"],
            compliance=salt.output.string_format(
                changes["compliance_report"], "nested", opts=opts
            ),
        )
    if not loaded.get("result", False):
        # Failure of some sort
        return ret
    if not loaded.get("already_configured", True):
        # We're making changes
        if test:
            ret["result"] = None
            return ret
        # Not test, changes were applied
        ret.update(
            {
                "result": True,
                "changes": changes,
                "comment": "Configuration changed!\n{}".format(loaded["comment"]),
            }
        )
        return ret
    # No changes
    ret.update({"result": True, "changes": {}})
    return ret
