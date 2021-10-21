#
#   Proxy minion metaproxy modules
#

import copy
import logging
import os
import sys
import threading
import traceback
import types

import salt
import salt.beacons
import salt.cli.daemons
import salt.client
import salt.config
import salt.crypt
import salt.defaults.exitcodes
import salt.engines
import salt.loader
import salt.log.setup
import salt.minion
import salt.payload
import salt.pillar
import salt.serializers.msgpack
import salt.syspaths
import salt.utils.args
import salt.utils.context
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.error
import salt.utils.event
import salt.utils.files
import salt.utils.jid
import salt.utils.minion
import salt.utils.minions
import salt.utils.network
import salt.utils.platform
import salt.utils.process
import salt.utils.schedule
import salt.utils.ssdp
import salt.utils.user
import salt.utils.zeromq
import tornado.gen
import tornado.ioloop
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltInvocationError,
    SaltSystemExit,
)
from salt.minion import ProxyMinion
from salt.utils.event import tagify
from salt.utils.process import SignalHandlingProcess

log = logging.getLogger(__name__)


def post_master_init(self, master):
    """
    Function to finish init after a deltaproxy proxy
    minion has finished connecting to a master.

    This is primarily loading modules, pillars, etc. (since they need
    to know which master they connected to)
    """

    if self.connected:
        self.opts["pillar"] = yield salt.pillar.get_async_pillar(
            self.opts,
            self.opts["grains"],
            self.opts["id"],
            saltenv=self.opts["saltenv"],
            pillarenv=self.opts.get("pillarenv"),
        ).compile_pillar()

        # Ensure that the value of master is the one we passed in.
        # if pillar_opts is enabled then master could be overwritten
        # when compile_pillar is run.
        self.opts["master"] = master

        tag = "salt/deltaproxy/start"
        self._fire_master(tag=tag)

    if "proxy" not in self.opts["pillar"] and "proxy" not in self.opts:
        errmsg = (
            "No proxy key found in pillar or opts for id {}. Check your pillar/opts "
            "configuration and contents.  Salt-proxy aborted.".format(self.opts["id"])
        )
        log.error(errmsg)
        self._running = False
        raise SaltSystemExit(code=-1, msg=errmsg)

    if "proxy" not in self.opts:
        self.opts["proxy"] = self.opts["pillar"]["proxy"]

    self.opts = salt.utils.dictupdate.merge(
        self.opts,
        self.opts["pillar"],
        strategy=self.opts.get("proxy_merge_pillar_in_opts_strategy"),
        merge_lists=self.opts.get("proxy_deep_merge_pillar_in_opts", False),
    )

    if self.opts.get("proxy_mines_pillar"):
        # Even when not required, some details such as mine configuration
        # should be merged anyway whenever possible.
        if "mine_interval" in self.opts["pillar"]:
            self.opts["mine_interval"] = self.opts["pillar"]["mine_interval"]
        if "mine_functions" in self.opts["pillar"]:
            general_proxy_mines = self.opts.get("mine_functions", [])
            specific_proxy_mines = self.opts["pillar"]["mine_functions"]
            try:
                self.opts["mine_functions"] = general_proxy_mines + specific_proxy_mines
            except TypeError as terr:
                log.error(
                    "Unable to merge mine functions from the pillar in the opts, for proxy %s",
                    self.opts["id"],
                )

    fq_proxyname = self.opts["proxy"]["proxytype"]

    # Need to load the modules so they get all the dunder variables
    (
        self.functions,
        self.returners,
        self.function_errors,
        self.executors,
    ) = self._load_modules()

    # we can then sync any proxymodules down from the master
    # we do a sync_all here in case proxy code was installed by
    # SPM or was manually placed in /srv/salt/_modules etc.
    self.functions["saltutil.sync_all"](saltenv=self.opts["saltenv"])

    # Pull in the utils
    self.utils = salt.loader.utils(self.opts)

    # Then load the proxy module
    self.proxy = salt.loader.proxy(self.opts, utils=self.utils)

    # And re-load the modules so the __proxy__ variable gets injected
    (
        self.functions,
        self.returners,
        self.function_errors,
        self.executors,
    ) = self._load_modules()
    self.functions.pack["__proxy__"] = self.proxy
    self.proxy.pack["__salt__"] = self.functions
    self.proxy.pack["__ret__"] = self.returners
    self.proxy.pack["__pillar__"] = self.opts["pillar"]

    # Reload utils as well (chicken and egg, __utils__ needs __proxy__ and __proxy__ needs __utils__
    self.utils = salt.loader.utils(self.opts, proxy=self.proxy)
    self.proxy.pack["__utils__"] = self.utils

    # Reload all modules so all dunder variables are injected
    self.proxy.reload_modules()

    # Start engines here instead of in the Minion superclass __init__
    # This is because we need to inject the __proxy__ variable but
    # it is not setup until now.
    self.io_loop.spawn_callback(
        salt.engines.start_engines, self.opts, self.process_manager, proxy=self.proxy
    )

    proxy_init_func_name = "{}.init".format(fq_proxyname)
    proxy_shutdown_func_name = "{}.shutdown".format(fq_proxyname)
    if (
        proxy_init_func_name not in self.proxy
        or proxy_shutdown_func_name not in self.proxy
    ):
        errmsg = (
            "Proxymodule {} is missing an init() or a shutdown() or both. "
            "Check your proxymodule.  Salt-proxy aborted.".format(fq_proxyname)
        )
        log.error(errmsg)
        self._running = False
        raise SaltSystemExit(code=-1, msg=errmsg)

    self.module_executors = self.proxy.get(
        "{}.module_executors".format(fq_proxyname), lambda: []
    )()
    proxy_init_fn = self.proxy[proxy_init_func_name]
    proxy_init_fn(self.opts)

    self.opts["grains"] = salt.loader.grains(self.opts, proxy=self.proxy)

    self.mod_opts = self._prep_mod_opts()
    self.matchers = salt.loader.matchers(self.opts)
    self.beacons = salt.beacons.Beacon(self.opts, self.functions)
    uid = salt.utils.user.get_uid(user=self.opts.get("user", None))
    self.proc_dir = salt.minion.get_proc_dir(self.opts["cachedir"], uid=uid)

    if self.connected and self.opts["pillar"]:
        # The pillar has changed due to the connection to the master.
        # Reload the functions so that they can use the new pillar data.
        (
            self.functions,
            self.returners,
            self.function_errors,
            self.executors,
        ) = self._load_modules()
        if hasattr(self, "schedule"):
            self.schedule.functions = self.functions
            self.schedule.returners = self.returners

    if not hasattr(self, "schedule"):
        self.schedule = salt.utils.schedule.Schedule(
            self.opts,
            self.functions,
            self.returners,
            cleanup=[salt.minion.master_event(type="alive")],
            proxy=self.proxy,
            _subprocess_list=self.subprocess_list,
        )

    # add default scheduling jobs to the minions scheduler
    if self.opts["mine_enabled"] and "mine.update" in self.functions:
        self.schedule.add_job(
            {
                "__mine_interval": {
                    "function": "mine.update",
                    "minutes": self.opts["mine_interval"],
                    "jid_include": True,
                    "maxrunning": 2,
                    "run_on_start": True,
                    "return_job": self.opts.get("mine_return_job", False),
                }
            },
            persist=True,
        )
        log.info("Added mine.update to scheduler")
    else:
        self.schedule.delete_job("__mine_interval", persist=True)

    # add master_alive job if enabled
    if self.opts["transport"] != "tcp" and self.opts["master_alive_interval"] > 0:
        self.schedule.add_job(
            {
                salt.minion.master_event(type="alive", master=self.opts["master"]): {
                    "function": "status.master",
                    "seconds": self.opts["master_alive_interval"],
                    "jid_include": True,
                    "maxrunning": 1,
                    "return_job": False,
                    "kwargs": {"master": self.opts["master"], "connected": True},
                }
            },
            persist=True,
        )
        if (
            self.opts["master_failback"]
            and "master_list" in self.opts
            and self.opts["master"] != self.opts["master_list"][0]
        ):
            self.schedule.add_job(
                {
                    salt.minion.master_event(type="failback"): {
                        "function": "status.ping_master",
                        "seconds": self.opts["master_failback_interval"],
                        "jid_include": True,
                        "maxrunning": 1,
                        "return_job": False,
                        "kwargs": {"master": self.opts["master_list"][0]},
                    }
                },
                persist=True,
            )
        else:
            self.schedule.delete_job(
                salt.minion.master_event(type="failback"), persist=True
            )
    else:
        self.schedule.delete_job(
            salt.minion.master_event(type="alive", master=self.opts["master"]),
            persist=True,
        )
        self.schedule.delete_job(
            salt.minion.master_event(type="failback"), persist=True
        )

    # proxy keepalive
    proxy_alive_fn = fq_proxyname + ".alive"
    if (
        proxy_alive_fn in self.proxy
        and "status.proxy_reconnect" in self.functions
        and self.opts.get("proxy_keep_alive", True)
    ):
        # if `proxy_keep_alive` is either not specified, either set to False does not retry reconnecting
        self.schedule.add_job(
            {
                "__proxy_keepalive": {
                    "function": "status.proxy_reconnect",
                    "minutes": self.opts.get(
                        "proxy_keep_alive_interval", 1
                    ),  # by default, check once per minute
                    "jid_include": True,
                    "maxrunning": 1,
                    "return_job": False,
                    "kwargs": {"proxy_name": fq_proxyname},
                }
            },
            persist=True,
        )
        self.schedule.enable_schedule()
    else:
        self.schedule.delete_job("__proxy_keepalive", persist=True)

    #  Sync the grains here so the proxy can communicate them to the master
    self.functions["saltutil.sync_grains"](saltenv="base")
    self.grains_cache = self.opts["grains"]
    # Now setup the deltaproxies
    self.deltaproxy = {}
    self.deltaproxy_opts = {}
    self.deltaproxy_objs = {}
    self.proxy_grains = {}
    self.proxy_pillar = {}
    self.proxy_context = {}
    self.add_periodic_callback("cleanup", self.cleanup_subprocesses)
    for _id in self.opts["proxy"].get("ids", []):
        control_id = self.opts["id"]
        proxyopts = self.opts.copy()
        proxyopts["id"] = _id

        proxyopts = salt.config.proxy_config(
            self.opts["conf_file"], defaults=proxyopts, minion_id=_id
        )
        proxyopts["id"] = proxyopts["proxyid"] = _id

        proxyopts["subproxy"] = True

        self.proxy_context[_id] = {"proxy_id": _id}

        # We need grains first to be able to load pillar, which is where we keep the proxy
        # configurations
        self.proxy_grains[_id] = salt.loader.grains(
            proxyopts, proxy=self.proxy, context=self.proxy_context[_id]
        )
        self.proxy_pillar[_id] = yield salt.pillar.get_async_pillar(
            proxyopts,
            self.proxy_grains[_id],
            _id,
            saltenv=proxyopts["saltenv"],
            pillarenv=proxyopts.get("pillarenv"),
        ).compile_pillar()

        proxyopts["proxy"] = self.proxy_pillar[_id].get("proxy", {})

        # Remove ids
        proxyopts["proxy"].pop("ids", None)

        proxyopts["pillar"] = self.proxy_pillar[_id]
        proxyopts["grains"] = self.proxy_grains[_id]

        proxyopts["hash_id"] = self.opts["id"]

        _proxy_minion = ProxyMinion(proxyopts)
        _proxy_minion.proc_dir = salt.minion.get_proc_dir(
            proxyopts["cachedir"], uid=uid
        )

        _proxy_minion.proxy = salt.loader.proxy(
            proxyopts, utils=self.utils, context=self.proxy_context[_id]
        )
        _proxy_minion.subprocess_list = self.subprocess_list

        # And load the modules
        (
            _proxy_minion.functions,
            _proxy_minion.returners,
            _proxy_minion.function_errors,
            _proxy_minion.executors,
        ) = _proxy_minion._load_modules(
            opts=proxyopts, grains=proxyopts["grains"], context=self.proxy_context[_id]
        )

        # we can then sync any proxymodules down from the master
        # we do a sync_all here in case proxy code was installed by
        # SPM or was manually placed in /srv/salt/_modules etc.
        _proxy_minion.functions["saltutil.sync_all"](saltenv=self.opts["saltenv"])

        # And re-load the modules so the __proxy__ variable gets injected
        (
            _proxy_minion.functions,
            _proxy_minion.returners,
            _proxy_minion.function_errors,
            _proxy_minion.executors,
        ) = _proxy_minion._load_modules(
            opts=proxyopts, grains=proxyopts["grains"], context=self.proxy_context[_id]
        )

        _proxy_minion.functions.pack["__proxy__"] = _proxy_minion.proxy
        _proxy_minion.proxy.pack["__salt__"] = _proxy_minion.functions
        _proxy_minion.proxy.pack["__ret__"] = _proxy_minion.returners
        _proxy_minion.proxy.pack["__pillar__"] = proxyopts["pillar"]
        _proxy_minion.proxy.pack["__grains__"] = proxyopts["grains"]

        # Reload utils as well (chicken and egg, __utils__ needs __proxy__ and __proxy__ needs __utils__
        _proxy_minion.proxy.utils = salt.loader.utils(
            proxyopts, proxy=_proxy_minion.proxy, context=self.proxy_context[_id]
        )

        _proxy_minion.proxy.pack["__utils__"] = _proxy_minion.proxy.utils

        # Reload all modules so all dunder variables are injected
        _proxy_minion.proxy.reload_modules()

        _proxy_minion.connected = True

        _fq_proxyname = proxyopts["proxy"]["proxytype"]

        proxy_init_fn = _proxy_minion.proxy[_fq_proxyname + ".init"]
        proxy_init_fn(proxyopts)

        # Reload the grains
        self.proxy_grains[_id] = salt.loader.grains(
            proxyopts, proxy=_proxy_minion.proxy, context=self.proxy_context[_id]
        )
        proxyopts["grains"] = self.proxy_grains[_id]

        if not hasattr(_proxy_minion, "schedule"):
            _proxy_minion.schedule = salt.utils.schedule.Schedule(
                proxyopts,
                _proxy_minion.functions,
                _proxy_minion.returners,
                cleanup=[salt.minion.master_event(type="alive")],
                proxy=_proxy_minion.proxy,
                new_instance=True,
                _subprocess_list=_proxy_minion.subprocess_list,
            )

        self.deltaproxy_objs[_id] = _proxy_minion
        self.deltaproxy_opts[_id] = copy.deepcopy(proxyopts)

        # proxy keepalive
        _proxy_alive_fn = _fq_proxyname + ".alive"
        if (
            _proxy_alive_fn in _proxy_minion.proxy
            and "status.proxy_reconnect" in self.deltaproxy_objs[_id].functions
            and proxyopts.get("proxy_keep_alive", True)
        ):
            # if `proxy_keep_alive` is either not specified, either set to False does not retry reconnecting
            _proxy_minion.schedule.add_job(
                {
                    "__proxy_keepalive": {
                        "function": "status.proxy_reconnect",
                        "minutes": proxyopts.get(
                            "proxy_keep_alive_interval", 1
                        ),  # by default, check once per minute
                        "jid_include": True,
                        "maxrunning": 1,
                        "return_job": False,
                        "kwargs": {"proxy_name": _fq_proxyname},
                    }
                },
                persist=True,
            )
            _proxy_minion.schedule.enable_schedule()
        else:
            _proxy_minion.schedule.delete_job("__proxy_keepalive", persist=True)

    self.ready = True


def target(cls, minion_instance, opts, data, connected):
    """
    Handle targeting of the minion.

    Calling _thread_multi_return or _thread_return
    depending on a single or multiple commands.
    """
    log.debug(
        "Deltaproxy minion_instance %s(ID: %s). Target: %s",
        minion_instance,
        minion_instance.opts["id"],
        opts["id"],
    )

    if not hasattr(minion_instance, "proc_dir"):
        uid = salt.utils.user.get_uid(user=opts.get("user", None))
        minion_instance.proc_dir = salt.minion.get_proc_dir(opts["cachedir"], uid=uid)

    with tornado.stack_context.StackContext(minion_instance.ctx):
        if isinstance(data["fun"], tuple) or isinstance(data["fun"], list):
            ProxyMinion._thread_multi_return(minion_instance, opts, data)
        else:
            ProxyMinion._thread_return(minion_instance, opts, data)


def thread_return(cls, minion_instance, opts, data):
    """
    This method should be used as a threading target, start the actual
    minion side execution.
    """
    fn_ = os.path.join(minion_instance.proc_dir, data["jid"])

    if opts["multiprocessing"] and not salt.utils.platform.is_windows():

        # Shutdown the multiprocessing before daemonizing
        salt.log.setup.shutdown_multiprocessing_logging()

        # Reconfigure multiprocessing logging after daemonizing
        salt.log.setup.setup_multiprocessing_logging()

    salt.utils.process.appendproctitle(
        "{}._thread_return {}".format(cls.__name__, data["jid"])
    )

    sdata = {"pid": os.getpid()}
    sdata.update(data)
    log.info("Starting a new job with PID %s", sdata["pid"])
    with salt.utils.files.fopen(fn_, "w+b") as fp_:
        fp_.write(salt.payload.dumps(sdata))
    ret = {"success": False}
    function_name = data["fun"]
    executors = (
        data.get("module_executors")
        or getattr(minion_instance, "module_executors", [])
        or opts.get("module_executors", ["direct_call"])
    )
    allow_missing_funcs = any(
        [
            minion_instance.executors["{}.allow_missing_func".format(executor)](
                function_name
            )
            for executor in executors
            if "{}.allow_missing_func".format(executor) in minion_instance.executors
        ]
    )
    if function_name in minion_instance.functions or allow_missing_funcs is True:
        try:
            minion_blackout_violation = False
            if minion_instance.connected and minion_instance.opts["pillar"].get(
                "minion_blackout", False
            ):
                whitelist = minion_instance.opts["pillar"].get(
                    "minion_blackout_whitelist", []
                )
                # this minion is blacked out. Only allow saltutil.refresh_pillar and the whitelist
                if (
                    function_name != "saltutil.refresh_pillar"
                    and function_name not in whitelist
                ):
                    minion_blackout_violation = True
            # use minion_blackout_whitelist from grains if it exists
            if minion_instance.opts["grains"].get("minion_blackout", False):
                whitelist = minion_instance.opts["grains"].get(
                    "minion_blackout_whitelist", []
                )
                if (
                    function_name != "saltutil.refresh_pillar"
                    and function_name not in whitelist
                ):
                    minion_blackout_violation = True
            if minion_blackout_violation:
                raise SaltInvocationError(
                    'Minion in blackout mode. Set "minion_blackout" '
                    "to False in pillar or grains to resume operations. Only "
                    "saltutil.refresh_pillar allowed in blackout mode."
                )

            if function_name in minion_instance.functions:
                func = minion_instance.functions[function_name]
                args, kwargs = salt.minion.load_args_and_kwargs(func, data["arg"], data)
            else:
                # only run if function_name is not in minion_instance.functions and allow_missing_funcs is True
                func = function_name
                args, kwargs = data["arg"], data
            minion_instance.functions.pack["__context__"]["retcode"] = 0
            minion_instance.functions.pack["__opts__"] = opts
            if isinstance(executors, str):
                executors = [executors]
            elif not isinstance(executors, list) or not executors:
                raise SaltInvocationError(
                    "Wrong executors specification: {}. String or non-empty list expected".format(
                        executors
                    )
                )
            if opts.get("sudo_user", "") and executors[-1] != "sudo":
                executors[-1] = "sudo"  # replace the last one with sudo
            log.debug("Executors list %s", executors)

            for name in executors:
                fname = "{}.execute".format(name)
                if fname not in minion_instance.executors:
                    raise SaltInvocationError(
                        "Executor '{}' is not available".format(name)
                    )

                return_data = minion_instance.executors[fname](
                    opts, data, func, args, kwargs
                )
                if return_data is not None:
                    break

            if isinstance(return_data, types.GeneratorType):
                ind = 0
                iret = {}
                for single in return_data:
                    if isinstance(single, dict) and isinstance(iret, dict):
                        iret.update(single)
                    else:
                        if not iret:
                            iret = []
                        iret.append(single)
                    tag = tagify([data["jid"], "prog", opts["id"], str(ind)], "job")
                    event_data = {"return": single}
                    minion_instance._fire_master(event_data, tag)
                    ind += 1
                ret["return"] = iret
            else:
                ret["return"] = return_data

            retcode = minion_instance.functions.pack["__context__"].get(
                "retcode", salt.defaults.exitcodes.EX_OK
            )
            if retcode == salt.defaults.exitcodes.EX_OK:
                # No nonzero retcode in __context__ dunder. Check if return
                # is a dictionary with a "result" or "success" key.
                try:
                    func_result = all(
                        return_data.get(x, True) for x in ("result", "success")
                    )
                except Exception:  # pylint: disable=broad-except
                    # return data is not a dict
                    func_result = True
                if not func_result:
                    retcode = salt.defaults.exitcodes.EX_GENERIC

            ret["retcode"] = retcode
            ret["success"] = retcode == salt.defaults.exitcodes.EX_OK
        except CommandNotFoundError as exc:
            msg = 'Command required for "{}" not found'.format(function_name)
            log.debug(msg, exc_info=True)
            ret["return"] = "{}: {}".format(msg, exc)
            ret["out"] = "nested"
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
        except CommandExecutionError as exc:
            log.error(
                'A command in "%s" had a problem: %s',
                function_name,
                exc,
                exc_info_on_loglevel=logging.DEBUG,
            )
            ret["return"] = "ERROR: {}".format(exc)
            ret["out"] = "nested"
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
        except SaltInvocationError as exc:
            log.error(
                'Problem executing "%s": %s',
                function_name,
                exc,
                exc_info_on_loglevel=logging.DEBUG,
            )
            ret["return"] = 'ERROR executing "{}": {}'.format(function_name, exc)
            ret["out"] = "nested"
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
        except TypeError as exc:
            msg = "Passed invalid arguments to {}: {}\n{}".format(
                function_name, exc, func.__doc__ or ""
            )
            log.warning(msg, exc_info_on_loglevel=logging.DEBUG)
            ret["return"] = msg
            ret["out"] = "nested"
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
        except Exception:  # pylint: disable=broad-except
            msg = "The minion function caused an exception"
            log.warning(msg, exc_info=True)
            salt.utils.error.fire_exception(
                salt.exceptions.MinionError(msg), opts, job=data
            )
            ret["return"] = "{}: {}".format(msg, traceback.format_exc())
            ret["out"] = "nested"
            ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
    else:
        docs = minion_instance.functions["sys.doc"]("{}*".format(function_name))
        if docs:
            docs[function_name] = minion_instance.functions.missing_fun_string(
                function_name
            )
            ret["return"] = docs
        else:
            ret["return"] = minion_instance.functions.missing_fun_string(function_name)
            mod_name = function_name.split(".")[0]
            if mod_name in minion_instance.function_errors:
                ret["return"] += ' Possible reasons: "{}"'.format(
                    minion_instance.function_errors[mod_name]
                )
        ret["success"] = False
        ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
        ret["out"] = "nested"

    ret["jid"] = data["jid"]
    ret["fun"] = data["fun"]
    ret["fun_args"] = data["arg"]
    if "master_id" in data:
        ret["master_id"] = data["master_id"]
    if "metadata" in data:
        if isinstance(data["metadata"], dict):
            ret["metadata"] = data["metadata"]
        else:
            log.warning("The metadata parameter must be a dictionary. Ignoring.")
    if minion_instance.connected:
        minion_instance._return_pub(ret, timeout=minion_instance._return_retry_timer())

    # Add default returners from minion config
    # Should have been coverted to comma-delimited string already
    if isinstance(opts.get("return"), str):
        if data["ret"]:
            data["ret"] = ",".join((data["ret"], opts["return"]))
        else:
            data["ret"] = opts["return"]

    # TODO: make a list? Seems odd to split it this late :/
    if data["ret"] and isinstance(data["ret"], str):
        if "ret_config" in data:
            ret["ret_config"] = data["ret_config"]
        if "ret_kwargs" in data:
            ret["ret_kwargs"] = data["ret_kwargs"]
        ret["id"] = opts["id"]
        for returner in set(data["ret"].split(",")):
            try:
                returner_str = "{}.returner".format(returner)
                if returner_str in minion_instance.returners:
                    minion_instance.returners[returner_str](ret)
                else:
                    returner_err = minion_instance.returners.missing_fun_string(
                        returner_str
                    )
                    log.error(
                        "Returner %s could not be loaded: %s",
                        returner_str,
                        returner_err,
                    )
            except Exception as exc:  # pylint: disable=broad-except
                log.exception("The return failed for job %s: %s", data["jid"], exc)


def thread_multi_return(cls, minion_instance, opts, data):
    """
    This method should be used as a threading target, start the actual
    minion side execution.
    """
    fn_ = os.path.join(minion_instance.proc_dir, data["jid"])

    if opts["multiprocessing"] and not salt.utils.platform.is_windows():
        # Shutdown the multiprocessing before daemonizing
        salt.log.setup.shutdown_multiprocessing_logging()

        salt.utils.process.daemonize_if(opts)

        # Reconfigure multiprocessing logging after daemonizing
        salt.log.setup.setup_multiprocessing_logging()

    salt.utils.process.appendproctitle(
        "{}._thread_multi_return {}".format(cls.__name__, data["jid"])
    )

    sdata = {"pid": os.getpid()}
    sdata.update(data)
    log.info("Starting a new job with PID %s", sdata["pid"])
    with salt.utils.files.fopen(fn_, "w+b") as fp_:
        fp_.write(salt.payload.dumps(sdata))

    multifunc_ordered = opts.get("multifunc_ordered", False)
    num_funcs = len(data["fun"])
    if multifunc_ordered:
        ret = {
            "return": [None] * num_funcs,
            "retcode": [None] * num_funcs,
            "success": [False] * num_funcs,
        }
    else:
        ret = {"return": {}, "retcode": {}, "success": {}}

    for ind in range(0, num_funcs):
        if not multifunc_ordered:
            ret["success"][data["fun"][ind]] = False
        try:
            minion_blackout_violation = False
            if minion_instance.connected and minion_instance.opts["pillar"].get(
                "minion_blackout", False
            ):
                whitelist = minion_instance.opts["pillar"].get(
                    "minion_blackout_whitelist", []
                )
                # this minion is blacked out. Only allow saltutil.refresh_pillar and the whitelist
                if (
                    data["fun"][ind] != "saltutil.refresh_pillar"
                    and data["fun"][ind] not in whitelist
                ):
                    minion_blackout_violation = True
            elif minion_instance.opts["grains"].get("minion_blackout", False):
                whitelist = minion_instance.opts["grains"].get(
                    "minion_blackout_whitelist", []
                )
                if (
                    data["fun"][ind] != "saltutil.refresh_pillar"
                    and data["fun"][ind] not in whitelist
                ):
                    minion_blackout_violation = True
            if minion_blackout_violation:
                raise SaltInvocationError(
                    'Minion in blackout mode. Set "minion_blackout" '
                    "to False in pillar or grains to resume operations. Only "
                    "saltutil.refresh_pillar allowed in blackout mode."
                )

            func = minion_instance.functions[data["fun"][ind]]

            args, kwargs = salt.minion.load_args_and_kwargs(
                func, data["arg"][ind], data
            )
            minion_instance.functions.pack["__context__"]["retcode"] = 0
            key = ind if multifunc_ordered else data["fun"][ind]
            ret["return"][key] = func(*args, **kwargs)
            retcode = minion_instance.functions.pack["__context__"].get("retcode", 0)
            if retcode == 0:
                # No nonzero retcode in __context__ dunder. Check if return
                # is a dictionary with a "result" or "success" key.
                try:
                    func_result = all(
                        ret["return"][key].get(x, True) for x in ("result", "success")
                    )
                except Exception:  # pylint: disable=broad-except
                    # return data is not a dict
                    func_result = True
                if not func_result:
                    retcode = 1

            ret["retcode"][key] = retcode
            ret["success"][key] = retcode == 0
        except Exception as exc:  # pylint: disable=broad-except
            trb = traceback.format_exc()
            log.warning("The minion function caused an exception: %s", exc)
            if multifunc_ordered:
                ret["return"][ind] = trb
            else:
                ret["return"][data["fun"][ind]] = trb
        ret["jid"] = data["jid"]
        ret["fun"] = data["fun"]
        ret["fun_args"] = data["arg"]
    if "metadata" in data:
        ret["metadata"] = data["metadata"]
    if minion_instance.connected:
        minion_instance._return_pub(ret, timeout=minion_instance._return_retry_timer())
    if data["ret"]:
        if "ret_config" in data:
            ret["ret_config"] = data["ret_config"]
        if "ret_kwargs" in data:
            ret["ret_kwargs"] = data["ret_kwargs"]
        for returner in set(data["ret"].split(",")):
            ret["id"] = opts["id"]
            try:
                minion_instance.returners["{}.returner".format(returner)](ret)
            except Exception as exc:  # pylint: disable=broad-except
                log.error("The return failed for job %s: %s", data["jid"], exc)


def handle_payload(self, payload):
    """
    Verify the publication and then pass
    the payload along to _handle_decoded_payload.
    """
    if payload is not None and payload["enc"] == "aes":
        # First handle payload for the "control" proxy
        if self._target_load(payload["load"]):
            self._handle_decoded_payload(payload["load"])

        # The following handles the sub-proxies
        sub_ids = self.opts["proxy"].get("ids", [self.opts["id"]])
        for _id in sub_ids:
            instance = self.deltaproxy_objs[_id]
            if instance._target_load(payload["load"]):
                instance._handle_decoded_payload(payload["load"])

    elif self.opts["zmq_filtering"]:
        # In the filtering enabled case, we"d like to know when minion sees something it shouldnt
        log.trace(
            "Broadcast message received not for this minion, Load: %s", payload["load"]
        )
    # If it"s not AES, and thus has not been verified, we do nothing.
    # In the future, we could add support for some clearfuncs, but
    # the minion currently has no need.


def handle_decoded_payload(self, data):
    """
    Override this method if you wish to handle the decoded data
    differently.
    """
    if "user" in data:
        log.info(
            "User %s Executing command %s with jid %s",
            data["user"],
            data["fun"],
            data["jid"],
        )
    else:
        log.info("Executing command %s with jid %s", data["fun"], data["jid"])
    log.debug("Command details %s", data)

    # Don"t duplicate jobs
    log.trace("Started JIDs: %s", self.jid_queue)
    if self.jid_queue is not None:
        if data["jid"] in self.jid_queue:
            return
        else:
            self.jid_queue.append(data["jid"])
            if len(self.jid_queue) > self.opts["minion_jid_queue_hwm"]:
                self.jid_queue.pop(0)

    if isinstance(data["fun"], str):
        if data["fun"] == "sys.reload_modules":
            (
                self.functions,
                self.returners,
                self.function_errors,
                self.executors,
            ) = self._load_modules()
            self.schedule.functions = self.functions
            self.schedule.returners = self.returners

    process_count_max = self.opts.get("process_count_max")
    if process_count_max > 0:
        process_count = self.subprocess_list.count
        once_logged = False
        while process_count >= process_count_max:
            if once_logged is False:
                log.debug(
                    "Maximum number of processes reached while executing jid %s, waiting...",
                    data["jid"],
                )
                once_logged = True
            yield tornado.gen.sleep(0.5)
            process_count = self.subprocess_list.count

    # We stash an instance references to allow for the socket
    # communication in Windows. You can"t pickle functions, and thus
    # python needs to be able to reconstruct the reference on the other
    # side.
    instance = self
    multiprocessing_enabled = self.opts.get("multiprocessing", True)
    if multiprocessing_enabled:
        if sys.platform.startswith("win"):
            # let python reconstruct the minion on the other side if we"re
            # running on windows
            instance = None
        process = SignalHandlingProcess(
            target=target, args=(self, instance, instance.opts, data, self.connected)
        )
    else:
        process = threading.Thread(
            target=target,
            args=(self, instance, instance.opts, data, self.connected),
            name=data["jid"],
        )

    process.start()
    process.name = "{}-Job-{}".format(process.name, data["jid"])
    self.subprocess_list.add(process)


def target_load(self, load):
    """
    Verify that the publication is valid.
    """
    for key in ("tgt", "jid", "fun", "arg"):
        if key not in load:
            return False
    # Verify that the publication applies to this minion

    # It"s important to note that the master does some pre-processing
    # to determine which minions to send a request to. So for example,
    # a "salt -G "grain_key:grain_val" test.ping" will invoke some
    # pre-processing on the master and this minion should not see the
    # publication if the master does not determine that it should.

    if "tgt_type" in load:
        match_func = self.matchers.get("{}_match.match".format(load["tgt_type"]), None)
        if match_func is None:
            return False
        if load["tgt_type"] in ("grain", "grain_pcre", "pillar"):
            delimiter = load.get("delimiter", DEFAULT_TARGET_DELIM)
            if not match_func(load["tgt"], delimiter=delimiter, opts=self.opts):
                return False
        elif not match_func(load["tgt"], opts=self.opts):
            return False
    else:
        if not self.matchers["glob_match.match"](load["tgt"], opts=self.opts):
            return False

    return True


# Main Minion Tune In
def tune_in(self, start=True):
    """
    Lock onto the publisher. This is the main event loop for the minion
    :rtype : None
    """
    for proxy_id in self.deltaproxy_objs:
        _proxy_minion = self.deltaproxy_objs[proxy_id]
        _proxy_minion.setup_scheduler()
        _proxy_minion.setup_beacons()
        _proxy_minion._state_run()
    super(ProxyMinion, self).tune_in(start=start)
