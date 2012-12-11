# -*- coding: utf-8 -*-
'''
    runtests_helpers.py
    ~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import tempfile

SYS_TMP_DIR = tempfile.gettempdir()
# This tempdir path is defined on tests.integration.__init__
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')


def get_salt_temp_dir_for_path(*path):
    return os.path.join(TMP, *path)


def get_sys_temp_dir_for_path(*path):
    return os.path.join(SYS_TMP_DIR, *path)
