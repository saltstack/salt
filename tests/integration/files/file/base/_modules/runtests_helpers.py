# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8
"""
    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details
"""

import os
import tempfile

# This tempdir path is defined on tests.integration.__init__
TMP = os.path.join(tempfile.gettempdir(), 'salt-tests-tmpdir')


def get_salt_temp_dir_for_path(path):
    return os.path.join(TMP, path)
