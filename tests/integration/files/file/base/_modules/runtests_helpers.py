# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    runtests_helpers.py
    ~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import tempfile

# Import salt libs
import salt.utils


SYS_TMP_DIR = os.path.realpath(
    os.environ.get(
        # Avoid MacOS ${TMPDIR} as it yields a base path too long for unix sockets:
        # 'error: AF_UNIX path too long'
        # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
        'TMPDIR' if not salt.utils.is_darwin() else '',
        tempfile.gettempdir()
    )
)

# This tempdir path is defined on tests.integration.__init__
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')


def get_salt_temp_dir():
    return TMP

def get_salt_temp_dir_for_path(*path):
    return os.path.join(TMP, *path)


def get_sys_temp_dir_for_path(*path):
    return os.path.join(SYS_TMP_DIR, *path)
