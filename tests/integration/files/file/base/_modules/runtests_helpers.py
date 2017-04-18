# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    runtests_helpers.py
    ~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import fnmatch
import os
import re
import tempfile

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six

SYS_TMP_DIR = os.path.realpath(
    # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
    # for unix sockets: ``error: AF_UNIX path too long``
    # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
    os.environ.get('TMPDIR', tempfile.gettempdir()) if not salt.utils.is_darwin() else '/tmp'
)
# This tempdir path is defined on tests.integration.__init__
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')


def get_salt_temp_dir():
    return TMP


def get_salt_temp_dir_for_path(*path):
    return os.path.join(TMP, *path)


def get_sys_temp_dir_for_path(*path):
    return os.path.join(SYS_TMP_DIR, *path)


def get_invalid_docs():
    '''
    Outputs the functions which do not have valid CLI example, or are missing a
    docstring.
    '''
    allow_failure = (
        'cmd.win_runas',
        'cp.recv',
        'glance.warn_until',
        'ipset.long_range',
        'libcloud_dns.get_driver',
        'log.critical',
        'log.debug',
        'log.error',
        'log.exception',
        'log.info',
        'log.warning',
        'lowpkg.bin_pkg_info',
        'lxc.run_cmd',
        'nspawn.restart',
        'nspawn.stop',
        'pkg.expand_repo_def',
        'pip.iteritems',
        'runtests_decorators.depends',
        'runtests_decorators.depends_will_fallback',
        'runtests_decorators.missing_depends',
        'runtests_decorators.missing_depends_will_fallback',
        'state.apply',
        'status.list2cmdline',
        'swift.head',
        'travisci.parse_qs',
        'vsphere.clean_kwargs',
        'vsphere.disconnect',
        'vsphere.get_service_instance_via_proxy',
        'vsphere.gets_service_instance_via_proxy',
        'vsphere.supports_proxies',
        'vsphere.test_vcenter_connection',
        'vsphere.wraps',
    )
    allow_failure_glob = (
        'runtests_helpers.*',
    )
    nodoc = set()
    noexample = set()
    for fun, docstring in six.iteritems(__salt__['sys.doc']()):
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
        elif not re.search(r'([E|e]xample(?:s)?)+(?:.*):?', docstring):
            noexample.add(fun)

    return {'missing_docstring': sorted(nodoc),
            'missing_cli_example': sorted(noexample)}
