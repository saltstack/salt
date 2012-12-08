# Import Python libs
import sys
from cStringIO import StringIO

# Import Salt libs
from salt.renderers.yaml import has_ordered_dict
from saltunittest import TestCase
import salt.loader
import salt.config

REQUISITES = ['require', 'require_in', 'use', 'use_in', 'watch', 'watch_in']

OPTS = salt.config.master_config('whatever, just load the defaults!')
# we should have used minion_config(), but that would try to resolve
# the master hostname, and retry for 30 seconds! Lucily for our purpose,
# master conf or minion conf, it doesn't matter.

OPTS['file_client'] = 'local'
OPTS['file_roots'] = dict(base=['/'])

RENDERERS = salt.loader.render(OPTS, {})

def render_sls(content, sls='', env='base', argline='-G yaml . jinja', **kws):
    return RENDERERS['stateconf'](
                StringIO(content), env=env, sls=sls,
                argline=argline,
                renderers=RENDERERS,
                **kws)


class StateConfigRendererTestCase(TestCase):

    def test_state_config(self):
        result = render_sls('''
.sls_params:
  stateconf.set:
    - name1: value1
    - name2: value2

.extra:
  stateconf:
    - set
    - name: value

# --- end of state config ---

test:
  cmd.run:
    - name: echo name1={{sls_params.name1}} name2={{sls_params.name2}} {{extra.name}}
    - cwd: /
''', sls='test')
        self.assertEqual(len(result), 3)
        self.assertTrue('test::sls_params' in result and 'test' in result)
        self.assertTrue('test::extra' in result)
        self.assertEqual(result['test']['cmd.run'][0]['name'],
                         'echo name1=value1 name2=value2 value')


    def test_sls_dir(self):
        result = render_sls('''
test:
  cmd.run:
    - name: echo sls_dir={{sls_dir}}
    - cwd: /
''', sls='path.to.sls')
        self.assertEqual(result['test']['cmd.run'][0]['name'],
                         'echo sls_dir=path/to')


    def test_states_declared_with_shorthand_no_args(self):
        result = render_sls('''
test:
  cmd.run:
    - name: echo testing
    - cwd: /
test1:
  pkg.installed
test2:
  user.present
'''     )
        self.assertTrue(len(result), 3)
        for args in (result['test1']['pkg.installed'],
                     result['test2']['user.present']  ):
            self.assertTrue(isinstance(args, list))
            self.assertEqual(len(args), 0)
        self.assertEqual(result['test']['cmd.run'][0]['name'], 'echo testing')


    def test_adding_state_name_arg_for_dot_state_id(self):
        result = render_sls('''
.test:
  pkg.installed:
    - cwd: /
.test2:
  pkg.installed:
    - name: vim
''', sls='test')
        self.assertEqual(
                result['test::test']['pkg.installed'][0]['name'], 'test')
        self.assertEqual(
                result['test::test2']['pkg.installed'][0]['name'], 'vim')


    def test_state_prefix(self):
        result = render_sls('''
.test:
  cmd.run:
    - name: echo renamed
    - cwd: /

state_id:
  cmd:
    - run
    - name: echo not renamed
    - cwd: /
''', sls='test')
        self.assertEqual(len(result), 2)
        self.assertTrue('test::test' in result)
        self.assertTrue('state_id' in result)


    def test_dot_state_id_in_requisites(self):
        for req in REQUISITES:
            result = render_sls('''
.test:
  cmd.run:
    - name: echo renamed
    - cwd: /

state_id:
  cmd.run:
    - name: echo not renamed
    - cwd: /
    - {0}:
      - cmd: .test

    '''.format(req), sls='test')
            self.assertEqual(len(result), 2)
            self.assertTrue('test::test' in result)
            self.assertTrue('state_id' in result)
            self.assertEqual(result['state_id']['cmd.run'][2][req][0]['cmd'],
                         'test::test')


    def test_relative_include_with_requisites(self):
        for req in REQUISITES:
            result = render_sls('''
include:
  - some.helper
  - .utils

state_id:
  cmd.run:
    - name: echo test
    - cwd: /
    - {0}:
      - cmd: .utils::some_state
'''.format(req), sls='test.work')
            self.assertEqual(result['include'][1], 'test.utils')
            self.assertEqual(result['state_id']['cmd.run'][2][req][0]['cmd'],
                         'test.utils::some_state')


    def test_relative_include_and_extend(self):
        result = render_sls('''
include:
  - some.helper
  - .utils

extend:
  .utils::some_state:
    cmd.run:
      - name: echo overriden
    ''', sls='test.work')
        self.assertTrue('test.utils::some_state' in result['extend'])


    def test_goal_state_generation(self):
        result = render_sls('''
{% for sid in "ABCDE": %}
{{sid}}:
  cmd.run:
    - name: echo this is {{sid}}
    - cwd: /
{% endfor %}

''', sls='test.goalstate', argline='yaml . jinja')
        self.assertTrue(len(result), len('ABCDE')+1)

        reqs = result['test.goalstate::goal']['stateconf.set'][1]['require']
        # note: arg 0 is the name arg.

        self.assertEqual(set([i.itervalues().next() for i in reqs]),
                         set('ABCDE'))

    def test_implicit_require_with_goal_state(self):
        if sys.version_info < (2, 7) and not HAS_ORDERED_DICT:
            self.skipTest('OrderedDict is not available')

        result = render_sls('''
{% for sid in "ABCDE": %}
{{sid}}:
  cmd.run:
    - name: echo this is {{sid}}
    - cwd: /
{% endfor %}

F:
  cmd.run:
    - name: echo this is F
    - cwd: /
    - require:
      - cmd: A
      - cmd: B

G:
  cmd.run:
    - name: echo this is G
    - cwd: /
    - require:
      - cmd: D
      - cmd: F
''', sls='test', argline='-o yaml . jinja')

        sids = 'ABCDEFG'[::-1]
        for i, sid in enumerate(sids):
            if i < len(sids)-1:
                self.assertEqual(
                    result[sid]['cmd.run'][2]['require'][0]['cmd'], sids[i+1])

        F_args = result['F']['cmd.run']
        self.assertEqual(len(F_args), 3)
        F_req = F_args[2]['require']
        self.assertEqual(len(F_req), 3)
        self.assertEqual(F_req[1]['cmd'], 'A')
        self.assertEqual(F_req[2]['cmd'], 'B')

        G_args = result['G']['cmd.run']
        self.assertEqual(len(G_args), 3)
        G_req = G_args[2]['require']
        self.assertEqual(len(G_req), 3)
        self.assertEqual(G_req[1]['cmd'], 'D')
        self.assertEqual(G_req[2]['cmd'], 'F')

        goal_args = result['test::goal']['stateconf.set']
        # Note: arg 0 is the auto-added name arg.

        self.assertEqual(len(goal_args), 2)
        self.assertEqual(
                [i.itervalues().next() for i in goal_args[1]['require']],
                list('ABCDEFG'))
