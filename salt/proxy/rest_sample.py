"""
This is a simple proxy-minion designed to connect to and communicate with
the bottle-based web service contained in https://github.com/saltstack/salt-contrib/tree/master/proxyminion_rest_example
"""

import logging

import salt.utils.http

HAS_REST_EXAMPLE = True

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ["rest_sample"]


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}

# Want logging!
log = logging.getLogger(__file__)


# This does nothing, it's here just as an example and to provide a log
# entry when the module is loaded.
def __virtual__():
    """
    Only return if all the modules are available
    """
    log.debug("rest_sample proxy __virtual__() called...")
    return True


# Every proxy module needs an 'init', though you can
# just put DETAILS['initialized'] = True here if nothing
# else needs to be done.


def init(opts):
    log.debug("rest_sample proxy init() called...")
    __context__["rest_sample"] = {"initialized": True, "url": opts["proxy"]["url"]}
    # Make sure the REST URL ends with a '/'
    if not __context__["rest_sample"]["url"].endswith("/"):
        __context__["rest_sample"]["url"] += "/"


def initialized():
    """
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    """
    return __context__["rest_sample"].get("initialized", False)


def alive(opts):
    log.debug("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")
    log.debug("proxys alive() fn called")
    log.debug("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")
    return ping()


def id(opts):
    """
    Return a unique ID for this proxy minion.  This ID MUST NOT CHANGE.
    If it changes while the proxy is running the salt-master will get
    really confused and may stop talking to this minion
    """
    r = salt.utils.http.query(
        opts["proxy"]["url"] + "id", decode_type="json", decode=True
    )
    return r["dict"]["id"].encode("ascii", "ignore")


def grains():
    """
    Get the grains from the proxied device
    """
    if not __context__["rest_sample"].get("grains_cache", {}):
        r = salt.utils.http.query(
            __context__["rest_sample"]["url"] + "info", decode_type="json", decode=True
        )
        __context__["rest_sample"]["grains_cache"] = r["dict"]
    return __context__["rest_sample"]["grains_cache"]


def grains_refresh():
    """
    Refresh the grains from the proxied device
    """
    __context__["rest_sample"]["grains_cache"] = None
    return grains()


def fns():
    return {
        "details": (
            "This key is here because a function in "
            "grains/rest_sample.py called fns() here in the proxymodule."
        )
    }


def service_start(name):
    """
    Start a "service" on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "service/start/" + name,
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def service_stop(name):
    """
    Stop a "service" on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "service/stop/" + name,
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def service_restart(name):
    """
    Restart a "service" on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "service/restart/" + name,
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def service_list():
    """
    List "services" on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "service/list",
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def service_status(name):
    """
    Check if a service is running on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "service/status/" + name,
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def package_list():
    """
    List "packages" installed on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "package/list",
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def package_install(name, **kwargs):
    """
    Install a "package" on the REST server
    """
    cmd = __context__["rest_sample"]["url"] + "package/install/" + name
    if kwargs.get("version", False):
        cmd += "/" + kwargs["version"]
    else:
        cmd += "/1.0"
    r = salt.utils.http.query(cmd, decode_type="json", decode=True)
    return r["dict"]


def fix_outage():
    r = salt.utils.http.query(__context__["rest_sample"]["url"] + "fix_outage")
    return r


def uptodate(name):
    """
    Call the REST endpoint to see if the packages on the "server" are up to date.
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "package/remove/" + name,
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def package_remove(name):
    """
    Remove a "package" on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "package/remove/" + name,
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def package_status(name):
    """
    Check the installation status of a package on the REST server
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "package/status/" + name,
        decode_type="json",
        decode=True,
    )
    return r["dict"]


def ping():
    """
    Is the REST server up?
    """
    r = salt.utils.http.query(
        __context__["rest_sample"]["url"] + "ping", decode_type="json", decode=True
    )
    try:
        return r["dict"].get("ret", False)
    except Exception:  # pylint: disable=broad-except
        return False


def shutdown(opts):
    """
    For this proxy shutdown is a no-op
    """
    log.debug("rest_sample proxy shutdown() called...")


def test_from_state():
    """
    Test function so we have something to call from a state
    :return:
    """
    log.debug("test_from_state called")
    return "testvalue"
