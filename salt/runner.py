"""
Execute salt convenience routines
"""

import logging
import os
from collections.abc import Mapping

import salt.channel.client
import salt.exceptions
import salt.loader
import salt.minion
import salt.utils.args
import salt.utils.error
import salt.utils.event
import salt.utils.files
import salt.utils.network
import salt.utils.resource_warnings
import salt.utils.user
from salt.client import mixins
from salt.output import display_output
from salt.utils.lazy import verify_fun

log = logging.getLogger(__name__)


class RunnerClient(mixins.SyncClientMixin, mixins.AsyncClientMixin):
    """
    The interface used by the :command:`salt-run` CLI tool on the Salt Master

    It executes :ref:`runner modules <all-salt.runners>` which run on the Salt
    Master.

    Importing and using ``RunnerClient`` must be done on the same machine as
    the Salt Master and it must be done using the same user that the Salt
    Master is running as.

    Salt's :conf_master:`external_auth` can be used to authenticate calls. The
    eauth user must be authorized to execute runner modules: (``@runner``).
    Only the :py:meth:`master_call` below supports eauth.
    """

    client = "runner"
    tag_prefix = "run"

    def __init__(self, opts, context=None):
        mixins.SyncClientMixin.__init__(self, opts, context=context)
        mixins.AsyncClientMixin.__init__(self, opts, context=context)
        self.opts = opts
        self.context = context or {}
        self.salt_user = salt.utils.user.get_specific_user()
        self.event = salt.utils.event.get_event(
            "master", self.opts["sock_dir"], opts=self.opts, listen=False
        )

    def destroy(self):
        # Each resource's teardown is isolated in its own try/except and its
        # attribute is unconditionally reset afterward, so one resource
        # raising during teardown can never prevent the others (in
        # particular _mminion) from being destroyed too.
        if self.event is not None:
            try:
                self.event.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error destroying RunnerClient event: %s", exc)
            self.event = None
        if hasattr(self, "_functions") and self._functions is not None:
            try:
                if hasattr(self._functions, "destroy"):
                    self._functions.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error destroying RunnerClient functions: %s", exc)
            self._functions = {}
        if hasattr(self, "utils") and self.utils is not None:
            try:
                if hasattr(self.utils, "destroy"):
                    self.utils.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error destroying RunnerClient utils: %s", exc)
            self.utils = {}
        if hasattr(self, "_mminion") and self._mminion is not None:
            try:
                self._mminion.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error destroying RunnerClient mminion: %s", exc)
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

    @property
    def functions(self):
        if not hasattr(self, "_functions"):
            if not hasattr(self, "utils"):
                self.utils = salt.loader.utils(self.opts)
            # Must be self.functions for mixin to work correctly :-/
            try:
                self._functions = salt.loader.runner(
                    self.opts, utils=self.utils, context=self.context
                )
            except AttributeError:
                # Just in case self.utils is still not present (perhaps due to
                # problems with the loader), load the runner funcs without them
                self._functions = salt.loader.runner(self.opts, context=self.context)

        return self._functions

    def _reformat_low(self, low):
        """
        Format the low data for RunnerClient()'s master_call() function

        This also normalizes the following low data formats to a single, common
        low data structure.

        Old-style low: ``{'fun': 'jobs.lookup_jid', 'jid': '1234'}``
        New-style: ``{'fun': 'jobs.lookup_jid', 'kwarg': {'jid': '1234'}}``
        CLI-style: ``{'fun': 'jobs.lookup_jid', 'arg': ['jid="1234"']}``
        """
        fun = low.pop("fun")
        verify_fun(self.functions, fun)

        eauth_creds = {
            i: low.pop(i)
            for i in [
                "username",
                "password",
                "eauth",
                "token",
                "client",
                "user",
                "key",
            ]
            if i in low
        }

        # Run name=value args through parse_input. We don't need to run kwargs
        # through because there is no way to send name=value strings in the low
        # dict other than by including an `arg` array.
        _arg, _kwarg = salt.utils.args.parse_input(low.pop("arg", []), condition=False)
        _kwarg.update(low.pop("kwarg", {}))

        # If anything hasn't been pop()'ed out of low by this point it must be
        # an old-style kwarg.
        _kwarg.update(low)

        # Finally, mung our kwargs to a format suitable for the byzantine
        # load_args_and_kwargs so that we can introspect the function being
        # called and fish for invalid kwargs.
        munged = []
        munged.extend(_arg)
        munged.append(dict(__kwarg__=True, **_kwarg))
        arg, kwarg = salt.minion.load_args_and_kwargs(
            self.functions[fun], munged, ignore_invalid=True
        )

        return dict(fun=fun, kwarg={"kwarg": kwarg, "arg": arg}, **eauth_creds)

    def cmd_async(self, low):
        """
        Execute a runner function asynchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.cmd_async({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        """
        reformatted_low = self._reformat_low(low)

        return mixins.AsyncClientMixin.cmd_async(self, reformatted_low)

    def cmd_sync(self, low, timeout=None, full_return=False):
        """
        Execute a runner function synchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.cmd_sync({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        """
        reformatted_low = self._reformat_low(low)
        return mixins.SyncClientMixin.cmd_sync(
            self, reformatted_low, timeout, full_return
        )

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

            >>> opts = salt.config.master_config('/etc/salt/master')
            >>> runner = salt.runner.RunnerClient(opts)
            >>> runner.cmd('jobs.list_jobs', [])
            {
                '20131219215650131543': {
                    'Arguments': [300],
                    'Function': 'test.sleep',
                    'StartTime': '2013, Dec 19 21:56:50.131543',
                    'Target': '*',
                    'Target-type': 'glob',
                    'User': 'saltdev'
                },
                '20131219215921857715': {
                    'Arguments': [300],
                    'Function': 'test.sleep',
                    'StartTime': '2013, Dec 19 21:59:21.857715',
                    'Target': '*',
                    'Target-type': 'glob',
                    'User': 'saltdev'
                },
            }

        """
        return super().cmd(fun, arg, pub_data, kwarg, print_event, full_return)


class Runner(RunnerClient):
    """
    Execute the salt runner interface
    """

    def __init__(self, opts, context=None):
        # In-process callers that construct ``Runner`` with
        # ``client_auth=True`` expect the opts to look like they came
        # out of :func:`salt.config.client_config` -- notably with
        # ``__role=client`` so downstream code (``RemoteRunner`` dispatch,
        # ``_send_token_request``) can tell this is a workstation client
        # and not the master-local path.  CLI invocations get this via
        # ``client_config``; in-process callers (and the tests covering
        # remote-CLI parity) get it here.  Mirrors the same shim in
        # :class:`salt.key.KeyCLI` so the two classes stay symmetric.
        if opts.get("client_auth") and opts.get("__role") != "client":
            opts = dict(opts)
            opts["__role"] = "client"
        super().__init__(opts, context=context)
        self.returners = salt.loader.returners(
            self.opts, self.functions, context=context
        )
        self.outputters = salt.loader.outputters(self.opts)

    def destroy(self):
        if hasattr(self, "returners") and self.returners is not None:
            if hasattr(self.returners, "destroy"):
                self.returners.destroy()
            self.returners = {}
        if hasattr(self, "outputters") and self.outputters is not None:
            if hasattr(self.outputters, "destroy"):
                self.outputters.destroy()
            self.outputters = {}
        super().destroy()

    def print_docs(self):
        """
        Print out the documentation!
        """
        arg = self.opts.get("fun", None)
        docs = super().get_docs(arg)
        for fun in sorted(docs):
            display_output(f"{fun}:", "text", self.opts)
            print(docs[fun])

    # TODO: move to mixin whenever we want a salt-wheel cli
    def run(self, print_event=True, full_return=False):
        """
        Execute the runner sequence
        """
        import salt.minion

        ret = {}
        if self.opts.get("doc", False):
            self.print_docs()
        else:
            low = {"fun": self.opts["fun"]}
            try:
                # Allocate a jid
                async_pub = self._gen_async_pub(jid=self.opts.get("jid"))
                self.jid = async_pub["jid"]

                fun_args = salt.utils.args.parse_input(
                    self.opts["arg"], no_parse=self.opts.get("no_parse", [])
                )

                verify_fun(self.functions, low["fun"])
                args, kwargs = salt.minion.load_args_and_kwargs(
                    self.functions[low["fun"]], fun_args
                )
                low["arg"] = args
                low["kwarg"] = kwargs

                # Skip eauth credential collection for client auth
                if self.opts.get("client_auth"):
                    # Client auth uses PKI keys, no credentials needed in low dict
                    pass
                elif self.opts.get("eauth"):
                    if "token" in self.opts:
                        try:
                            with salt.utils.files.fopen(
                                os.path.join(self.opts["cachedir"], ".root_key"), "r"
                            ) as fp_:
                                low["key"] = salt.utils.stringutils.to_unicode(
                                    fp_.readline()
                                )
                        except OSError:
                            low["token"] = self.opts["token"]

                    # If using eauth and a token hasn't already been loaded into
                    # low, prompt the user to enter auth credentials
                    if "token" not in low and "key" not in low and self.opts["eauth"]:
                        # This is expensive. Don't do it unless we need to.
                        import salt.auth

                        resolver = salt.auth.Resolver(self.opts)
                        res = resolver.cli(self.opts["eauth"])
                        if self.opts["mktoken"] and res:
                            tok = resolver.token_cli(self.opts["eauth"], res)
                            if tok:
                                low["token"] = tok.get("token", "")
                        if not res:
                            log.error("Authentication failed")
                            return ret
                        low.update(res)
                        low["eauth"] = self.opts["eauth"]
                else:
                    user = salt.utils.user.get_specific_user()

                if low["fun"] in ["state.orchestrate", "state.orch", "state.sls"]:
                    low["kwarg"]["orchestration_jid"] = async_pub["jid"]

                # Run the runner!
                if self.opts.get("async", False):
                    if self.opts.get("eauth") or self.opts.get("client_auth"):
                        async_pub = self.cmd_async(low)
                    else:
                        async_pub = self.asynchronous(
                            self.opts["fun"], low, user=user, pub=async_pub
                        )
                    # by default: info will be not enougth to be printed out !
                    log.warning(
                        "Running in asynchronous mode. Results of this execution may "
                        "be collected by attaching to the master event bus or "
                        "by examining the master job cache, if configured. "
                        "This execution is running under tag %s",
                        async_pub["tag"],
                    )
                    return async_pub["jid"]  # return the jid

                # otherwise run it in the main process
                if self.opts.get("show_jid"):
                    print(f"jid: {self.jid}")

                if self.opts.get("eauth") or self.opts.get("client_auth"):
                    ret = self.cmd_sync(low)
                    if isinstance(ret, dict) and set(ret) == {"data", "outputter"}:
                        outputter = ret["outputter"]
                        ret = ret["data"]
                    else:
                        outputter = None
                    display_output(ret, outputter, self.opts)
                else:
                    ret = self._proc_function(
                        instance=self,
                        opts=self.opts,
                        fun=self.opts["fun"],
                        low=low,
                        user=user,
                        tag=async_pub["tag"],
                        jid=async_pub["jid"],
                        daemonize=False,
                        print_event=print_event,
                        full_return=full_return,
                    )
            except salt.exceptions.SaltException as exc:
                with salt.utils.event.get_event("master", opts=self.opts) as evt:
                    evt.fire_event(
                        {
                            "success": False,
                            "return": f"{exc}",
                            "retcode": 254,
                            "fun": self.opts["fun"],
                            "fun_args": fun_args,
                            "jid": self.jid,
                        },
                        tag=f"salt/run/{self.jid}/ret",
                    )
                # Attempt to grab documentation
                if "fun" in low:
                    ret = self.get_docs("{}*".format(low["fun"]))
                else:
                    ret = None

                # If we didn't get docs returned then
                # return the `not availble` message.
                if not ret:
                    ret = f"{exc}"
                if not self.opts.get("quiet", False):
                    display_output(ret, "nested", self.opts)
            else:
                log.debug("Runner return: %s", ret)

            return ret


class RemoteRunnerClient(mixins.SyncClientMixin):
    """
    Remote-only runner client.

    Instantiated by the CLI dispatch when ``opts["__role"] == "client"`` --
    ``salt-run`` running on a workstation against a remote master.  Sends
    runner calls to the master's ``ClearFuncs.runner`` endpoint over a
    clear ``ReqChannel`` using eauth / token / client-key authentication.

    The runner result arrives on the event bus as ``salt/run/<jid>/ret``;
    the inherited :meth:`salt.client.mixins.SyncClientMixin.cmd_sync`
    subscribes and waits for it via :class:`ClientEventSubscriber`.

    Runner modules are loaded locally only for CLI arg introspection by
    :meth:`RemoteRunner.run`.  Actual execution happens on the master.

    See :class:`RunnerClient` for the master-local variant.
    """

    client = "runner"
    tag_prefix = "run"

    def __init__(self, opts, context=None):
        mixins.SyncClientMixin.__init__(self, opts, context=context)
        self.opts = opts
        self.context = context or {}
        self.salt_user = salt.utils.user.get_specific_user()
        # Loaded locally for CLI arg introspection; execution is remote.
        # Any runner whose dependencies are missing on the client box will
        # silently fail to load -- not a problem for remote execution.
        try:
            self.functions = salt.loader.runner(opts, context=self.context)
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "Failed to load runner modules locally for introspection; "
                "remote execution still works",
                exc_info=True,
            )
            self.functions = {}
        from salt.utils import client_event as _client_event

        self.event = _client_event.ClientEventSubscriber(self.opts)

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
        Send a runner call to the remote master.

        Uses ``crypt="aes"`` so the eauth credentials in ``kwargs``
        travel encrypted under the PKI-handshake session key.  The
        master bridges the AES-wrapped ``runner`` cmd through
        :meth:`salt.master.MWorker._handle_payload_inner` to
        :meth:`salt.daemons.masterapi.LocalFuncs.runner` on ClearFuncs,
        which then validates the eauth creds inside the decrypted load.
        """
        load = kwargs
        load["cmd"] = "runner"
        # Pure-PKI remote clients (no eauth / token in kwargs) still
        # need to prove identity to ``ClearFuncs.runner``; set
        # ``client_id`` so the master's ``_prep_auth_info`` can route
        # them through ``auth_type="client"``.  Stacked PKI+eauth
        # flows set both; the master prefers eauth/token when present.
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


class RemoteRunner(RemoteRunnerClient):
    """
    CLI entry for remote ``salt-run``.

    Mirrors :class:`Runner` but drops the local-master execution path --
    everything flows through :meth:`RemoteRunnerClient.cmd_sync`.
    """

    def print_docs(self):
        """
        Print runner docstrings.

        Reads from the locally-loaded runner modules (``self.functions``
        populated by ``RemoteRunnerClient.__init__`` for argspec and doc
        introspection), *not* from the master.  This is a deliberate
        design choice: doc output is query-only metadata and treating it
        like ``git`` / ``kubectl`` / ``aws`` ``--help`` -- served from
        the client binary -- avoids a server round-trip for every
        introspection call.

        Caveats operators should be aware of:
          * runners whose dependencies aren't installed on the client
            workstation won't appear in ``--doc`` output even if the
            master has them (``salt.loader.runner`` silently skips
            modules that fail to import)
          * if client and master run different Salt versions, the
            printed docstrings may drift from what the server actually
            implements

        Every other remote-CLI operation (publish / runner execution /
        wheel / mk_token / batch adopt) routes through the master.
        """
        arg = self.opts.get("fun", None)
        docs = self.get_docs(arg)
        for fun in sorted(docs):
            display_output(f"{fun}:", "text", self.opts)
            print(docs[fun])

    def run(self, full_return=False):
        """
        Execute the runner sequence against a remote master.
        """
        if self.opts.get("doc", False):
            self.print_docs()
            return {}

        low = {"fun": self.opts["fun"]}
        fun_args = salt.utils.args.parse_input(
            self.opts["arg"], no_parse=self.opts.get("no_parse", [])
        )

        if self.functions and low["fun"] in self.functions:
            verify_fun(self.functions, low["fun"])
            args, kwargs = salt.minion.load_args_and_kwargs(
                self.functions[low["fun"]], fun_args
            )
        else:
            # Runner module not loadable locally; forward raw args to master.
            args, kwargs = fun_args, {}
            if (
                isinstance(fun_args, list)
                and fun_args
                and isinstance(fun_args[-1], dict)
            ):
                args, kwargs = fun_args[:-1], fun_args[-1]
        low["arg"] = args
        low["kwarg"] = kwargs

        # Client-auth path uses the PKI identity already on the ReqChannel;
        # eauth path collects credentials and attaches them to the load.
        # When eauth is in play we also need a Salt token to authenticate
        # the event subscriber (otherwise the ClientEventSubscriber would
        # fall back to its PKI handshake and block on a missing client.pem).
        if self.opts.get("eauth"):
            # Aliased import -- a bare ``import salt.auth`` here would
            # shadow the module-level ``salt`` binding used earlier in
            # this function for ``salt.utils.args`` / ``salt.minion``.
            from salt import auth as _auth

            if "token" in self.opts and self.opts["token"]:
                low["token"] = self.opts["token"]
            if "token" not in low and self.opts["eauth"]:
                resolver = _auth.Resolver(self.opts)
                creds = resolver.cli(self.opts["eauth"])
                if not creds:
                    log.error("Authentication failed")
                    return {}
                # Always mint a token so the event subscriber can
                # authenticate on the token path.  ``--make-token`` only
                # controls whether the token is persisted to disk.
                tok = resolver.token_cli(self.opts["eauth"], creds)
                if tok and tok.get("token"):
                    low["token"] = tok["token"]
                else:
                    # Could not mint a token; fall back to passing creds
                    # directly in the publish load.  Event stream will be
                    # unusable in this mode -- caller gets JID only.
                    low.update(creds)
                low["eauth"] = self.opts["eauth"]

            # If we have a token, pre-authenticate the event subscriber
            # on the token path so cmd_sync's event.connect() succeeds
            # without needing a client PKI key.
            if (
                "token" in low
                and self.event is not None
                and not getattr(self.event, "authenticated", False)
            ):
                try:
                    self.event.connect(
                        salt_token=low["token"], eauth=self.opts.get("eauth")
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    log.warning(
                        "Could not pre-authenticate event subscriber on "
                        "the token path: %s. Event stream may be unusable.",
                        exc,
                    )

        if self.opts.get("async", False):
            async_pub = self.master_call(**low)
            log.warning(
                "Running in asynchronous mode. Results of this execution may "
                "be collected by attaching to the master event bus or by "
                "examining the master job cache, if configured. This "
                "execution is running under tag %s",
                async_pub.get("tag"),
            )
            return async_pub.get("jid")

        if self.opts.get("show_jid"):
            # cmd_sync returns the ret event dict; printing the jid before
            # the result requires a separate async_pub step -- skip for now.
            pass

        ret = self.cmd_sync(low)
        if isinstance(ret, dict) and set(ret) == {"data", "outputter"}:
            outputter = ret["outputter"]
            ret = ret["data"]
        else:
            outputter = None
        display_output(ret, outputter, self.opts)
        return ret
