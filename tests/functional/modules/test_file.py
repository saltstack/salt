# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import sys

# Posix only
try:
    import grp
    import pwd
except ImportError:
    pass

# Import 3rd-party libs
import pytest

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils

# Import testing libs
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture
def myfile():
    _myfile = os.path.join(RUNTIME_VARS.TMP, 'myfile')
    with salt.utils.files.fopen(_myfile, 'w+') as fp:
        fp.write(salt.utils.stringutils.to_str('Hello' + os.linesep))
    yield _myfile
    os.unlink(_myfile)


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='No chgrp on Windows')
def test_chown(running_username, myfile, modules):
    if sys.platform == 'darwin':
        group = 'staff'
    elif sys.platform.startswith(('linux', 'freebsd', 'openbsd')):
        group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
    assert modules.file.chown(myfile, running_username, group) is None
    fstat = os.stat(myfile)
    assert fstat.st_uid == os.getuid()
    assert fstat.st_gid == grp.getgrnam(group).gr_gid
