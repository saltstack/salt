"""
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
"""

import logging
import os
import sys
import traceback

import salt
import salt.channel.client
import salt.defaults.exitcodes
import salt.loader
import salt.minion
import salt.output
import salt.payload
import salt.utils.args
import salt.utils.files
import salt.utils.jid
import salt.utils.minion
import salt.utils.profile
import salt.utils.stringutils
from salt._logging import LOG_LEVELS
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltClientError,
    SaltInvocationError,
)

log = logging.getLogger(__name__)


class Caller:
    """
    Factory class to create salt-call callers for different transport
    """

    @staticmethod
    def factory(opts, **kwargs):
        return ZeroMQCaller(opts, **kwargs)


class BaseCaller:
    """
    Base class for caller transports
    """

    def __init__(self, opts):
        """
        Pass in command line opts
        """
        self.opts = opts
        self.opts["caller"] = True
        # Handle this here so other deeper code which might
        # be imported as part of the salt api doesn't do  a
        # nasty sys.exit() and tick off our developer users
        try:
            if self.opts.get("proxyid"):
                self.minion = salt.minion.SProxyMinion(opts)
            else:
                self.minion = salt.minion.SMinion(opts)
        except SaltClientError as exc:
            raise SystemExit(str(exc))

    def print_docs(self):
        """
        Pick up the documentation for all of the modules and print it out.
        """
        docs = {}
        for name, func in self.minion.functions.items():
            if name not in docs:
                if func.__doc__:
                    docs[name] = func.__doc__
        for name in sorted(docs):
            if name.startswith(self.opts.get("fun", "")):
                salt.utils.stringutils.print_cli(f"{name}:\n{docs[name]}\n")

    def print_grains(self):
        """
        Print out the grains
        """
        grains = self.minion.opts.get("grains") or salt.loader.grains(self.opts)
        salt.output.display_output({"local": grains}, "grains", self.opts)

    def run(self):
        """
        Execute the salt call logic
        """
        profiling_enabled = self.opts.get("profiling_enabled", False)
        try:
            pr = salt.utils.profile.activate_profile(profiling_enabled)
            try:
                ret = self.call()
            finally:
                salt.utils.profile.output_profile(
                    pr,
                    stats_path=self.opts.get("profiling_path", "/tmp/stats"),
                    stop=True,
                )
            out = ret.get("out", "nested")
            if self.opts["print_metadata"]:
                print_ret = ret
                out = "nested"
            else:
                print_ret = ret.get("return", {})
            salt.output.display_output(
                {"local": print_ret},
                out=out,
                opts=self.opts,
                _retcode=ret.get("retcode", 0),
            )
            # _retcode will be available in the kwargs of the outputter function
            if self.opts.get("retcode_passthrough", False):
                sys.exit(ret["retcode"])
            elif ret.get("retcode") != salt.defaults.exitcodes.EX_OK:
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        except SaltInvocationError as err:
            raise SystemExit(err)

    def call(self):
        """
        Call the module
        """
        if self.opts.get("resources_dispatch"):
            return self._call_with_resources()
        ret = {}
        fun = self.opts["fun"]
        ret["jid"] = salt.utils.jid.gen_jid(self.opts)
        proc_fn = os.path.join(
            salt.minion.get_proc_dir(self.opts["cachedir"]), ret["jid"]
        )
        if fun not in self.minion.functions:
            docs = self.minion.functions["sys.doc"](f"{fun}*")
            if docs:
                docs[fun] = self.minion.functions.missing_fun_string(fun)
                ret["out"] = "nested"
                ret["return"] = docs
                return ret
            sys.stderr.write(self.minion.functions.missing_fun_string(fun))
            mod_name = fun.split(".")[0]
            if mod_name in self.minion.function_errors:
                sys.stderr.write(
                    " Possible reasons: {}\n".format(
                        self.minion.function_errors[mod_name]
                    )
                )
            else:
                sys.stderr.write("\n")
            sys.exit(-1)
        metadata = self.opts.get("metadata")
        if metadata is not None:
            metadata = salt.utils.args.yamlify_arg(metadata)
        try:
            sdata = {
                "fun": fun,
                "pid": os.getpid(),
                "jid": ret["jid"],
                "tgt": "salt-call",
            }
            if metadata is not None:
                sdata["metadata"] = metadata
            args, kwargs = salt.minion.load_args_and_kwargs(
                self.minion.functions[fun],
                salt.utils.args.parse_input(
                    self.opts["arg"], no_parse=self.opts.get("no_parse", [])
                ),
                data=sdata,
            )
            try:
                with salt.utils.files.fopen(proc_fn, "w+b") as fp_:
                    fp_.write(salt.payload.dumps(sdata))
            except NameError:
                # Don't require msgpack with local
                pass
            except OSError:
                sys.stderr.write(
                    "Cannot write to process directory. "
                    "Do you have permissions to "
                    "write to {} ?\n".format(proc_fn)
                )
            func = self.minion.functions[fun]
            data = {"arg": args, "fun": fun}
            data.update(kwargs)
            executors = getattr(
                self.minion, "module_executors", []
            ) or salt.utils.args.yamlify_arg(
                self.opts.get("module_executors", "[direct_call]")
            )
            if self.opts.get("executor_opts", None):
                data["executor_opts"] = salt.utils.args.yamlify_arg(
                    self.opts["executor_opts"]
                )
            if isinstance(executors, str):
                executors = [executors]
            try:
                for name in executors:
                    fname = f"{name}.execute"
                    if fname not in self.minion.executors:
                        raise SaltInvocationError(f"Executor '{name}' is not available")
                    ret["return"] = self.minion.executors[fname](
                        self.opts, data, func, args, kwargs
                    )
                    if ret["return"] is not None:
                        break
            except TypeError as exc:
                sys.stderr.write(f"\nPassed invalid arguments: {exc}.\n\nUsage:\n")
                salt.utils.stringutils.print_cli(func.__doc__)
                active_level = LOG_LEVELS.get(
                    self.opts["log_level"].lower(), logging.ERROR
                )
                if active_level <= logging.DEBUG:
                    trace = traceback.format_exc()
                    sys.stderr.write(trace)
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)
            try:
                retcode = self.minion.executors.pack["__context__"].get("retcode", 0)
            except AttributeError:
                retcode = salt.defaults.exitcodes.EX_GENERIC

            if retcode == 0:
                # No nonzero retcode in __context__ dunder. Check if return
                # is a dictionary with a "result" or "success" key.
                try:
                    func_result = all(
                        ret["return"].get(x, True) for x in ("result", "success")
                    )
                except Exception:  # pylint: disable=broad-except
                    # return data is not a dict
                    func_result = True
                if not func_result:
                    retcode = salt.defaults.exitcodes.EX_GENERIC

            ret["retcode"] = retcode
        except CommandExecutionError as exc:
            msg = "Error running '{0}': {1}\n"
            active_level = LOG_LEVELS.get(self.opts["log_level"].lower(), logging.ERROR)
            if active_level <= logging.DEBUG:
                sys.stderr.write(traceback.format_exc())
            sys.stderr.write(msg.format(fun, exc))
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        except CommandNotFoundError as exc:
            msg = "Command required for '{0}' not found: {1}\n"
            sys.stderr.write(msg.format(fun, exc))
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        try:
            os.remove(proc_fn)
        except OSError:
            pass
        if hasattr(self.minion.functions[fun], "__outputter__"):
            oput = self.minion.functions[fun].__outputter__
            if isinstance(oput, str):
                ret["out"] = oput
        is_local = (
            self.opts["local"]
            or self.opts.get("file_client", False) == "local"
            or self.opts.get("master_type") == "disable"
        )
        returners = self.opts.get("return", "").split(",")
        if (not is_local) or returners:
            ret["id"] = self.opts["id"]
            ret["fun"] = fun
            ret["fun_args"] = self.opts["arg"]
            if metadata is not None:
                ret["metadata"] = metadata

        for returner in returners:
            if not returner:  # if we got an empty returner somehow, skip
                continue
            try:
                ret["success"] = True
                self.minion.returners[f"{returner}.returner"](ret)
            except Exception:  # pylint: disable=broad-except
                pass

        # return the job infos back up to the respective minion's master
        if not is_local and not self.opts.get("no_return_event", False):
            try:
                mret = ret.copy()
                mret["jid"] = "req"
                self.return_pub(mret)
            except Exception:  # pylint: disable=broad-except
                pass
        elif self.opts["cache_jobs"]:
            # Local job cache has been enabled
            salt.utils.minion.cache_jobs(self.opts, ret["jid"], ret)

        return ret

    def _call_with_resources(self):
        """
        Dispatch a salt-call invocation to the managing minion and/or its
        managed resources.

        Triggered by ``salt-call -r/--resources``.  Reuses
        ``Minion._resolve_resource_targets`` (exposed on ``MinionBase``) to
        compute the resource target list from ``--tgt`` / ``--tgt-type``,
        runs the function once per matched target, and combines results
        into the same shape the master CLI produces:

        * Non-merge functions (e.g. ``test.ping``) — ``{target_id: result}``
          when more than one target matched, bare value when only one did.
        * Merge functions (``state.apply``, ``state.highstate``, …) — one
          combined state dict per managing minion with each resource's
          state IDs prefixed by the resource id (matches the master
          merge-mode output exactly).
        """
        # Lazy import — only paid for on -r.
        import salt.loader.context as _loader_ctx  # noqa: PLC0415

        fun = self.opts["fun"]
        tgt = self.opts.get("resources_tgt", "*")
        tgt_type = self.opts.get("resources_tgt_type", "glob")

        # Resolve resources via the inherited helper (set up on MinionBase
        # so SMinion sees it). The helper consults the minion's pillar
        # (``opts["resources"]``) and per-resource grains cache.
        load = {"fun": fun, "tgt": tgt, "tgt_type": tgt_type}
        try:
            resource_targets = self.minion._resolve_resource_targets(load)
        except Exception:  # pylint: disable=broad-except
            log.exception("Failed to resolve resource targets for -r dispatch")
            resource_targets = []

        # When the target is purely T@/M@ compound terms (e.g.
        # ``T@dummy:dummy-01``), the managing minion should NOT also receive
        # the call — the operator is addressing resources, not the minion.
        # Mirrors Minion._target_load behaviour for master-driven jobs.
        is_pure_resource_tgt = self.minion._is_pure_resource_target(load)
        minion_matches = (
            False
            if is_pure_resource_tgt
            else self._target_matches_managing_minion(tgt, tgt_type)
        )

        # Argument parsing — pick any reachable copy of the function so
        # ``load_args_and_kwargs`` can introspect its signature.
        parsed = salt.utils.args.parse_input(
            self.opts["arg"], no_parse=self.opts.get("no_parse", [])
        )
        sig_func = self.minion.functions.get(fun)
        if sig_func is None:
            for loader in getattr(self.minion, "resource_loaders", {}).values():
                if fun in loader:
                    sig_func = loader[fun]
                    break
        if sig_func is None:
            sys.stderr.write(
                f"Function '{fun}' is not available on the managing minion or "
                "any per-resource loader.\n"
            )
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        args, kwargs = salt.minion.load_args_and_kwargs(sig_func, parsed)

        merge_funs = getattr(self.minion, "_MERGE_RESOURCE_FUNS", frozenset())
        is_merge = fun in merge_funs

        results = {}
        minion_id = self.minion.opts["id"]
        minion_ret = None

        # 1. Run the function on the managing minion if it matches the target.
        if minion_matches:
            try:
                minion_ret = self.minion.functions[fun](*args, **kwargs)
            except KeyError:
                minion_ret = f"Function '{fun}' is not available on the managing minion"
            except Exception as exc:  # pylint: disable=broad-except
                log.exception("Managing minion %s raised running %s", minion_id, fun)
                minion_ret = f"ERROR running {fun}: {exc}"
            results[minion_id] = minion_ret

        # 2. Run the function once per matched resource.
        resource_funcs = getattr(self.minion, "resource_funcs", None)
        for resource in resource_targets:
            rid = resource["id"]
            rtype = resource["type"]
            loader = getattr(self.minion, "resource_loaders", {}).get(rtype)
            if loader is None:
                results[rid] = (
                    f"No resource loader for type '{rtype}'. Ensure the "
                    "resource module exists and the minion is configured "
                    "to manage resources of this type."
                )
                continue
            if fun not in loader:
                results[rid] = (
                    f"Function '{fun}' is not supported for resource "
                    f"type '{rtype}'."
                )
                continue
            token = _loader_ctx.resource_ctxvar.set(resource)
            # Swap ``__grains__`` for this resource so functions like
            # ``grains.items`` return the resource's grains rather than the
            # managing minion's. Mirrors what Minion._thread_return does for
            # master-driven resource jobs (salt/minion.py ~2724).
            grains_fn = f"{rtype}.grains"
            prior_grains = loader.pack.get("__grains__")
            grains_swapped = False
            if resource_funcs is not None and grains_fn in resource_funcs:
                try:
                    loader.pack["__grains__"] = resource_funcs[grains_fn]()
                    grains_swapped = True
                except Exception as exc:  # pylint: disable=broad-except
                    log.warning(
                        "Failed to render grains for resource %s:%s — falling "
                        "back to managing minion's grains: %s",
                        rtype,
                        rid,
                        exc,
                    )
            try:
                results[rid] = loader[fun](*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.exception("Resource %s raised running %s", rid, fun)
                results[rid] = f"ERROR running {fun} for '{rid}': {exc}"
            finally:
                _loader_ctx.resource_ctxvar.reset(token)
                if grains_swapped:
                    if prior_grains is None:
                        loader.pack.pop("__grains__", None)
                    else:
                        loader.pack["__grains__"] = prior_grains

        # 3. For merge funs, fold per-resource state dicts into the
        #    managing minion's state dict with prefixed IDs (master shape).
        if is_merge and isinstance(minion_ret, dict):
            merged = self._merge_resource_state_results(
                minion_ret, resource_targets, results
            )
            return {"return": merged, "retcode": self._aggregate_retcode(merged)}

        # 4. Output: bare value if exactly one target ran, dict otherwise.
        if not results:
            return {"return": {}, "retcode": salt.defaults.exitcodes.EX_OK}
        if len(results) == 1:
            value = next(iter(results.values()))
            return {"return": value, "retcode": self._aggregate_retcode(value)}
        return {"return": results, "retcode": self._aggregate_retcode(results)}

    def _target_matches_managing_minion(self, tgt, tgt_type):
        """
        Return True if the target expression matches the managing minion's
        own id (so the function should also run on the minion in addition
        to its resources).

        Uses the minion's already-loaded matcher modules.  Falls back to
        ``False`` if the matcher isn't available — the operator still gets
        the per-resource dispatch.
        """
        matchers = getattr(self.minion, "matchers", None)
        if not matchers:
            return False
        match_fn = matchers.get(f"{tgt_type}_match.match")
        if match_fn is None:
            return False
        try:
            if tgt_type in ("grain", "grain_pcre", "pillar", "pillar_pcre"):
                delimiter = self.opts.get("delimiter") or ":"
                return bool(match_fn(tgt, delimiter=delimiter))
            return bool(match_fn(tgt))
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "Managing-minion match check failed for %s/%s",
                tgt_type,
                tgt,
                exc_info=True,
            )
            return False

    def _merge_resource_state_results(self, base, resource_targets, results):
        """
        Combine per-resource state-result dicts into ``base`` with each
        state ID prefixed by the resource id.  Matches the master merge
        path in :meth:`Minion._thread_return`.
        """
        # Bypass instance binding — the rebind in salt/minion.py loses the
        # @staticmethod wrapper, so accessing via the class avoids self
        # injection.
        prefix = salt.minion.Minion.__dict__["_prefix_resource_state_key"]
        if hasattr(prefix, "__func__"):
            prefix = prefix.__func__
        merged = dict(base)
        run_num_base = (
            max(
                (
                    v.get("__run_num__", 0)
                    for v in merged.values()
                    if isinstance(v, dict)
                ),
                default=0,
            )
            + 1
        )
        for resource in resource_targets:
            rid = resource["id"]
            r_ret = results.get(rid)
            if isinstance(r_ret, dict):
                for sid, sval in r_ret.items():
                    if isinstance(sval, dict):
                        entry = dict(sval)
                        entry["__run_num__"] = run_num_base
                    else:
                        entry = {
                            "result": True,
                            "comment": str(sval),
                            "name": f"[{rid}]",
                            "changes": {},
                            "__run_num__": run_num_base,
                        }
                    run_num_base += 1
                    merged[prefix(sid, rid)] = entry
            else:
                merged[f"no_|-{rid}_|-{rid}_|-None"] = {
                    "result": False,
                    "comment": str(r_ret),
                    "name": rid,
                    "changes": {},
                    "__run_num__": run_num_base,
                }
                run_num_base += 1
        return merged

    @staticmethod
    def _aggregate_retcode(payload):
        """
        Best-effort retcode aggregation across all targets.

        Returns ``EX_GENERIC`` when any target returned a falsy ``result`` /
        ``success`` key; otherwise ``EX_OK``.  Preserves the existing
        salt-call non-resource ``call()`` semantics where retcode is taken
        from ``__context__["retcode"]`` first; here we don't have a single
        context, so we fall back to inspecting the return shape.
        """
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, dict):
                    if not all(value.get(k, True) for k in ("result", "success")):
                        return salt.defaults.exitcodes.EX_GENERIC
        return salt.defaults.exitcodes.EX_OK


class ZeroMQCaller(BaseCaller):
    """
    Object to wrap the calling of local salt modules for the salt-call command
    """

    def __init__(self, opts):  # pylint: disable=useless-super-delegation
        """
        Pass in the command line options
        """
        super().__init__(opts)

    def return_pub(self, ret):
        """
        Return the data up to the master
        """
        with salt.channel.client.ReqChannel.factory(
            self.opts, usage="salt_call"
        ) as channel:
            load = {"cmd": "_return", "id": self.opts["id"]}
            for key, value in ret.items():
                load[key] = value
            channel.send(load)
