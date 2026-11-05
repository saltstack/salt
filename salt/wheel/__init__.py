"""
Modules used to control the master itself
"""

import logging
import os
from collections.abc import Mapping

import salt.channel.client
import salt.client.mixins
import salt.config
import salt.loader
import salt.utils.error
import salt.utils.event
import salt.utils.network
import salt.utils.resource_warnings
import salt.utils.user

log = logging.getLogger(__name__)


class WheelClient(
    salt.client.mixins.SyncClientMixin, salt.client.mixins.AsyncClientMixin
):
    """
    An interface to Salt's wheel modules

    :ref:`Wheel modules <all-salt.wheel>` interact with various parts of the
    Salt Master.

    Importing and using ``WheelClient`` must be done on the same machine as the
    Salt Master and it must be done using the same user that the Salt Master is
    running as. Unless :conf_master:`external_auth` is configured and the user
    is authorized to execute wheel functions: (``@wheel``).

    Usage:

    .. code-block:: python

        import salt.config
        import salt.wheel
        opts = salt.config.master_config('/etc/salt/master')
        wheel = salt.wheel.WheelClient(opts)
    """

    client = "wheel"
    tag_prefix = "wheel"

    def __init__(self, opts, context=None):
        salt.client.mixins.SyncClientMixin.__init__(self, opts, context=context)
        salt.client.mixins.AsyncClientMixin.__init__(self, opts, context=context)
        self.opts = opts
        self.context = context or {}
        self.salt_user = salt.utils.user.get_specific_user()
        self.event = salt.utils.event.get_event(
            "master", self.opts["sock_dir"], opts=self.opts, listen=False
        )
        self.functions = salt.loader.wheels(opts, context=self.context)

    def destroy(self):
        # Each resource's teardown is isolated in its own try/except and its
        # attribute is unconditionally reset afterward, so one resource
        # raising during teardown can never prevent the others (in
        # particular _mminion) from being destroyed too.
        if self.event is not None:
            try:
                self.event.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error destroying WheelClient event: %s", exc)
            self.event = None
        if hasattr(self, "functions") and self.functions is not None:
            try:
                if hasattr(self.functions, "destroy"):
                    self.functions.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error destroying WheelClient functions: %s", exc)
            self.functions = {}
        if hasattr(self, "_mminion") and self._mminion is not None:
            try:
                self._mminion.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error destroying WheelClient mminion: %s", exc)
            self._mminion = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.destroy()

    # pylint: disable=W1701
    def __del__(self):
        # LTS safety-net: keep the pre-``0c3f53d9172`` GC-time
        # ``destroy()`` fallback so callers that never wrapped the
        # client in a context manager do not silently leak the
        # underlying event socket, but also emit a
        # ``warn_until_close`` so the missing-``destroy()`` shows up in
        # normal Salt logs (Python filters ``ResourceWarning`` by
        # default).  The companion change on ``master`` drops the
        # fallback and requires callers to be explicit.
        try:
            unclosed = getattr(self, "event", None) is not None
        except Exception:  # pylint: disable=broad-except
            return
        if not unclosed:
            return
        try:
            salt.utils.resource_warnings.warn_until_close(
                f"unclosed {type(self).__name__} {self!r}; call "
                f"``destroy()`` or use as a context manager",
                source=self,
                log=log,
            )
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            self.destroy()
        except Exception:  # pylint: disable=broad-except
            # Finalizer must never raise.
            pass

    # pylint: enable=W1701

    # TODO: remove/deprecate
    def call_func(self, fun, **kwargs):
        """
        Backwards compatibility
        """
        return self.low(
            fun,
            kwargs,
            print_event=kwargs.get("print_event", True),
            full_return=kwargs.get("full_return", False),
        )

    # TODO: Inconsistent with runner client-- the runner client's master_call gives
    # an asynchronous return, unlike this
    def master_call(self, **kwargs):
        """
        Execute a wheel function through the master network interface (eauth).
        """
        load = kwargs
        load["cmd"] = "wheel"
        interface = self.opts["interface"]
        if interface == "0.0.0.0":
            interface = "127.0.0.1"
        if interface == "::":
            interface = "::1"
        master_uri = "tcp://{}:{}".format(
            salt.utils.network.ip_bracket(interface),
            str(self.opts["ret_port"]),
        )
        with salt.channel.client.ReqChannel.factory(
            self.opts, crypt="clear", master_uri=master_uri, usage="master_call"
        ) as channel:
            ret = channel.send(load)

        if isinstance(ret, Mapping):
            if "error" in ret:
                salt.utils.error.raise_error(**ret["error"])

        return ret

    def cmd_sync(self, low, timeout=None, full_return=False):
        """
        Execute a wheel function synchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@wheel``).

        .. code-block:: python

            >>> wheel.cmd_sync({
            'fun': 'key.finger',
            'match': 'jerry',
            'eauth': 'auto',
            'username': 'saltdev',
            'password': 'saltdev',
            })
            {'minions': {'jerry': '5d:f6:79:43:5e:d4:42:3f:57:b8:45:a8:7e:a4:6e:ca'}}
        """
        return self.master_call(**low)

    # TODO: Inconsistent with runner client-- that one uses the master_call function
    # and runs within the master daemon. Need to pick one...
    def cmd_async(self, low):
        """
        Execute a function asynchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized

        .. code-block:: python

            >>> wheel.cmd_async({
                'fun': 'key.finger',
                'match': 'jerry',
                'eauth': 'auto',
                'username': 'saltdev',
                'password': 'saltdev',
            })
            {'jid': '20131219224744416681', 'tag': 'salt/wheel/20131219224744416681'}
        """
        fun = low.get("fun")
        return self.asynchronous(fun, low, local=False)

    def cmd(
        self,
        fun,
        arg=None,
        pub_data=None,
        kwarg=None,
        print_event=True,
        full_return=False,
    ):  # pylint: disable=useless-super-delegation
        """
        Execute a function

        .. code-block:: python

            >>> wheel.cmd('key.finger', ['jerry'])
            {'minions': {'jerry': '5d:f6:79:43:5e:d4:42:3f:57:b8:45:a8:7e:a4:6e:ca'}}
        """
        return super().cmd(fun, arg, pub_data, kwarg, print_event, full_return)


Wheel = WheelClient  # for backward-compat


class RemoteWheelClient:
    """
    Remote-only wheel client.

    Instantiated by the CLI dispatch when ``opts["__role"] == "client"`` --
    i.e. ``salt-key`` running on a workstation against a remote master.
    Sends wheel calls to the master's ``ClearFuncs.wheel`` endpoint over a
    clear ``ReqChannel`` using eauth / token / client-key authentication.

    The local wheel loader is still populated because :class:`salt.key.KeyCLI`
    uses ``self.client.functions[fstr]`` to introspect each wheel function's
    argspec for CLI arg parsing.  The modules themselves do not execute
    locally -- the master runs them.

    See :class:`WheelClient` for the master-local variant.
    """

    client = "wheel"
    tag_prefix = "wheel"

    def __init__(self, opts, context=None):
        self.opts = opts
        self.context = context or {}
        self.salt_user = salt.utils.user.get_specific_user()
        # Loaded locally for CLI arg introspection only; execution is remote.
        self.functions = salt.loader.wheels(opts, context=self.context)
        # Lazy -- sync wheel does not need the event subscriber because the
        # master's wheel endpoint blocks server-side and returns the full
        # {tag, data} response inline.  Async callers will populate it.
        self.event = None

    def destroy(self):
        if self.event is not None:
            try:
                self.event.destroy()
            finally:
                self.event = None
        if hasattr(self, "functions") and self.functions is not None:
            if hasattr(self.functions, "destroy"):
                self.functions.destroy()
            self.functions = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.destroy()

    # pylint: disable=W1701
    def __del__(self):
        try:
            unclosed = getattr(self, "event", None) is not None or getattr(
                self, "functions", None
            )
        except Exception:  # pylint: disable=broad-except
            return
        if not unclosed:
            return
        try:
            salt.utils.resource_warnings.warn_until_close(
                f"unclosed {type(self).__name__} {self!r}; call "
                f"``destroy()`` or use as a context manager",
                source=self,
                log=log,
            )
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            self.destroy()
        except Exception:  # pylint: disable=broad-except
            pass

    # pylint: enable=W1701

    def master_call(self, **kwargs):
        """
        Send a wheel call to the remote master.

        Uses ``crypt="aes"`` so eauth credentials inside ``kwargs``
        travel encrypted under the PKI-handshake session key.  See
        :class:`salt.runner.RemoteRunnerClient.master_call` for the
        master-side bridge that routes AES-wrapped ``wheel`` cmds to
        :meth:`salt.daemons.masterapi.LocalFuncs.wheel`.
        """
        load = kwargs
        load["cmd"] = "wheel"
        # Pure-PKI remote clients (no eauth / token in kwargs) still
        # need to prove identity to ``ClearFuncs.wheel``; set
        # ``client_id`` so the master's ``_prep_auth_info`` can route
        # them through ``auth_type="client"``.
        load.setdefault("client_id", self.opts["id"])
        master = self.opts.get("master", "localhost")
        master_uri = "tcp://{}:{}".format(
            salt.utils.network.ip_bracket(master),
            str(self.opts["ret_port"]),
        )
        with salt.channel.client.ReqChannel.factory(
            self.opts, crypt="aes", master_uri=master_uri, usage="master_call"
        ) as channel:
            ret = channel.send(load)
        if isinstance(ret, Mapping) and "error" in ret:
            salt.utils.error.raise_error(**ret["error"])
        return ret

    def cmd_sync(self, low, timeout=None, full_return=False):
        """
        Execute a wheel function synchronously via the remote master.

        The master's ``ClearFuncs.wheel`` endpoint blocks on
        ``wheel_client.call_func(fun, **load)`` and returns
        ``{"tag": tag, "data": {"return": ..., "success": ..., "jid": ...}}``.
        Return the full response so callers that match the local
        :class:`WheelClient` contract (e.g. :class:`salt.key.KeyCLI`) can
        unwrap ``data["return"]`` themselves.
        """
        return self.master_call(**low)

    def cmd_async(self, low):
        """
        Execute a wheel function asynchronously; returns ``{"jid", "tag"}``.

        Note: the master's wheel endpoint is synchronous server-side -- the
        call blocks until the wheel function completes before returning.
        "async" here means the client does not wait on the event bus for a
        separate completion event; the ``{jid, tag}`` is extracted from the
        same synchronous response.
        """
        ret = self.master_call(**low)
        if isinstance(ret, Mapping) and "data" in ret:
            data = ret["data"]
            return {"jid": data.get("jid", ""), "tag": ret.get("tag", "")}
        return ret

    def cmd(
        self,
        fun,
        arg=None,
        pub_data=None,
        kwarg=None,
        print_event=True,
        full_return=False,
    ):
        """
        Execute a wheel function.  Mirrors :meth:`WheelClient.cmd`.
        """
        low = {"fun": fun}
        if arg:
            low["arg"] = arg
        if kwarg:
            low["kwarg"] = kwarg
        return self.cmd_sync(low, full_return=full_return)

    def call_func(self, fun, **kwargs):
        """
        Backwards-compatibility wrapper.
        """
        return self.cmd(fun, kwarg=kwargs)
