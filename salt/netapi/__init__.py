"""
Make api awesomeness
"""


import copy
import inspect
import logging
import os

import salt.auth
import salt.client
import salt.client.ssh.client
import salt.config
import salt.daemons.masterapi
import salt.exceptions
import salt.runner
import salt.syspaths
import salt.utils.args
import salt.utils.minions
import salt.wheel
from salt.defaults import DEFAULT_TARGET_DELIM

log = logging.getLogger(__name__)


def sorted_permissions(perms):
    """
    Return a sorted list of the passed in permissions, de-duplicating in the process
    """
    _str_perms = []
    _non_str_perms = []
    for entry in perms:
        if isinstance(entry, str):
            if entry in _str_perms:
                continue
            _str_perms.append(entry)
            continue
        if entry in _non_str_perms:
            continue
        _non_str_perms.append(entry)
    return sorted(_str_perms) + sorted(_non_str_perms, key=repr)


def sum_permissions(token, eauth):
    """
    Returns the sum of '*', user-specific and group specific permissions
    """
    perms = eauth.get(token["name"], [])
    perms.extend(eauth.get("*", []))

    if "groups" in token and token["groups"]:
        user_groups = set(token["groups"])
        eauth_groups = {i.rstrip("%") for i in eauth.keys() if i.endswith("%")}

        for group in user_groups & eauth_groups:
            perms.extend(eauth["{}%".format(group)])
    return perms


class NetapiClient:
    """
    Provide a uniform method of accessing the various client interfaces in Salt
    in the form of low-data data structures. For example:

    >>> client = NetapiClient(__opts__)
    >>> lowstate = {'client': 'local', 'tgt': '*', 'fun': 'test.ping', 'arg': ''}
    >>> client.run(lowstate)
    """

    def __init__(self, opts):
        self.opts = opts
        apiopts = copy.deepcopy(self.opts)
        apiopts["enable_ssh_minions"] = True
        apiopts["cachedir"] = os.path.join(opts["cachedir"], "saltapi")
        if not os.path.exists(apiopts["cachedir"]):
            os.makedirs(apiopts["cachedir"])
        self.resolver = salt.auth.Resolver(apiopts)
        self.loadauth = salt.auth.LoadAuth(apiopts)
        self.key = salt.daemons.masterapi.access_keys(apiopts)
        self.ckminions = salt.utils.minions.CkMinions(apiopts)

    def _is_master_running(self):
        """
        Perform a lightweight check to see if the master daemon is running

        Note, this will return an invalid success if the master crashed or was
        not shut down cleanly.
        """
        # Windows doesn't have IPC. Assume the master is running.
        # At worse, it will error 500.
        if salt.utils.platform.is_windows():
            return True

        if self.opts["transport"] == "tcp":
            ipc_file = "publish_pull.ipc"
        else:
            ipc_file = "workers.ipc"
        return os.path.exists(os.path.join(self.opts["sock_dir"], ipc_file))

    def _prep_auth_info(self, clear_load):
        sensitive_load_keys = []
        key = None
        if "token" in clear_load:
            auth_type = "token"
            err_name = "TokenAuthenticationError"
            sensitive_load_keys = ["token"]
            return auth_type, err_name, key, sensitive_load_keys
        elif "eauth" in clear_load:
            auth_type = "eauth"
            err_name = "EauthAuthenticationError"
            sensitive_load_keys = ["username", "password"]
            return auth_type, err_name, key, sensitive_load_keys
        raise salt.exceptions.EauthAuthenticationError(
            "No authentication credentials given"
        )

    def _authorize_ssh(self, low):
        auth_type, err_name, key, sensitive_load_keys = self._prep_auth_info(low)
        auth_check = self.loadauth.check_authentication(low, auth_type, key=key)
        auth_list = auth_check.get("auth_list", [])
        error = auth_check.get("error")
        if error:
            raise salt.exceptions.EauthAuthenticationError(error)
        delimiter = low.get("kwargs", {}).get("delimiter", DEFAULT_TARGET_DELIM)
        _res = self.ckminions.check_minions(
            low["tgt"], low.get("tgt_type", "glob"), delimiter
        )
        minions = _res.get("minions", list())
        missing = _res.get("missing", list())
        authorized = self.ckminions.auth_check(
            auth_list,
            low["fun"],
            low.get("arg", []),
            low["tgt"],
            low.get("tgt_type", "glob"),
            minions=minions,
        )
        if not authorized:
            raise salt.exceptions.EauthAuthenticationError(
                "Authorization error occurred."
            )

    def run(self, low):
        """
        Execute the specified function in the specified client by passing the
        lowstate
        """
        # Eauth currently requires a running daemon and commands run through
        # this method require eauth so perform a quick check to raise a
        # more meaningful error.
        if not self._is_master_running():
            raise salt.exceptions.SaltDaemonNotRunning("Salt Master is not available.")

        if low.get("client") not in CLIENTS:
            raise salt.exceptions.SaltInvocationError(
                "Invalid client specified: '{}'".format(low.get("client"))
            )

        if low.get("client") not in self.opts.get("netapi_enable_clients"):
            raise salt.exceptions.SaltInvocationError(
                "Client disabled: '{}'. Add to 'netapi_enable_clients' master config option to enable.".format(
                    low.get("client")
                )
            )

        if not ("token" in low or "eauth" in low):
            raise salt.exceptions.EauthAuthenticationError(
                "No authentication credentials given"
            )

        if low.get("raw_shell") and not self.opts.get("netapi_allow_raw_shell"):
            raise salt.exceptions.EauthAuthenticationError(
                "Raw shell option not allowed."
            )

        if low["client"] == "ssh":
            self._authorize_ssh(low)

        l_fun = getattr(self, low["client"])
        f_call = salt.utils.args.format_call(l_fun, low)
        return l_fun(*f_call.get("args", ()), **f_call.get("kwargs", {}))

    def local_async(self, *args, **kwargs):
        """
        Run :ref:`execution modules <all-salt.modules>` asynchronously

        Wraps :py:meth:`salt.client.LocalClient.run_job`.

        :return: job ID
        """
        with salt.client.get_local_client(mopts=self.opts) as client:
            return client.run_job(*args, **kwargs)

    def local(self, *args, **kwargs):
        """
        Run :ref:`execution modules <all-salt.modules>` synchronously

        See :py:meth:`salt.client.LocalClient.cmd` for all available
        parameters.

        Sends a command from the master to the targeted minions. This is the
        same interface that Salt's own CLI uses. Note the ``arg`` and ``kwarg``
        parameters are sent down to the minion(s) and the given function,
        ``fun``, is called with those parameters.

        :return: Returns the result from the execution module
        """
        with salt.client.get_local_client(mopts=self.opts) as client:
            return client.cmd(*args, **kwargs)

    def local_subset(self, *args, **kwargs):
        """
        Run :ref:`execution modules <all-salt.modules>` against subsets of minions

        .. versionadded:: 2016.3.0

        Wraps :py:meth:`salt.client.LocalClient.cmd_subset`
        """
        with salt.client.get_local_client(mopts=self.opts) as client:
            return client.cmd_subset(*args, **kwargs)

    def local_batch(self, *args, **kwargs):
        """
        Run :ref:`execution modules <all-salt.modules>` against batches of minions

        .. versionadded:: 0.8.4

        Wraps :py:meth:`salt.client.LocalClient.cmd_batch`

        :return: Returns the result from the exeuction module for each batch of
            returns
        """
        with salt.client.get_local_client(mopts=self.opts) as client:
            return client.cmd_batch(*args, **kwargs)

    def ssh(self, *args, **kwargs):
        """
        Run salt-ssh commands synchronously

        Wraps :py:meth:`salt.client.ssh.client.SSHClient.cmd_sync`.

        :return: Returns the result from the salt-ssh command
        """
        with salt.client.ssh.client.SSHClient(
            mopts=self.opts, disable_custom_roster=True
        ) as client:
            return client.cmd_sync(kwargs)

    def runner(self, fun, timeout=None, full_return=False, **kwargs):
        """
        Run `runner modules <all-salt.runners>` synchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_sync`.

        Note that runner functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the runner module
        """
        kwargs["fun"] = fun
        runner = salt.runner.RunnerClient(self.opts)
        return runner.cmd_sync(kwargs, timeout=timeout, full_return=full_return)

    def runner_async(self, fun, **kwargs):
        """
        Run `runner modules <all-salt.runners>` asynchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_async`.

        Note that runner functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: event data and a job ID for the executed function.
        """
        kwargs["fun"] = fun
        runner = salt.runner.RunnerClient(self.opts)
        return runner.cmd_async(kwargs)

    def wheel(self, fun, **kwargs):
        """
        Run :ref:`wheel modules <all-salt.wheel>` synchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        Note that wheel functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the wheel module
        """
        kwargs["fun"] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.cmd_sync(kwargs)

    def wheel_async(self, fun, **kwargs):
        """
        Run :ref:`wheel modules <all-salt.wheel>` asynchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        Note that wheel functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the wheel module
        """
        kwargs["fun"] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.cmd_async(kwargs)


CLIENTS = [
    name
    for name, _ in inspect.getmembers(NetapiClient, predicate=None)
    if not (name == "run" or name.startswith("_"))
]
