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
OPTS['test'] = False
OPTS['grains'] = salt.loader.grains(OPTS)
STATE = State(OPTS)

def render_sls(content, sls='', env='base', **kws):
    return STATE.rend['pydsl'](
                StringIO(content), env=env, sls=sls,
                **kws)

            

class PyDSLRendererTestCase(TestCase):

    def setUp(self):
        STATE.load_modules()
        sys.modules['salt.loaded.int.render.pydsl'].__salt__ = STATE.functions
        self.PyDslError = sys.modules['salt.loaded.int.module.pydsl'].PyDslError

    def test_state_declarations(self):
        result = render_sls('''
state('A').cmd.run('ls -la', cwd='/var/tmp')
state().file.managed('myfile.txt', source='salt://path/to/file')
state('X').cmd('run', 'echo hello world', cwd='/')

a_cmd = state('A').cmd
a_cmd.run(shell='/bin/bash')
state('A').service.running(name='apache')
''')
        self.assertTrue('A' in result and 'X' in result)
        A_cmd = result['A']['cmd']
        self.assertEqual(A_cmd[0], 'run')
        self.assertEqual(A_cmd[1]['name'], 'ls -la')
        self.assertEqual(A_cmd[2]['cwd'], '/var/tmp')
        self.assertEqual(A_cmd[3]['shell'], '/bin/bash')

        A_service = result['A']['service']
        self.assertEqual(A_service[0], 'running')
        self.assertEqual(A_service[1]['name'], 'apache')

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


    def test_requisite_declarations(self):
        result = render_sls('''
state('X').cmd.run('echo hello')
state('A').cmd.run('mkdir tmp', cwd='/var')
state('B').cmd.run('ls -la', cwd='/var/tmp') \
              .require(state('X').cmd) \
              .require('cmd', 'A') \
              .watch('service', 'G')
state('G').service.running(name='collectd')
state('G').service.watch_in(state('A').cmd)

state('H').cmd.require_in('cmd', 'echo hello')
state('H').cmd.run('echo world')
''')
        self.assertTrue(len(result), 6)            
        self.assertTrue(set("X A B G H".split()).issubset(set(result.keys())))
        b = result['B']['cmd']
        self.assertEqual(b[0], 'run')
        self.assertEqual(b[1]['name'], 'ls -la')
        self.assertEqual(b[2]['cwd'], '/var/tmp')
        self.assertEqual(b[3]['require'][0]['cmd'], 'X')
        self.assertEqual(b[4]['require'][0]['cmd'], 'A')
        self.assertEqual(b[5]['watch'][0]['service'], 'G')
        self.assertEqual(result['G']['service'][2]['watch_in'][0]['cmd'], 'A')
        self.assertEqual(result['H']['cmd'][1]['require_in'][0]['cmd'], 'echo hello')


    def test_include_extend(self):
        result = render_sls('''
include(
    'some.sls.file',
    'another.sls.file',
    'more.sls.file'
)
extend(
    state('X').cmd.run(cwd='/a/b/c'),
    state('Y').file('managed', name='a_file.txt'),
    state('Z').service.watch('file', 'A')
)
''')
        self.assertEqual(len(result), 3)
        self.assertEqual(result['include'],
                         'some.sls.file another.sls.file more.sls.file'.split())
        extend = result['extend']
        self.assertEqual(extend['X']['cmd'][0], 'run')
        self.assertEqual(extend['X']['cmd'][1]['cwd'], '/a/b/c')
        self.assertEqual(extend['Y']['file'][0], 'managed')
        self.assertEqual(extend['Y']['file'][1]['name'], 'a_file.txt')
        self.assertEqual(len(extend['Z']['service']), 1)
        self.assertEqual(extend['Z']['service'][0]['watch'][0]['file'], 'A')


    def test_cmd_call(self):
        result = STATE.call_template_str('''#!pydsl
state('A').cmd.run('echo this is state A', cwd='/')

some_var = 12345
def do_something(a, b, *args, **kws):
    return dict(result=True, changes={'a': a, 'b': b, 'args': args, 'kws': kws, 'some_var': some_var})

state('C').cmd.call(do_something, 1, 2, 3, x=1, y=2) \
              .require(state('A').cmd)

state('G').cmd.wait('echo this is state G', cwd='/') \
              .watch(state('C').cmd)
''')
        ret = (result[k] for k in result.keys() if 'do_something' in k).next()
        changes = ret['changes']
        self.assertEqual(changes, dict(a=1, b=2, args=(3,), kws=dict(x=1, y=2), some_var=12345))

        ret = (result[k] for k in result.keys() if '-G_' in k).next()
        self.assertEqual(ret['changes']['stdout'], 'this is state G')


    def test_multiple_state_func_in_state_mod(self):
        with self.assertRaisesRegexp(self.PyDslError, 'Multiple state functions'):
            render_sls('''
state('A').cmd.run('echo hoho')
state('A').cmd.wait('echo hehe')
''')


    def test_no_state_func_in_state_mod(self):
        with self.assertRaisesRegexp(self.PyDslError, 'No state function specified'):
            render_sls('''
state('B').cmd.require('cmd', 'hoho')
''')


    def test_load_highstate(self):
        result = render_sls('''
import yaml
__pydsl__.load_highstate(yaml.load("""
A:
  cmd.run:
    - name: echo hello
    - cwd: /
B:
  pkg:
    - installed
  service:
    - running
    - require:
      - pkg: B
    - watch:
      - cmd: A
"""))

state('A').cmd.run(name='echo hello world')
''')
        self.assertEqual(len(result), 3)
        self.assertEqual(result['A']['cmd'][0], 'run')
        self.assertEqual(result['A']['cmd'][1]['name'], 'echo hello')
        self.assertEqual(result['A']['cmd'][2]['cwd'], '/')
        self.assertEqual(result['A']['cmd'][3]['name'], 'echo hello world')

        self.assertEqual(len(result['B']['pkg']), 1)
        self.assertEqual(result['B']['pkg'][0], 'installed')

        self.assertEqual(result['B']['service'][0], 'running')
        self.assertEqual(result['B']['service'][1]['require'][0]['pkg'], 'B')
        self.assertEqual(result['B']['service'][2]['watch'][0]['cmd'], 'A')


