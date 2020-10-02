"""
Routines to set up a minion
"""

import contextlib
import copy
import functools
import logging
import multiprocessing
import os
import random
import signal
import sys
import threading
import time
import traceback
import types
from binascii import crc32
from random import randint, shuffle
from stat import S_IMODE

import salt
import salt.beacons
import salt.cli.daemons
import salt.client
import salt.crypt
import salt.defaults.events
import salt.defaults.exitcodes
import salt.engines

# pylint: enable=no-name-in-module,redefined-builtin
import salt.ext.tornado
import salt.ext.tornado.gen  # pylint: disable=F0401
import salt.ext.tornado.ioloop  # pylint: disable=F0401
import salt.loader
import salt.log.setup
import salt.payload
import salt.pillar
import salt.serializers.msgpack
import salt.syspaths
import salt.transport.client
import salt.utils.args
import salt.utils.context
import salt.utils.crypt
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
from salt._compat import ipaddress
from salt.config import DEFAULT_MINION_OPTS
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltClientError,
    SaltDaemonNotRunning,
    SaltException,
    SaltInvocationError,
    SaltMasterUnresolvableError,
    SaltReqTimeoutError,
    SaltSystemExit,
)

# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range
from salt.template import SLS_ENCODING
from salt.utils.ctx import RequestContext
from salt.utils.debug import enable_sigusr1_handler
from salt.utils.event import tagify
from salt.utils.network import parse_host_port
from salt.utils.odict import OrderedDict
from salt.utils.process import ProcessManager, SignalHandlingProcess, default_signals
from salt.utils.zeromq import ZMQ_VERSION_INFO, ZMQDefaultLoop, install_zmq, zmq

HAS_PSUTIL = False
try:
    import salt.utils.psutil_compat as psutil

    HAS_PSUTIL = True
except ImportError:
    pass

HAS_RESOURCE = False
try:
    import resource

    HAS_RESOURCE = True
except ImportError:
    pass

try:
    import salt.utils.win_functions

    HAS_WIN_FUNCTIONS = True
except ImportError:
    HAS_WIN_FUNCTIONS = False
# pylint: enable=import-error

log = logging.getLogger(__name__)

# To set up a minion:
# 1. Read in the configuration
# 2. Generate the function mapping dict
# 3. Authenticate with the master
# 4. Store the AES key
# 5. Connect to the publisher
# 6. Handle publications


def resolve_dns(opts, fallback=True):
    """
    Resolves the master_ip and master_uri options
    """
    ret = {}
    check_dns = True
    if opts.get("file_client", "remote") == "local" and not opts.get(
        "use_master_when_local", False
    ):
        check_dns = False
    # Since salt.log is imported below, salt.utils.network needs to be imported here as well
    import salt.utils.network

    if check_dns is True:
        try:
            if opts["master"] == "":
                raise SaltSystemExit
            ret["master_ip"] = salt.utils.network.dns_check(
                opts["master"], int(opts["master_port"]), True, opts["ipv6"]
            )
        except SaltClientError:
            retry_dns_count = opts.get("retry_dns_count", None)
            if opts["retry_dns"]:
                while True:
                    if retry_dns_count is not None:
                        if retry_dns_count == 0:
                            raise SaltMasterUnresolvableError
                        retry_dns_count -= 1
                    import salt.log

                    msg = (
                        "Master hostname: '{}' not found or not responsive. "
                        "Retrying in {} seconds"
                    ).format(opts["master"], opts["retry_dns"])
                    if salt.log.setup.is_console_configured():
                        log.error(msg)
                    else:
                        print("WARNING: {}".format(msg))
                    time.sleep(opts["retry_dns"])
                    try:
                        ret["master_ip"] = salt.utils.network.dns_check(
                            opts["master"], int(opts["master_port"]), True, opts["ipv6"]
                        )
                        break
                    except SaltClientError:
                        pass
            else:
                if fallback:
                    ret["master_ip"] = "127.0.0.1"
                else:
                    raise
        except SaltSystemExit:
            unknown_str = "unknown address"
            master = opts.get("master", unknown_str)
            if master == "":
                master = unknown_str
            if opts.get("__role") == "syndic":
                err = (
                    "Master address: '{}' could not be resolved. Invalid or unresolveable address. "
                    "Set 'syndic_master' value in minion config.".format(master)
                )
            else:
                err = (
                    "Master address: '{}' could not be resolved. Invalid or unresolveable address. "
                    "Set 'master' value in minion config.".format(master)
                )
            log.error(err)
            raise SaltSystemExit(code=42, msg=err)
    else:
        ret["master_ip"] = "127.0.0.1"

    if "master_ip" in ret and "master_ip" in opts:
        if ret["master_ip"] != opts["master_ip"]:
            log.warning(
                "Master ip address changed from %s to %s",
                opts["master_ip"],
                ret["master_ip"],
            )
    if opts["source_interface_name"]:
        log.trace("Custom source interface required: %s", opts["source_interface_name"])
        interfaces = salt.utils.network.interfaces()
        log.trace("The following interfaces are available on this Minion:")
        log.trace(interfaces)
        if opts["source_interface_name"] in interfaces:
            if interfaces[opts["source_interface_name"]]["up"]:
                addrs = (
                    interfaces[opts["source_interface_name"]]["inet"]
                    if not opts["ipv6"]
                    else interfaces[opts["source_interface_name"]]["inet6"]
                )
                ret["source_ip"] = addrs[0]["address"]
                log.debug("Using %s as source IP address", ret["source_ip"])
            else:
                log.warning(
                    "The interface %s is down so it cannot be used as source to connect to the Master",
                    opts["source_interface_name"],
                )
        else:
            log.warning(
                "%s is not a valid interface. Ignoring.", opts["source_interface_name"]
            )
    elif opts["source_address"]:
        ret["source_ip"] = salt.utils.network.dns_check(
            opts["source_address"], int(opts["source_ret_port"]), True, opts["ipv6"]
        )
        log.debug("Using %s as source IP address", ret["source_ip"])
    if opts["source_ret_port"]:
        ret["source_ret_port"] = int(opts["source_ret_port"])
        log.debug("Using %d as source port for the ret server", ret["source_ret_port"])
    if opts["source_publish_port"]:
        ret["source_publish_port"] = int(opts["source_publish_port"])
        log.debug(
            "Using %d as source port for the master pub", ret["source_publish_port"]
        )
    ret["master_uri"] = "tcp://{ip}:{port}".format(
        ip=ret["master_ip"], port=opts["master_port"]
    )
    log.debug("Master URI: %s", ret["master_uri"])

    return ret


def prep_ip_port(opts):
    """
    parse host:port values from opts['master'] and return valid:
        master: ip address or hostname as a string
        master_port: (optional) master returner port as integer

    e.g.:
      - master: 'localhost:1234' -> {'master': 'localhost', 'master_port': 1234}
      - master: '127.0.0.1:1234' -> {'master': '127.0.0.1', 'master_port' :1234}
      - master: '[::1]:1234' -> {'master': '::1', 'master_port': 1234}
      - master: 'fe80::a00:27ff:fedc:ba98' -> {'master': 'fe80::a00:27ff:fedc:ba98'}
    """
    ret = {}
    # Use given master IP if "ip_only" is set or if master_ip is an ipv6 address without
    # a port specified. The is_ipv6 check returns False if brackets are used in the IP
    # definition such as master: '[::1]:1234'.
    if opts["master_uri_format"] == "ip_only":
        ret["master"] = ipaddress.ip_address(opts["master"])
    else:
        try:
            host, port = parse_host_port(opts["master"])
        except ValueError as exc:
            raise SaltClientError(exc)
        ret = {"master": host}
        if port:
            ret.update({"master_port": port})

    return ret


def get_proc_dir(cachedir, **kwargs):
    """
    Given the cache directory, return the directory that process data is
    stored in, creating it if it doesn't exist.
    The following optional Keyword Arguments are handled:

    mode: which is anything os.makedir would accept as mode.

    uid: the uid to set, if not set, or it is None or -1 no changes are
         made. Same applies if the directory is already owned by this
         uid. Must be int. Works only on unix/unix like systems.

    gid: the gid to set, if not set, or it is None or -1 no changes are
         made. Same applies if the directory is already owned by this
         gid. Must be int. Works only on unix/unix like systems.
    """
    fn_ = os.path.join(cachedir, "proc")
    mode = kwargs.pop("mode", None)

    if mode is None:
        mode = {}
    else:
        mode = {"mode": mode}

    if not os.path.isdir(fn_):
        # proc_dir is not present, create it with mode settings
        os.makedirs(fn_, **mode)

    d_stat = os.stat(fn_)

    # if mode is not an empty dict then we have an explicit
    # dir mode. So lets check if mode needs to be changed.
    if mode:
        mode_part = S_IMODE(d_stat.st_mode)
        if mode_part != mode["mode"]:
            os.chmod(fn_, (d_stat.st_mode ^ mode_part) | mode["mode"])

    if hasattr(os, "chown"):
        # only on unix/unix like systems
        uid = kwargs.pop("uid", -1)
        gid = kwargs.pop("gid", -1)

        # if uid and gid are both -1 then go ahead with
        # no changes at all
        if (d_stat.st_uid != uid or d_stat.st_gid != gid) and [
            i for i in (uid, gid) if i != -1
        ]:
            os.chown(fn_, uid, gid)

    return fn_


def load_args_and_kwargs(func, args, data=None, ignore_invalid=False):
    """
    Detect the args and kwargs that need to be passed to a function call, and
    check them against what was passed.
    """
    argspec = salt.utils.args.get_function_argspec(func)
    _args = []
    _kwargs = {}
    invalid_kwargs = []

    for arg in args:
        if isinstance(arg, dict) and arg.pop("__kwarg__", False) is True:
            # if the arg is a dict with __kwarg__ == True, then its a kwarg
            for key, val in arg.items():
                if argspec.keywords or key in argspec.args:
                    # Function supports **kwargs or is a positional argument to
                    # the function.
                    _kwargs[key] = val
                else:
                    # **kwargs not in argspec and parsed argument name not in
                    # list of positional arguments. This keyword argument is
                    # invalid.
                    invalid_kwargs.append("{}={}".format(key, val))
            continue

        else:
            string_kwarg = salt.utils.args.parse_input([arg], condition=False)[
                1
            ]  # pylint: disable=W0632
            if string_kwarg:
                if argspec.keywords or next(iter(string_kwarg.keys())) in argspec.args:
                    # Function supports **kwargs or is a positional argument to
                    # the function.
                    _kwargs.update(string_kwarg)
                else:
                    # **kwargs not in argspec and parsed argument name not in
                    # list of positional arguments. This keyword argument is
                    # invalid.
                    for key, val in string_kwarg.items():
                        invalid_kwargs.append("{}={}".format(key, val))
            else:
                _args.append(arg)

    if invalid_kwargs and not ignore_invalid:
        salt.utils.args.invalid_kwargs(invalid_kwargs)

    if argspec.keywords and isinstance(data, dict):
        # this function accepts **kwargs, pack in the publish data
        for key, val in data.items():
            _kwargs["__pub_{}".format(key)] = val

    return _args, _kwargs


def eval_master_func(opts):
    """
    Evaluate master function if master type is 'func'
    and save it result in opts['master']
    """
    if "__master_func_evaluated" not in opts:
        # split module and function and try loading the module
        mod_fun = opts["master"]
        mod, fun = mod_fun.split(".")
        try:
            master_mod = salt.loader.raw_mod(opts, mod, fun)
            if not master_mod:
                raise KeyError
            # we take whatever the module returns as master address
            opts["master"] = master_mod[mod_fun]()
            # Check for valid types
            if not isinstance(opts["master"], ((str,), list)):
                raise TypeError
            opts["__master_func_evaluated"] = True
        except KeyError:
            log.error("Failed to load module %s", mod_fun)
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        except TypeError:
            log.error("%s returned from %s is not a string", opts["master"], mod_fun)
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        log.info("Evaluated master from module: %s", mod_fun)


def master_event(type, master=None):
    """
    Centralized master event function which will return event type based on event_map
    """
    event_map = {
        "connected": "__master_connected",
        "disconnected": "__master_disconnected",
        "failback": "__master_failback",
        "alive": "__master_alive",
    }

    if type == "alive" and master is not None:
        return "{}_{}".format(event_map.get(type), master)

    return event_map.get(type, None)


def service_name():
    """
    Return the proper service name based on platform
    """
    return "salt_minion" if "bsd" in sys.platform else "salt-minion"


class MinionBase:
    def __init__(self, opts):
        self.opts = opts
        self.beacons_leader = opts.get("beacons_leader", True)

    def gen_modules(self, initial_load=False, context=None):
        """
        Tell the minion to reload the execution modules

        CLI Example:

        .. code-block:: bash

            salt '*' sys.reload_modules
        """
        if initial_load:
            self.opts["pillar"] = salt.pillar.get_pillar(
                self.opts,
                self.opts["grains"],
                self.opts["id"],
                self.opts["saltenv"],
                pillarenv=self.opts.get("pillarenv"),
            ).compile_pillar()

        self.utils = salt.loader.utils(self.opts, context=context)
        self.functions = salt.loader.minion_mods(
            self.opts, utils=self.utils, context=context
        )
        self.serializers = salt.loader.serializers(self.opts)
        self.returners = salt.loader.returners(
            self.opts, functions=self.functions, context=context
        )
        self.proxy = salt.loader.proxy(
            self.opts, functions=self.functions, returners=self.returners
        )
        # TODO: remove
        self.function_errors = {}  # Keep the funcs clean
        self.states = salt.loader.states(
            self.opts,
            functions=self.functions,
            utils=self.utils,
            serializers=self.serializers,
            context=context,
        )
        self.rend = salt.loader.render(
            self.opts, functions=self.functions, context=context
        )
        #        self.matcher = Matcher(self.opts, self.functions)
        self.matchers = salt.loader.matchers(self.opts)
        self.functions["sys.reload_modules"] = self.gen_modules
        self.executors = salt.loader.executors(
            self.opts, functions=self.functions, proxy=self.proxy, context=context
        )

    @staticmethod
    def process_schedule(minion, loop_interval):
        try:
            if hasattr(minion, "schedule"):
                minion.schedule.eval()
            else:
                log.error(
                    "Minion scheduler not initialized. Scheduled jobs will not be run."
                )
                return
            # Check if scheduler requires lower loop interval than
            # the loop_interval setting
            if minion.schedule.loop_interval < loop_interval:
                loop_interval = minion.schedule.loop_interval
                log.debug("Overriding loop_interval because of scheduled jobs.")
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Exception %s occurred in scheduled job", exc)
        return loop_interval

    def process_beacons(self, functions):
        """
        Evaluate all of the configured beacons, grab the config again in case
        the pillar or grains changed
        """
        if "config.merge" in functions:
            b_conf = functions["config.merge"](
                "beacons", self.opts["beacons"], omit_opts=True
            )
            if b_conf:
                return self.beacons.process(
                    b_conf, self.opts["grains"]
                )  # pylint: disable=no-member
        return []

    @salt.ext.tornado.gen.coroutine
    def eval_master(self, opts, timeout=60, safe=True, failed=False, failback=False):
        """
        Evaluates and returns a tuple of the current master address and the pub_channel.

        In standard mode, just creates a pub_channel with the given master address.

        With master_type=func evaluates the current master address from the given
        module and then creates a pub_channel.

        With master_type=failover takes the list of masters and loops through them.
        The first one that allows the minion to create a pub_channel is then
        returned. If this function is called outside the minions initialization
        phase (for example from the minions main event-loop when a master connection
        loss was detected), 'failed' should be set to True. The current
        (possibly failed) master will then be removed from the list of masters.
        """
        # return early if we are not connecting to a master
        if opts["master_type"] == "disable":
            log.warning("Master is set to disable, skipping connection")
            self.connected = False
            raise salt.ext.tornado.gen.Return((None, None))

        # Run masters discovery over SSDP. This may modify the whole configuration,
        # depending of the networking and sets of masters.
        self._discover_masters()

        # check if master_type was altered from its default
        if opts["master_type"] != "str" and opts["__role"] != "syndic":
            # check for a valid keyword
            if opts["master_type"] == "func":
                eval_master_func(opts)

            # if failover or distributed is set, master has to be of type list
            elif opts["master_type"] in ("failover", "distributed"):
                if isinstance(opts["master"], list):
                    log.info(
                        "Got list of available master addresses: %s", opts["master"]
                    )

                    if opts["master_type"] == "distributed":
                        master_len = len(opts["master"])
                        if master_len > 1:
                            secondary_masters = opts["master"][1:]
                            master_idx = crc32(opts["id"]) % master_len
                            try:
                                preferred_masters = opts["master"]
                                preferred_masters[0] = opts["master"][master_idx]
                                preferred_masters[1:] = [
                                    m
                                    for m in opts["master"]
                                    if m != preferred_masters[0]
                                ]
                                opts["master"] = preferred_masters
                                log.info(
                                    "Distributed to the master at '%s'.",
                                    opts["master"][0],
                                )
                            except (KeyError, AttributeError, TypeError):
                                log.warning(
                                    "Failed to distribute to a specific master."
                                )
                        else:
                            log.warning(
                                "master_type = distributed needs more than 1 master."
                            )

                    if opts["master_shuffle"]:
                        log.warning(
                            "Use of 'master_shuffle' detected. 'master_shuffle' is deprecated in favor "
                            "of 'random_master'. Please update your minion config file."
                        )
                        opts["random_master"] = opts["master_shuffle"]

                    opts["auth_tries"] = 0
                    if (
                        opts["master_failback"]
                        and opts["master_failback_interval"] == 0
                    ):
                        opts["master_failback_interval"] = opts["master_alive_interval"]
                # if opts['master'] is a str and we have never created opts['master_list']
                elif isinstance(opts["master"], str) and ("master_list" not in opts):
                    # We have a string, but a list was what was intended. Convert.
                    # See issue 23611 for details
                    opts["master"] = [opts["master"]]
                elif opts["__role"] == "syndic":
                    log.info("Syndic setting master_syndic to '%s'", opts["master"])

                # if failed=True, the minion was previously connected
                # we're probably called from the minions main-event-loop
                # because a master connection loss was detected. remove
                # the possibly failed master from the list of masters.
                elif failed:
                    if failback:
                        # failback list of masters to original config
                        opts["master"] = opts["master_list"]
                    else:
                        log.info(
                            "Moving possibly failed master %s to the end of "
                            "the list of masters",
                            opts["master"],
                        )
                        if opts["master"] in opts["local_masters"]:
                            # create new list of master with the possibly failed
                            # one moved to the end
                            failed_master = opts["master"]
                            opts["master"] = [
                                x for x in opts["local_masters"] if opts["master"] != x
                            ]
                            opts["master"].append(failed_master)
                        else:
                            opts["master"] = opts["master_list"]
                else:
                    msg = (
                        "master_type set to 'failover' but 'master' "
                        "is not of type list but of type "
                        "{}".format(type(opts["master"]))
                    )
                    log.error(msg)
                    sys.exit(salt.defaults.exitcodes.EX_GENERIC)
                # If failover is set, minion have to failover on DNS errors instead of retry DNS resolve.
                # See issue 21082 for details
                if opts["retry_dns"] and opts["master_type"] == "failover":
                    msg = (
                        "'master_type' set to 'failover' but 'retry_dns' is not 0. "
                        "Setting 'retry_dns' to 0 to failover to the next master on DNS errors."
                    )
                    log.critical(msg)
                    opts["retry_dns"] = 0
            else:
                msg = "Invalid keyword '{}' for variable " "'master_type'".format(
                    opts["master_type"]
                )
                log.error(msg)
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)

        # FIXME: if SMinion don't define io_loop, it can't switch master see #29088
        # Specify kwargs for the channel factory so that SMinion doesn't need to define an io_loop
        # (The channel factories will set a default if the kwarg isn't passed)
        factory_kwargs = {"timeout": timeout, "safe": safe}
        if getattr(self, "io_loop", None):
            factory_kwargs["io_loop"] = self.io_loop  # pylint: disable=no-member

        tries = opts.get("master_tries", 1)
        attempts = 0

        # if we have a list of masters, loop through them and be
        # happy with the first one that allows us to connect
        if isinstance(opts["master"], list):
            conn = False
            last_exc = None
            opts["master_uri_list"] = []
            opts["local_masters"] = copy.copy(opts["master"])

            # shuffle the masters and then loop through them
            if opts["random_master"]:
                # master_failback is only used when master_type is set to failover
                if opts["master_type"] == "failover" and opts["master_failback"]:
                    secondary_masters = opts["local_masters"][1:]
                    shuffle(secondary_masters)
                    opts["local_masters"][1:] = secondary_masters
                else:
                    shuffle(opts["local_masters"])

            # This sits outside of the connection loop below because it needs to set
            # up a list of master URIs regardless of which masters are available
            # to connect _to_. This is primarily used for masterless mode, when
            # we need a list of master URIs to fire calls back to.
            for master in opts["local_masters"]:
                opts["master"] = master
                opts.update(prep_ip_port(opts))
                if opts["master_type"] == "failover":
                    try:
                        opts["master_uri_list"].append(
                            resolve_dns(opts, False)["master_uri"]
                        )
                    except SaltClientError:
                        continue
                else:
                    opts["master_uri_list"].append(resolve_dns(opts)["master_uri"])

            if not opts["master_uri_list"]:
                msg = "No master could be resolved"
                log.error(msg)
                raise SaltClientError(msg)

            pub_channel = None
            while True:
                if attempts != 0:
                    # Give up a little time between connection attempts
                    # to allow the IOLoop to run any other scheduled tasks.
                    yield salt.ext.tornado.gen.sleep(opts["acceptance_wait_time"])
                attempts += 1
                if tries > 0:
                    log.debug("Connecting to master. Attempt %s of %s", attempts, tries)
                else:
                    log.debug(
                        "Connecting to master. Attempt %s (infinite attempts)", attempts
                    )
                for master in opts["local_masters"]:
                    opts["master"] = master
                    opts.update(prep_ip_port(opts))
                    if opts["master_type"] == "failover":
                        try:
                            opts.update(resolve_dns(opts, False))
                        except SaltClientError:
                            continue
                    else:
                        opts.update(resolve_dns(opts))

                    # on first run, update self.opts with the whole master list
                    # to enable a minion to re-use old masters if they get fixed
                    if "master_list" not in opts:
                        opts["master_list"] = copy.copy(opts["local_masters"])

                    self.opts = opts

                    pub_channel = salt.transport.client.AsyncPubChannel.factory(
                        opts, **factory_kwargs
                    )
                    try:
                        yield pub_channel.connect()
                        conn = True
                        break
                    except SaltClientError as exc:
                        last_exc = exc
                        if exc.strerror.startswith("Could not access"):
                            msg = (
                                "Failed to initiate connection with Master "
                                "%s: check ownership/permissions. Error "
                                "message: %s",
                                opts["master"],
                                exc,
                            )
                        else:
                            msg = (
                                "Master %s could not be reached, trying next "
                                "next master (if any)",
                                opts["master"],
                            )
                        log.info(msg)
                        pub_channel.close()
                        pub_channel = None
                        continue

                if not conn:
                    if attempts == tries:
                        # Exhausted all attempts. Return exception.
                        self.connected = False
                        self.opts["master"] = copy.copy(self.opts["local_masters"])
                        log.error(
                            "No master could be reached or all masters "
                            "denied the minion's connection attempt."
                        )
                        if pub_channel:
                            pub_channel.close()
                        # If the code reaches this point, 'last_exc'
                        # should already be set.
                        raise last_exc  # pylint: disable=E0702
                else:
                    self.tok = pub_channel.auth.gen_token(b"salt")
                    self.connected = True
                    raise salt.ext.tornado.gen.Return((opts["master"], pub_channel))

        # single master sign in
        else:
            if opts["random_master"]:
                log.warning(
                    "random_master is True but there is only one master specified. Ignoring."
                )
            pub_channel = None
            while True:
                if attempts != 0:
                    # Give up a little time between connection attempts
                    # to allow the IOLoop to run any other scheduled tasks.
                    yield salt.ext.tornado.gen.sleep(opts["acceptance_wait_time"])
                attempts += 1
                if tries > 0:
                    log.debug("Connecting to master. Attempt %s of %s", attempts, tries)
                else:
                    log.debug(
                        "Connecting to master. Attempt %s (infinite attempts)", attempts
                    )
                opts.update(prep_ip_port(opts))
                opts.update(resolve_dns(opts))
                try:
                    if self.opts["transport"] == "detect":
                        self.opts["detect_mode"] = True
                        for trans in ("zeromq", "tcp"):
                            if trans == "zeromq" and not zmq:
                                continue
                            self.opts["transport"] = trans
                            pub_channel = salt.transport.client.AsyncPubChannel.factory(
                                self.opts, **factory_kwargs
                            )
                            yield pub_channel.connect()
                            if not pub_channel.auth.authenticated:
                                continue
                            del self.opts["detect_mode"]
                            break
                    else:
                        pub_channel = salt.transport.client.AsyncPubChannel.factory(
                            self.opts, **factory_kwargs
                        )
                        yield pub_channel.connect()
                    self.tok = pub_channel.auth.gen_token(b"salt")
                    self.connected = True
                    raise salt.ext.tornado.gen.Return((opts["master"], pub_channel))
                except SaltClientError:
                    if attempts == tries:
                        # Exhausted all attempts. Return exception.
                        self.connected = False
                        if pub_channel:
                            pub_channel.close()
                        raise

    def _discover_masters(self):
        """
        Discover master(s) and decide where to connect, if SSDP is around.
        This modifies the configuration on the fly.
        :return:
        """
        if (
            self.opts["master"] == DEFAULT_MINION_OPTS["master"]
            and self.opts["discovery"] is not False
        ):
            master_discovery_client = salt.utils.ssdp.SSDPDiscoveryClient()
            masters = {}
            for att in range(self.opts["discovery"].get("attempts", 3)):
                try:
                    att += 1
                    log.info("Attempting %s time(s) to discover masters", att)
                    masters.update(master_discovery_client.discover())
                    if not masters:
                        time.sleep(self.opts["discovery"].get("pause", 5))
                    else:
                        break
                except Exception as err:  # pylint: disable=broad-except
                    log.error("SSDP discovery failure: %s", err)
                    break

            if masters:
                policy = self.opts.get("discovery", {}).get("match", "any")
                if policy not in ["any", "all"]:
                    log.error(
                        'SSDP configuration matcher failure: unknown value "%s". '
                        'Should be "any" or "all"',
                        policy,
                    )
                else:
                    mapping = self.opts["discovery"].get("mapping", {})
                    for addr, mappings in masters.items():
                        for proto_data in mappings:
                            cnt = len(
                                [
                                    key
                                    for key, value in mapping.items()
                                    if proto_data.get("mapping", {}).get(key) == value
                                ]
                            )
                            if policy == "any" and bool(cnt) or cnt == len(mapping):
                                self.opts["master"] = proto_data["master"]
                                return

    def _return_retry_timer(self):
        """
        Based on the minion configuration, either return a randomized timer or
        just return the value of the return_retry_timer.
        """
        msg = "Minion return retry timer set to %s seconds"
        if self.opts.get("return_retry_timer_max"):
            try:
                random_retry = randint(
                    self.opts["return_retry_timer"], self.opts["return_retry_timer_max"]
                )
                retry_msg = msg % random_retry
                log.debug("%s (randomized)", msg % random_retry)
                return random_retry
            except ValueError:
                # Catch wiseguys using negative integers here
                log.error(
                    "Invalid value (return_retry_timer: %s or "
                    "return_retry_timer_max: %s). Both must be positive "
                    "integers.",
                    self.opts["return_retry_timer"],
                    self.opts["return_retry_timer_max"],
                )
                log.debug(msg, DEFAULT_MINION_OPTS["return_retry_timer"])
                return DEFAULT_MINION_OPTS["return_retry_timer"]
        else:
            log.debug(msg, self.opts.get("return_retry_timer"))
            return self.opts.get("return_retry_timer")


class SMinion(MinionBase):
    """
    Create an object that has loaded all of the minion module functions,
    grains, modules, returners etc.  The SMinion allows developers to
    generate all of the salt minion functions and present them with these
    functions for general use.
    """

    def __init__(self, opts, context=None):
        # Late setup of the opts grains, so we can log from the grains module
        import salt.loader

        opts["grains"] = salt.loader.grains(opts)
        super().__init__(opts)

        # Clean out the proc directory (default /var/cache/salt/minion/proc)
        if self.opts.get("file_client", "remote") == "remote" or self.opts.get(
            "use_master_when_local", False
        ):
            install_zmq()
            io_loop = ZMQDefaultLoop.current()
            io_loop.run_sync(lambda: self.eval_master(self.opts, failed=True))
        self.gen_modules(initial_load=True, context=context or {})

        # If configured, cache pillar data on the minion
        if self.opts["file_client"] == "remote" and self.opts.get(
            "minion_pillar_cache", False
        ):
            import salt.utils.yaml

            pdir = os.path.join(self.opts["cachedir"], "pillar")
            if not os.path.isdir(pdir):
                os.makedirs(pdir, 0o700)
            ptop = os.path.join(pdir, "top.sls")
            if self.opts["saltenv"] is not None:
                penv = self.opts["saltenv"]
            else:
                penv = "base"
            cache_top = {penv: {self.opts["id"]: ["cache"]}}
            with salt.utils.files.fopen(ptop, "wb") as fp_:
                salt.utils.yaml.safe_dump(cache_top, fp_, encoding=SLS_ENCODING)
                os.chmod(ptop, 0o600)
            cache_sls = os.path.join(pdir, "cache.sls")
            with salt.utils.files.fopen(cache_sls, "wb") as fp_:
                salt.utils.yaml.safe_dump(
                    self.opts["pillar"], fp_, encoding=SLS_ENCODING
                )
                os.chmod(cache_sls, 0o600)


class MasterMinion:
    """
    Create a fully loaded minion function object for generic use on the
    master. What makes this class different is that the pillar is
    omitted, otherwise everything else is loaded cleanly.
    """

    def __init__(
        self,
        opts,
        returners=True,
        states=True,
        rend=True,
        matcher=True,
        whitelist=None,
        ignore_config_errors=True,
    ):
        self.opts = salt.config.minion_config(
            opts["conf_file"], ignore_config_errors=ignore_config_errors, role="master"
        )
        self.opts.update(opts)
        self.whitelist = whitelist
        self.opts["grains"] = salt.loader.grains(opts)
        self.opts["pillar"] = {}
        self.mk_returners = returners
        self.mk_states = states
        self.mk_rend = rend
        self.mk_matcher = matcher
        self.gen_modules(initial_load=True)

    def gen_modules(self, initial_load=False):
        """
        Tell the minion to reload the execution modules

        CLI Example:

        .. code-block:: bash

            salt '*' sys.reload_modules
        """
        self.utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(
            self.opts,
            utils=self.utils,
            whitelist=self.whitelist,
            initial_load=initial_load,
        )
        self.serializers = salt.loader.serializers(self.opts)
        if self.mk_returners:
            self.returners = salt.loader.returners(self.opts, self.functions)
        if self.mk_states:
            self.states = salt.loader.states(
                self.opts, self.functions, self.utils, self.serializers
            )
        if self.mk_rend:
            self.rend = salt.loader.render(self.opts, self.functions)
        if self.mk_matcher:
            self.matchers = salt.loader.matchers(self.opts)
        self.functions["sys.reload_modules"] = self.gen_modules


class MinionManager(MinionBase):
    """
    Create a multi minion interface, this creates as many minions as are
    defined in the master option and binds each minion object to a respective
    master.
    """

    def __init__(self, opts):
        super().__init__(opts)
        self.auth_wait = self.opts["acceptance_wait_time"]
        self.max_auth_wait = self.opts["acceptance_wait_time_max"]
        self.minions = []
        self.jid_queue = []

        install_zmq()
        self.io_loop = ZMQDefaultLoop.current()
        self.process_manager = ProcessManager(name="MultiMinionProcessManager")
        self.io_loop.spawn_callback(
            self.process_manager.run, **{"asynchronous": True}
        )  # Tornado backward compat

    # pylint: disable=W1701
    def __del__(self):
        self.destroy()

    # pylint: enable=W1701

    def _bind(self):
        # start up the event publisher, so we can see events during startup
        self.event_publisher = salt.utils.event.AsyncEventPublisher(
            self.opts, io_loop=self.io_loop,
        )
        self.event = salt.utils.event.get_event(
            "minion", opts=self.opts, io_loop=self.io_loop
        )
        self.event.subscribe("")
        self.event.set_event_handler(self.handle_event)

    @salt.ext.tornado.gen.coroutine
    def handle_event(self, package):
        for minion in self.minions:
            minion.handle_event(package)

    def _create_minion_object(
        self, opts, timeout, safe, io_loop=None, loaded_base_name=None, jid_queue=None
    ):
        """
        Helper function to return the correct type of object
        """
        return Minion(
            opts,
            timeout,
            safe,
            io_loop=io_loop,
            loaded_base_name=loaded_base_name,
            jid_queue=jid_queue,
        )

    def _check_minions(self):
        """
        Check the size of self.minions and raise an error if it's empty
        """
        if not self.minions:
            err = "Minion unable to successfully connect to " "a Salt Master."
            log.error(err)

    def _spawn_minions(self, timeout=60):
        """
        Spawn all the coroutines which will sign in to masters
        """
        masters = self.opts["master"]
        if (self.opts["master_type"] in ("failover", "distributed")) or not isinstance(
            self.opts["master"], list
        ):
            masters = [masters]

        beacons_leader = True
        for master in masters:
            s_opts = copy.deepcopy(self.opts)
            s_opts["master"] = master
            s_opts["multimaster"] = True
            s_opts["beacons_leader"] = beacons_leader
            if beacons_leader:
                beacons_leader = False
            minion = self._create_minion_object(
                s_opts,
                s_opts["auth_timeout"],
                False,
                io_loop=self.io_loop,
                loaded_base_name="salt.loader.{}".format(s_opts["master"]),
                jid_queue=self.jid_queue,
            )
            self.io_loop.spawn_callback(self._connect_minion, minion)
        self.io_loop.call_later(timeout, self._check_minions)

    @salt.ext.tornado.gen.coroutine
    def _connect_minion(self, minion):
        """
        Create a minion, and asynchronously connect it to a master
        """
        last = 0  # never have we signed in
        auth_wait = minion.opts["acceptance_wait_time"]
        failed = False
        while True:
            try:
                if minion.opts.get("beacons_before_connect", False):
                    minion.setup_beacons(before_connect=True)
                if minion.opts.get("scheduler_before_connect", False):
                    minion.setup_scheduler(before_connect=True)
                yield minion.connect_master(failed=failed)
                minion.tune_in(start=False)
                self.minions.append(minion)
                break
            except SaltClientError as exc:
                failed = True
                log.error(
                    "Error while bringing up minion for multi-master. Is "
                    "master at %s responding?",
                    minion.opts["master"],
                )
                last = time.time()
                if auth_wait < self.max_auth_wait:
                    auth_wait += self.auth_wait
                yield salt.ext.tornado.gen.sleep(auth_wait)  # TODO: log?
            except SaltMasterUnresolvableError:
                err = (
                    "Master address: '{}' could not be resolved. Invalid or unresolveable address. "
                    "Set 'master' value in minion config.".format(minion.opts["master"])
                )
                log.error(err)
                break
            except Exception as e:  # pylint: disable=broad-except
                failed = True
                log.critical(
                    "Unexpected error while connecting to %s",
                    minion.opts["master"],
                    exc_info=True,
                )

    # Multi Master Tune In
    def tune_in(self):
        """
        Bind to the masters

        This loop will attempt to create connections to masters it hasn't connected
        to yet, but once the initial connection is made it is up to ZMQ to do the
        reconnect (don't know of an API to get the state here in salt)
        """
        self._bind()

        # Fire off all the minion coroutines
        self._spawn_minions()

        # serve forever!
        self.io_loop.start()

    @property
    def restart(self):
        for minion in self.minions:
            if minion.restart:
                return True
        return False

    def stop(self, signum):
        for minion in self.minions:
            minion.process_manager.stop_restarting()
            minion.process_manager.send_signal_to_processes(signum)
            # kill any remaining processes
            minion.process_manager.kill_children()
            minion.destroy()

    def destroy(self):
        for minion in self.minions:
            minion.destroy()


class Minion(MinionBase):
    """
    This class instantiates a minion, runs connections for a minion,
    and loads all of the functions into the minion
    """

    def __init__(
        self,
        opts,
        timeout=60,
        safe=True,
        loaded_base_name=None,
        io_loop=None,
        jid_queue=None,
    ):  # pylint: disable=W0231
        """
        Pass in the options dict
        """
        # this means that the parent class doesn't know *which* master we connect to
        super().__init__(opts)
        self.timeout = timeout
        self.safe = safe

        self._running = None
        self.win_proc = []
        self.subprocess_list = salt.utils.process.SubprocessList()
        self.loaded_base_name = loaded_base_name
        self.connected = False
        self.restart = False
        # Flag meaning minion has finished initialization including first connect to the master.
        # True means the Minion is fully functional and ready to handle events.
        self.ready = False
        self.jid_queue = [] if jid_queue is None else jid_queue
        self.periodic_callbacks = {}

        if io_loop is None:
            install_zmq()
            self.io_loop = ZMQDefaultLoop.current()
        else:
            self.io_loop = io_loop

        # Warn if ZMQ < 3.2
        if zmq:
            if ZMQ_VERSION_INFO < (3, 2):
                log.warning(
                    "You have a version of ZMQ less than ZMQ 3.2! There are "
                    "known connection keep-alive issues with ZMQ < 3.2 which "
                    "may result in loss of contact with minions. Please "
                    "upgrade your ZMQ!"
                )
        # Late setup of the opts grains, so we can log from the grains
        # module.  If this is a proxy, however, we need to init the proxymodule
        # before we can get the grains.  We do this for proxies in the
        # post_master_init
        if not salt.utils.platform.is_proxy():
            self.opts["grains"] = salt.loader.grains(opts)
        else:
            if self.opts.get("beacons_before_connect", False):
                log.warning(
                    "'beacons_before_connect' is not supported "
                    "for proxy minions. Setting to False"
                )
                self.opts["beacons_before_connect"] = False
            if self.opts.get("scheduler_before_connect", False):
                log.warning(
                    "'scheduler_before_connect' is not supported "
                    "for proxy minions. Setting to False"
                )
                self.opts["scheduler_before_connect"] = False

        log.info("Creating minion process manager")

        if self.opts["random_startup_delay"]:
            sleep_time = random.randint(0, self.opts["random_startup_delay"])
            log.info(
                "Minion sleeping for %s seconds due to configured "
                "startup_delay between 0 and %s seconds",
                sleep_time,
                self.opts["random_startup_delay"],
            )
            time.sleep(sleep_time)

        self.process_manager = ProcessManager(name="MinionProcessManager")
        self.io_loop.spawn_callback(self.process_manager.run, **{"asynchronous": True})
        # We don't have the proxy setup yet, so we can't start engines
        # Engines need to be able to access __proxy__
        if not salt.utils.platform.is_proxy():
            self.io_loop.spawn_callback(
                salt.engines.start_engines, self.opts, self.process_manager
            )

        # Install the SIGINT/SIGTERM handlers if not done so far
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGINT, self._handle_signals)

        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGTERM, self._handle_signals)

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        self._running = False
        # escalate the signals to the process manager
        self.process_manager.stop_restarting()
        self.process_manager.send_signal_to_processes(signum)
        # kill any remaining processes
        self.process_manager.kill_children()
        time.sleep(1)
        sys.exit(0)

    def sync_connect_master(self, timeout=None, failed=False):
        """
        Block until we are connected to a master
        """
        self._sync_connect_master_success = False
        log.debug("sync_connect_master")

        def on_connect_master_future_done(future):
            self._sync_connect_master_success = True
            self.io_loop.stop()

        self._connect_master_future = self.connect_master(failed=failed)
        # finish connecting to master
        self._connect_master_future.add_done_callback(on_connect_master_future_done)
        if timeout:
            self.io_loop.call_later(timeout, self.io_loop.stop)
        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.destroy()
        # I made the following 3 line oddity to preserve traceback.
        # Please read PR #23978 before changing, hopefully avoiding regressions.
        # Good luck, we're all counting on you.  Thanks.
        if self._connect_master_future.done():
            future_exception = self._connect_master_future.exception()
            if future_exception:
                # This needs to be re-raised to preserve restart_on_error behavior.
                raise six.reraise(*future_exception)
        if timeout and self._sync_connect_master_success is False:
            raise SaltDaemonNotRunning("Failed to connect to the salt-master")

    @salt.ext.tornado.gen.coroutine
    def connect_master(self, failed=False):
        """
        Return a future which will complete when you are connected to a master
        """
        master, self.pub_channel = yield self.eval_master(
            self.opts, self.timeout, self.safe, failed
        )
        yield self._post_master_init(master)

    # TODO: better name...
    @salt.ext.tornado.gen.coroutine
    def _post_master_init(self, master):
        """
        Function to finish init after connecting to a master

        This is primarily loading modules, pillars, etc. (since they need
        to know which master they connected to)

        If this function is changed, please check ProxyMinion._post_master_init
        to see if those changes need to be propagated.

        Minions and ProxyMinions need significantly different post master setups,
        which is why the differences are not factored out into separate helper
        functions.
        """
        if self.connected:
            self.opts["master"] = master

            # Initialize pillar before loader to make pillar accessible in modules
            async_pillar = salt.pillar.get_async_pillar(
                self.opts,
                self.opts["grains"],
                self.opts["id"],
                self.opts["saltenv"],
                pillarenv=self.opts.get("pillarenv"),
            )
            self.opts["pillar"] = yield async_pillar.compile_pillar()
            async_pillar.destroy()

        if not self.ready:
            self._setup_core()
        elif self.connected and self.opts["pillar"]:
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
                cleanup=[master_event(type="alive")],
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
        if (
            self.opts["transport"] != "tcp"
            and self.opts["master_alive_interval"] > 0
            and self.connected
        ):
            self.schedule.add_job(
                {
                    master_event(type="alive", master=self.opts["master"]): {
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
                        master_event(type="failback"): {
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
                self.schedule.delete_job(master_event(type="failback"), persist=True)
        else:
            self.schedule.delete_job(
                master_event(type="alive", master=self.opts["master"]), persist=True
            )
            self.schedule.delete_job(master_event(type="failback"), persist=True)

    def _prep_mod_opts(self):
        """
        Returns a copy of the opts with key bits stripped out
        """
        mod_opts = {}
        for key, val in self.opts.items():
            if key == "logger":
                continue
            mod_opts[key] = val
        return mod_opts

    def _load_modules(
        self, force_refresh=False, notify=False, grains=None, opts=None, context=None
    ):
        """
        Return the functions and the returners loaded up from the loader
        module
        """
        opt_in = True
        if not opts:
            opts = self.opts
            opt_in = False
        # if this is a *nix system AND modules_max_memory is set, lets enforce
        # a memory limit on module imports
        # this feature ONLY works on *nix like OSs (resource module doesn't work on windows)
        modules_max_memory = False
        if opts.get("modules_max_memory", -1) > 0 and HAS_PSUTIL and HAS_RESOURCE:
            log.debug(
                "modules_max_memory set, enforcing a maximum of %s",
                opts["modules_max_memory"],
            )
            modules_max_memory = True
            old_mem_limit = resource.getrlimit(resource.RLIMIT_AS)
            rss, vms = psutil.Process(os.getpid()).memory_info()[:2]
            mem_limit = rss + vms + opts["modules_max_memory"]
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        elif opts.get("modules_max_memory", -1) > 0:
            if not HAS_PSUTIL:
                log.error(
                    "Unable to enforce modules_max_memory because psutil is missing"
                )
            if not HAS_RESOURCE:
                log.error(
                    "Unable to enforce modules_max_memory because resource is missing"
                )

        # This might be a proxy minion
        if hasattr(self, "proxy"):
            proxy = self.proxy
        else:
            proxy = None

        if context is None:
            context = {}

        if grains is None:
            opts["grains"] = salt.loader.grains(
                opts, force_refresh, proxy=proxy, context=context
            )
        self.utils = salt.loader.utils(opts, proxy=proxy, context=context)

        if opts.get("multimaster", False):
            s_opts = copy.deepcopy(opts)
            functions = salt.loader.minion_mods(
                s_opts,
                utils=self.utils,
                proxy=proxy,
                loaded_base_name=self.loaded_base_name,
                notify=notify,
                context=context,
            )
        else:
            functions = salt.loader.minion_mods(
                opts, utils=self.utils, notify=notify, proxy=proxy, context=context,
            )
        returners = salt.loader.returners(opts, functions, proxy=proxy, context=context)
        errors = {}
        if "_errors" in functions:
            errors = functions["_errors"]
            functions.pop("_errors")

        # we're done, reset the limits!
        if modules_max_memory is True:
            resource.setrlimit(resource.RLIMIT_AS, old_mem_limit)

        executors = salt.loader.executors(opts, functions, proxy=proxy, context=context)

        if opt_in:
            self.opts = opts

        return functions, returners, errors, executors

    def _send_req_sync(self, load, timeout):

        if self.opts["minion_sign_messages"]:
            log.trace("Signing event to be published onto the bus.")
            minion_privkey_path = os.path.join(self.opts["pki_dir"], "minion.pem")
            sig = salt.crypt.sign_message(
                minion_privkey_path, salt.serializers.msgpack.serialize(load)
            )
            load["sig"] = sig

        with salt.transport.client.ReqChannel.factory(self.opts) as channel:
            return channel.send(load, timeout=timeout)

    @salt.ext.tornado.gen.coroutine
    def _send_req_async(self, load, timeout):

        if self.opts["minion_sign_messages"]:
            log.trace("Signing event to be published onto the bus.")
            minion_privkey_path = os.path.join(self.opts["pki_dir"], "minion.pem")
            sig = salt.crypt.sign_message(
                minion_privkey_path, salt.serializers.msgpack.serialize(load)
            )
            load["sig"] = sig

        with salt.transport.client.AsyncReqChannel.factory(self.opts) as channel:
            ret = yield channel.send(load, timeout=timeout)
            raise salt.ext.tornado.gen.Return(ret)

    def _fire_master(
        self,
        data=None,
        tag=None,
        events=None,
        pretag=None,
        timeout=60,
        sync=True,
        timeout_handler=None,
        include_startup_grains=False,
    ):
        """
        Fire an event on the master, or drop message if unable to send.
        """
        load = {
            "id": self.opts["id"],
            "cmd": "_minion_event",
            "pretag": pretag,
            "tok": self.tok,
        }
        if events:
            load["events"] = events
        elif data and tag:
            load["data"] = data
            load["tag"] = tag
        elif not data and tag:
            load["data"] = {}
            load["tag"] = tag
        else:
            return

        if include_startup_grains:
            grains_to_add = {
                k: v
                for k, v in self.opts.get("grains", {}).items()
                if k in self.opts["start_event_grains"]
            }
            load["grains"] = grains_to_add

        if sync:
            try:
                self._send_req_sync(load, timeout)
            except salt.exceptions.SaltReqTimeoutError:
                log.info(
                    "fire_master failed: master could not be contacted. Request timed out."
                )
                return False
            except Exception:  # pylint: disable=broad-except
                log.info("fire_master failed: %s", traceback.format_exc())
                return False
        else:
            if timeout_handler is None:

                def handle_timeout(*_):
                    log.info(
                        "fire_master failed: master could not be contacted. Request timed out."
                    )
                    return True

                timeout_handler = handle_timeout

            with salt.ext.tornado.stack_context.ExceptionStackContext(timeout_handler):
                # pylint: disable=unexpected-keyword-arg
                self._send_req_async(load, timeout, callback=lambda f: None)
                # pylint: enable=unexpected-keyword-arg
        return True

    @salt.ext.tornado.gen.coroutine
    def _handle_decoded_payload(self, data):
        """
        Override this method if you wish to handle the decoded data
        differently.
        """
        # Ensure payload is unicode. Disregard failure to decode binary blobs.
        if six.PY2:
            data = salt.utils.data.decode(data, keep=True)
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

        # Don't duplicate jobs
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
            process_count = len(salt.utils.minion.running(self.opts))
            while process_count >= process_count_max:
                log.warning(
                    "Maximum number of processes reached while executing jid %s, waiting...",
                    data["jid"],
                )
                yield salt.ext.tornado.gen.sleep(10)
                process_count = len(salt.utils.minion.running(self.opts))

        # We stash an instance references to allow for the socket
        # communication in Windows. You can't pickle functions, and thus
        # python needs to be able to reconstruct the reference on the other
        # side.
        instance = self
        multiprocessing_enabled = self.opts.get("multiprocessing", True)
        if multiprocessing_enabled:
            if sys.platform.startswith("win"):
                # let python reconstruct the minion on the other side if we're
                # running on windows
                instance = None
            with default_signals(signal.SIGINT, signal.SIGTERM):
                process = SignalHandlingProcess(
                    target=self._target,
                    name="ProcessPayload",
                    args=(instance, self.opts, data, self.connected),
                )
                process._after_fork_methods.append(
                    (salt.utils.crypt.reinit_crypto, [], {})
                )
        else:
            process = threading.Thread(
                target=self._target,
                args=(instance, self.opts, data, self.connected),
                name=data["jid"],
            )

        if multiprocessing_enabled:
            with default_signals(signal.SIGINT, signal.SIGTERM):
                # Reset current signals before starting the process in
                # order not to inherit the current signal handlers
                process.start()
        else:
            process.start()
        process.name = "{}-Job-{}".format(process.name, data["jid"])
        self.subprocess_list.add(process)

    def ctx(self):
        """
        Return a single context manager for the minion's data
        """
        exitstack = contextlib.ExitStack()
        exitstack.enter_context(self.functions.context_dict.clone())
        exitstack.enter_context(self.returners.context_dict.clone())
        exitstack.enter_context(self.executors.context_dict.clone())
        return exitstack

    @classmethod
    def _target(cls, minion_instance, opts, data, connected):
        if not minion_instance:
            minion_instance = cls(opts)
            minion_instance.connected = connected
            if not hasattr(minion_instance, "functions"):
                (
                    functions,
                    returners,
                    function_errors,
                    executors,
                ) = minion_instance._load_modules(grains=opts["grains"])
                minion_instance.functions = functions
                minion_instance.returners = returners
                minion_instance.function_errors = function_errors
                minion_instance.executors = executors
            if not hasattr(minion_instance, "serial"):
                minion_instance.serial = salt.payload.Serial(opts)
            if not hasattr(minion_instance, "proc_dir"):
                uid = salt.utils.user.get_uid(user=opts.get("user", None))
                minion_instance.proc_dir = get_proc_dir(opts["cachedir"], uid=uid)

        def run_func(minion_instance, opts, data):
            if isinstance(data["fun"], tuple) or isinstance(data["fun"], list):
                return Minion._thread_multi_return(minion_instance, opts, data)
            else:
                return Minion._thread_return(minion_instance, opts, data)

        with salt.ext.tornado.stack_context.StackContext(
            functools.partial(RequestContext, {"data": data, "opts": opts})
        ):
            with salt.ext.tornado.stack_context.StackContext(minion_instance.ctx):
                run_func(minion_instance, opts, data)

    def _execute_job_function(
        self, function_name, function_args, executors, opts, data
    ):
        """
        Executes a function within a job given it's name, the args and the executors.
        It also checks if the function is allowed to run if 'blackout mode' is enabled.
        """
        minion_blackout_violation = False
        if self.connected and self.opts["pillar"].get("minion_blackout", False):
            whitelist = self.opts["pillar"].get("minion_blackout_whitelist", [])
            # this minion is blacked out. Only allow saltutil.refresh_pillar and the whitelist
            if (
                function_name != "saltutil.refresh_pillar"
                and function_name not in whitelist
            ):
                minion_blackout_violation = True
        # use minion_blackout_whitelist from grains if it exists
        if self.opts["grains"].get("minion_blackout", False):
            whitelist = self.opts["grains"].get("minion_blackout_whitelist", [])
            if (
                function_name != "saltutil.refresh_pillar"
                and function_name not in whitelist
            ):
                minion_blackout_violation = True
        if minion_blackout_violation:
            raise SaltInvocationError(
                "Minion in blackout mode. Set 'minion_blackout' "
                "to False in pillar or grains to resume operations. Only "
                "saltutil.refresh_pillar allowed in blackout mode."
            )

        if function_name in self.functions:
            func = self.functions[function_name]
            args, kwargs = load_args_and_kwargs(func, function_args, data)
        else:
            # only run if function_name is not in minion_instance.functions and allow_missing_funcs is True
            func = function_name
            args, kwargs = function_args, data
        self.functions.pack["__context__"]["retcode"] = 0

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
        log.trace("Executors list %s", executors)  # pylint: disable=no-member

        for name in executors:
            fname = "{}.execute".format(name)
            if fname not in self.executors:
                raise SaltInvocationError("Executor '{}' is not available".format(name))
            return_data = self.executors[fname](opts, data, func, args, kwargs)
            if return_data is not None:
                return return_data

        return None

    @classmethod
    def _thread_return(cls, minion_instance, opts, data):
        """
        This method should be used as a threading target, start the actual
        minion side execution.
        """
        minion_instance.gen_modules()
        fn_ = os.path.join(minion_instance.proc_dir, data["jid"])

        salt.utils.process.appendproctitle(
            "{}._thread_return {}".format(cls.__name__, data["jid"])
        )

        sdata = {"pid": os.getpid()}
        sdata.update(data)
        log.info("Starting a new job %s with PID %s", data["jid"], sdata["pid"])
        with salt.utils.files.fopen(fn_, "w+b") as fp_:
            fp_.write(minion_instance.serial.dumps(sdata))
        ret = {"success": False}
        function_name = data["fun"]
        function_args = data["arg"]
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
                return_data = minion_instance._execute_job_function(
                    function_name, function_args, executors, opts, data
                )

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
                msg = "Command required for '{}' not found".format(function_name)
                log.debug(msg, exc_info=True)
                ret["return"] = "{}: {}".format(msg, exc)
                ret["out"] = "nested"
                ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
            except CommandExecutionError as exc:
                log.error(
                    "A command in '%s' had a problem: %s",
                    function_name,
                    exc,
                    exc_info_on_loglevel=logging.DEBUG,
                )
                ret["return"] = "ERROR: {}".format(exc)
                ret["out"] = "nested"
                ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
            except SaltInvocationError as exc:
                log.error(
                    "Problem executing '%s': %s",
                    function_name,
                    exc,
                    exc_info_on_loglevel=logging.DEBUG,
                )
                ret["return"] = "ERROR executing '{}': {}".format(function_name, exc)
                ret["out"] = "nested"
                ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
            except TypeError as exc:
                msg = "Passed invalid arguments to {}: {}\n{}".format(
                    function_name,
                    exc,
                    minion_instance.functions[function_name].__doc__ or "",
                )
                log.warning(msg, exc_info_on_loglevel=logging.DEBUG)
                ret["return"] = msg
                ret["out"] = "nested"
                ret["retcode"] = salt.defaults.exitcodes.EX_GENERIC
            except Exception:  # pylint: disable=broad-except
                msg = "The minion function caused an exception"
                log.warning(msg, exc_info_on_loglevel=True)
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
                ret["return"] = minion_instance.functions.missing_fun_string(
                    function_name
                )
                mod_name = function_name.split(".")[0]
                if mod_name in minion_instance.function_errors:
                    ret["return"] += " Possible reasons: '{}'".format(
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
            minion_instance._return_pub(
                ret, timeout=minion_instance._return_retry_timer()
            )

        # Add default returners from minion config
        # Should have been coverted to comma-delimited string already
        if isinstance(opts.get("return"), str):
            if data["ret"]:
                data["ret"] = ",".join((data["ret"], opts["return"]))
            else:
                data["ret"] = opts["return"]

        log.debug("minion return: %s", ret)
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

    @classmethod
    def _thread_multi_return(cls, minion_instance, opts, data):
        """
        This method should be used as a threading target, start the actual
        minion side execution.
        """
        minion_instance.gen_modules()
        fn_ = os.path.join(minion_instance.proc_dir, data["jid"])

        salt.utils.process.appendproctitle(
            "{}._thread_multi_return {}".format(cls.__name__, data["jid"])
        )

        sdata = {"pid": os.getpid()}
        sdata.update(data)
        log.info("Starting a new job with PID %s", sdata["pid"])
        with salt.utils.files.fopen(fn_, "w+b") as fp_:
            fp_.write(minion_instance.serial.dumps(sdata))

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
        executors = (
            data.get("module_executors")
            or getattr(minion_instance, "module_executors", [])
            or opts.get("module_executors", ["direct_call"])
        )

        for ind in range(0, num_funcs):
            function_name = data["fun"][ind]
            function_args = data["arg"][ind]
            if not multifunc_ordered:
                ret["success"][function_name] = False
            try:
                return_data = minion_instance._execute_job_function(
                    function_name, function_args, executors, opts, data
                )

                key = ind if multifunc_ordered else data["fun"][ind]
                ret["return"][key] = return_data
                retcode = minion_instance.functions.pack["__context__"].get(
                    "retcode", 0
                )
                if retcode == 0:
                    # No nonzero retcode in __context__ dunder. Check if return
                    # is a dictionary with a "result" or "success" key.
                    try:
                        func_result = all(
                            ret["return"][key].get(x, True)
                            for x in ("result", "success")
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
            minion_instance._return_pub(
                ret, timeout=minion_instance._return_retry_timer()
            )
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

    def _return_pub(self, ret, ret_cmd="_return", timeout=60, sync=True):
        """
        Return the data from the executed command to the master server
        """
        jid = ret.get("jid", ret.get("__jid__"))
        fun = ret.get("fun", ret.get("__fun__"))
        if self.opts["multiprocessing"]:
            fn_ = os.path.join(self.proc_dir, jid)
            if os.path.isfile(fn_):
                try:
                    os.remove(fn_)
                except OSError:
                    # The file is gone already
                    pass
        log.info("Returning information for job: %s", jid)
        log.trace("Return data: %s", ret)
        if ret_cmd == "_syndic_return":
            load = {
                "cmd": ret_cmd,
                "id": self.opts["uid"],
                "jid": jid,
                "fun": fun,
                "arg": ret.get("arg"),
                "tgt": ret.get("tgt"),
                "tgt_type": ret.get("tgt_type"),
                "load": ret.get("__load__"),
            }
            if "__master_id__" in ret:
                load["master_id"] = ret["__master_id__"]
            load["return"] = {}
            for key, value in ret.items():
                if key.startswith("__"):
                    continue
                load["return"][key] = value
        else:
            load = {"cmd": ret_cmd, "id": self.opts["id"]}
            for key, value in ret.items():
                load[key] = value

        if "out" in ret:
            if isinstance(ret["out"], str):
                load["out"] = ret["out"]
            else:
                log.error("Invalid outputter %s. This is likely a bug.", ret["out"])
        else:
            try:
                oput = self.functions[fun].__outputter__
            except (KeyError, AttributeError, TypeError):
                pass
            else:
                if isinstance(oput, str):
                    load["out"] = oput
        if self.opts["cache_jobs"]:
            # Local job cache has been enabled
            if ret["jid"] == "req":
                ret["jid"] = salt.utils.jid.gen_jid(self.opts)
            salt.utils.minion.cache_jobs(self.opts, ret["jid"], ret)

        if not self.opts["pub_ret"]:
            return ""

        def timeout_handler(*_):
            log.warning(
                "The minion failed to return the job information for job %s. "
                "This is often due to the master being shut down or "
                "overloaded. If the master is running, consider increasing "
                "the worker_threads value.",
                jid,
            )
            return True

        if sync:
            try:
                ret_val = self._send_req_sync(load, timeout=timeout)
            except SaltReqTimeoutError:
                timeout_handler()
                return ""
        else:
            with salt.ext.tornado.stack_context.ExceptionStackContext(timeout_handler):
                # pylint: disable=unexpected-keyword-arg
                ret_val = self._send_req_async(
                    load, timeout=timeout, callback=lambda f: None
                )
                # pylint: enable=unexpected-keyword-arg

        log.trace("ret_val = %s", ret_val)  # pylint: disable=no-member
        return ret_val

    def _return_pub_multi(self, rets, ret_cmd="_return", timeout=60, sync=True):
        """
        Return the data from the executed command to the master server
        """
        if not isinstance(rets, list):
            rets = [rets]
        jids = {}
        for ret in rets:
            jid = ret.get("jid", ret.get("__jid__"))
            fun = ret.get("fun", ret.get("__fun__"))
            if self.opts["multiprocessing"]:
                fn_ = os.path.join(self.proc_dir, jid)
                if os.path.isfile(fn_):
                    try:
                        os.remove(fn_)
                    except OSError:
                        # The file is gone already
                        pass
            log.info("Returning information for job: %s", jid)
            load = jids.setdefault(jid, {})
            if ret_cmd == "_syndic_return":
                if not load:
                    load.update(
                        {
                            "id": self.opts["id"],
                            "jid": jid,
                            "fun": fun,
                            "arg": ret.get("arg"),
                            "tgt": ret.get("tgt"),
                            "tgt_type": ret.get("tgt_type"),
                            "load": ret.get("__load__"),
                            "return": {},
                        }
                    )
                if "__master_id__" in ret:
                    load["master_id"] = ret["__master_id__"]
                for key, value in ret.items():
                    if key.startswith("__"):
                        continue
                    load["return"][key] = value
            else:
                load.update({"id": self.opts["id"]})
                for key, value in ret.items():
                    load[key] = value

            if "out" in ret:
                if isinstance(ret["out"], str):
                    load["out"] = ret["out"]
                else:
                    log.error("Invalid outputter %s. This is likely a bug.", ret["out"])
            else:
                try:
                    oput = self.functions[fun].__outputter__
                except (KeyError, AttributeError, TypeError):
                    pass
                else:
                    if isinstance(oput, str):
                        load["out"] = oput
            if self.opts["cache_jobs"]:
                # Local job cache has been enabled
                salt.utils.minion.cache_jobs(self.opts, load["jid"], ret)

        load = {"cmd": ret_cmd, "load": list(jids.values())}

        def timeout_handler(*_):
            log.warning(
                "The minion failed to return the job information for job %s. "
                "This is often due to the master being shut down or "
                "overloaded. If the master is running, consider increasing "
                "the worker_threads value.",
                jid,
            )
            return True

        if sync:
            try:
                ret_val = self._send_req_sync(load, timeout=timeout)
            except SaltReqTimeoutError:
                timeout_handler()
                return ""
        else:
            with salt.ext.tornado.stack_context.ExceptionStackContext(timeout_handler):
                # pylint: disable=unexpected-keyword-arg
                ret_val = self._send_req_async(
                    load, timeout=timeout, callback=lambda f: None
                )
                # pylint: enable=unexpected-keyword-arg

        log.trace("ret_val = %s", ret_val)  # pylint: disable=no-member
        return ret_val

    def _state_run(self):
        """
        Execute a state run based on information set in the minion config file
        """
        if self.opts["startup_states"]:
            if (
                self.opts.get("master_type", "str") == "disable"
                and self.opts.get("file_client", "remote") == "remote"
            ):
                log.warning(
                    "Cannot run startup_states when 'master_type' is set "
                    "to 'disable' and 'file_client' is set to "
                    "'remote'. Skipping."
                )
            else:
                data = {"jid": "req", "ret": self.opts.get("ext_job_cache", "")}
                if self.opts["startup_states"] == "sls":
                    data["fun"] = "state.sls"
                    data["arg"] = [self.opts["sls_list"]]
                elif self.opts["startup_states"] == "top":
                    data["fun"] = "state.top"
                    data["arg"] = [self.opts["top_file"]]
                else:
                    data["fun"] = "state.highstate"
                    data["arg"] = []
                self._handle_decoded_payload(data)

    def _refresh_grains_watcher(self, refresh_interval_in_minutes):
        """
        Create a loop that will fire a pillar refresh to inform a master about a change in the grains of this minion
        :param refresh_interval_in_minutes:
        :return: None
        """
        if "__update_grains" not in self.opts.get("schedule", {}):
            if "schedule" not in self.opts:
                self.opts["schedule"] = {}
            self.opts["schedule"].update(
                {
                    "__update_grains": {
                        "function": "event.fire",
                        "args": [{}, "grains_refresh"],
                        "minutes": refresh_interval_in_minutes,
                    }
                }
            )

    def _fire_master_minion_start(self):
        include_grains = False
        if self.opts["start_event_grains"]:
            include_grains = True
        # Send an event to the master that the minion is live
        if self.opts["enable_legacy_startup_events"]:
            # Old style event. Defaults to False in 3001 release.
            self._fire_master(
                "Minion {} started at {}".format(self.opts["id"], time.asctime()),
                "minion_start",
                include_startup_grains=include_grains,
            )
        # send name spaced event
        self._fire_master(
            "Minion {} started at {}".format(self.opts["id"], time.asctime()),
            tagify([self.opts["id"], "start"], "minion"),
            include_startup_grains=include_grains,
        )

    def module_refresh(self, force_refresh=False, notify=False):
        """
        Refresh the functions and returners.
        """
        log.debug("Refreshing modules. Notify=%s", notify)
        self.functions, self.returners, _, self.executors = self._load_modules(
            force_refresh, notify=notify
        )

        self.schedule.functions = self.functions
        self.schedule.returners = self.returners

    def beacons_refresh(self):
        """
        Refresh the functions and returners.
        """
        if not self.beacons_leader:
            return
        log.debug("Refreshing beacons.")
        self.beacons = salt.beacons.Beacon(self.opts, self.functions)

    def matchers_refresh(self):
        """
        Refresh the matchers
        """
        log.debug("Refreshing matchers.")
        self.matchers = salt.loader.matchers(self.opts)

    # TODO: only allow one future in flight at a time?
    @salt.ext.tornado.gen.coroutine
    def pillar_refresh(self, force_refresh=False):
        """
        Refresh the pillar
        """
        self.module_refresh(force_refresh)

        if self.connected:
            log.debug("Refreshing pillar.")
            async_pillar = salt.pillar.get_async_pillar(
                self.opts,
                self.opts["grains"],
                self.opts["id"],
                self.opts["saltenv"],
                pillarenv=self.opts.get("pillarenv"),
            )
            try:
                self.opts["pillar"] = yield async_pillar.compile_pillar()
            except SaltClientError:
                # Do not exit if a pillar refresh fails.
                log.error(
                    "Pillar data could not be refreshed. "
                    "One or more masters may be down!"
                )
            finally:
                async_pillar.destroy()
        self.matchers_refresh()
        self.beacons_refresh()
        with salt.utils.event.get_event("minion", opts=self.opts, listen=False) as evt:
            evt.fire_event(
                {"complete": True},
                tag=salt.defaults.events.MINION_PILLAR_REFRESH_COMPLETE,
            )

    def manage_schedule(self, tag, data):
        """
        Refresh the functions and returners.
        """
        func = data.get("func", None)
        name = data.get("name", None)
        schedule = data.get("schedule", None)
        where = data.get("where", None)
        persist = data.get("persist", None)

        funcs = {
            "delete": ("delete_job", (name, persist)),
            "add": ("add_job", (schedule, persist)),
            "modify": ("modify_job", (name, schedule, persist)),
            "enable": ("enable_schedule", (persist,)),
            "disable": ("disable_schedule", (persist,)),
            "enable_job": ("enable_job", (name, persist)),
            "run_job": ("run_job", (name,)),
            "disable_job": ("disable_job", (name, persist)),
            "postpone_job": ("postpone_job", (name, data)),
            "skip_job": ("skip_job", (name, data)),
            "reload": ("reload", (schedule,)),
            "list": ("list", (where,)),
            "save_schedule": ("save_schedule", ()),
            "get_next_fire_time": ("get_next_fire_time", (name,)),
        }

        # Call the appropriate schedule function
        try:
            alias, params = funcs.get(func)
            getattr(self.schedule, alias)(*params)
        except TypeError:
            log.error('Function "%s" is unavailable in salt.utils.scheduler', func)

    def manage_beacons(self, tag, data):
        """
        Manage Beacons
        """
        if not self.beacons_leader:
            return

        func = data.get("func", None)
        name = data.get("name", None)
        beacon_data = data.get("beacon_data", None)
        include_pillar = data.get("include_pillar", None)
        include_opts = data.get("include_opts", None)

        funcs = {
            "add": ("add_beacon", (name, beacon_data)),
            "modify": ("modify_beacon", (name, beacon_data)),
            "delete": ("delete_beacon", (name,)),
            "enable": ("enable_beacons", ()),
            "disable": ("disable_beacons", ()),
            "enable_beacon": ("enable_beacon", (name,)),
            "disable_beacon": ("disable_beacon", (name,)),
            "list": ("list_beacons", (include_opts, include_pillar)),
            "list_available": ("list_available_beacons", ()),
            "validate_beacon": ("validate_beacon", (name, beacon_data)),
            "reset": ("reset", ()),
        }

        # Call the appropriate beacon function
        try:
            alias, params = funcs.get(func)
            getattr(self.beacons, alias)(*params)
        except TypeError:
            log.error('Function "%s" is unavailable in salt.utils.beacons', func)

    def environ_setenv(self, tag, data):
        """
        Set the salt-minion main process environment according to
        the data contained in the minion event data
        """
        environ = data.get("environ", None)
        if environ is None:
            return False
        false_unsets = data.get("false_unsets", False)
        clear_all = data.get("clear_all", False)
        import salt.modules.environ as mod_environ

        return mod_environ.setenv(environ, false_unsets, clear_all)

    def _pre_tune(self):
        """
        Set the minion running flag and issue the appropriate warnings if
        the minion cannot be started or is already running
        """
        if self._running is None:
            self._running = True
        elif self._running is False:
            log.error(
                "This %s was scheduled to stop. Not running %s.tune_in()",
                self.__class__.__name__,
                self.__class__.__name__,
            )
            return
        elif self._running is True:
            log.error(
                "This %s is already running. Not running %s.tune_in()",
                self.__class__.__name__,
                self.__class__.__name__,
            )
            return

        try:
            log.info(
                "%s is starting as user '%s'",
                self.__class__.__name__,
                salt.utils.user.get_user(),
            )
        except Exception as err:  # pylint: disable=broad-except
            # Only windows is allowed to fail here. See #3189. Log as debug in
            # that case. Else, error.
            log.log(
                salt.utils.platform.is_windows() and logging.DEBUG or logging.ERROR,
                "Failed to get the user who is starting %s",
                self.__class__.__name__,
                exc_info=err,
            )

    def _mine_send(self, tag, data):
        """
        Send mine data to the master
        """
        with salt.transport.client.ReqChannel.factory(self.opts) as channel:
            data["tok"] = self.tok
            try:
                ret = channel.send(data)
                return ret
            except SaltReqTimeoutError:
                log.warning("Unable to send mine data to master.")
                return None

    @salt.ext.tornado.gen.coroutine
    def handle_event(self, package):
        """
        Handle an event from the epull_sock (all local minion events)
        """
        if not self.ready:
            raise salt.ext.tornado.gen.Return()
        tag, data = salt.utils.event.SaltEvent.unpack(package)

        if "proxy_target" in data and self.opts.get("metaproxy") == "deltaproxy":
            proxy_target = data["proxy_target"]
            _minion = self.deltaproxy_objs[proxy_target]
        else:
            _minion = self

        log.debug("Minion of '%s' is handling event tag '%s'", self.opts["master"], tag)
        if tag.startswith("module_refresh"):
            _minion.module_refresh(
                force_refresh=data.get("force_refresh", False),
                notify=data.get("notify", False),
            )
        elif tag.startswith("pillar_refresh"):
            yield _minion.pillar_refresh(force_refresh=data.get("force_refresh", False))
        elif tag.startswith("beacons_refresh"):
            _minion.beacons_refresh()
        elif tag.startswith("matchers_refresh"):
            _minion.matchers_refresh()
        elif tag.startswith("manage_schedule"):
            _minion.manage_schedule(tag, data)
        elif tag.startswith("manage_beacons"):
            _minion.manage_beacons(tag, data)
        elif tag.startswith("grains_refresh"):
            if (
                data.get("force_refresh", False)
                or _minion.grains_cache != _minion.opts["grains"]
            ):
                _minion.pillar_refresh(force_refresh=True)
                _minion.grains_cache = _minion.opts["grains"]
        elif tag.startswith("environ_setenv"):
            self.environ_setenv(tag, data)
        elif tag.startswith("_minion_mine"):
            self._mine_send(tag, data)
        elif tag.startswith("fire_master"):
            if self.connected:
                log.debug("Forwarding master event tag=%s", data["tag"])
                self._fire_master(
                    data["data"],
                    data["tag"],
                    data["events"],
                    data["pretag"],
                    sync=False,
                )
        elif tag.startswith(master_event(type="disconnected")) or tag.startswith(
            master_event(type="failback")
        ):
            # if the master disconnect event is for a different master, raise an exception
            if (
                tag.startswith(master_event(type="disconnected"))
                and data["master"] != self.opts["master"]
            ):
                # not mine master, ignore
                raise salt.ext.tornado.gen.Return()
            if tag.startswith(master_event(type="failback")):
                # if the master failback event is not for the top master, raise an exception
                if data["master"] != self.opts["master_list"][0]:
                    raise SaltException(
                        "Bad master '{}' when mine failback is '{}'".format(
                            data["master"], self.opts["master"]
                        )
                    )
                # if the master failback event is for the current master, raise an exception
                elif data["master"] == self.opts["master"][0]:
                    raise SaltException(
                        "Already connected to '{}'".format(data["master"])
                    )

            if self.connected:
                # we are not connected anymore
                self.connected = False
                log.info("Connection to master %s lost", self.opts["master"])

                if self.opts["master_type"] != "failover":
                    # modify the scheduled job to fire on reconnect
                    if self.opts["transport"] != "tcp":
                        schedule = {
                            "function": "status.master",
                            "seconds": self.opts["master_alive_interval"],
                            "jid_include": True,
                            "maxrunning": 1,
                            "return_job": False,
                            "kwargs": {
                                "master": self.opts["master"],
                                "connected": False,
                            },
                        }
                        self.schedule.modify_job(
                            name=master_event(type="alive", master=self.opts["master"]),
                            schedule=schedule,
                        )
                else:
                    # delete the scheduled job to don't interfere with the failover process
                    if self.opts["transport"] != "tcp":
                        self.schedule.delete_job(name=master_event(type="alive"))

                    log.info("Trying to tune in to next master from master-list")

                    if hasattr(self, "pub_channel"):
                        self.pub_channel.on_recv(None)
                        if hasattr(self.pub_channel, "auth"):
                            self.pub_channel.auth.invalidate()
                        if hasattr(self.pub_channel, "close"):
                            self.pub_channel.close()
                        del self.pub_channel

                    # if eval_master finds a new master for us, self.connected
                    # will be True again on successful master authentication
                    try:
                        master, self.pub_channel = yield self.eval_master(
                            opts=self.opts,
                            failed=True,
                            failback=tag.startswith(master_event(type="failback")),
                        )
                    except SaltClientError:
                        pass

                    if self.connected:
                        self.opts["master"] = master

                        # re-init the subsystems to work with the new master
                        log.info(
                            "Re-initialising subsystems for new master %s",
                            self.opts["master"],
                        )
                        # put the current schedule into the new loaders
                        self.opts["schedule"] = self.schedule.option("schedule")
                        (
                            self.functions,
                            self.returners,
                            self.function_errors,
                            self.executors,
                        ) = self._load_modules()
                        # make the schedule to use the new 'functions' loader
                        self.schedule.functions = self.functions
                        self.pub_channel.on_recv(self._handle_payload)
                        self._fire_master_minion_start()
                        log.info("Minion is ready to receive requests!")

                        # update scheduled job to run with the new master addr
                        if self.opts["transport"] != "tcp":
                            schedule = {
                                "function": "status.master",
                                "seconds": self.opts["master_alive_interval"],
                                "jid_include": True,
                                "maxrunning": 1,
                                "return_job": False,
                                "kwargs": {
                                    "master": self.opts["master"],
                                    "connected": True,
                                },
                            }
                            self.schedule.modify_job(
                                name=master_event(
                                    type="alive", master=self.opts["master"]
                                ),
                                schedule=schedule,
                            )

                            if (
                                self.opts["master_failback"]
                                and "master_list" in self.opts
                            ):
                                if self.opts["master"] != self.opts["master_list"][0]:
                                    schedule = {
                                        "function": "status.ping_master",
                                        "seconds": self.opts[
                                            "master_failback_interval"
                                        ],
                                        "jid_include": True,
                                        "maxrunning": 1,
                                        "return_job": False,
                                        "kwargs": {
                                            "master": self.opts["master_list"][0]
                                        },
                                    }
                                    self.schedule.modify_job(
                                        name=master_event(type="failback"),
                                        schedule=schedule,
                                    )
                                else:
                                    self.schedule.delete_job(
                                        name=master_event(type="failback"), persist=True
                                    )
                    else:
                        self.restart = True
                        self.io_loop.stop()

        elif tag.startswith(master_event(type="connected")):
            # handle this event only once. otherwise it will pollute the log
            # also if master type is failover all the reconnection work is done
            # by `disconnected` event handler and this event must never happen,
            # anyway check it to be sure
            if not self.connected and self.opts["master_type"] != "failover":
                log.info("Connection to master %s re-established", self.opts["master"])
                self.connected = True
                # modify the __master_alive job to only fire,
                # if the connection is lost again
                if self.opts["transport"] != "tcp":
                    schedule = {
                        "function": "status.master",
                        "seconds": self.opts["master_alive_interval"],
                        "jid_include": True,
                        "maxrunning": 1,
                        "return_job": False,
                        "kwargs": {"master": self.opts["master"], "connected": True},
                    }

                    self.schedule.modify_job(
                        name=master_event(type="alive", master=self.opts["master"]),
                        schedule=schedule,
                    )
        elif tag.startswith("__schedule_return"):
            # reporting current connection with master
            if data["schedule"].startswith(master_event(type="alive", master="")):
                if data["return"]:
                    log.debug(
                        "Connected to master %s",
                        data["schedule"].split(master_event(type="alive", master=""))[
                            1
                        ],
                    )
            self._return_pub(data, ret_cmd="_return", sync=False)
        elif tag.startswith("_salt_error"):
            if self.connected:
                log.debug("Forwarding salt error event tag=%s", tag)
                self._fire_master(data, tag, sync=False)
        elif tag.startswith("salt/auth/creds"):
            key = tuple(data["key"])
            log.debug(
                "Updating auth data for %s: %s -> %s",
                key,
                salt.crypt.AsyncAuth.creds_map.get(key),
                data["creds"],
            )
            salt.crypt.AsyncAuth.creds_map[tuple(data["key"])] = data["creds"]
        elif tag.startswith("__beacons_return"):
            if self.connected:
                log.debug("Firing beacons to master")
                self._fire_master(events=data["beacons"])

    def cleanup_subprocesses(self):
        """
        Clean up subprocesses and spawned threads.
        """
        # Add an extra fallback in case a forked process leaks through
        multiprocessing.active_children()
        self.subprocess_list.cleanup()
        if self.schedule:
            self.schedule.cleanup_subprocesses()

    def _setup_core(self):
        """
        Set up the core minion attributes.
        This is safe to call multiple times.
        """
        if not self.ready:
            # First call. Initialize.
            (
                self.functions,
                self.returners,
                self.function_errors,
                self.executors,
            ) = self._load_modules()
            self.serial = salt.payload.Serial(self.opts)
            self.mod_opts = self._prep_mod_opts()
            #            self.matcher = Matcher(self.opts, self.functions)
            self.matchers = salt.loader.matchers(self.opts)
            if self.beacons_leader:
                self.beacons = salt.beacons.Beacon(self.opts, self.functions)
            uid = salt.utils.user.get_uid(user=self.opts.get("user", None))
            self.proc_dir = get_proc_dir(self.opts["cachedir"], uid=uid)
            self.grains_cache = self.opts["grains"]
            self.ready = True

    def setup_beacons(self, before_connect=False):
        """
        Set up the beacons.
        This is safe to call multiple times.
        """
        # In multimaster configuration the only one minion shall execute beacons
        if not self.beacons_leader:
            return

        self._setup_core()
        loop_interval = self.opts["loop_interval"]
        if "beacons" not in self.periodic_callbacks:
            self.beacons = salt.beacons.Beacon(self.opts, self.functions)

            def handle_beacons():
                # Process Beacons
                beacons = None
                try:
                    beacons = self.process_beacons(self.functions)
                except Exception:  # pylint: disable=broad-except
                    log.critical("The beacon errored: ", exc_info=True)
                if beacons:
                    event = salt.utils.event.get_event(
                        "minion", opts=self.opts, listen=False
                    )
                    event.fire_event({"beacons": beacons}, "__beacons_return")
                    event.destroy()

            if before_connect:
                # Make sure there is a chance for one iteration to occur before connect
                handle_beacons()

            self.add_periodic_callback("beacons", handle_beacons)

    def setup_scheduler(self, before_connect=False):
        """
        Set up the scheduler.
        This is safe to call multiple times.
        """
        self._setup_core()

        loop_interval = self.opts["loop_interval"]

        if "schedule" not in self.periodic_callbacks:
            if "schedule" not in self.opts:
                self.opts["schedule"] = {}
            if not hasattr(self, "schedule"):
                self.schedule = salt.utils.schedule.Schedule(
                    self.opts,
                    self.functions,
                    self.returners,
                    utils=self.utils,
                    cleanup=[master_event(type="alive")],
                )

            try:
                if self.opts["grains_refresh_every"]:  # In minutes, not seconds!
                    log.debug(
                        "Enabling the grains refresher. Will run every %d minute(s).",
                        self.opts["grains_refresh_every"],
                    )
                    self._refresh_grains_watcher(abs(self.opts["grains_refresh_every"]))
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Exception occurred in attempt to initialize grain refresh "
                    "routine during minion tune-in: %s",
                    exc,
                )

            # TODO: actually listen to the return and change period
            def handle_schedule():
                self.process_schedule(self, loop_interval)

            if before_connect:
                # Make sure there is a chance for one iteration to occur before connect
                handle_schedule()

            self.add_periodic_callback("schedule", handle_schedule)

    def add_periodic_callback(self, name, method, interval=1):
        """
        Add a periodic callback to the event loop and call its start method.
        If a callback by the given name exists this method returns False
        """
        if name in self.periodic_callbacks:
            return False
        self.periodic_callbacks[name] = salt.ext.tornado.ioloop.PeriodicCallback(
            method, interval * 1000,
        )
        self.periodic_callbacks[name].start()
        return True

    def remove_periodic_callback(self, name):
        """
        Remove a periodic callback.
        If a callback by the given name does not exist this method returns False
        """
        callback = self.periodic_callbacks.pop(name, None)
        if callback is None:
            return False
        callback.stop()
        return True

    # Main Minion Tune In
    def tune_in(self, start=True):
        """
        Lock onto the publisher. This is the main event loop for the minion
        :rtype : None
        """
        self._pre_tune()

        log.debug("Minion '%s' trying to tune in", self.opts["id"])

        if start:
            if self.opts.get("beacons_before_connect", False):
                self.setup_beacons(before_connect=True)
            if self.opts.get("scheduler_before_connect", False):
                self.setup_scheduler(before_connect=True)
            self.sync_connect_master()
        if self.connected:
            self._fire_master_minion_start()
            log.info("Minion is ready to receive requests!")

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        # Make sure to gracefully handle CTRL_LOGOFF_EVENT
        if HAS_WIN_FUNCTIONS:
            salt.utils.win_functions.enable_ctrl_logoff_handler()

        # On first startup execute a state run if configured to do so
        self._state_run()

        self.setup_beacons()
        self.setup_scheduler()
        self.add_periodic_callback("cleanup", self.cleanup_subprocesses)

        # schedule the stuff that runs every interval
        ping_interval = self.opts.get("ping_interval", 0) * 60
        if ping_interval > 0 and self.connected:

            def ping_master():
                try:

                    def ping_timeout_handler(*_):
                        if self.opts.get("auth_safemode", False):
                            log.error(
                                "** Master Ping failed. Attempting to restart minion**"
                            )
                            delay = self.opts.get("random_reauth_delay", 5)
                            log.info("delaying random_reauth_delay %ss", delay)
                            try:
                                self.functions["service.restart"](service_name())
                            except KeyError:
                                # Probably no init system (running in docker?)
                                log.warning(
                                    "ping_interval reached without response "
                                    "from the master, but service.restart "
                                    "could not be run to restart the minion "
                                    "daemon. ping_interval requires that the "
                                    "minion is running under an init system."
                                )

                    self._fire_master(
                        "ping",
                        "minion_ping",
                        sync=False,
                        timeout_handler=ping_timeout_handler,
                    )
                except Exception:  # pylint: disable=broad-except
                    log.warning(
                        "Attempt to ping master failed.", exc_on_loglevel=logging.DEBUG
                    )

            self.remove_periodic_callback("ping")
            self.add_periodic_callback("ping", ping_master, ping_interval)

        # add handler to subscriber
        if hasattr(self, "pub_channel") and self.pub_channel is not None:
            self.pub_channel.on_recv(self._handle_payload)
        elif self.opts.get("master_type") != "disable":
            log.error("No connection to master found. Scheduled jobs will not run.")

        if start:
            try:
                self.io_loop.start()
                if self.restart:
                    self.destroy()
            except (
                KeyboardInterrupt,
                RuntimeError,
            ):  # A RuntimeError can be re-raised by Tornado on shutdown
                self.destroy()

    def _handle_payload(self, payload):
        if payload is not None and payload["enc"] == "aes":
            if self._target_load(payload["load"]):
                self._handle_decoded_payload(payload["load"])
            elif self.opts["zmq_filtering"]:
                # In the filtering enabled case, we'd like to know when minion sees something it shouldnt
                log.trace(
                    "Broadcast message received not for this minion, Load: %s",
                    payload["load"],
                )
        # If it's not AES, and thus has not been verified, we do nothing.
        # In the future, we could add support for some clearfuncs, but
        # the minion currently has no need.

    def _target_load(self, load):
        # Verify that the publication is valid
        if (
            "tgt" not in load
            or "jid" not in load
            or "fun" not in load
            or "arg" not in load
        ):
            return False
        # Verify that the publication applies to this minion

        # It's important to note that the master does some pre-processing
        # to determine which minions to send a request to. So for example,
        # a "salt -G 'grain_key:grain_val' test.ping" will invoke some
        # pre-processing on the master and this minion should not see the
        # publication if the master does not determine that it should.

        if "tgt_type" in load:
            match_func = self.matchers.get(
                "{}_match.match".format(load["tgt_type"]), None
            )
            if match_func is None:
                return False
            if load["tgt_type"] in ("grain", "grain_pcre", "pillar"):
                delimiter = load.get("delimiter", DEFAULT_TARGET_DELIM)
                if not match_func(load["tgt"], delimiter=delimiter):
                    return False
            elif not match_func(load["tgt"]):
                return False
        else:
            if not self.matchers["glob_match.match"](load["tgt"]):
                return False

        return True

    def destroy(self):
        """
        Tear down the minion
        """
        if self._running is False:
            return

        self._running = False
        if hasattr(self, "schedule"):
            del self.schedule
        if hasattr(self, "pub_channel") and self.pub_channel is not None:
            self.pub_channel.on_recv(None)
            if hasattr(self.pub_channel, "close"):
                self.pub_channel.close()
            del self.pub_channel
        if hasattr(self, "periodic_callbacks"):
            for cb in self.periodic_callbacks.values():
                cb.stop()

    # pylint: disable=W1701
    def __del__(self):
        self.destroy()

    # pylint: enable=W1701


class Syndic(Minion):
    """
    Make a Syndic minion, this minion will use the minion keys on the
    master to authenticate with a higher level master.
    """

    def __init__(self, opts, **kwargs):
        self._syndic_interface = opts.get("interface")
        self._syndic = True
        # force auth_safemode True because Syndic don't support autorestart
        opts["auth_safemode"] = True
        opts["loop_interval"] = 1
        super().__init__(opts, **kwargs)
        self.mminion = salt.minion.MasterMinion(opts)
        self.jid_forward_cache = set()
        self.jids = {}
        self.raw_events = []
        self.pub_future = None

    def _handle_decoded_payload(self, data):
        """
        Override this method if you wish to handle the decoded data
        differently.
        """
        # TODO: even do this??
        data["to"] = int(data.get("to", self.opts["timeout"])) - 1
        # Only forward the command if it didn't originate from ourselves
        if data.get("master_id", 0) != self.opts.get("master_id", 1):
            self.syndic_cmd(data)

    def syndic_cmd(self, data):
        """
        Take the now clear load and forward it on to the client cmd
        """
        # Set up default tgt_type
        if "tgt_type" not in data:
            data["tgt_type"] = "glob"
        kwargs = {}

        # optionally add a few fields to the publish data
        for field in (
            "master_id",  # which master the job came from
            "user",  # which user ran the job
        ):
            if field in data:
                kwargs[field] = data[field]

        def timeout_handler(*args):
            log.warning("Unable to forward pub data: %s", args[1])
            return True

        with salt.ext.tornado.stack_context.ExceptionStackContext(timeout_handler):
            self.local.pub_async(
                data["tgt"],
                data["fun"],
                data["arg"],
                data["tgt_type"],
                data["ret"],
                data["jid"],
                data["to"],
                io_loop=self.io_loop,
                callback=lambda _: None,
                **kwargs
            )

    def fire_master_syndic_start(self):
        # Send an event to the master that the minion is live
        if self.opts["enable_legacy_startup_events"]:
            # Old style event. Defaults to false in 3001 release.
            self._fire_master(
                "Syndic {} started at {}".format(self.opts["id"], time.asctime()),
                "syndic_start",
                sync=False,
            )
        self._fire_master(
            "Syndic {} started at {}".format(self.opts["id"], time.asctime()),
            tagify([self.opts["id"], "start"], "syndic"),
            sync=False,
        )

    # TODO: clean up docs
    def tune_in_no_block(self):
        """
        Executes the tune_in sequence but omits extra logging and the
        management of the event bus assuming that these are handled outside
        the tune_in sequence
        """
        # Instantiate the local client
        self.local = salt.client.get_local_client(
            self.opts["_minion_conf_file"], io_loop=self.io_loop
        )

        # add handler to subscriber
        self.pub_channel.on_recv(self._process_cmd_socket)

    def _process_cmd_socket(self, payload):
        if payload is not None and payload["enc"] == "aes":
            log.trace("Handling payload")
            self._handle_decoded_payload(payload["load"])
        # If it's not AES, and thus has not been verified, we do nothing.
        # In the future, we could add support for some clearfuncs, but
        # the syndic currently has no need.

    @salt.ext.tornado.gen.coroutine
    def reconnect(self):
        if hasattr(self, "pub_channel"):
            self.pub_channel.on_recv(None)
            if hasattr(self.pub_channel, "close"):
                self.pub_channel.close()
            del self.pub_channel

        # if eval_master finds a new master for us, self.connected
        # will be True again on successful master authentication
        master, self.pub_channel = yield self.eval_master(opts=self.opts)

        if self.connected:
            self.opts["master"] = master
            self.pub_channel.on_recv(self._process_cmd_socket)
            log.info("Minion is ready to receive requests!")

        raise salt.ext.tornado.gen.Return(self)

    def destroy(self):
        """
        Tear down the syndic minion
        """
        # We borrowed the local clients poller so give it back before
        # it's destroyed. Reset the local poller reference.
        super().destroy()
        if hasattr(self, "local"):
            del self.local

        if hasattr(self, "forward_events"):
            self.forward_events.stop()


# TODO: need a way of knowing if the syndic connection is busted
class SyndicManager(MinionBase):
    """
    Make a MultiMaster syndic minion, this minion will handle relaying jobs and returns from
    all minions connected to it to the list of masters it is connected to.

    Modes (controlled by `syndic_mode`:
        sync: This mode will synchronize all events and publishes from higher level masters
        cluster: This mode will only sync job publishes and returns

    Note: jobs will be returned best-effort to the requesting master. This also means
    (since we are using zmq) that if a job was fired and the master disconnects
    between the publish and return, that the return will end up in a zmq buffer
    in this Syndic headed to that original master.

    In addition, since these classes all seem to use a mix of blocking and non-blocking
    calls (with varying timeouts along the way) this daemon does not handle failure well,
    it will (under most circumstances) stall the daemon for ~15s trying to forward events
    to the down master
    """

    # time to connect to upstream master
    SYNDIC_CONNECT_TIMEOUT = 5
    SYNDIC_EVENT_TIMEOUT = 5

    def __init__(self, opts, io_loop=None):
        opts["loop_interval"] = 1
        super().__init__(opts)
        self.mminion = salt.minion.MasterMinion(opts)
        # sync (old behavior), cluster (only returns and publishes)
        self.syndic_mode = self.opts.get("syndic_mode", "sync")
        self.syndic_failover = self.opts.get("syndic_failover", "random")

        self.auth_wait = self.opts["acceptance_wait_time"]
        self.max_auth_wait = self.opts["acceptance_wait_time_max"]

        self._has_master = threading.Event()
        self.jid_forward_cache = set()

        if io_loop is None:
            install_zmq()
            self.io_loop = ZMQDefaultLoop.current()
        else:
            self.io_loop = io_loop

        # List of events
        self.raw_events = []
        # Dict of rets: {master_id: {event_tag: job_ret, ...}, ...}
        self.job_rets = {}
        # List of delayed job_rets which was unable to send for some reason and will be resend to
        # any available master
        self.delayed = []
        # Active pub futures: {master_id: (future, [job_ret, ...]), ...}
        self.pub_futures = {}

    def _spawn_syndics(self):
        """
        Spawn all the coroutines which will sign in the syndics
        """
        self._syndics = OrderedDict()  # mapping of opts['master'] -> syndic
        masters = self.opts["master"]
        if not isinstance(masters, list):
            masters = [masters]
        for master in masters:
            s_opts = copy.copy(self.opts)
            s_opts["master"] = master
            self._syndics[master] = self._connect_syndic(s_opts)

    @salt.ext.tornado.gen.coroutine
    def _connect_syndic(self, opts):
        """
        Create a syndic, and asynchronously connect it to a master
        """
        last = 0  # never have we signed in
        auth_wait = opts["acceptance_wait_time"]
        failed = False
        while True:
            log.debug("Syndic attempting to connect to %s", opts["master"])
            try:
                syndic = Syndic(
                    opts,
                    timeout=self.SYNDIC_CONNECT_TIMEOUT,
                    safe=False,
                    io_loop=self.io_loop,
                )
                yield syndic.connect_master(failed=failed)
                # set up the syndic to handle publishes (specifically not event forwarding)
                syndic.tune_in_no_block()

                # Send an event to the master that the minion is live
                syndic.fire_master_syndic_start()

                log.info("Syndic successfully connected to %s", opts["master"])
                break
            except SaltClientError as exc:
                failed = True
                log.error(
                    "Error while bringing up syndic for multi-syndic. Is the "
                    "master at %s responding?",
                    opts["master"],
                )
                last = time.time()
                if auth_wait < self.max_auth_wait:
                    auth_wait += self.auth_wait
                yield salt.ext.tornado.gen.sleep(auth_wait)  # TODO: log?
            except (KeyboardInterrupt, SystemExit):  # pylint: disable=try-except-raise
                raise
            except Exception:  # pylint: disable=broad-except
                failed = True
                log.critical(
                    "Unexpected error while connecting to %s",
                    opts["master"],
                    exc_info=True,
                )

        raise salt.ext.tornado.gen.Return(syndic)

    def _mark_master_dead(self, master):
        """
        Mark a master as dead. This will start the sign-in routine
        """
        # if its connected, mark it dead
        if self._syndics[master].done():
            syndic = self._syndics[master].result()  # pylint: disable=no-member
            self._syndics[master] = syndic.reconnect()
        else:
            # TODO: debug?
            log.info(
                "Attempting to mark %s as dead, although it is already " "marked dead",
                master,
            )

    def _call_syndic(self, func, args=(), kwargs=None, master_id=None):
        """
        Wrapper to call a given func on a syndic, best effort to get the one you asked for
        """
        if kwargs is None:
            kwargs = {}
        successful = False
        # Call for each master
        for master, syndic_future in self.iter_master_options(master_id):
            if not syndic_future.done() or syndic_future.exception():
                log.error(
                    "Unable to call %s on %s, that syndic is not connected",
                    func,
                    master,
                )
                continue

            try:
                getattr(syndic_future.result(), func)(*args, **kwargs)
                successful = True
            except SaltClientError:
                log.error("Unable to call %s on %s, trying another...", func, master)
                self._mark_master_dead(master)
        if not successful:
            log.critical("Unable to call %s on any masters!", func)

    def _return_pub_syndic(self, values, master_id=None):
        """
        Wrapper to call the '_return_pub_multi' a syndic, best effort to get the one you asked for
        """
        func = "_return_pub_multi"
        for master, syndic_future in self.iter_master_options(master_id):
            if not syndic_future.done() or syndic_future.exception():
                log.error(
                    "Unable to call %s on %s, that syndic is not connected",
                    func,
                    master,
                )
                continue

            future, data = self.pub_futures.get(master, (None, None))
            if future is not None:
                if not future.done():
                    if master == master_id:
                        # Targeted master previous send not done yet, call again later
                        return False
                    else:
                        # Fallback master is busy, try the next one
                        continue
                elif future.exception():
                    # Previous execution on this master returned an error
                    log.error(
                        "Unable to call %s on %s, trying another...", func, master
                    )
                    self._mark_master_dead(master)
                    del self.pub_futures[master]
                    # Add not sent data to the delayed list and try the next master
                    self.delayed.extend(data)
                    continue
            future = getattr(syndic_future.result(), func)(
                values, "_syndic_return", timeout=self._return_retry_timer(), sync=False
            )
            self.pub_futures[master] = (future, values)
            return True
        # Loop done and didn't exit: wasn't sent, try again later
        return False

    def iter_master_options(self, master_id=None):
        """
        Iterate (in order) over your options for master
        """
        masters = list(self._syndics.keys())
        if self.opts["syndic_failover"] == "random":
            shuffle(masters)
        if master_id not in self._syndics:
            master_id = masters.pop(0)
        else:
            masters.remove(master_id)

        while True:
            yield master_id, self._syndics[master_id]
            if not masters:
                break
            master_id = masters.pop(0)

    def _reset_event_aggregation(self):
        self.job_rets = {}
        self.raw_events = []

    def reconnect_event_bus(self, something):
        future = self.local.event.set_event_handler(self._process_event)
        self.io_loop.add_future(future, self.reconnect_event_bus)

    # Syndic Tune In
    def tune_in(self):
        """
        Lock onto the publisher. This is the main event loop for the syndic
        """
        self._spawn_syndics()
        # Instantiate the local client
        self.local = salt.client.get_local_client(
            self.opts["_minion_conf_file"], io_loop=self.io_loop
        )
        self.local.event.subscribe("")

        log.debug("SyndicManager '%s' trying to tune in", self.opts["id"])

        # register the event sub to the poller
        self.job_rets = {}
        self.raw_events = []
        self._reset_event_aggregation()
        future = self.local.event.set_event_handler(self._process_event)
        self.io_loop.add_future(future, self.reconnect_event_bus)

        # forward events every syndic_event_forward_timeout
        self.forward_events = salt.ext.tornado.ioloop.PeriodicCallback(
            self._forward_events, self.opts["syndic_event_forward_timeout"] * 1000,
        )
        self.forward_events.start()

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        self.io_loop.start()

    def _process_event(self, raw):
        # TODO: cleanup: Move down into event class
        mtag, data = self.local.event.unpack(raw, self.local.event.serial)
        log.trace("Got event %s", mtag)  # pylint: disable=no-member

        tag_parts = mtag.split("/")
        if (
            len(tag_parts) >= 4
            and tag_parts[1] == "job"
            and salt.utils.jid.is_jid(tag_parts[2])
            and tag_parts[3] == "ret"
            and "return" in data
        ):
            if "jid" not in data:
                # Not a job return
                return
            if self.syndic_mode == "cluster" and data.get(
                "master_id", 0
            ) == self.opts.get("master_id", 1):
                log.debug("Return received with matching master_id, not forwarding")
                return

            master = data.get("master_id")
            jdict = self.job_rets.setdefault(master, {}).setdefault(mtag, {})
            if not jdict:
                jdict["__fun__"] = data.get("fun")
                jdict["__jid__"] = data["jid"]
                jdict["__load__"] = {}
                fstr = "{}.get_load".format(self.opts["master_job_cache"])
                # Only need to forward each load once. Don't hit the disk
                # for every minion return!
                if data["jid"] not in self.jid_forward_cache:
                    jdict["__load__"].update(self.mminion.returners[fstr](data["jid"]))
                    self.jid_forward_cache.add(data["jid"])
                    if (
                        len(self.jid_forward_cache)
                        > self.opts["syndic_jid_forward_cache_hwm"]
                    ):
                        # Pop the oldest jid from the cache
                        tmp = sorted(list(self.jid_forward_cache))
                        tmp.pop(0)
                        self.jid_forward_cache = set(tmp)
            if master is not None:
                # __'s to make sure it doesn't print out on the master cli
                jdict["__master_id__"] = master
            ret = {}
            for key in "return", "retcode", "success":
                if key in data:
                    ret[key] = data[key]
            jdict[data["id"]] = ret
        else:
            # TODO: config to forward these? If so we'll have to keep track of who
            # has seen them
            # if we are the top level masters-- don't forward all the minion events
            if self.syndic_mode == "sync":
                # Add generic event aggregation here
                if "retcode" not in data:
                    self.raw_events.append({"data": data, "tag": mtag})

    def _forward_events(self):
        log.trace("Forwarding events")  # pylint: disable=no-member
        if self.raw_events:
            events = self.raw_events
            self.raw_events = []
            self._call_syndic(
                "_fire_master",
                kwargs={
                    "events": events,
                    "pretag": tagify(self.opts["id"], base="syndic"),
                    "timeout": self._return_retry_timer(),
                    "sync": False,
                },
            )
        if self.delayed:
            res = self._return_pub_syndic(self.delayed)
            if res:
                self.delayed = []
        for master in list(self.job_rets.keys()):
            values = list(self.job_rets[master].values())
            res = self._return_pub_syndic(values, master_id=master)
            if res:
                del self.job_rets[master]


class ProxyMinionManager(MinionManager):
    """
    Create the multi-minion interface but for proxy minions
    """

    def _create_minion_object(
        self, opts, timeout, safe, io_loop=None, loaded_base_name=None, jid_queue=None
    ):
        """
        Helper function to return the correct type of object
        """
        return ProxyMinion(
            opts,
            timeout,
            safe,
            io_loop=io_loop,
            loaded_base_name=loaded_base_name,
            jid_queue=jid_queue,
        )


def _metaproxy_call(opts, fn_name):
    loaded_base_name = "{}.{}".format(opts["id"], salt.loader.LOADED_BASE_NAME)
    metaproxy = salt.loader.metaproxy(opts, loaded_base_name=loaded_base_name)
    try:
        metaproxy_name = opts["metaproxy"]
    except KeyError:
        metaproxy_name = "proxy"
        errmsg = (
            "No metaproxy key found in opts for id "
            + opts["id"]
            + ". "
            + "Defaulting to standard proxy minion"
        )
        log.error(errmsg)

    metaproxy_fn = metaproxy_name + "." + fn_name
    return metaproxy[metaproxy_fn]


class ProxyMinion(Minion):
    """
    This class instantiates a 'proxy' minion--a minion that does not manipulate
    the host it runs on, but instead manipulates a device that cannot run a minion.
    """

    # TODO: better name...
    @salt.ext.tornado.gen.coroutine
    def _post_master_init(self, master):
        """
        Function to finish init after connecting to a master

        This is primarily loading modules, pillars, etc. (since they need
        to know which master they connected to)

        If this function is changed, please check Minion._post_master_init
        to see if those changes need to be propagated.

        ProxyMinions need a significantly different post master setup,
        which is why the differences are not factored out into separate helper
        functions.
        """
        mp_call = _metaproxy_call(self.opts, "post_master_init")
        return mp_call(self, master)

    def tune_in(self, start=True):
        """
        Lock onto the publisher. This is the main event loop for the minion
        :rtype : None
        """
        mp_call = _metaproxy_call(self.opts, "tune_in")
        return mp_call(self, start)

    def _target_load(self, load):
        """
        Verify that the publication is valid and applies to this minion
        """
        mp_call = _metaproxy_call(self.opts, "target_load")
        return mp_call(self, load)

    def _handle_payload(self, payload):
        mp_call = _metaproxy_call(self.opts, "handle_payload")
        return mp_call(self, payload)

    @salt.ext.tornado.gen.coroutine
    def _handle_decoded_payload(self, data):
        mp_call = _metaproxy_call(self.opts, "handle_decoded_payload")
        return mp_call(self, data)

    @classmethod
    def _target(cls, minion_instance, opts, data, connected):

        mp_call = _metaproxy_call(opts, "target")
        return mp_call(cls, minion_instance, opts, data, connected)

    @classmethod
    def _thread_return(cls, minion_instance, opts, data):
        mp_call = _metaproxy_call(opts, "thread_return")
        return mp_call(cls, minion_instance, opts, data)

    @classmethod
    def _thread_multi_return(cls, minion_instance, opts, data):
        mp_call = _metaproxy_call(opts, "thread_multi_return")
        return mp_call(cls, minion_instance, opts, data)


class SProxyMinion(SMinion):
    """
    Create an object that has loaded all of the minion module functions,
    grains, modules, returners etc.  The SProxyMinion allows developers to
    generate all of the salt minion functions and present them with these
    functions for general use.
    """

    def gen_modules(self, initial_load=False, context=None):
        """
        Tell the minion to reload the execution modules

        CLI Example:

        .. code-block:: bash

            salt '*' sys.reload_modules
        """
        self.opts["grains"] = salt.loader.grains(self.opts)
        self.opts["pillar"] = salt.pillar.get_pillar(
            self.opts,
            self.opts["grains"],
            self.opts["id"],
            saltenv=self.opts["saltenv"],
            pillarenv=self.opts.get("pillarenv"),
        ).compile_pillar()

        if "proxy" not in self.opts["pillar"] and "proxy" not in self.opts:
            errmsg = (
                'No "proxy" configuration key found in pillar or opts '
                "dictionaries for id {id}. Check your pillar/options "
                "configuration and contents. Salt-proxy aborted."
            ).format(id=self.opts["id"])
            log.error(errmsg)
            self._running = False
            raise SaltSystemExit(code=salt.defaults.exitcodes.EX_GENERIC, msg=errmsg)

        if "proxy" not in self.opts:
            self.opts["proxy"] = self.opts["pillar"]["proxy"]

        # Then load the proxy module
        self.proxy = salt.loader.proxy(self.opts)

        self.utils = salt.loader.utils(self.opts, proxy=self.proxy, context=context)

        self.functions = salt.loader.minion_mods(
            self.opts, utils=self.utils, notify=False, proxy=self.proxy, context=context
        )
        self.returners = salt.loader.returners(
            self.opts, functions=self.functions, proxy=self.proxy, context=context
        )
        self.matchers = salt.loader.matchers(self.opts)
        self.functions["sys.reload_modules"] = self.gen_modules
        self.executors = salt.loader.executors(
            self.opts, functions=self.functions, proxy=self.proxy, context=context,
        )

        fq_proxyname = self.opts["proxy"]["proxytype"]

        # we can then sync any proxymodules down from the master
        # we do a sync_all here in case proxy code was installed by
        # SPM or was manually placed in /srv/salt/_modules etc.
        self.functions["saltutil.sync_all"](saltenv=self.opts["saltenv"])

        self.functions.pack["__proxy__"] = self.proxy
        self.proxy.pack["__salt__"] = self.functions
        self.proxy.pack["__ret__"] = self.returners
        self.proxy.pack["__pillar__"] = self.opts["pillar"]

        # Reload utils as well (chicken and egg, __utils__ needs __proxy__ and __proxy__ needs __utils__
        self.utils = salt.loader.utils(self.opts, proxy=self.proxy, context=context)
        self.proxy.pack["__utils__"] = self.utils

        # Reload all modules so all dunder variables are injected
        self.proxy.reload_modules()

        if (
            "{}.init".format(fq_proxyname) not in self.proxy
            or "{}.shutdown".format(fq_proxyname) not in self.proxy
        ):
            errmsg = (
                "Proxymodule {} is missing an init() or a shutdown() or both. ".format(
                    fq_proxyname
                )
                + "Check your proxymodule.  Salt-proxy aborted."
            )
            log.error(errmsg)
            self._running = False
            raise SaltSystemExit(code=salt.defaults.exitcodes.EX_GENERIC, msg=errmsg)

        self.module_executors = self.proxy.get(
            "{}.module_executors".format(fq_proxyname), lambda: []
        )()
        proxy_init_fn = self.proxy[fq_proxyname + ".init"]
        proxy_init_fn(self.opts)

        self.opts["grains"] = salt.loader.grains(self.opts, proxy=self.proxy)

        #  Sync the grains here so the proxy can communicate them to the master
        self.functions["saltutil.sync_grains"](saltenv="base")
        self.grains_cache = self.opts["grains"]
        self.ready = True
