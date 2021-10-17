import copy
import logging
import os
import random

import salt.config
import salt.syspaths
import salt.utils.args
from salt.exceptions import SaltClientError

log = logging.getLogger(__name__)


class SSHClient:
    """
    Create a client object for executing routines via the salt-ssh backend

    .. versionadded:: 2015.5.0
    """

    def __init__(
        self,
        c_path=os.path.join(salt.syspaths.CONFIG_DIR, "master"),
        mopts=None,
        disable_custom_roster=False,
    ):
        if mopts:
            self.opts = mopts
        else:
            if os.path.isdir(c_path):
                log.warning(
                    "%s expects a file path not a directory path(%s) to "
                    "its 'c_path' keyword argument",
                    self.__class__.__name__,
                    c_path,
                )
            self.opts = salt.config.client_config(c_path)

        # Salt API should never offer a custom roster!
        self.opts["__disable_custom_roster"] = disable_custom_roster

    def sanitize_kwargs(self, kwargs):
        roster_vals = [
            ("host", str),
            ("ssh_user", str),
            ("ssh_passwd", str),
            ("ssh_port", int),
            ("ssh_sudo", bool),
            ("ssh_sudo_user", str),
            ("ssh_priv", str),
            ("ssh_priv_passwd", str),
            ("ssh_identities_only", bool),
            ("ssh_remote_port_forwards", str),
            ("ssh_options", list),
            ("ssh_max_procs", int),
            ("ssh_askpass", bool),
            ("ssh_key_deploy", bool),
            ("ssh_update_roster", bool),
            ("ssh_scan_ports", str),
            ("ssh_scan_timeout", int),
            ("ssh_timeout", int),
            ("ssh_log_file", str),
            ("raw_shell", bool),
            ("refresh_cache", bool),
            ("roster", str),
            ("roster_file", str),
            ("rosters", list),
            ("ignore_host_keys", bool),
            ("raw_shell", bool),
            ("extra_filerefs", str),
            ("min_extra_mods", str),
            ("thin_extra_mods", str),
            ("verbose", bool),
            ("static", bool),
            ("ssh_wipe", bool),
            ("rand_thin_dir", bool),
            ("regen_thin", bool),
            ("ssh_run_pre_flight", bool),
            ("no_host_keys", bool),
            ("saltfile", str),
        ]
        sane_kwargs = {}
        for name, kind in roster_vals:
            if name not in kwargs:
                continue
            try:
                val = kind(kwargs[name])
            except ValueError:
                log.warning("Unable to cast kwarg %s", name)
                continue
            if kind is bool or kind is int:
                sane_kwargs[name] = val
            elif kind is str:
                if val.find("ProxyCommand") != -1:
                    log.warning("Filter unsafe value for kwarg %s", name)
                    continue
                sane_kwargs[name] = val
            elif kind is list:
                sane_val = []
                for item in val:
                    # This assumes the values are strings
                    if item.find("ProxyCommand") != -1:
                        log.warning("Filter unsafe value for kwarg %s", name)
                        continue
                    sane_val.append(item)
                sane_kwargs[name] = sane_val
        return sane_kwargs

    def _prep_ssh(
        self, tgt, fun, arg=(), timeout=None, tgt_type="glob", kwarg=None, **kwargs
    ):
        """
        Prepare the arguments
        """
        kwargs = self.sanitize_kwargs(kwargs)
        opts = copy.deepcopy(self.opts)
        opts.update(kwargs)
        if timeout:
            opts["timeout"] = timeout
        arg = salt.utils.args.condition_input(arg, kwarg)
        opts["argv"] = [fun] + arg
        opts["selected_target_option"] = tgt_type
        opts["tgt"] = tgt
        opts["arg"] = arg
        return salt.client.ssh.SSH(opts)

    def cmd_iter(
        self,
        tgt,
        fun,
        arg=(),
        timeout=None,
        tgt_type="glob",
        ret="",
        kwarg=None,
        **kwargs
    ):
        """
        Execute a single command via the salt-ssh subsystem and return a
        generator

        .. versionadded:: 2015.5.0
        """
        ssh = self._prep_ssh(tgt, fun, arg, timeout, tgt_type, kwarg, **kwargs)
        yield from ssh.run_iter(jid=kwargs.get("jid", None))

    def cmd(
        self, tgt, fun, arg=(), timeout=None, tgt_type="glob", kwarg=None, **kwargs
    ):
        """
        Execute a single command via the salt-ssh subsystem and return all
        routines at once

        .. versionadded:: 2015.5.0
        """
        ssh = self._prep_ssh(tgt, fun, arg, timeout, tgt_type, kwarg, **kwargs)
        final = {}
        for ret in ssh.run_iter(jid=kwargs.get("jid", None)):
            final.update(ret)
        return final

    def cmd_sync(self, low):
        """
        Execute a salt-ssh call synchronously.

        .. versionadded:: 2015.5.0

        WARNING: Eauth is **NOT** respected

        .. code-block:: python

            client.cmd_sync({
                'tgt': 'silver',
                'fun': 'test.ping',
                'arg': (),
                'tgt_type'='glob',
                'kwarg'={}
                })
            {'silver': {'fun_args': [], 'jid': '20141202152721523072', 'return': True, 'retcode': 0, 'success': True, 'fun': 'test.ping', 'id': 'silver'}}
        """

        kwargs = copy.deepcopy(low)

        for ignore in ["tgt", "fun", "arg", "timeout", "tgt_type", "kwarg"]:
            if ignore in kwargs:
                del kwargs[ignore]

        return self.cmd(
            low["tgt"],
            low["fun"],
            low.get("arg", []),
            low.get("timeout"),
            low.get("tgt_type"),
            low.get("kwarg"),
            **kwargs
        )

    def cmd_async(self, low, timeout=None):
        """
        Execute aa salt-ssh asynchronously

        WARNING: Eauth is **NOT** respected

        .. code-block:: python

            client.cmd_sync({
                'tgt': 'silver',
                'fun': 'test.ping',
                'arg': (),
                'tgt_type'='glob',
                'kwarg'={}
                })
            {'silver': {'fun_args': [], 'jid': '20141202152721523072', 'return': True, 'retcode': 0, 'success': True, 'fun': 'test.ping', 'id': 'silver'}}
        """
        # TODO Not implemented
        raise SaltClientError

    def cmd_subset(
        self,
        tgt,
        fun,
        arg=(),
        timeout=None,
        tgt_type="glob",
        ret="",
        kwarg=None,
        subset=3,
        **kwargs
    ):
        """
        Execute a command on a random subset of the targeted systems

        The function signature is the same as :py:meth:`cmd` with the
        following exceptions.

        :param subset: The number of systems to execute on

        .. code-block:: python

            >>> import salt.client.ssh.client
            >>> sshclient= salt.client.ssh.client.SSHClient()
            >>> sshclient.cmd_subset('*', 'test.ping', subset=1)
            {'jerry': True}

        .. versionadded:: 2017.7.0
        """
        minion_ret = self.cmd(tgt, "sys.list_functions", tgt_type=tgt_type, **kwargs)
        minions = list(minion_ret)
        random.shuffle(minions)
        f_tgt = []
        for minion in minions:
            if fun in minion_ret[minion]["return"]:
                f_tgt.append(minion)
            if len(f_tgt) >= subset:
                break
        return self.cmd_iter(
            f_tgt, fun, arg, timeout, tgt_type="list", ret=ret, kwarg=kwarg, **kwargs
        )

    def destroy(self):
        """
        API compatibility method with salt.client.LocalClient
        """

    def __enter__(self):
        """
        API compatibility method with salt.client.LocalClient
        """
        return self

    def __exit__(self, *args):
        """
        API compatibility method with salt.client.LocalClient
        """
        self.destroy()
