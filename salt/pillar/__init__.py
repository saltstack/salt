"""
Render the pillar data
"""

import collections
import copy
import fnmatch
import logging
import os
import sys
import time
import traceback

import tornado.gen

import salt.channel.client
import salt.fileclient
import salt.loader
import salt.minion
import salt.utils.args
import salt.utils.cache
import salt.utils.crypt
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.url
from salt.exceptions import SaltClientError
from salt.template import compile_template

# Even though dictupdate is imported, invoking salt.utils.dictupdate.merge here
# causes an UnboundLocalError. This should be investigated and fixed, but until
# then, leave the import directly below this comment intact.
from salt.utils.dictupdate import merge
from salt.utils.odict import OrderedDict
from salt.version import __version__

log = logging.getLogger(__name__)


def get_pillar(
    opts,
    grains,
    minion_id,
    saltenv=None,
    ext=None,
    funcs=None,
    pillar_override=None,
    pillarenv=None,
    extra_minion_data=None,
    clean_cache=False,
):
    """
    Return the correct pillar driver based on the file_client option
    """
    # When file_client is 'local' this makes the minion masterless
    # but sometimes we want the minion to read its files from the local
    # filesystem instead of asking for them from the master, but still
    # get commands from the master.
    # To enable this functionality set file_client=local and
    # use_master_when_local=True in the minion config.  Then here we override
    # the file client to be 'remote' for getting pillar.  If we don't do this
    # then the minion never sends the event that the master uses to update
    # its minion_data_cache.  If the master doesn't update the minion_data_cache
    # then the SSE salt-master plugin won't see any grains for those minions.
    file_client = opts["file_client"]
    if opts.get("master_type") == "disable" and file_client == "remote":
        file_client = "local"
    elif file_client == "local" and opts.get("use_master_when_local"):
        file_client = "remote"

    ptype = {"remote": RemotePillar, "local": Pillar}.get(file_client, Pillar)
    # If local pillar and we're caching, run through the cache system first
    log.debug("Determining pillar cache")
    if opts["pillar_cache"]:
        log.debug("get_pillar using pillar cache with ext: %s", ext)
        return PillarCache(
            opts,
            grains,
            minion_id,
            saltenv,
            ext=ext,
            functions=funcs,
            pillar_override=pillar_override,
            pillarenv=pillarenv,
            clean_cache=clean_cache,
            extra_minion_data=extra_minion_data,
        )
    return ptype(
        opts,
        grains,
        minion_id,
        saltenv,
        ext,
        functions=funcs,
        pillar_override=pillar_override,
        pillarenv=pillarenv,
        extra_minion_data=extra_minion_data,
    )


# TODO: migrate everyone to this one!
def get_async_pillar(
    opts,
    grains,
    minion_id,
    saltenv=None,
    ext=None,
    funcs=None,
    pillar_override=None,
    pillarenv=None,
    extra_minion_data=None,
    clean_cache=False,
):
    """
    Return the correct pillar driver based on the file_client option
    """
    file_client = opts["file_client"]
    if opts.get("master_type") == "disable" and file_client == "remote":
        file_client = "local"
    elif file_client == "local" and opts.get("use_master_when_local"):
        file_client = "remote"
    ptype = {"remote": AsyncRemotePillar, "local": AsyncPillar}.get(
        file_client, AsyncPillar
    )
    if file_client == "remote":
        # AsyncPillar does not currently support calls to PillarCache
        # clean_cache is a kwarg for PillarCache
        return ptype(
            opts,
            grains,
            minion_id,
            saltenv,
            ext,
            functions=funcs,
            pillar_override=pillar_override,
            pillarenv=pillarenv,
            extra_minion_data=extra_minion_data,
            clean_cache=clean_cache,
        )
    return ptype(
        opts,
        grains,
        minion_id,
        saltenv,
        ext,
        functions=funcs,
        pillar_override=pillar_override,
        pillarenv=pillarenv,
        extra_minion_data=extra_minion_data,
    )


class RemotePillarMixin:
    """
    Common remote pillar functionality
    """

    def get_ext_pillar_extra_minion_data(self, opts):
        """
        Returns the extra data from the minion's opts dict (the config file).

        This data will be passed to external pillar functions.
        """

        def get_subconfig(opts_key):
            """
            Returns a dict containing the opts key subtree, while maintaining
            the opts structure
            """
            ret_dict = aux_dict = {}
            config_val = opts
            subkeys = opts_key.split(":")
            # Build an empty dict with the opts path
            for subkey in subkeys[:-1]:
                aux_dict[subkey] = {}
                aux_dict = aux_dict[subkey]
                if not config_val.get(subkey):
                    # The subkey is not in the config
                    return {}
                config_val = config_val[subkey]
            if subkeys[-1] not in config_val:
                return {}
            aux_dict[subkeys[-1]] = config_val[subkeys[-1]]
            return ret_dict

        extra_data = {}
        if "pass_to_ext_pillars" in opts:
            if not isinstance(opts["pass_to_ext_pillars"], list):
                log.exception("'pass_to_ext_pillars' config is malformed.")
                raise SaltClientError("'pass_to_ext_pillars' config is malformed.")
            for key in opts["pass_to_ext_pillars"]:
                salt.utils.dictupdate.update(
                    extra_data,
                    get_subconfig(key),
                    recursive_update=True,
                    merge_lists=True,
                )
        log.trace("ext_pillar_extra_data = %s", extra_data)
        return extra_data


class AsyncRemotePillar(RemotePillarMixin):
    """
    Get the pillar from the master
    """

    def __init__(
        self,
        opts,
        grains,
        minion_id,
        saltenv,
        ext=None,
        functions=None,
        pillar_override=None,
        pillarenv=None,
        extra_minion_data=None,
        clean_cache=False,
    ):
        self.opts = opts
        self.opts["saltenv"] = saltenv
        self.ext = ext
        self.grains = grains
        self.minion_id = minion_id
        self.channel = salt.channel.client.AsyncReqChannel.factory(opts)
        if pillarenv is not None:
            self.opts["pillarenv"] = pillarenv
        self.pillar_override = pillar_override or {}
        if not isinstance(self.pillar_override, dict):
            self.pillar_override = {}
            log.error("Pillar data must be a dictionary")
        self.extra_minion_data = extra_minion_data or {}
        if not isinstance(self.extra_minion_data, dict):
            self.extra_minion_data = {}
            log.error("Extra minion data must be a dictionary")
        salt.utils.dictupdate.update(
            self.extra_minion_data,
            self.get_ext_pillar_extra_minion_data(opts),
            recursive_update=True,
            merge_lists=True,
        )
        self._closing = False
        self.clean_cache = clean_cache

    @tornado.gen.coroutine
    def compile_pillar(self):
        """
        Return a future which will contain the pillar data from the master
        """
        load = {
            "id": self.minion_id,
            "grains": self.grains,
            "saltenv": self.opts["saltenv"],
            "pillarenv": self.opts["pillarenv"],
            "pillar_override": self.pillar_override,
            "extra_minion_data": self.extra_minion_data,
            "ver": "2",
            "cmd": "_pillar",
        }
        if self.clean_cache:
            load["clean_cache"] = self.clean_cache
        if self.ext:
            load["ext"] = self.ext
        start = time.monotonic()
        try:
            ret_pillar = yield self.channel.crypted_transfer_decode_dictentry(
                load,
                dictkey="pillar",
            )
        except salt.crypt.AuthenticationError as exc:
            log.error(exc.message)
            raise SaltClientError("Exception getting pillar.")
        except salt.exceptions.SaltReqTimeoutError:
            raise SaltClientError(
                f"Pillar timed out after {int(time.monotonic() - start)} seconds"
            )
        except Exception:  # pylint: disable=broad-except
            log.exception("Exception getting pillar:")
            raise SaltClientError("Exception getting pillar.")

        if not isinstance(ret_pillar, dict):
            msg = "Got a bad pillar from master, type {}, expecting dict: {}".format(
                type(ret_pillar).__name__, ret_pillar
            )
            log.error(msg)
            # raise an exception! Pillar isn't empty, we can't sync it!
            raise SaltClientError(msg)
        raise tornado.gen.Return(ret_pillar)

    def destroy(self):
        if self._closing:
            return

        self._closing = True
        self.channel.close()

    # pylint: disable=W1701
    def __del__(self):
        self.destroy()

    # pylint: enable=W1701


class RemotePillar(RemotePillarMixin):
    """
    Get the pillar from the master
    """

    def __init__(
        self,
        opts,
        grains,
        minion_id,
        saltenv,
        ext=None,
        functions=None,
        pillar_override=None,
        pillarenv=None,
        extra_minion_data=None,
    ):
        self.opts = opts
        self.opts["saltenv"] = saltenv
        self.ext = ext
        self.grains = grains
        self.minion_id = minion_id
        self.channel = salt.channel.client.ReqChannel.factory(opts)
        if pillarenv is not None:
            self.opts["pillarenv"] = pillarenv
        self.pillar_override = pillar_override or {}
        if not isinstance(self.pillar_override, dict):
            self.pillar_override = {}
            log.error("Pillar data must be a dictionary")
        self.extra_minion_data = extra_minion_data or {}
        if not isinstance(self.extra_minion_data, dict):
            self.extra_minion_data = {}
            log.error("Extra minion data must be a dictionary")
        salt.utils.dictupdate.update(
            self.extra_minion_data,
            self.get_ext_pillar_extra_minion_data(opts),
            recursive_update=True,
            merge_lists=True,
        )
        self._closing = False

    def compile_pillar(self):
        """
        Return the pillar data from the master
        """
        load = {
            "id": self.minion_id,
            "grains": self.grains,
            "saltenv": self.opts["saltenv"],
            "pillarenv": self.opts["pillarenv"],
            "pillar_override": self.pillar_override,
            "extra_minion_data": self.extra_minion_data,
            "ver": "2",
            "cmd": "_pillar",
        }
        if self.ext:
            load["ext"] = self.ext

        start = time.monotonic()
        try:
            ret_pillar = self.channel.crypted_transfer_decode_dictentry(
                load,
                dictkey="pillar",
            )
        except salt.crypt.AuthenticationError as exc:
            log.error(exc.message)
            raise SaltClientError("Exception getting pillar.")
        except salt.exceptions.SaltReqTimeoutError:
            raise SaltClientError(
                f"Pillar timed out after {int(time.monotonic() - start)} seconds"
            )
        except Exception:  # pylint: disable=broad-except
            log.exception("Exception getting pillar:")
            raise SaltClientError("Exception getting pillar.")

        if not isinstance(ret_pillar, dict):
            log.error(
                "Got a bad pillar from master, type %s, expecting dict: %s",
                type(ret_pillar).__name__,
                ret_pillar,
            )
            return {}
        return ret_pillar

    def destroy(self):
        if hasattr(self, "_closing") and self._closing:
            return

        self._closing = True
        self.channel.close()

    # pylint: disable=W1701
    def __del__(self):
        self.destroy()

    # pylint: enable=W1701


class PillarCache:
    """
    Return a cached pillar if it exists, otherwise cache it.

    Pillar caches are structed in two diminensions: minion_id with a dict of
    saltenvs. Each saltenv contains a pillar dict

    Example data structure:

    ```
    {'minion_1':
        {'base': {'pilar_key_1' 'pillar_val_1'}
    }
    """

    # TODO ABC?
    def __init__(
        self,
        opts,
        grains,
        minion_id,
        saltenv,
        ext=None,
        functions=None,
        pillar_override=None,
        pillarenv=None,
        extra_minion_data=None,
        clean_cache=False,
    ):
        # Yes, we need all of these because we need to route to the Pillar object
        # if we have no cache. This is another refactor target.

        # Go ahead and assign these because they may be needed later
        self.opts = opts
        self.grains = grains
        self.minion_id = minion_id
        self.ext = ext
        self.functions = functions
        self.pillar_override = pillar_override
        self.pillarenv = pillarenv
        self.clean_cache = clean_cache
        self.extra_minion_data = extra_minion_data

        if saltenv is None:
            self.saltenv = "base"
        else:
            self.saltenv = saltenv

        # Determine caching backend
        self.cache = salt.utils.cache.CacheFactory.factory(
            self.opts["pillar_cache_backend"],
            self.opts["pillar_cache_ttl"],
            minion_cache_path=self._minion_cache_path(minion_id),
        )

    def _minion_cache_path(self, minion_id):
        """
        Return the path to the cache file for the minion.

        Used only for disk-based backends
        """
        return os.path.join(self.opts["cachedir"], "pillar_cache", minion_id)

    def fetch_pillar(self):
        """
        In the event of a cache miss, we need to incur the overhead of caching
        a new pillar.
        """
        log.debug("Pillar cache getting external pillar with ext: %s", self.ext)
        fresh_pillar = Pillar(
            self.opts,
            self.grains,
            self.minion_id,
            self.saltenv,
            ext=self.ext,
            functions=self.functions,
            pillar_override=self.pillar_override,
            pillarenv=self.pillarenv,
            extra_minion_data=self.extra_minion_data,
        )
        return fresh_pillar.compile_pillar()

    def clear_pillar(self):
        """
        Clear the cache
        """
        self.cache.clear()

        return True

    def compile_pillar(self, *args, **kwargs):  # Will likely just be pillar_dirs
        if self.clean_cache:
            self.clear_pillar()
        log.debug(
            "Scanning pillar cache for information about minion %s and pillarenv %s",
            self.minion_id,
            self.pillarenv,
        )
        if self.opts["pillar_cache_backend"] == "memory":
            cache_dict = self.cache
        else:
            cache_dict = self.cache._dict

        log.debug("Scanning cache: %s", cache_dict)
        # Check the cache!
        if self.minion_id in self.cache:  # Keyed by minion_id
            # TODO Compare grains, etc?
            if self.pillarenv in self.cache[self.minion_id]:
                # We have a cache hit! Send it back.
                log.debug(
                    "Pillar cache hit for minion %s and pillarenv %s",
                    self.minion_id,
                    self.pillarenv,
                )
                return self.cache[self.minion_id][self.pillarenv]
            else:
                # We found the minion but not the env. Store it.
                fresh_pillar = self.fetch_pillar()

                minion_cache = self.cache[self.minion_id]
                minion_cache[self.pillarenv] = fresh_pillar
                self.cache[self.minion_id] = minion_cache

                log.debug(
                    "Pillar cache miss for pillarenv %s for minion %s",
                    self.pillarenv,
                    self.minion_id,
                )
                return fresh_pillar
        else:
            # We haven't seen this minion yet in the cache. Store it.
            fresh_pillar = self.fetch_pillar()
            self.cache[self.minion_id] = {self.pillarenv: fresh_pillar}
            log.debug("Pillar cache miss for minion %s", self.minion_id)
            log.debug("Current pillar cache: %s", cache_dict)  # FIXME hack!
            return fresh_pillar


class Pillar:
    """
    Read over the pillar top files and render the pillar data
    """

    def __init__(
        self,
        opts,
        grains,
        minion_id,
        saltenv,
        ext=None,
        functions=None,
        pillar_override=None,
        pillarenv=None,
        extra_minion_data=None,
    ):
        self.minion_id = minion_id
        self.ext = ext
        if pillarenv is None:
            if opts.get("pillarenv_from_saltenv", False):
                opts["pillarenv"] = saltenv
        # use the local file client
        self.opts = self.__gen_opts(opts, grains, saltenv=saltenv, pillarenv=pillarenv)
        self.saltenv = saltenv
        self.client = salt.fileclient.get_file_client(self.opts, True)
        self.fileclient = salt.fileclient.get_file_client(self.opts, False)
        self.avail = self.__gather_avail()

        if opts.get("file_client", "") == "local" and not opts.get(
            "use_master_when_local", False
        ):
            opts["grains"] = grains

        # if we didn't pass in functions, lets load them
        if functions is None:
            utils = salt.loader.utils(opts, file_client=self.client)
            if opts.get("file_client", "") == "local":
                self.functions = salt.loader.minion_mods(
                    opts,
                    utils=utils,
                    file_client=salt.fileclient.ContextlessFileClient(self.fileclient),
                )
            else:
                self.functions = salt.loader.minion_mods(
                    self.opts,
                    utils=utils,
                    file_client=salt.fileclient.ContextlessFileClient(self.fileclient),
                )
        else:
            self.functions = functions

        self.opts["minion_id"] = minion_id
        self.matchers = salt.loader.matchers(self.opts)
        self.rend = salt.loader.render(
            self.opts, self.functions, self.client, file_client=self.client
        )
        ext_pillar_opts = copy.deepcopy(self.opts)
        # Keep the incoming opts ID intact, ie, the master id
        if "id" in opts:
            ext_pillar_opts["id"] = opts["id"]
        self.merge_strategy = "smart"
        if opts.get("pillar_source_merging_strategy"):
            self.merge_strategy = opts["pillar_source_merging_strategy"]

        self.ext_pillars = salt.loader.pillars(ext_pillar_opts, self.functions)
        self.ignored_pillars = {}
        self.pillar_override = pillar_override or {}
        if not isinstance(self.pillar_override, dict):
            self.pillar_override = {}
            log.error("Pillar data must be a dictionary")
        self.extra_minion_data = extra_minion_data or {}
        if not isinstance(self.extra_minion_data, dict):
            self.extra_minion_data = {}
            log.error("Extra minion data must be a dictionary")
        self._closing = False

    def __valid_on_demand_ext_pillar(self, opts):
        """
        Check to see if the on demand external pillar is allowed
        """
        if not isinstance(self.ext, dict):
            log.error("On-demand pillar %s is not formatted as a dictionary", self.ext)
            return False

        on_demand = opts.get("on_demand_ext_pillar", [])
        try:
            invalid_on_demand = {x for x in self.ext if x not in on_demand}
        except TypeError:
            # Prevent traceback when on_demand_ext_pillar option is malformed
            log.error(
                "The 'on_demand_ext_pillar' configuration option is "
                "malformed, it should be a list of ext_pillar module names"
            )
            return False

        if invalid_on_demand:
            log.error(
                "The following ext_pillar modules are not allowed for "
                "on-demand pillar data: %s. Valid on-demand ext_pillar "
                "modules are: %s. The valid modules can be adjusted by "
                "setting the 'on_demand_ext_pillar' config option.",
                ", ".join(sorted(invalid_on_demand)),
                ", ".join(on_demand),
            )
            return False
        return True

    def __gather_avail(self):
        """
        Gather the lists of available sls data from the master
        """
        avail = {}
        for saltenv in self._get_envs():
            avail[saltenv] = self.client.list_states(saltenv)
        return avail

    def __gen_opts(self, opts_in, grains, saltenv=None, ext=None, pillarenv=None):
        """
        The options need to be altered to conform to the file client
        """
        opts = copy.deepcopy(opts_in)
        opts["file_client"] = "local"
        if not grains:
            opts["grains"] = {}
        else:
            opts["grains"] = grains
        # Allow minion/CLI saltenv/pillarenv to take precedence over master
        opts["saltenv"] = saltenv if saltenv is not None else opts.get("saltenv")
        opts["pillarenv"] = (
            pillarenv if pillarenv is not None else opts.get("pillarenv")
        )
        opts["id"] = self.minion_id
        if opts["state_top"].startswith("salt://"):
            opts["state_top"] = opts["state_top"]
        elif opts["state_top"].startswith("/"):
            opts["state_top"] = salt.utils.url.create(opts["state_top"][1:])
        else:
            opts["state_top"] = salt.utils.url.create(opts["state_top"])
        if self.ext and self.__valid_on_demand_ext_pillar(opts):
            if "ext_pillar" in opts:
                opts["ext_pillar"].append(self.ext)
            else:
                opts["ext_pillar"] = [self.ext]
        if "__env__" in opts["pillar_roots"]:
            env = opts.get("pillarenv") or opts.get("saltenv") or "base"
            if env not in opts["pillar_roots"]:
                log.debug(
                    "pillar environment '%s' maps to __env__ pillar_roots directory",
                    env,
                )
                opts["pillar_roots"][env] = opts["pillar_roots"].pop("__env__")
                for idx, root in enumerate(opts["pillar_roots"][env]):
                    opts["pillar_roots"][env][idx] = opts["pillar_roots"][env][
                        idx
                    ].replace("__env__", env)
            else:
                log.debug(
                    "pillar_roots __env__ ignored (environment '%s' found in pillar_roots)",
                    env,
                )
                opts["pillar_roots"].pop("__env__")
        return opts

    def _get_envs(self):
        """
        Pull the file server environments out of the master options
        """
        envs = ["base"]
        if "pillar_roots" in self.opts:
            envs.extend([x for x in list(self.opts["pillar_roots"]) if x not in envs])
        return envs

    def get_tops(self):
        """
        Gather the top files
        """
        tops = collections.defaultdict(list)
        include = collections.defaultdict(list)
        done = collections.defaultdict(list)
        errors = []
        # Gather initial top files
        try:
            saltenvs = set()
            if self.opts["pillarenv"]:
                # If the specified pillarenv is not present in the available
                # pillar environments, do not cache the pillar top file.
                if self.opts["pillarenv"] not in self.opts["pillar_roots"]:
                    log.debug(
                        "pillarenv '%s' not found in the configured pillar "
                        "environments (%s)",
                        self.opts["pillarenv"],
                        ", ".join(self.opts["pillar_roots"]),
                    )
                else:
                    saltenvs.add(self.opts["pillarenv"])
            else:
                saltenvs.update(self._get_envs())
                if self.opts.get("pillar_source_merging_strategy", None) == "none":
                    saltenvs &= {self.saltenv or "base"}

            for saltenv in saltenvs:
                top = self.client.cache_file(self.opts["state_top"], saltenv)
                if top:
                    tops[saltenv].append(
                        compile_template(
                            top,
                            self.rend,
                            self.opts["renderer"],
                            self.opts["renderer_blacklist"],
                            self.opts["renderer_whitelist"],
                            saltenv=saltenv,
                            _pillar_rend=True,
                        )
                    )
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(f"Rendering Primary Top file failed, render error:\n{exc}")
            log.exception("Pillar rendering failed for minion %s", self.minion_id)

        # Search initial top files for includes
        for saltenv, ctops in tops.items():
            for ctop in ctops:
                if "include" not in ctop:
                    continue
                for sls in ctop["include"]:
                    include[saltenv].append(sls)
                ctop.pop("include")
        # Go through the includes and pull out the extra tops and add them
        while include:
            pops = []
            for saltenv, states in include.items():
                pops.append(saltenv)
                if not states:
                    continue
                for sls in states:
                    if sls in done[saltenv]:
                        continue
                    try:
                        tops[saltenv].append(
                            compile_template(
                                self.client.get_state(sls, saltenv).get("dest", False),
                                self.rend,
                                self.opts["renderer"],
                                self.opts["renderer_blacklist"],
                                self.opts["renderer_whitelist"],
                                saltenv=saltenv,
                                _pillar_rend=True,
                            )
                        )
                    except Exception as exc:  # pylint: disable=broad-except
                        errors.append(
                            "Rendering Top file {} failed, render error:\n{}".format(
                                sls, exc
                            )
                        )
                    done[saltenv].append(sls)
            for saltenv in pops:
                if saltenv in include:
                    include.pop(saltenv)

        return tops, errors

    def merge_tops(self, tops):
        """
        Cleanly merge the top files
        """
        top = collections.defaultdict(OrderedDict)
        orders = collections.defaultdict(OrderedDict)
        for ctops in tops.values():
            for ctop in ctops:
                for saltenv, targets in ctop.items():
                    if saltenv == "include":
                        continue
                    for tgt in targets:
                        matches = []
                        states = OrderedDict()
                        orders[saltenv][tgt] = 0
                        ignore_missing = False
                        for comp in ctop[saltenv][tgt]:
                            if isinstance(comp, dict):
                                if "match" in comp:
                                    matches.append(comp)
                                if "order" in comp:
                                    order = comp["order"]
                                    if not isinstance(order, int):
                                        try:
                                            order = int(order)
                                        except ValueError:
                                            order = 0
                                    orders[saltenv][tgt] = order
                                if comp.get("ignore_missing", False):
                                    ignore_missing = True
                            if isinstance(comp, str):
                                states[comp] = True
                        if ignore_missing:
                            if saltenv not in self.ignored_pillars:
                                self.ignored_pillars[saltenv] = []
                            self.ignored_pillars[saltenv].extend(states.keys())
                        top[saltenv][tgt] = matches
                        top[saltenv][tgt].extend(states)
        return self.sort_top_targets(top, orders)

    def sort_top_targets(self, top, orders):
        """
        Returns the sorted high data from the merged top files
        """
        sorted_top = collections.defaultdict(OrderedDict)
        # pylint: disable=cell-var-from-loop
        for saltenv, targets in top.items():
            sorted_targets = sorted(targets, key=lambda target: orders[saltenv][target])
            for target in sorted_targets:
                sorted_top[saltenv][target] = targets[target]
        # pylint: enable=cell-var-from-loop
        return sorted_top

    def get_top(self):
        """
        Returns the high data derived from the top file
        """
        tops, errors = self.get_tops()
        try:
            merged_tops = self.merge_tops(tops)
        except TypeError as err:
            merged_tops = OrderedDict()
            errors.append("Error encountered while rendering pillar top file.")
        return merged_tops, errors

    def top_matches(self, top, reload=False):
        """
        Search through the top high data for matches and return the states
        that this minion needs to execute.

        Returns:
        {'saltenv': ['state1', 'state2', ...]}

        reload
            Reload the matcher loader
        """
        matches = {}
        if reload:
            self.matchers = salt.loader.matchers(self.opts)
        for saltenv, body in top.items():
            if self.opts["pillarenv"]:
                if saltenv != self.opts["pillarenv"]:
                    continue
            for match, data in body.items():
                if self.matchers["confirm_top.confirm_top"](
                    match,
                    data,
                    self.opts.get("nodegroups", {}),
                ):
                    if saltenv not in matches:
                        matches[saltenv] = env_matches = []
                    else:
                        env_matches = matches[saltenv]
                    for item in data:
                        if isinstance(item, str) and item not in env_matches:
                            env_matches.append(item)
        return matches

    def render_pstate(self, sls, saltenv, mods, defaults=None):
        """
        Collect a single pillar sls file and render it
        """
        if defaults is None:
            defaults = {}
        err = ""
        errors = []
        state_data = self.client.get_state(sls, saltenv)
        fn_ = state_data.get("dest", False)
        if not fn_:
            if sls in self.ignored_pillars.get(saltenv, []):
                log.debug(
                    "Skipping ignored and missing SLS '%s' in environment '%s'",
                    sls,
                    saltenv,
                )
                return None, mods, errors
            elif self.opts["pillar_roots"].get(saltenv):
                msg = (
                    "Specified SLS '{}' in environment '{}' is not"
                    " available on the salt master".format(sls, saltenv)
                )
                log.error(msg)
                errors.append(msg)
            else:
                msg = "Specified SLS '{}' in environment '{}' was not found. ".format(
                    sls, saltenv
                )
                if self.opts.get("__git_pillar", False) is True:
                    msg += (
                        "This is likely caused by a git_pillar top file "
                        "containing an environment other than the one for the "
                        "branch in which it resides. Each git_pillar "
                        "branch/tag must have its own top file."
                    )
                else:
                    msg += (
                        "This could be because SLS '{0}' is in an "
                        "environment other than '{1}', but '{1}' is "
                        "included in that environment's Pillar top file. It "
                        "could also be due to environment '{1}' not being "
                        "defined in 'pillar_roots'.".format(sls, saltenv)
                    )
                log.debug(msg)
                # return state, mods, errors
                return None, mods, errors
        state = None
        try:
            state = compile_template(
                fn_,
                self.rend,
                self.opts["renderer"],
                self.opts["renderer_blacklist"],
                self.opts["renderer_whitelist"],
                saltenv,
                sls,
                _pillar_rend=True,
                **defaults,
            )
        except Exception as exc:  # pylint: disable=broad-except
            msg = f"Rendering SLS '{sls}' failed, render error:\n{exc}"
            log.critical(msg, exc_info=True)
            if self.opts.get("pillar_safe_render_error", True):
                errors.append(
                    "Rendering SLS '{}' failed. Please see master log for "
                    "details.".format(sls)
                )
            else:
                errors.append(msg)
        mods[sls] = state
        nstate = None
        if state:
            if not isinstance(state, dict):
                msg = f"SLS '{sls}' does not render to a dictionary"
                log.error(msg)
                errors.append(msg)
            else:
                if "include" in state:
                    if not isinstance(state["include"], list):
                        msg = (
                            "Include Declaration in SLS '{}' is not "
                            "formed as a list".format(sls)
                        )
                        log.error(msg)
                        errors.append(msg)
                    else:
                        # render included state(s)
                        include_states = []
                        for sub_sls in state.pop("include"):
                            if isinstance(sub_sls, dict):
                                sub_sls, v = next(iter(sub_sls.items()))
                                defaults = v.get("defaults", {})
                                key = v.get("key", None)
                            else:
                                key = None
                            try:
                                matched_pstates = fnmatch.filter(
                                    self.avail[saltenv],
                                    sub_sls.lstrip(".").replace("/", "."),
                                )
                                if sub_sls.startswith("."):
                                    if state_data.get("source", "").endswith(
                                        "/init.sls"
                                    ):
                                        include_parts = sls.split(".")
                                    else:
                                        include_parts = sls.split(".")[:-1]
                                    sub_sls = ".".join(include_parts + [sub_sls[1:]])
                                matches = fnmatch.filter(
                                    self.avail[saltenv],
                                    sub_sls,
                                )
                                matched_pstates.extend(matches)
                            except KeyError:
                                errors.extend(
                                    [
                                        "No matching pillar environment for environment"
                                        " '{}' found".format(saltenv)
                                    ]
                                )
                                matched_pstates = [sub_sls]
                            # If matched_pstates is empty, set to sub_sls
                            if len(matched_pstates) < 1:
                                matched_pstates = [sub_sls]
                            for m_sub_sls in matched_pstates:
                                if m_sub_sls not in mods:
                                    nstate, mods, err = self.render_pstate(
                                        m_sub_sls, saltenv, mods, defaults
                                    )
                                else:
                                    nstate = mods[m_sub_sls]
                                if nstate:
                                    if key:
                                        # If key is x:y, convert it to {x: {y: nstate}}
                                        for key_fragment in reversed(key.split(":")):
                                            nstate = {key_fragment: nstate}
                                    if not self.opts.get(
                                        "pillar_includes_override_sls", False
                                    ):
                                        include_states.append(nstate)
                                    else:
                                        state = merge(
                                            state,
                                            nstate,
                                            self.merge_strategy,
                                            self.opts.get("renderer", "yaml"),
                                            self.opts.get("pillar_merge_lists", False),
                                        )
                                if err:
                                    errors += err
                        if not self.opts.get("pillar_includes_override_sls", False):
                            # merge included state(s) with the current state
                            # merged last to ensure that its values are
                            # authoritative.
                            include_states.append(state)
                            state = None
                            for s in include_states:
                                if state is None:
                                    state = s
                                else:
                                    state = merge(
                                        state,
                                        s,
                                        self.merge_strategy,
                                        self.opts.get("renderer", "yaml"),
                                        self.opts.get("pillar_merge_lists", False),
                                    )
        return state, mods, errors

    def render_pillar(self, matches, errors=None):
        """
        Extract the sls pillar files from the matches and render them into the
        pillar
        """
        pillar = copy.copy(self.pillar_override)
        if errors is None:
            errors = []
        for saltenv, pstates in matches.items():
            pstatefiles = []
            mods = {}
            for sls_match in pstates:
                matched_pstates = []
                try:
                    matched_pstates = fnmatch.filter(self.avail[saltenv], sls_match)
                except KeyError:
                    errors.extend(
                        [
                            "No matching pillar environment for environment "
                            "'{}' found".format(saltenv)
                        ]
                    )
                if matched_pstates:
                    pstatefiles.extend(matched_pstates)
                else:
                    pstatefiles.append(sls_match)

            for sls in pstatefiles:
                pstate, mods, err = self.render_pstate(sls, saltenv, mods)

                if err:
                    errors += err

                if pstate is not None:
                    if not isinstance(pstate, dict):
                        log.error(
                            "The rendered pillar sls file, '%s' state did "
                            "not return the expected data format. This is "
                            "a sign of a malformed pillar sls file. Returned "
                            "errors: %s",
                            sls,
                            ", ".join([f"'{e}'" for e in errors]),
                        )
                        continue
                    pillar = merge(
                        pillar,
                        pstate,
                        self.merge_strategy,
                        self.opts.get("renderer", "yaml"),
                        self.opts.get("pillar_merge_lists", False),
                    )

        return pillar, errors

    def _external_pillar_data(self, pillar, val, key):
        """
        Builds actual pillar data structure and updates the ``pillar`` variable
        """
        ext = None
        args = salt.utils.args.get_function_argspec(self.ext_pillars[key]).args

        if isinstance(val, dict):
            if ("extra_minion_data" in args) and self.extra_minion_data:
                ext = self.ext_pillars[key](
                    self.minion_id,
                    pillar,
                    extra_minion_data=self.extra_minion_data,
                    **val,
                )
            else:
                ext = self.ext_pillars[key](self.minion_id, pillar, **val)
        elif isinstance(val, list):
            if ("extra_minion_data" in args) and self.extra_minion_data:
                ext = self.ext_pillars[key](
                    self.minion_id,
                    pillar,
                    *val,
                    extra_minion_data=self.extra_minion_data,
                )
            else:
                ext = self.ext_pillars[key](self.minion_id, pillar, *val)
        else:
            if ("extra_minion_data" in args) and self.extra_minion_data:
                ext = self.ext_pillars[key](
                    self.minion_id,
                    pillar,
                    val,
                    extra_minion_data=self.extra_minion_data,
                )
            else:
                ext = self.ext_pillars[key](self.minion_id, pillar, val)
        return ext

    def ext_pillar(self, pillar, errors=None):
        """
        Render the external pillar data
        """
        if errors is None:
            errors = []
        try:
            # Make sure that on-demand git_pillar is fetched before we try to
            # compile the pillar data. git_pillar will fetch a remote when
            # the git ext_pillar() func is run, but only for masterless.
            if self.ext and "git" in self.ext and self.opts.get("__role") != "minion":
                # Avoid circular import
                import salt.pillar.git_pillar
                import salt.utils.gitfs

                git_pillar = salt.utils.gitfs.GitPillar(
                    self.opts,
                    self.ext["git"],
                    per_remote_overrides=salt.pillar.git_pillar.PER_REMOTE_OVERRIDES,
                    per_remote_only=salt.pillar.git_pillar.PER_REMOTE_ONLY,
                    global_only=salt.pillar.git_pillar.GLOBAL_ONLY,
                )
                git_pillar.fetch_remotes()
        except TypeError:
            # Handle malformed ext_pillar
            pass
        if "ext_pillar" not in self.opts:
            return pillar, errors
        if not isinstance(self.opts["ext_pillar"], list):
            errors.append('The "ext_pillar" option is malformed')
            log.critical(errors[-1])
            return pillar, errors
        ext = None
        # Bring in CLI pillar data
        if self.pillar_override:
            pillar = merge(
                pillar,
                self.pillar_override,
                self.merge_strategy,
                self.opts.get("renderer", "yaml"),
                self.opts.get("pillar_merge_lists", False),
            )

        for run in self.opts["ext_pillar"]:
            if not isinstance(run, dict):
                errors.append('The "ext_pillar" option is malformed')
                log.critical(errors[-1])
                return {}, errors
            if next(iter(run.keys())) in self.opts.get("exclude_ext_pillar", []):
                continue
            for key, val in run.items():
                if key not in self.ext_pillars:
                    log.critical(
                        "Specified ext_pillar interface %s is unavailable", key
                    )
                    continue
                try:
                    ext = self._external_pillar_data(pillar, val, key)
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(
                        "Failed to load ext_pillar {}: {}".format(
                            key,
                            exc,
                        )
                    )
                    log.error(
                        "Exception caught loading ext_pillar '%s':\n%s",
                        key,
                        "".join(traceback.format_tb(sys.exc_info()[2])),
                    )
            if ext:
                pillar = merge(
                    pillar,
                    ext,
                    self.merge_strategy,
                    self.opts.get("renderer", "yaml"),
                    self.opts.get("pillar_merge_lists", False),
                )
                ext = None
        return pillar, errors

    def compile_pillar(self, ext=True):
        """
        Render the pillar data and return
        """
        top, top_errors = self.get_top()
        if ext:
            if self.opts.get("ext_pillar_first", False):
                self.opts["pillar"], errors = self.ext_pillar(self.pillar_override)
                self.rend = salt.loader.render(self.opts, self.functions)
                matches = self.top_matches(top, reload=True)
                pillar, errors = self.render_pillar(matches, errors=errors)
                pillar = merge(
                    self.opts["pillar"],
                    pillar,
                    self.merge_strategy,
                    self.opts.get("renderer", "yaml"),
                    self.opts.get("pillar_merge_lists", False),
                )
            else:
                matches = self.top_matches(top)
                pillar, errors = self.render_pillar(matches)
                pillar, errors = self.ext_pillar(pillar, errors=errors)
        else:
            matches = self.top_matches(top)
            pillar, errors = self.render_pillar(matches)
        errors.extend(top_errors)
        if self.opts.get("pillar_opts", False):
            mopts = dict(self.opts)
            if "grains" in mopts:
                mopts.pop("grains")
            mopts["saltversion"] = __version__
            pillar["master"] = mopts
        if "pillar" in self.opts and self.opts.get("ssh_merge_pillar", False):
            pillar = merge(
                self.opts["pillar"],
                pillar,
                self.merge_strategy,
                self.opts.get("renderer", "yaml"),
                self.opts.get("pillar_merge_lists", False),
            )
        if errors:
            for error in errors:
                log.critical("Pillar render error: %s", error)
            pillar["_errors"] = errors

        if self.pillar_override:
            pillar = merge(
                pillar,
                self.pillar_override,
                self.merge_strategy,
                self.opts.get("renderer", "yaml"),
                self.opts.get("pillar_merge_lists", False),
            )

        decrypt_errors = self.decrypt_pillar(pillar)
        if decrypt_errors:
            pillar.setdefault("_errors", []).extend(decrypt_errors)
        return pillar

    def decrypt_pillar(self, pillar):
        """
        Decrypt the specified pillar dictionary items, if configured to do so
        """
        errors = []
        if self.opts.get("decrypt_pillar"):
            decrypt_pillar = self.opts["decrypt_pillar"]
            if not isinstance(decrypt_pillar, dict):
                decrypt_pillar = salt.utils.data.repack_dictlist(
                    self.opts["decrypt_pillar"]
                )
            if not decrypt_pillar:
                errors.append("decrypt_pillar config option is malformed")
            for key, rend in decrypt_pillar.items():
                ptr = salt.utils.data.traverse_dict(
                    pillar,
                    key,
                    default=None,
                    delimiter=self.opts["decrypt_pillar_delimiter"],
                )
                if ptr is None:
                    log.debug("Pillar key %s not present", key)
                    continue
                try:
                    hash(ptr)
                    immutable = True
                except TypeError:
                    immutable = False
                try:
                    ret = salt.utils.crypt.decrypt(
                        ptr,
                        rend or self.opts["decrypt_pillar_default"],
                        renderers=self.rend,
                        opts=self.opts,
                        valid_rend=self.opts["decrypt_pillar_renderers"],
                    )
                    if immutable:
                        # Since the key pointed to an immutable type, we need
                        # to replace it in the pillar dict. First we will find
                        # the parent, and then we will replace the child key
                        # with the return data from the renderer.
                        parent, _, child = key.rpartition(
                            self.opts["decrypt_pillar_delimiter"]
                        )
                        if not parent:
                            # key is a top-level key, so the pointer to the
                            # parent is the pillar dict itself.
                            ptr = pillar
                        else:
                            ptr = salt.utils.data.traverse_dict(
                                pillar,
                                parent,
                                default=None,
                                delimiter=self.opts["decrypt_pillar_delimiter"],
                            )
                        if ptr is not None:
                            ptr[child] = ret
                except Exception as exc:  # pylint: disable=broad-except
                    msg = f"Failed to decrypt pillar key '{key}': {exc}"
                    errors.append(msg)
                    log.error(msg, exc_info=True)
        return errors

    def destroy(self):
        """
        This method exist in order to be API compatible with RemotePillar
        """
        if self._closing:
            return
        self._closing = True
        if self.client:
            try:
                self.client.destroy()
            except AttributeError:
                pass
        if self.fileclient:
            try:
                self.fileclient.destroy()
            except AttributeError:
                pass

    # pylint: disable=W1701
    def __del__(self):
        self.destroy()

    # pylint: enable=W1701


# TODO: actually migrate from Pillar to AsyncPillar to allow for futures in
# ext_pillar etc.
class AsyncPillar(Pillar):
    @tornado.gen.coroutine
    def compile_pillar(self, ext=True):
        ret = super().compile_pillar(ext=ext)
        raise tornado.gen.Return(ret)
