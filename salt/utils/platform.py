"""
Functions for identifying which platform a machine is
"""

import contextlib
import functools
import multiprocessing
import os
import platform
import subprocess
import sys

import distro


# Use a local wraps-based memoize rather than importing from salt.utils.decorators.
# This module is synced to the remote's extmods/utils/platform.py, and in
# Python 3.14+ (forkserver default start method) it can be accidentally
# imported as the stdlib ``platform`` module when extmods/utils/ sits at
# sys.path[0].  Importing from salt.utils.decorators in that context
# creates a circular import:
#   salt.utils.decorators → salt.utils.versions → salt.version
#   → import platform (ourselves!) → salt.utils.decorators  (cycle)
# functools is part of the stdlib and has no such dependency.
#
# We cannot use functools.cache/lru_cache directly as the decorator because
# those produce functools._lru_cache_wrapper objects which fail
# inspect.isfunction(), causing the Salt loader to skip them when loading
# salt.utils.platform as a utils module (salt/loader/lazy.py line ~1109).
def real_memoize(func):
    """Cache the result of a zero-or-more-argument function (stdlib-only, loader-safe)."""
    cache = {}
    _sentinel = object()

    @functools.wraps(func)
    def _wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        result = cache.get(key, _sentinel)
        if result is _sentinel:
            result = func(*args, **kwargs)
            cache[key] = result
        return result

    return _wrapper


def linux_distribution(full_distribution_name=True):
    """
    Simple function to return information about the OS distribution (id_name, version, codename).
    """
    if full_distribution_name:
        distro_name = distro.name()
    else:
        distro_name = distro.id()
    # Empty string fallbacks
    distro_version = distro_codename = ""
    with contextlib.suppress(subprocess.CalledProcessError):
        distro_version = distro.version(best=True)
    with contextlib.suppress(subprocess.CalledProcessError):
        distro_codename = distro.codename()
    return distro_name, distro_version, distro_codename


@real_memoize
def is_windows():
    """
    Simple function to return if a host is Windows or not
    """
    return sys.platform.startswith("win")


@real_memoize
def is_proxy():
    """
    Return True if this minion is a proxy minion.
    Leverages the fact that is_linux() and is_windows
    both return False for proxies.
    TODO: Need to extend this for proxies that might run on
    other Unices
    """
    import __main__ as main

    # This is a hack.  If a proxy minion is started by other
    # means, e.g. a custom script that creates the minion objects
    # then this will fail.
    ret = False
    try:
        # Changed this from 'salt-proxy in main...' to 'proxy in main...'
        # to support the testsuite's temp script that is called 'cli_salt_proxy'
        #
        # Add '--proxyid' or '--proxyid=...' in sys.argv so that salt-call
        # is seen as a proxy minion
        if "proxy" in main.__file__ or any(
            arg for arg in sys.argv if arg.startswith("--proxyid")
        ):
            ret = True
    except AttributeError:
        pass
    return ret


@real_memoize
def is_linux():
    """
    Simple function to return if a host is Linux or not.
    Note for a proxy minion, we need to return something else
    """
    return sys.platform.startswith("linux")


@real_memoize
def is_darwin():
    """
    Simple function to return if a host is Darwin (macOS) or not
    """
    return sys.platform.startswith("darwin")


@real_memoize
def is_sunos():
    """
    Simple function to return if host is SunOS or not
    """
    return sys.platform.startswith("sunos")


@real_memoize
def is_smartos():
    """
    Simple function to return if host is SmartOS (Illumos) or not
    """
    if not is_sunos():
        return False
    else:
        return os.uname()[3].startswith("joyent_")


@real_memoize
def is_smartos_globalzone():
    """
    Function to return if host is SmartOS (Illumos) global zone or not
    """
    if not is_smartos():
        return False
    else:
        try:
            zonename_proc = subprocess.Popen(
                ["zonename"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            zonename_output = (
                zonename_proc.communicate()[0].strip().decode(__salt_system_encoding__)
            )
            zonename_retcode = zonename_proc.poll()
        except OSError:
            return False
        if zonename_retcode:
            return False
        if zonename_output == "global":
            return True

        return False


@real_memoize
def is_smartos_zone():
    """
    Function to return if host is SmartOS (Illumos) and not the gz
    """
    if not is_smartos():
        return False
    else:
        try:
            zonename_proc = subprocess.Popen(
                ["zonename"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            zonename_output = (
                zonename_proc.communicate()[0].strip().decode(__salt_system_encoding__)
            )
            zonename_retcode = zonename_proc.poll()
        except OSError:
            return False
        if zonename_retcode:
            return False
        if zonename_output == "global":
            return False

        return True


@real_memoize
def is_junos():
    """
    Simple function to return if host is Junos or not
    """
    return sys.platform.startswith("freebsd") and os.uname().release.startswith("JNPR")


@real_memoize
def is_freebsd():
    """
    Simple function to return if host is FreeBSD or not
    """
    return sys.platform.startswith("freebsd")


@real_memoize
def is_netbsd():
    """
    Simple function to return if host is NetBSD or not
    """
    return sys.platform.startswith("netbsd")


@real_memoize
def is_openbsd():
    """
    Simple function to return if host is OpenBSD or not
    """
    return sys.platform.startswith("openbsd")


@real_memoize
def is_aix():
    """
    Simple function to return if host is AIX or not
    """
    return sys.platform.startswith("aix")


@real_memoize
def is_fedora():
    """
    Simple function to return if host is Fedora or not
    """
    (osname, osrelease, oscodename) = (
        x.strip('"').strip("'") for x in linux_distribution()
    )
    return osname == "Fedora"


@real_memoize
def is_photonos():
    """
    Simple function to return if host is Photon OS or not
    """
    (osname, osrelease, oscodename) = (
        x.strip('"').strip("'") for x in linux_distribution()
    )
    return osname == "VMware Photon OS"


@real_memoize
def is_aarch64():
    """
    Simple function to return if host is AArch64 or not
    """
    if is_darwin():
        # Allow for MacOS Arm64 platform returning differently from Linux
        return platform.machine().startswith("arm64")
    else:
        return platform.machine().startswith("aarch64")


def spawning_platform():
    """
    Returns True if the multiprocessing start method requires pickling to transfer
    process state to the child.  This is the case for both "spawn" and "forkserver".

    "spawn" is the default on Windows (Python >= 3.4) and macOS (Python >= 3.8).
    Salt forces macOS to spawning by default on all Python versions.

    "forkserver" became the Linux default in Python 3.14 (via PEP 741).  Like
    "spawn", it transfers the Process object to the child via pickle rather than
    inheriting it through a plain fork of the parent process.  Salt must therefore
    treat it identically: capture *args/**kwargs in __new__ so that __getstate__
    can reconstruct the object on the other side, and skip parent-inherited
    logging teardown since the child starts with a clean file-descriptor table.
    """
    return multiprocessing.get_start_method(allow_none=False) in ("spawn", "forkserver")


def get_machine_identifier():
    """
    Provide the machine-id for machine/virtualization combination
    """
    # pylint: disable=resource-leakage
    # Provides:
    #   machine-id
    locations = ["/etc/machine-id", "/var/lib/dbus/machine-id"]
    existing_locations = [loc for loc in locations if os.path.exists(loc)]
    if not existing_locations:
        return {}
    else:
        # cannot use salt.utils.files.fopen due to circular dependency
        with open(
            existing_locations[0], encoding=__salt_system_encoding__
        ) as machineid:
            return {"machine_id": machineid.read().strip()}
