# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import sys
import shutil
import tempfile
import textwrap
import copy

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.paths import TMP

# Import Salt libs
import salt.loader
import salt.config
import salt.utils.files
import salt.utils.versions
from salt.state import HighState
from salt.utils.pydsl import PyDslError


# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import StringIO


REQUISITES = ['require', 'require_in', 'use', 'use_in', 'watch', 'watch_in']


class CommonTestCaseBoilerplate(TestCase):

    def setUp(self):
        self.root_dir = tempfile.mkdtemp(dir=TMP)
        self.state_tree_dir = os.path.join(self.root_dir, 'state_tree')
        self.cache_dir = os.path.join(self.root_dir, 'cachedir')
        if not os.path.isdir(self.root_dir):
            os.makedirs(self.root_dir)

        if not os.path.isdir(self.state_tree_dir):
            os.makedirs(self.state_tree_dir)

        if not os.path.isdir(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.config = salt.config.minion_config(None)
        self.config['root_dir'] = self.root_dir
        self.config['state_events'] = False
        self.config['id'] = 'match'
        self.config['file_client'] = 'local'
        self.config['file_roots'] = dict(base=[self.state_tree_dir])
        self.config['cachedir'] = self.cache_dir
        self.config['test'] = False
        self.config['grains'] = salt.loader.grains(self.config)
        self.HIGHSTATE = HighState(self.config)
        self.HIGHSTATE.push_active()

    def tearDown(self):
        try:
            self.HIGHSTATE.pop_active()
        except IndexError:
            pass
        del self.config
        del self.HIGHSTATE

    def state_highstate(self, state, dirpath):
        opts = copy.copy(self.config)
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


class PyDSLRendererTestCase(CommonTestCaseBoilerplate):
    '''
    WARNING: If tests in here are flaky, they may need
    to be moved to their own class. Sharing HighState, especially
    through setUp/tearDown can create dangerous race conditions!
    '''

    def render_sls(self, content, sls='', saltenv='base', **kws):
        if 'env' in kws:
            # "env" is not supported; Use "saltenv".
            kws.pop('env')

        return self.HIGHSTATE.state.rend['pydsl'](
            StringIO(content), saltenv=saltenv, sls=sls, **kws
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

        s_iter = six.itervalues(result)
        try:
            s = next(s_iter)['file']
        except KeyError:
            s = next(s_iter)['file']
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
        ret = next(result[k] for k in six.iterkeys(result) if 'do_something' in k)
        changes = ret['changes']
        self.assertEqual(
            changes,
            dict(a=1, b=2, args=(3,), kws=dict(x=1, y=2), some_var=12345)
        )

        ret = next(result[k] for k in six.iterkeys(result) if '-G_' in k)
        self.assertEqual(ret['changes']['stdout'], 'this is state G')

    def test_multiple_state_func_in_state_mod(self):
        with self.assertRaisesRegex(PyDslError, 'Multiple state functions'):
            self.render_sls(textwrap.dedent('''
                state('A').cmd.run('echo hoho')
                state('A').cmd.wait('echo hehe')
            '''))

    def test_no_state_func_in_state_mod(self):
        with self.assertRaisesRegex(PyDslError, 'No state function specified'):
            self.render_sls(textwrap.dedent('''
                state('B').cmd.require(cmd='hoho')
            '''))

    def test_load_highstate(self):
        result = self.render_sls(textwrap.dedent('''
            import salt.utils.yaml
            __pydsl__.load_highstate(salt.utils.yaml.safe_load("""
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
        self.assertIn({'name': 'echo hello'}, result['A']['cmd'])
        self.assertIn({'cwd': '/'}, result['A']['cmd'])
        self.assertIn({'name': 'echo hello world'}, result['A']['cmd'])
        self.assertEqual(len(result['A']['cmd']), 4)

        self.assertEqual(len(result['B']['pkg']), 1)
        self.assertEqual(result['B']['pkg'][0], 'installed')

        self.assertEqual(result['B']['service'][0], 'running')
        self.assertIn({'require': [{'pkg': 'B'}]}, result['B']['service'])
        self.assertIn({'watch': [{'cmd': 'A'}]}, result['B']['service'])
        self.assertEqual(len(result['B']['service']), 3)

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
        dirpath = tempfile.mkdtemp(dir=TMP)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory \'{0}\' was not created'.format(
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
                    - name: echo Y >> {0}
                    - cwd: /
                .Z:
                  cmd.run:
                    - name: echo Z >> {0}
                    - cwd: /
                '''.format(output.replace('\\', '/'))))
            write_to(os.path.join(dirpath, 'yyy.sls'), textwrap.dedent('''\
                #!pydsl|stateconf -ps

                __pydsl__.set(ordered=True)
                state('.D').cmd.run('echo D >> {0}', cwd='/')
                state('.E').cmd.run('echo E >> {0}', cwd='/')
                state('.F').cmd.run('echo F >> {0}', cwd='/')
                '''.format(output.replace('\\', '/'))))

            write_to(os.path.join(dirpath, 'aaa.sls'), textwrap.dedent('''\
                #!pydsl|stateconf -ps

                include('xxx', 'yyy')

                # make all states in xxx run BEFORE states in this sls.
                extend(state('.start').stateconf.require(stateconf='xxx::goal'))

                # make all states in yyy run AFTER this sls.
                extend(state('.goal').stateconf.require_in(stateconf='yyy::start'))

                __pydsl__.set(ordered=True)

                state('.A').cmd.run('echo A >> {0}', cwd='/')
                state('.B').cmd.run('echo B >> {0}', cwd='/')
                state('.C').cmd.run('echo C >> {0}', cwd='/')
                '''.format(output.replace('\\', '/'))))

            self.state_highstate({'base': ['aaa']}, dirpath)
            with salt.utils.files.fopen(output, 'r') as f:
                self.assertEqual(''.join(f.read().split()), "XYZABCDEF")

        finally:
            shutil.rmtree(dirpath, ignore_errors=True)

    def test_compile_time_state_execution(self):
        if not sys.stdin.isatty():
            self.skipTest('Not attached to a TTY')
        dirpath = tempfile.mkdtemp(dir=TMP)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory \'{0}\' was not created'.format(
                    dirpath
                )
            )
        try:
            # The Windows shell will include any spaces before the redirect
            # in the text that is redirected.
            # For example: echo hello > test.txt will contain "hello "
            write_to(os.path.join(dirpath, 'aaa.sls'), textwrap.dedent('''\
                #!pydsl

                __pydsl__.set(ordered=True)
                A = state('A')
                A.cmd.run('echo hehe>{0}/zzz.txt', cwd='/')
                A.file.managed('{0}/yyy.txt', source='salt://zzz.txt')
                A()
                A()

                state().cmd.run('echo hoho>>{0}/yyy.txt', cwd='/')

                A.file.managed('{0}/xxx.txt', source='salt://zzz.txt')
                A()
                '''.format(dirpath.replace('\\', '/'))))
            self.state_highstate({'base': ['aaa']}, dirpath)
            with salt.utils.files.fopen(os.path.join(dirpath, 'yyy.txt'), 'rt') as f:
                self.assertEqual(f.read(), 'hehe' + os.linesep + 'hoho' + os.linesep)
            with salt.utils.files.fopen(os.path.join(dirpath, 'xxx.txt'), 'rt') as f:
                self.assertEqual(f.read(), 'hehe' + os.linesep)
        finally:
            shutil.rmtree(dirpath, ignore_errors=True)

    def test_nested_high_state_execution(self):
        dirpath = tempfile.mkdtemp(dir=TMP)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory \'{0}\' was not created'.format(
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
                # {{ salt['state.sls']('ccc') }}
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
            self.state_highstate({'base': ['aaa']}, dirpath)
        finally:
            shutil.rmtree(dirpath, ignore_errors=True)

    def test_repeat_includes(self):
        dirpath = tempfile.mkdtemp(dir=TMP)
        if not os.path.isdir(dirpath):
            self.skipTest(
                'The temporary directory \'{0}\' was not created'.format(
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
            self.state_highstate({'base': ['b']}, dirpath)
            self.state_highstate({'base': ['c', 'd']}, dirpath)
        finally:
            shutil.rmtree(dirpath, ignore_errors=True)


def write_to(fpath, content):
    with salt.utils.files.fopen(fpath, 'w') as f:
        f.write(content)
