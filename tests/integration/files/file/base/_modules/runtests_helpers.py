# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    runtests_helpers.py
    ~~~~~~~~~~~~~~~~~~~
"""

# Import python libs
from __future__ import absolute_import

import fnmatch
import os
import re
import sys
import tempfile

# Import salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six

# Import tests libs
try:
    from tests.support.runtests import RUNTIME_VARS
except ImportError:
    # Salt SSH Tests
    SYS_TMP_DIR = os.path.realpath(
        # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
        # for unix sockets: ``error: AF_UNIX path too long``
        # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
        os.environ.get("TMPDIR", tempfile.gettempdir())
        if not salt.utils.platform.is_darwin()
        else "/tmp"
    )
    # This tempdir path is defined on tests.integration.__init__
    TMP = os.path.join(SYS_TMP_DIR, "salt-tests-tmpdir")

    class RUNTIME_VARS(object):
        TMP = TMP
        SYS_TMP_DIR = SYS_TMP_DIR


def get_salt_temp_dir():
    return RUNTIME_VARS.TMP


def get_salt_temp_dir_for_path(*path):
    return os.path.join(RUNTIME_VARS.TMP, *path)


def get_sys_temp_dir_for_path(*path):
    return os.path.join(RUNTIME_VARS.SYS_TMP_DIR, *path)


def get_invalid_docs():
    """
    Outputs the functions which do not have valid CLI example, or are missing a
    docstring.
    """
    allow_failure = (
        "cmd.win_runas",
        "cp.recv",
        "cp.recv_chunked",
        "glance.warn_until",
        "ipset.long_range",
        "libcloud_compute.get_driver",
        "libcloud_dns.get_driver",
        "libcloud_loadbalancer.get_driver",
        "libcloud_storage.get_driver",
        "log.critical",
        "log.debug",
        "log.error",
        "log.exception",
        "log.info",
        "log.warning",
        "lowpkg.bin_pkg_info",
        "lxc.run_cmd",
        "mantest.install",
        "mantest.search",
        "nspawn.restart",
        "nspawn.stop",
        "pkg.expand_repo_def",
        "pip.iteritems",
        "pip.parse_version",
        "peeringdb.clean_kwargs",
        "runtests_decorators.depends",
        "runtests_decorators.depends_will_fallback",
        "runtests_decorators.missing_depends",
        "runtests_decorators.missing_depends_will_fallback",
        "state.apply",
        "status.list2cmdline",
        "swift.head",
        "test.rand_str",
        "travisci.parse_qs",
        "vsphere.clean_kwargs",
        "vsphere.disconnect",
        "vsphere.get_service_instance_via_proxy",
        "vsphere.gets_service_instance_via_proxy",
        "vsphere.supports_proxies",
        "vsphere.test_vcenter_connection",
        "vsphere.wraps",
    )
    allow_failure_glob = (
        "runtests_decorators.*",
        "runtests_helpers.*",
        "vsphere.*",
    )
    nodoc = set()
    noexample = set()
    for fun, docstring in six.iteritems(__salt__["sys.doc"]()):
        if fun in allow_failure:
            continue
        else:
            for pat in allow_failure_glob:
                if fnmatch.fnmatch(fun, pat):
                    matched_glob = True
                    break
            else:
                matched_glob = False
            if matched_glob:
                continue
        if not isinstance(docstring, six.string_types):
            nodoc.add(fun)
        elif isinstance(docstring, dict) and not re.search(
            r"([E|e]xample(?:s)?)+(?:.*):?", docstring
        ):
            noexample.add(fun)

    return {
        "missing_docstring": sorted(nodoc),
        "missing_cli_example": sorted(noexample),
    }


def modules_available(*names):
    """
    Returns a list of modules not available. Empty list if modules are all available
    """
    not_found = []
    for name in names:
        if "." not in name:
            name = name + ".*"
        if not fnmatch.filter(list(__salt__), name):
            not_found.append(name)
    return not_found


def nonzero_retcode_return_true():
    """
    Sets a nonzero retcode before returning. Designed to test orchestration.
    """
    __context__["retcode"] = 1
    return True


def nonzero_retcode_return_false():
    """
    Sets a nonzero retcode before returning. Designed to test orchestration.
    """
    __context__["retcode"] = 1
    return False


def fail_function(*args, **kwargs):  # pylint: disable=unused-argument
    """
    Return False no matter what is passed to it
    """
    return False


def get_python_executable():
    """
    Return the path to the python executable.

    This is particularly important when running the test suite within a virtualenv, while trying
    to create virtualenvs on windows.
    """
    try:
        if salt.utils.platform.is_windows():
            python_binary = os.path.join(
                sys.real_prefix, os.path.basename(sys.executable)
            )
        else:
            python_binary = os.path.join(
                sys.real_prefix, "bin", os.path.basename(sys.executable)
            )
        if not os.path.exists(python_binary):
            python_binary = None
    except AttributeError:
        # We're not running inside a virtualenv
        python_binary = sys.executable
    return python_binary
