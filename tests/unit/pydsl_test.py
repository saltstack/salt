# Import Python libs
import sys
from cStringIO import StringIO

# Import Salt libs
from saltunittest import TestCase
import salt.loader
import salt.config
from salt.state import State

REQUISITES = ['require', 'require_in', 'use', 'use_in', 'watch', 'watch_in']

OPTS = salt.config.master_config('whatever, just load the defaults!')
# we should have used minion_config(), but that would try to resolve
# the master hostname, and retry for 30 seconds! Lucily for our purpose,
# master conf or minion conf, it doesn't matter.
OPTS['id'] = 'whatever'
OPTS['file_client'] = 'local'
OPTS['file_roots'] = dict(base=['/'])

OPTS['grains'] = salt.loader.grains(OPTS)
STATE = State(OPTS)

def render_sls(content, sls='', env='base', **kws):
    sys.modules['salt.loaded.int.render.pydsl'].__salt__ = STATE.functions
    return STATE.rend['pydsl'](
                StringIO(content), env=env, sls=sls,
                **kws)

            

class PyDSLRendererTestCase(TestCase):

    def test_state_declarations(self):
        result = render_sls('''
state('A').cmd.run('ls -la', cwd='/var/tmp')
state().file.managed('myfile.txt', source='salt://path/to/file')
state('X').cmd('run', 'echo hello world', cwd='/')
''')
        self.assertTrue('A' in result and 'X' in result)
        A_cmd = result['A']['cmd']
        self.assertEqual(A_cmd[0], 'run')
        self.assertEqual(A_cmd[1]['name'], 'ls -la')
        self.assertEqual(A_cmd[2]['cwd'], '/var/tmp')

        X_cmd = result['X']['cmd']
        self.assertEqual(X_cmd[0], 'run')
        self.assertEqual(X_cmd[1]['name'], 'echo hello world')
        self.assertEqual(X_cmd[2]['cwd'], '/')

        del result['A']
        del result['X']
        self.assertEqual(len(result), 2)
        # 2 rather than 1 because pydsl adds an extra no-op state
        # declaration.

        s = result.itervalues().next()['file']
        self.assertEqual(s[0], 'managed')
        self.assertEqual(s[1]['name'], 'myfile.txt')
        self.assertEqual(s[2]['source'], 'salt://path/to/file')


