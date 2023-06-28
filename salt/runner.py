"""
Execute salt convenience routines
"""

import logging
import os

import salt.exceptions
import salt.loader
import salt.minion
import salt.utils.args
import salt.utils.event
import salt.utils.files
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
        super().__init__(opts, context=context)
        self.returners = salt.loader.returners(opts, self.functions, context=context)
        self.outputters = salt.loader.outputters(opts)

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
    def run(self, full_return=False):
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

                if self.opts.get("eauth"):
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
                    if self.opts.get("eauth"):
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
                if self.opts.get("eauth"):
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
