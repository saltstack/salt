"""
This is the a dummy proxy-minion designed for testing the proxy minion subsystem.
"""

import copy
import logging
import os
import pprint
from contextlib import contextmanager

import salt.utils.files
import salt.utils.msgpack
from salt.exceptions import CommandExecutionError, MinionError

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ["dummy"]

log = logging.getLogger(__file__)


# This does nothing, it's here just as an example and to provide a log
# entry when the module is loaded.
def __virtual__():
    """
    Only return if all the modules are available
    """
    log.debug("dummy proxy __virtual__() called...")
    return True


def _save_state(opts, details):
    _id = __context__["dummy_proxy"]["id"]
    cachefile = os.path.join(opts["cachedir"], f"dummy-proxy-{_id}.cache")
    with salt.utils.files.fopen(cachefile, "wb") as pck:
        pck.write(salt.utils.msgpack.packb(details, use_bin_type=True))
    log.warning("Dummy Proxy Saved State(%s):\n%s", cachefile, pprint.pformat(details))


def _load_state(opts):
    _id = __context__["dummy_proxy"]["id"]
    cachefile = os.path.join(opts["cachedir"], f"dummy-proxy-{_id}.cache")
    try:
        with salt.utils.files.fopen(cachefile, "rb") as pck:
            state = salt.utils.msgpack.unpackb(pck.read(), raw=False)
    except FileNotFoundError:
        state = _initial_state()
        _save_state(opts, state)
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Failed to load state: %s", exc, exc_info=True)
        state = _initial_state()
        _save_state(opts, state)
    log.warning("Dummy Proxy Loaded State(%s):\n%s", cachefile, pprint.pformat(state))
    return state


@contextmanager
def _loaded_state(opts):
    state = _load_state(opts)
    original = copy.deepcopy(state)
    try:
        yield state
    finally:
        if state != original:
            _save_state(opts, state)


def _initial_state():
    return {
        "services": {"apache": "running", "ntp": "running", "samba": "stopped"},
        "packages": {
            "coreutils": "1.0",
            "apache": "2.4",
            "tinc": "1.4",
            "redbull": "999.99",
        },
    }


# Every proxy module needs an 'init', though you can
# just put DETAILS['initialized'] = True here if nothing
# else needs to be done.


def init(opts):
    """
    Required.
    Can be used to initialize the server connection.
    """
    # Added to test situation when a proxy minion throws
    # an exception during init.
    if opts["proxy"].get("raise_minion_error"):
        raise MinionError(message="Raising A MinionError.")
    if opts["proxy"].get("raise_commandexec_error"):
        raise CommandExecutionError(message="Raising A CommandExecutionError.")
    __context__["dummy_proxy"] = {"id": opts["id"]}
    log.debug("dummy proxy init() called...")
    with _loaded_state(opts) as state:
        state["initialized"] = True  # pylint: disable=unsupported-assignment-operation


def initialized():
    """
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    """
    with _loaded_state(__opts__) as state:
        return state.get("initialized", False)


def grains():
    """
    Make up some grains
    """
    with _loaded_state(__opts__) as state:
        # pylint: disable=unsupported-assignment-operation,unsupported-membership-test
        state["grains_cache"] = {
            "dummy_grain_1": "one",
            "dummy_grain_2": "two",
            "dummy_grain_3": "three",
        }
        return state["grains_cache"]


def grains_refresh():
    """
    Refresh the grains
    """
    with _loaded_state(__opts__) as state:
        if "grains_cache" in state:  # pylint: disable=unsupported-membership-test
            state.pop("grains_cache")
    return grains()


def fns():
    """
    Method called by grains module.
    """
    return {
        "details": (
            "This key is here because a function in "
            "grains/rest_sample.py called fns() here in the proxymodule."
        )
    }


def service_start(name):
    """
    Start a "service" on the dummy server
    """
    with _loaded_state(__opts__) as state:
        state["services"][name] = "running"
    return "running"


def service_stop(name):
    """
    Stop a "service" on the dummy server
    """
    with _loaded_state(__opts__) as state:
        state["services"][name] = "stopped"
    return "stopped"


def service_restart(name):
    """
    Restart a "service" on the REST server
    """
    return True


def service_list():
    """
    List "services" on the REST server
    """
    with _loaded_state(__opts__) as state:
        return list(state["services"])


def service_status(name):
    """
    Check if a service is running on the REST server
    """
    with _loaded_state(__opts__) as state:
        if state["services"][name] == "running":
            return {"comment": "running"}
        else:
            return {"comment": "stopped"}


def package_list():
    """
    List "packages" installed on the REST server
    """
    with _loaded_state(__opts__) as state:
        return state["packages"]


def package_install(name, **kwargs):
    """
    Install a "package" on the REST server
    """
    if kwargs.get("version", False):
        version = kwargs["version"]
    else:
        version = "1.0"
    with _loaded_state(__opts__) as state:
        state["packages"][name] = version
    return {name: version}


def upgrade():
    """
    "Upgrade" packages
    """
    with _loaded_state(__opts__) as state:
        for p in state["packages"]:
            version_float = float(state["packages"][p])
            version_float = version_float + 1.0
            state["packages"][p] = str(version_float)
        return state["packages"]


def uptodate():
    """
    Call the REST endpoint to see if the packages on the "server" are up to date.
    """
    with _loaded_state(__opts__) as state:
        return state["packages"]


def package_remove(name):
    """
    Remove a "package" on the REST server
    """
    __context__["dummy_proxy"]["foo"] = "bar"
    with _loaded_state(__opts__) as state:
        state["packages"].pop(name)
        return state["packages"]


def package_status(name):
    """
    Check the installation status of a package on the REST server
    """
    with _loaded_state(__opts__) as state:
        if name in state["packages"]:
            return {name: state["packages"][name]}


def ping():
    """
    Degenerate ping
    """
    log.debug("dummy proxy returning ping")
    return True


def shutdown(opts):
    """
    For this proxy shutdown is a no-op
    """
    log.debug("dummy proxy shutdown() called...")
    with _loaded_state(__opts__) as state:
        if "filename" in state:  # pylint: disable=unsupported-membership-test
            os.unlink(state["filename"])


def test_from_state():
    """
    Test function so we have something to call from a state
    :return:
    """
    log.debug("test_from_state called")
    return "testvalue"
