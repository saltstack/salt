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
    # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
    # for unix sockets: ``error: AF_UNIX path too long``
    # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
    os.environ.get('TMPDIR', tempfile.gettempdir()) if salt.utils.is_darwin() else '/tmp'
)
# This tempdir path is defined on tests.integration.__init__
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')


def get_salt_temp_dir():
    return TMP

def get_salt_temp_dir_for_path(*path):
    return os.path.join(TMP, *path)


def get_sys_temp_dir_for_path(*path):
    return os.path.join(SYS_TMP_DIR, *path)
