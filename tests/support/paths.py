# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.paths
    ~~~~~~~~~~~~~~~~~~~

    Tests related paths
'''

# Import python libs
from __future__ import absolute_import
import os
import sys
import stat
import logging
import tempfile

log = logging.getLogger(__name__)

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.normpath(os.path.abspath(__file__))))
if os.name == 'nt':
    TESTS_DIR = TESTS_DIR.replace('\\', '\\\\')
CODE_DIR = os.path.dirname(TESTS_DIR)
INTEGRATION_TEST_DIR = os.path.join(TESTS_DIR, 'integration')

# Let's inject CODE_DIR so salt is importable if not there already
if TESTS_DIR in sys.path:
    sys.path.remove(TESTS_DIR)
if CODE_DIR in sys.path and sys.path[0] != CODE_DIR:
    sys.path.remove(CODE_DIR)
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(1, TESTS_DIR)

SYS_TMP_DIR = os.path.realpath(
    # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
    # for unix sockets: ``error: AF_UNIX path too long``
    # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
    os.environ.get('TMPDIR', tempfile.gettempdir()) if not sys.platform.startswith('darwin') else '/tmp'
)
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')
FILES = os.path.join(INTEGRATION_TEST_DIR, 'files')
PYEXEC = 'python{0}.{1}'.format(*sys.version_info)
MOCKBIN = os.path.join(INTEGRATION_TEST_DIR, 'mockbin')
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')
TMP_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-state-tree')
TMP_PRODENV_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-prodenv-state-tree')
TMP_CONF_DIR = os.path.join(TMP, 'config')
TMP_SUB_MINION_CONF_DIR = os.path.join(TMP_CONF_DIR, 'sub-minion')
TMP_SYNDIC_MINION_CONF_DIR = os.path.join(TMP_CONF_DIR, 'syndic-minion')
TMP_SYNDIC_MASTER_CONF_DIR = os.path.join(TMP_CONF_DIR, 'syndic-master')
CONF_DIR = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
PILLAR_DIR = os.path.join(FILES, 'pillar')
TMP_SCRIPT_DIR = os.path.join(TMP, 'scripts')
ENGINES_DIR = os.path.join(FILES, 'engines')
LOG_HANDLERS_DIR = os.path.join(FILES, 'log_handlers')


SCRIPT_TEMPLATES = {
    'salt': [
        'from salt.scripts import salt_main\n',
        'if __name__ == \'__main__\':\n'
        '    salt_main()'
    ],
    'salt-api': [
        'import salt.cli\n',
        'def main():\n',
        '    sapi = salt.cli.SaltAPI()',
        '    sapi.start()\n',
        'if __name__ == \'__main__\':',
        '    main()'
    ],
    'common': [
        'from salt.scripts import salt_{0}\n',
        'from salt.utils import is_windows\n\n',
        'if __name__ == \'__main__\':\n',
        '    if is_windows():\n',
        '        import os.path\n',
        '        import py_compile\n',
        '        cfile = os.path.splitext(__file__)[0] + ".pyc"\n',
        '        if not os.path.exists(cfile):\n',
        '            py_compile.compile(__file__, cfile)\n',
        '    salt_{0}()'
    ]
}


class ScriptPathMixin(object):

    def get_script_path(self, script_name):
        '''
        Return the path to a testing runtime script
        '''
        if not os.path.isdir(TMP_SCRIPT_DIR):
            os.makedirs(TMP_SCRIPT_DIR)

        script_path = os.path.join(TMP_SCRIPT_DIR,
                                   'cli_{0}.py'.format(script_name.replace('-', '_')))

        if not os.path.isfile(script_path):
            log.info('Generating {0}'.format(script_path))

            # Late import
            import salt.utils

            with salt.utils.fopen(script_path, 'w') as sfh:
                script_template = SCRIPT_TEMPLATES.get(script_name, None)
                if script_template is None:
                    script_template = SCRIPT_TEMPLATES.get('common', None)
                if script_template is None:
                    raise RuntimeError(
                        '{0} does not know how to handle the {1} script'.format(
                            self.__class__.__name__,
                            script_name
                        )
                    )
                sfh.write(
                    '#!{0}\n\n'.format(sys.executable) +
                    'import sys\n' +
                    'CODE_DIR="{0}"\n'.format(CODE_DIR) +
                    'if CODE_DIR not in sys.path:\n' +
                    '    sys.path.insert(0, CODE_DIR)\n\n' +
                    '\n'.join(script_template).format(script_name.replace('salt-', ''))
                )
            fst = os.stat(script_path)
            os.chmod(script_path, fst.st_mode | stat.S_IEXEC)

        log.info('Returning script path %r', script_path)
        return script_path
