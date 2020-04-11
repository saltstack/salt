# coding: utf-8
"""
A collection of mixins useful for the various *Client interfaces
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals, with_statement

import collections
import copy as pycopy
import fnmatch
import logging
import signal
import traceback
import weakref

# Import Salt libs
import salt.exceptions

# Import 3rd-party libs
import salt.ext.tornado.stack_context
import salt.log.setup
import salt.minion
import salt.transport.client
import salt.utils.args
import salt.utils.doc
import salt.utils.error
import salt.utils.event
import salt.utils.jid
import salt.utils.job
import salt.utils.lazy
import salt.utils.platform
import salt.utils.process
import salt.utils.state
import salt.utils.user
import salt.utils.versions
from salt.ext import six

log = logging.getLogger(__name__)

CLIENT_INTERNAL_KEYWORDS = frozenset(
    [
        "client",
        "cmd",
        "eauth",
        "fun",
        "kwarg",
        "match",
        "token",
        "__jid__",
        "__tag__",
        "__user__",
        "username",
        "password",
        "full_return",
        "print_event",
    ]
)


class ClientFuncsDict(collections.MutableMapping):
    """
    Class to make a read-only dict for accessing runner funcs "directly"
    """

    def __init__(self, client):
        self.client = client

    def __getattr__(self, attr):
        """
        Provide access eg. to 'pack'
        """
        return getattr(self.client.functions, attr)

    def __setitem__(self, key, val):
        raise NotImplementedError()

    def __delitem__(self, key):
        raise NotImplementedError()

    def __getitem__(self, key):
        """
        Return a function that you can call with regular func params, but
        will do all the _proc_function magic
        """
        if key not in self.client.functions:
            raise KeyError

        def wrapper(*args, **kwargs):
            low = {
                "fun": key,
                "args": args,
                "kwargs": kwargs,
            }
            pub_data = {}
            # Copy kwargs keys so we can iterate over and pop the pub data
            kwargs_keys = list(kwargs)

            # pull out pub_data if you have it
            for kwargs_key in kwargs_keys:
                if kwargs_key.startswith("__pub_"):
                    pub_data[kwargs_key] = kwargs.pop(kwargs_key)

            async_pub = self.client._gen_async_pub(pub_data.get("__pub_jid"))

            user = salt.utils.user.get_specific_user()
            return self.client._proc_function(
                key,
                low,
                user,
                async_pub["tag"],  # TODO: fix
                async_pub["jid"],  # TODO: fix
                False,  # Don't daemonize
            )

        return wrapper

    def __len__(self):
        return len(self.client.functions)

    def __iter__(self):
        return iter(self.client.functions)


class SyncClientMixin(object):
    """
    A mixin for *Client interfaces to abstract common function execution
    """

    functions = ()

    def functions_dict(self):
        """
        Return a dict that will mimic the "functions" dict used all over salt.
        It creates a wrapper around the function allowing **kwargs, and if pub_data
        is passed in as kwargs, will re-use the JID passed in
        """
        return ClientFuncsDict(self)

    def master_call(self, **kwargs):
        """
        Execute a function through the master network interface.
        """
        load = kwargs
        load["cmd"] = self.client

        with salt.transport.client.ReqChannel.factory(
            self.opts, crypt="clear", usage="master_call"
        ) as channel:
            ret = channel.send(load)
            if isinstance(ret, collections.Mapping):
                if "error" in ret:
                    salt.utils.error.raise_error(**ret["error"])
            return ret

    def cmd_sync(self, low, timeout=None, full_return=False):
        """
        Execute a runner function synchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.eauth_sync({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        """
        with salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=True
        ) as event:
            job = self.master_call(**low)
            ret_tag = salt.utils.event.tagify("ret", base=job["tag"])

            if timeout is None:
                timeout = self.opts.get("rest_timeout", 300)
            ret = event.get_event(
                tag=ret_tag, full=True, wait=timeout, auto_reconnect=True
            )
            if ret is None:
                raise salt.exceptions.SaltClientTimeout(
                    "RunnerClient job '{0}' timed out".format(job["jid"]),
                    jid=job["jid"],
                )

            return ret if full_return else ret["data"]["return"]

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
        if arg is None:
            arg = tuple()
        if not isinstance(arg, list) and not isinstance(arg, tuple):
            raise salt.exceptions.SaltInvocationError(
                "arg must be formatted as a list/tuple"
            )
        if pub_data is None:
            pub_data = {}
        if not isinstance(pub_data, dict):
            raise salt.exceptions.SaltInvocationError(
                "pub_data must be formatted as a dictionary"
            )
        if kwarg is None:
            kwarg = {}
        if not isinstance(kwarg, dict):
            raise salt.exceptions.SaltInvocationError(
                "kwarg must be formatted as a dictionary"
            )
        arglist = salt.utils.args.parse_input(
            arg, no_parse=self.opts.get("no_parse", [])
        )

        # if you were passed kwarg, add it to arglist
        if kwarg:
            kwarg["__kwarg__"] = True
            arglist.append(kwarg)

        args, kwargs = salt.minion.load_args_and_kwargs(
            self.functions[fun], arglist, pub_data
        )
        low = {"fun": fun, "arg": args, "kwarg": kwargs}
        return self.low(fun, low, print_event=print_event, full_return=full_return)

    @property
    def mminion(self):
        if not hasattr(self, "_mminion"):
            self._mminion = salt.minion.MasterMinion(
                self.opts, states=False, rend=False
            )
        return self._mminion

    @property
    def store_job(self):
        """
        Helper that allows us to turn off storing jobs for different classes
        that may incorporate this mixin.
        """
        try:
            class_name = self.__class__.__name__.lower()
        except AttributeError:
            log.warning(
                "Unable to determine class name", exc_info_on_loglevel=logging.DEBUG
            )
            return True

        try:
            return self.opts["{0}_returns".format(class_name)]
        except KeyError:
            # No such option, assume this isn't one we care about gating and
            # just return True.
            return True

    def low(self, fun, low, print_event=True, full_return=False):
        """
        Execute a function from low data
        Low data includes:
            required:
                - fun: the name of the function to run
            optional:
                - arg: a list of args to pass to fun
                - kwarg: kwargs for fun
                - __user__: user who is running the command
                - __jid__: jid to run under
                - __tag__: tag to run under
        """
        # fire the mminion loading (if not already done) here
        # this is not to clutter the output with the module loading
        # if we have a high debug level.
        self.mminion  # pylint: disable=W0104
        jid = low.get("__jid__", salt.utils.jid.gen_jid(self.opts))
        tag = low.get("__tag__", salt.utils.event.tagify(jid, prefix=self.tag_prefix))

        data = {
            "fun": "{0}.{1}".format(self.client, fun),
            "jid": jid,
            "user": low.get("__user__", "UNKNOWN"),
        }

        if print_event:
            print_func = (
                self.print_async_event if hasattr(self, "print_async_event") else None
            )
        else:
            # Suppress printing of return event (this keeps us from printing
            # runner/wheel output during orchestration).
            print_func = None

        with salt.utils.event.NamespacedEvent(
            salt.utils.event.get_event(
                "master",
                self.opts["sock_dir"],
                self.opts["transport"],
                opts=self.opts,
                listen=False,
            ),
            tag,
            print_func=print_func,
        ) as namespaced_event:

            # TODO: test that they exist
            # TODO: Other things to inject??
            func_globals = {
                "__jid__": jid,
                "__user__": data["user"],
                "__tag__": tag,
                # weak ref to avoid the Exception in interpreter
                # teardown of event
                "__jid_event__": weakref.proxy(namespaced_event),
            }

            try:
                self_functions = pycopy.copy(self.functions)
                salt.utils.lazy.verify_fun(self_functions, fun)

                # Inject some useful globals to *all* the function's global
                # namespace only once per module-- not per func
                completed_funcs = []

                for mod_name in six.iterkeys(self_functions):
                    if "." not in mod_name:
                        continue
                    mod, _ = mod_name.split(".", 1)
                    if mod in completed_funcs:
                        continue
                    completed_funcs.append(mod)
                    for global_key, value in six.iteritems(func_globals):
                        self.functions[mod_name].__globals__[global_key] = value

                # There are some discrepancies of what a "low" structure is in the
                # publisher world it is a dict including stuff such as jid, fun,
                # arg (a list of args, with kwargs packed in). Historically this
                # particular one has had no "arg" and just has had all the kwargs
                # packed into the top level object. The plan is to move away from
                # that since the caller knows what is an arg vs a kwarg, but while
                # we make the transition we will load "kwargs" using format_call if
                # there are no kwargs in the low object passed in.

                if "arg" in low and "kwarg" in low:
                    args = low["arg"]
                    kwargs = low["kwarg"]
                else:
                    f_call = salt.utils.args.format_call(
                        self.functions[fun],
                        low,
                        expected_extra_kws=CLIENT_INTERNAL_KEYWORDS,
                    )
                    args = f_call.get("args", ())
                    kwargs = f_call.get("kwargs", {})

                # Update the event data with loaded args and kwargs
                data["fun_args"] = list(args) + ([kwargs] if kwargs else [])
                func_globals["__jid_event__"].fire_event(data, "new")

                # Initialize a context for executing the method.
                with salt.ext.tornado.stack_context.StackContext(
                    self.functions.context_dict.clone
                ):
                    func = self.functions[fun]
                    try:
                        data["return"] = func(*args, **kwargs)
                    except TypeError as exc:
                        data[
                            "return"
                        ] = "\nPassed invalid arguments: {0}\n\nUsage:\n{1}".format(
                            exc, func.__doc__
                        )
                    try:
                        data["success"] = self.context.get("retcode", 0) == 0
                    except AttributeError:
                        # Assume a True result if no context attribute
                        data["success"] = True
                    if isinstance(data["return"], dict) and "data" in data["return"]:
                        # some functions can return boolean values
                        data["success"] = salt.utils.state.check_result(
                            data["return"]["data"]
                        )
            except (Exception, SystemExit) as ex:  # pylint: disable=broad-except
                if isinstance(ex, salt.exceptions.NotImplemented):
                    data["return"] = six.text_type(ex)
                else:
                    data["return"] = "Exception occurred in {0} {1}: {2}".format(
                        self.client, fun, traceback.format_exc(),
                    )
                data["success"] = False

            if self.store_job:
                try:
                    salt.utils.job.store_job(
                        self.opts,
                        {
                            "id": self.opts["id"],
                            "tgt": self.opts["id"],
                            "jid": data["jid"],
                            "return": data,
                        },
                        event=None,
                        mminion=self.mminion,
                    )
                except salt.exceptions.SaltCacheError:
                    log.error(
                        "Could not store job cache info. "
                        "Job details for this run may be unavailable."
                    )

            # Outputters _can_ mutate data so write to the job cache first!
            namespaced_event.fire_event(data, "ret")

            # if we fired an event, make sure to delete the event object.
            # This will ensure that we call destroy, which will do the 0MQ linger
            log.info("Runner completed: %s", data["jid"])
            return data if full_return else data["return"]

    def get_docs(self, arg=None):
        """
        Return a dictionary of functions and the inline documentation for each
        """
        if arg:
            if "*" in arg:
                target_mod = arg
                _use_fnmatch = True
            else:
                target_mod = arg + "." if not arg.endswith(".") else arg
                _use_fnmatch = False
            if _use_fnmatch:
                docs = [
                    (fun, self.functions[fun].__doc__)
                    for fun in fnmatch.filter(self.functions, target_mod)
                ]
            else:
                docs = [
                    (fun, self.functions[fun].__doc__)
                    for fun in sorted(self.functions)
                    if fun == arg or fun.startswith(target_mod)
                ]
        else:
            docs = [
                (fun, self.functions[fun].__doc__) for fun in sorted(self.functions)
            ]
        docs = dict(docs)
        return salt.utils.doc.strip_rst(docs)


class AsyncClientMixin(object):
    """
    A mixin for *Client interfaces to enable easy asynchronous function execution
    """

    client = None
    tag_prefix = None

    def _proc_function(self, fun, low, user, tag, jid, daemonize=True):
        """
        Run this method in a multiprocess target to execute the function in a
        multiprocess and fire the return data on the event bus
        """
        if daemonize and not salt.utils.platform.is_windows():
            # Shutdown the multiprocessing before daemonizing
            salt.log.setup.shutdown_multiprocessing_logging()

            salt.utils.process.daemonize()

            # Reconfigure multiprocessing logging after daemonizing
            salt.log.setup.setup_multiprocessing_logging()

        # pack a few things into low
        low["__jid__"] = jid
        low["__user__"] = user
        low["__tag__"] = tag

        return self.low(fun, low, full_return=False)

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
        return self.master_call(**low)

    def _gen_async_pub(self, jid=None):
        if jid is None:
            jid = salt.utils.jid.gen_jid(self.opts)
        tag = salt.utils.event.tagify(jid, prefix=self.tag_prefix)
        return {"tag": tag, "jid": jid}

    def asynchronous(self, fun, low, user="UNKNOWN", pub=None):
        """
        Execute the function in a multiprocess and return the event tag to use
        to watch for the return
        """
        async_pub = pub if pub is not None else self._gen_async_pub()
        proc = salt.utils.process.SignalHandlingProcess(
            target=self._proc_function,
            name="ProcessFunc",
            args=(fun, low, user, async_pub["tag"], async_pub["jid"]),
        )
        with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):
            # Reset current signals before starting the process in
            # order not to inherit the current signal handlers
            proc.start()
        proc.join()  # MUST join, otherwise we leave zombies all over
        return async_pub

    def print_async_event(self, suffix, event):
        """
        Print all of the events with the prefix 'tag'
        """
        if not isinstance(event, dict):
            return

        # if we are "quiet", don't print
        if self.opts.get("quiet", False):
            return

        # some suffixes we don't want to print
        if suffix in ("new",):
            return

        try:
            outputter = self.opts.get(
                "output",
                event.get("outputter", None) or event.get("return").get("outputter"),
            )
        except AttributeError:
            outputter = None

        # if this is a ret, we have our own set of rules
        if suffix == "ret":
            # Check if outputter was passed in the return data. If this is the case,
            # then the return data will be a dict two keys: 'data' and 'outputter'
            if isinstance(event.get("return"), dict) and set(event["return"]) == set(
                ("data", "outputter")
            ):
                event_data = event["return"]["data"]
                outputter = event["return"]["outputter"]
            else:
                event_data = event["return"]
        else:
            event_data = {"suffix": suffix, "event": event}

        salt.output.display_output(event_data, outputter, self.opts)
