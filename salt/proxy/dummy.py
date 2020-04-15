# -*- coding: utf-8 -*-
"""
This is the a dummy proxy-minion designed for testing the proxy minion subsystem.
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import python libs
import os
import pickle

# Import Salt libs
import salt.ext.six as six
import salt.utils.files

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ["dummy"]


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
DETAILS = {}

DETAILS["services"] = {"apache": "running", "ntp": "running", "samba": "stopped"}
DETAILS["packages"] = {
    "coreutils": "1.0",
    "apache": "2.4",
    "tinc": "1.4",
    "redbull": "999.99",
}
FILENAME = salt.utils.files.mkstemp()
# Want logging!
log = logging.getLogger(__file__)


# This does nothing, it's here just as an example and to provide a log
# entry when the module is loaded.
def __virtual__():
    """
    Only return if all the modules are available
    """
    log.debug("dummy proxy __virtual__() called...")
    return True


def _save_state(details):
    with salt.utils.files.fopen(FILENAME, "wb") as pck:
        pickle.dump(details, pck)


def _load_state():
    try:
        if six.PY3 is True:
            mode = "rb"
        else:
            mode = "r"

        with salt.utils.files.fopen(FILENAME, mode) as pck:
            DETAILS = pickle.load(pck)
    except EOFError:
        DETAILS = {}
        DETAILS["initialized"] = False
        _save_state(DETAILS)

    return DETAILS


# Every proxy module needs an 'init', though you can
# just put DETAILS['initialized'] = True here if nothing
# else needs to be done.


def init(opts):
    log.debug("dummy proxy init() called...")
    DETAILS["initialized"] = True
    _save_state(DETAILS)


def initialized():
    """
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    """
    DETAILS = _load_state()
    return DETAILS.get("initialized", False)


def grains():
    """
    Make up some grains
    """
    DETAILS = _load_state()
    if "grains_cache" not in DETAILS:
        DETAILS["grains_cache"] = {
            "dummy_grain_1": "one",
            "dummy_grain_2": "two",
            "dummy_grain_3": "three",
        }
        _save_state(DETAILS)

    return DETAILS["grains_cache"]


def grains_refresh():
    """
    Refresh the grains
    """
    DETAILS = _load_state()
    DETAILS["grains_cache"] = None
    _save_state(DETAILS)
    return grains()


def fns():
    return {
        "details": "This key is here because a function in "
        "grains/rest_sample.py called fns() here in the proxymodule."
    }


def service_start(name):
    """
    Start a "service" on the dummy server
    """
    DETAILS = _load_state()
    DETAILS["services"][name] = "running"
    _save_state(DETAILS)
    return "running"


def service_stop(name):
    """
    Stop a "service" on the dummy server
    """
    DETAILS = _load_state()
    DETAILS["services"][name] = "stopped"
    _save_state(DETAILS)
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
    DETAILS = _load_state()
    return list(DETAILS["services"])


def service_status(name):
    """
    Check if a service is running on the REST server
    """
    DETAILS = _load_state()
    if DETAILS["services"][name] == "running":
        return {"comment": "running"}
    else:
        return {"comment": "stopped"}


def package_list():
    """
    List "packages" installed on the REST server
    """
    DETAILS = _load_state()
    return DETAILS["packages"]


def package_install(name, **kwargs):
    """
    Install a "package" on the REST server
    """
    DETAILS = _load_state()
    if kwargs.get("version", False):
        version = kwargs["version"]
    else:
        version = "1.0"
    DETAILS["packages"][name] = version
    _save_state(DETAILS)
    return {name: version}


def upgrade():
    """
    "Upgrade" packages
    """
    DETAILS = _load_state()
    pkgs = uptodate()
    DETAILS["packages"] = pkgs
    _save_state(DETAILS)
    return pkgs


def uptodate():
    """
    Call the REST endpoint to see if the packages on the "server" are up to date.
    """
    DETAILS = _load_state()
    for p in DETAILS["packages"]:
        version_float = float(DETAILS["packages"][p])
        version_float = version_float + 1.0
        DETAILS["packages"][p] = six.text_type(version_float)
    return DETAILS["packages"]


def package_remove(name):
    """
    Remove a "package" on the REST server
    """
    DETAILS = _load_state()
    DETAILS["packages"].pop(name)
    _save_state(DETAILS)
    return DETAILS["packages"]


def package_status(name):
    """
    Check the installation status of a package on the REST server
    """
    DETAILS = _load_state()
    if name in DETAILS["packages"]:
        return {name: DETAILS["packages"][name]}


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
    DETAILS = _load_state()
    if "filename" in DETAILS:
        os.unlink(DETAILS["filename"])


def test_from_state():
    """
    Test function so we have something to call from a state
    :return:
    """
    log.debug("test_from_state called")
    return "testvalue"
