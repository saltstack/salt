# -*- coding: utf-8 -*-

# Import Python libs
import os
import sys
import shutil
import tempfile
import textwrap
import copy
from cStringIO import StringIO

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

# Import Salt libs
import integration
import salt.loader
import salt.config
import salt.utils
from salt.state import HighState
from salt.utils.pydsl import PyDslError

REQUISITES = ['require', 'require_in', 'use', 'use_in', 'watch', 'watch_in']

OPTS = salt.config.minion_config(None)
OPTS['state_events'] = False
OPTS['id'] = 'whatever'
OPTS['file_client'] = 'local'
OPTS['file_roots'] = dict(base=['/tmp'])
OPTS['cachedir'] = 'cachedir'
OPTS['test'] = False
OPTS['grains'] = salt.loader.grains(OPTS)


class PyDSLRendererTestCase(TestCase):

    def setUp(self):
        self.HIGHSTATE = HighState(OPTS)
        self.HIGHSTATE.push_active()

    def tearDown(self):
        self.HIGHSTATE.pop_active()

    def render_sls(self, content, sls='', env='base', **kws):
        return self.HIGHSTATE.state.rend['pydsl'](
            StringIO(content), env=env, sls=sls, **kws
        )

    def test_state_declarations(self):
        result = self.render_sls(textwrap.dedent('''
            state('A').cmd.run('ls -la', cwd='/var/tmp')
            state().file.managed('myfile.txt', source='salt://path/to/file')
            state('X').cmd('run', 'echo hello world', cwd='/')

            a_cmd = state('A').cmd
            a_cmd.run(shell='/bin/bash')
            state('A').service.running(name='apache')
        '''))
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

        s_iter = result.itervalues()
        try:
            s = s_iter.next()['file']
        except KeyError:
            s = s_iter.next()['file']
        self.assertEqual(s[0], 'managed')
        self.assertEqual(s[1]['name'], 'myfile.txt')
        self.assertEqual(s[2]['source'], 'salt://path/to/file')

    def test_requisite_declarations(self):
        result = self.render_sls(textwrap.dedent('''
            state('X').cmd.run('echo hello')
            state('A').cmd.run('mkdir tmp', cwd='/var')
            state('B').cmd.run('ls -la', cwd='/var/tmp') \
                        .require(state('X').cmd) \
                        .require(cmd='A') \
                        .watch(service='G')
            state('G').service.running(name='collectd')
            state('G').service.watch_in(state('A').cmd)

            state('H').cmd.require_in(cmd='echo hello')
            state('H').cmd.run('echo world')
        '''))
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
        self.assertEqual(
            result['H']['cmd'][1]['require_in'][0]['cmd'], 'echo hello'
        )

    def test_include_extend(self):
        result = self.render_sls(textwrap.dedent('''
            include(
                'some.sls.file',
                'another.sls.file',
                'more.sls.file',
                delayed=True
            )
            A = state('A').cmd.run('echo hoho', cwd='/')
            state('B').cmd.run('echo hehe', cwd='/')
            extend(
                A,
                state('X').cmd.run(cwd='/a/b/c'),
                state('Y').file('managed', name='a_file.txt'),
                state('Z').service.watch(file='A')
            )
        '''))
        self.assertEqual(len(result), 4)
        self.assertEqual(
            result['include'],
            [{'base': sls} for sls in
             ('some.sls.file', 'another.sls.file', 'more.sls.file')]
        )
        extend = result['extend']
        self.assertEqual(extend['X']['cmd'][0], 'run')
        self.assertEqual(extend['X']['cmd'][1]['cwd'], '/a/b/c')
        self.assertEqual(extend['Y']['file'][0], 'managed')
        self.assertEqual(extend['Y']['file'][1]['name'], 'a_file.txt')
        self.assertEqual(len(extend['Z']['service']), 1)
        self.assertEqual(extend['Z']['service'][0]['watch'][0]['file'], 'A')

        self.assertEqual(result['B']['cmd'][0], 'run')
        self.assertTrue('A' not in result)
        self.assertEqual(extend['A']['cmd'][0], 'run')

    def test_cmd_call(self):
        result = self.HIGHSTATE.state.call_template_str(textwrap.dedent('''\
            #!pydsl
            state('A').cmd.run('echo this is state A', cwd='/')

            some_var = 12345
            def do_something(a, b, *args, **kws):
                return dict(result=True, changes={'a': a, 'b': b, 'args': args, 'kws': kws, 'some_var': some_var})

            state('C').cmd.call(do_something, 1, 2, 3, x=1, y=2) \
                          .require(state('A').cmd)

            state('G').cmd.wait('echo this is state G', cwd='/') \
                          .watch(state('C').cmd)
        '''))
        ret = (result[k] for k in result.keys() if 'do_something' in k).next()
        changes = ret['changes']
        self.assertEqual(
            changes,
            dict(a=1, b=2, args=(3,), kws=dict(x=1, y=2), some_var=12345)
        )

        ret = (result[k] for k in result.keys() if '-G_' in k).next()
        self.assertEqual(ret['changes']['stdout'], 'this is state G')

    def test_multiple_state_func_in_state_mod(self):
        with self.assertRaisesRegexp(PyDslError, 'Multiple state functions'):
            self.render_sls(textwrap.dedent('''
                state('A').cmd.run('echo hoho')
                state('A').cmd.wait('echo hehe')
            '''))

    def test_no_state_func_in_state_mod(self):
        with self.assertRaisesRegexp(PyDslError, 'No state function specified'):
            self.render_sls(textwrap.dedent('''
                state('B').cmd.require(cmd='hoho')
            '''))

    def test_load_highstate(self):
        result = self.render_sls(textwrap.dedent('''
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
            '''))
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

    def test_ordered_states(self):
        result = self.render_sls(textwrap.dedent('''
            __pydsl__.set(ordered=True)
            A = state('A')
            state('B').cmd.run('echo bbbb')
            A.cmd.run('echo aaa')
            state('B').cmd.run(cwd='/')
            state('C').cmd.run('echo ccc')
            state('B').file.managed(source='/a/b/c')
            '''))
        self.assertEqual(len(result['B']['cmd']), 3)
        self.assertEqual(result['A']['cmd'][1]['require'][0]['cmd'], 'B')
        self.assertEqual(result['C']['cmd'][1]['require'][0]['cmd'], 'A')
        self.assertEqual(result['B']['file'][1]['require'][0]['cmd'], 'C')

    def test_pipe_through_stateconf(self):
        dirpath = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory {0!r} was not created'.format(
                    dirpath
                )
            )
        output = os.path.join(dirpath, 'output')
        try:
            write_to(os.path.join(dirpath, 'xxx.sls'), textwrap.dedent(
                '''#!stateconf -os yaml . jinja
                .X:
                  cmd.run:
                    - name: echo X >> {0}
                    - cwd: /
                .Y:
                  cmd.run:
                    - name: echo Y >> {1}
                    - cwd: /
                .Z:
                  cmd.run:
                    - name: echo Z >> {2}
                    - cwd: /
                '''.format(output, output, output)))
            write_to(os.path.join(dirpath, 'yyy.sls'), textwrap.dedent('''\
                #!pydsl|stateconf -ps

                __pydsl__.set(ordered=True)
                state('.D').cmd.run('echo D >> {0}', cwd='/')
                state('.E').cmd.run('echo E >> {1}', cwd='/')
                state('.F').cmd.run('echo F >> {2}', cwd='/')
                '''.format(output, output, output)))

            write_to(os.path.join(dirpath, 'aaa.sls'), textwrap.dedent('''\
                #!pydsl|stateconf -ps

                include('xxx', 'yyy')

                # make all states in xxx run BEFORE states in this sls.
                extend(state('.start').stateconf.require(stateconf='xxx::goal'))

                # make all states in yyy run AFTER this sls.
                extend(state('.goal').stateconf.require_in(stateconf='yyy::start'))

                __pydsl__.set(ordered=True)

                state('.A').cmd.run('echo A >> {0}', cwd='/')
                state('.B').cmd.run('echo B >> {1}', cwd='/')
                state('.C').cmd.run('echo C >> {2}', cwd='/')
                '''.format(output, output, output)))

            state_highstate({'base': ['aaa']}, dirpath)
            with salt.utils.fopen(output, 'r') as f:
                self.assertEqual(''.join(f.read().split()), "XYZABCDEF")

        finally:
            shutil.rmtree(dirpath, ignore_errors=True)

    def test_rendering_includes(self):
        dirpath = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory {0!r} was not created'.format(
                    dirpath
                )
            )
        output = os.path.join(dirpath, 'output')
        try:
            write_to(os.path.join(dirpath, 'aaa.sls'), textwrap.dedent('''\
                #!pydsl|stateconf -ps

                include('xxx')
                yyy = include('yyy')

                # ensure states in xxx are run first, then those in yyy and then those in aaa last.
                extend(state('yyy::start').stateconf.require(stateconf='xxx::goal'))
                extend(state('.start').stateconf.require(stateconf='yyy::goal'))

                extend(state('yyy::Y2').cmd.run('echo Y2 extended >> {0}'))

                __pydsl__.set(ordered=True)

                yyy.hello('red', 1)
                yyy.hello('green', 2)
                yyy.hello('blue', 3)
                '''.format(output)))

            write_to(os.path.join(dirpath, 'xxx.sls'), textwrap.dedent('''\
                #!stateconf -os yaml . jinja

                include:
                  - yyy

                extend:
                  yyy::start:
                    stateconf.set:
                      - require:
                        - stateconf: .goal

                  yyy::Y1:
                    cmd.run:
                      - name: 'echo Y1 extended >> {0}'

                .X1:
                  cmd.run:
                    - name: echo X1 >> {1}
                    - cwd: /
                .X2:
                  cmd.run:
                    - name: echo X2 >> {2}
                    - cwd: /
                .X3:
                  cmd.run:
                    - name: echo X3 >> {3}
                    - cwd: /

                '''.format(output, output, output, output)))

            write_to(os.path.join(dirpath, 'yyy.sls'), textwrap.dedent('''\
                #!pydsl|stateconf -ps

                include('xxx')
                __pydsl__.set(ordered=True)

                state('.Y1').cmd.run('echo Y1 >> {0}', cwd='/')
                state('.Y2').cmd.run('echo Y2 >> {1}', cwd='/')
                state('.Y3').cmd.run('echo Y3 >> {2}', cwd='/')

                def hello(color, number):
                    state(color).cmd.run('echo hello '+color+' '+str(number)+' >> {3}', cwd='/')
                '''.format(output, output, output, output)))

            state_highstate({'base': ['aaa']}, dirpath)
            expected = textwrap.dedent('''\
                X1
                X2
                X3
                Y1 extended
                Y2 extended
                Y3
                hello red 1
                hello green 2
                hello blue 3
                ''')

            with salt.utils.fopen(output, 'r') as f:
                self.assertEqual(sorted(f.read()), sorted(expected))

        finally:
            shutil.rmtree(dirpath, ignore_errors=True)

    def test_compile_time_state_execution(self):
        if not sys.stdin.isatty():
            self.skipTest('Not attached to a TTY')
        dirpath = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory {0!r} was not created'.format(
                    dirpath
                )
            )
        try:
            write_to(os.path.join(dirpath, 'aaa.sls'), textwrap.dedent('''\
                #!pydsl

                __pydsl__.set(ordered=True)
                A = state('A')
                A.cmd.run('echo hehe > {0}/zzz.txt', cwd='/')
                A.file.managed('{1}/yyy.txt', source='salt://zzz.txt')
                A()
                A()

                state().cmd.run('echo hoho >> {2}/yyy.txt', cwd='/')

                A.file.managed('{3}/xxx.txt', source='salt://zzz.txt')
                A()
                '''.format(dirpath, dirpath, dirpath, dirpath)))
            state_highstate({'base': ['aaa']}, dirpath)
            with salt.utils.fopen(os.path.join(dirpath, 'yyy.txt'), 'r') as f:

                self.assertEqual(f.read(), 'hehe\nhoho\n')
            with salt.utils.fopen(os.path.join(dirpath, 'xxx.txt'), 'r') as f:
                self.assertEqual(f.read(), 'hehe\n')
        finally:
            shutil.rmtree(dirpath, ignore_errors=True)

    def test_nested_high_state_execution(self):
        dirpath = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory {0!r} was not created'.format(
                    dirpath
                )
            )
        output = os.path.join(dirpath, 'output')
        try:
            write_to(os.path.join(dirpath, 'aaa.sls'), textwrap.dedent('''\
                #!pydsl
                __salt__['state.sls']('bbb')
                state().cmd.run('echo bbbbbb', cwd='/')
                '''))
            write_to(os.path.join(dirpath, 'bbb.sls'), textwrap.dedent(
                '''
                # {{ salt['state.sls']('ccc')
                test:
                  cmd.run:
                    - name: echo bbbbbbb
                    - cwd: /
                '''))
            write_to(os.path.join(dirpath, 'ccc.sls'), textwrap.dedent(
                '''
                #!pydsl
                state().cmd.run('echo ccccc', cwd='/')
                '''))
            state_highstate({'base': ['aaa']}, dirpath)
        finally:
            shutil.rmtree(dirpath, ignore_errors=True)

    def test_repeat_includes(self):
        dirpath = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory {0!r} was not created'.format(
                    dirpath
                )
            )
        output = os.path.join(dirpath, 'output')
        try:
            write_to(os.path.join(dirpath, 'b.sls'), textwrap.dedent('''\
                #!pydsl
                include('c')
                include('d')
                '''))
            write_to(os.path.join(dirpath, 'c.sls'), textwrap.dedent('''\
                #!pydsl
                modtest = include('e')
                modtest.success
                '''))
            write_to(os.path.join(dirpath, 'd.sls'), textwrap.dedent('''\
                #!pydsl
                modtest = include('e')
                modtest.success
                '''))
            write_to(os.path.join(dirpath, 'e.sls'), textwrap.dedent('''\
                #!pydsl
                success = True
                '''))
            state_highstate({'base': ['b']}, dirpath)
            state_highstate({'base': ['c', 'd']}, dirpath)
        finally:
            shutil.rmtree(dirpath, ignore_errors=True)


def write_to(fpath, content):
    with salt.utils.fopen(fpath, 'w') as f:
        f.write(content)


def state_highstate(state, dirpath):
    opts = copy.copy(OPTS)
    opts['file_roots'] = dict(base=[dirpath])
    HIGHSTATE = HighState(opts)
    HIGHSTATE.push_active()
    try:
        high, errors = HIGHSTATE.render_highstate(state)
        if errors:
            import pprint
            pprint.pprint('\n'.join(errors))
            pprint.pprint(high)

        out = HIGHSTATE.state.call_high(high)
        # pprint.pprint(out)
    finally:
        HIGHSTATE.pop_active()


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PyDSLRendererTestCase, needs_daemon=False)
