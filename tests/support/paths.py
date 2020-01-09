# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    :copyright: Copyright 2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.paths
    ~~~~~~~~~~~~~~~~~~~

    Tests related paths
'''

# Import python libs
from __future__ import absolute_import
import os
import re
import sys
import logging
import tempfile

import salt.utils.path

log = logging.getLogger(__name__)

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.normpath(os.path.abspath(__file__))))
if TESTS_DIR.startswith('//'):
    # Have we been given an initial double forward slash? Ditch it!
    TESTS_DIR = TESTS_DIR[1:]
if sys.platform.startswith('win'):
    TESTS_DIR = os.path.normcase(TESTS_DIR)
CODE_DIR = os.path.dirname(TESTS_DIR)
if sys.platform.startswith('win'):
    CODE_DIR = CODE_DIR.replace('\\', '\\\\')
UNIT_TEST_DIR = os.path.join(TESTS_DIR, 'unit')
INTEGRATION_TEST_DIR = os.path.join(TESTS_DIR, 'integration')
MULTIMASTER_TEST_DIR = os.path.join(TESTS_DIR, 'multimaster')

# Let's inject CODE_DIR so salt is importable if not there already
if TESTS_DIR in sys.path:
    sys.path.remove(TESTS_DIR)
if CODE_DIR in sys.path and sys.path[0] != CODE_DIR:
    sys.path.remove(CODE_DIR)
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(1, TESTS_DIR)

SYS_TMP_DIR = os.path.abspath(os.path.realpath(
    # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
    # for unix sockets: ``error: AF_UNIX path too long``
    # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
    os.environ.get('TMPDIR', tempfile.gettempdir()) if not sys.platform.startswith('darwin') else '/tmp'
))
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')
TMP_ROOT_DIR = os.path.join(TMP, 'rootdir')
FILES = os.path.join(INTEGRATION_TEST_DIR, 'files')
BASE_FILES = os.path.join(INTEGRATION_TEST_DIR, 'files', 'file', 'base')
PROD_FILES = os.path.join(INTEGRATION_TEST_DIR, 'files', 'file', 'prod')
PYEXEC = 'python{0}.{1}'.format(*sys.version_info)
MOCKBIN = os.path.join(INTEGRATION_TEST_DIR, 'mockbin')
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')
TMP_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-state-tree')
TMP_PILLAR_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-pillar-tree')
TMP_PRODENV_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-prodenv-state-tree')
TMP_CONF_DIR = os.path.join(TMP, 'config')
TMP_SUB_MINION_CONF_DIR = os.path.join(TMP_CONF_DIR, 'sub-minion')
TMP_SYNDIC_MINION_CONF_DIR = os.path.join(TMP_CONF_DIR, 'syndic-minion')
TMP_SYNDIC_MASTER_CONF_DIR = os.path.join(TMP_CONF_DIR, 'syndic-master')
TMP_MM_CONF_DIR = os.path.join(TMP_CONF_DIR, 'multimaster')
TMP_MM_SUB_CONF_DIR = os.path.join(TMP_CONF_DIR, 'sub-multimaster')
TMP_PROXY_CONF_DIR = os.path.join(TMP_CONF_DIR, 'proxy')
CONF_DIR = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
PILLAR_DIR = os.path.join(FILES, 'pillar')
TMP_SCRIPT_DIR = os.path.join(TMP, 'scripts')
ENGINES_DIR = os.path.join(FILES, 'engines')
LOG_HANDLERS_DIR = os.path.join(FILES, 'log_handlers')


def list_test_mods():
    '''
    A generator which returns all of the test files
    '''
    test_re = re.compile(r'^test_.+\.py$')
    for dirname in (UNIT_TEST_DIR, INTEGRATION_TEST_DIR, MULTIMASTER_TEST_DIR):
        test_type = os.path.basename(dirname)
        for root, _, files in salt.utils.path.os_walk(dirname):
            parent_mod = root[len(dirname):].lstrip(os.sep).replace(os.sep, '.')
            for filename in files:
                if test_re.match(filename):
                    mod_name = test_type
                    if parent_mod:
                        mod_name += '.' + parent_mod
                    mod_name += '.' + filename[:-3]
                    yield mod_name
