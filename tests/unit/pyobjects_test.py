# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import uuid

from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

import salt.state
from salt.config import minion_config
from salt.template import compile_template
from salt.utils.odict import OrderedDict
from salt.utils.pyobjects import (StateFactory, State, Registry,
                                  SaltObject, InvalidFunction, DuplicateState)

File = StateFactory('file')
Service = StateFactory('service')

pydmesg_expected = {
    'file.managed': [
        {'group': 'root'},
        {'mode': '0755'},
        {'require': [{'file': '/usr/local/bin'}]},
        {'source': 'salt://debian/files/pydmesg.py'},
        {'user': 'root'},
    ]
}
pydmesg_salt_expected = OrderedDict([
    ('/usr/local/bin/pydmesg', pydmesg_expected)
])
pydmesg_kwargs = dict(user='root', group='root', mode='0755',
                      source='salt://debian/files/pydmesg.py')

basic_template = '''#!pyobjects
File.directory('/tmp', mode='1777', owner='root', group='root')
'''

invalid_template = '''#!pyobjects
File.fail('/tmp')
'''

include_template = '''#!pyobjects
include('http')
'''

extend_template = '''#!pyobjects
include('http')
Service.running(extend('apache'), watch=[{'file': '/etc/file'}])
'''

map_template = '''#!pyobjects
class Samba(Map):
    __merge__ = 'samba:lookup'

    class Debian:
        server = 'samba'
        client = 'samba-client'
        service = 'samba'

    class RougeChapeau:
        __match__ = 'RedHat'
        server = 'samba'
        client = 'samba'
        service = 'smb'

    class Ubuntu:
        __grain__ = 'os'
        service = 'smbd'

with Pkg.installed("samba", names=[Samba.server, Samba.client]):
    Service.running("samba", name=Samba.service)
'''

import_template = '''#!pyobjects
import salt://map.sls

Pkg.removed("samba-imported", names=[Samba.server, Samba.client])
'''

from_import_template = '''#!pyobjects
# this spacing is like this on purpose to ensure it's stripped properly
from   salt://map.sls  import     Samba

Pkg.removed("samba-imported", names=[Samba.server, Samba.client])
'''


class StateTests(TestCase):
    def setUp(self):
        Registry.empty()

    def test_serialization(self):
        f = State('/usr/local/bin/pydmesg', 'file', 'managed',
                  require=File('/usr/local/bin'),
                  **pydmesg_kwargs)

        self.assertEqual(f(), pydmesg_expected)

    def test_factory_serialization(self):
        File.managed('/usr/local/bin/pydmesg',
                     require=File('/usr/local/bin'),
                     **pydmesg_kwargs)

        self.assertEqual(
            Registry.states['/usr/local/bin/pydmesg'],
            pydmesg_expected
        )

    def test_context_manager(self):
        with File('/usr/local/bin'):
            pydmesg = File.managed('/usr/local/bin/pydmesg', **pydmesg_kwargs)

            self.assertEqual(
                Registry.states['/usr/local/bin/pydmesg'],
                pydmesg_expected
            )

            with pydmesg:
                File.managed('/tmp/something', owner='root')

                self.assertEqual(
                    Registry.states['/tmp/something'],
                    {
                        'file.managed': [
                            {'owner': 'root'},
                            {'require': [
                                {'file': '/usr/local/bin'},
                                {'file': '/usr/local/bin/pydmesg'}
                            ]},
                        ]
                    }
                )

    def test_salt_data(self):
        File.managed('/usr/local/bin/pydmesg',
                     require=File('/usr/local/bin'),
                     **pydmesg_kwargs)

        self.assertEqual(
            Registry.states['/usr/local/bin/pydmesg'],
            pydmesg_expected
        )

        self.assertEqual(
            Registry.salt_data(),
            pydmesg_salt_expected
        )

        self.assertEqual(
            Registry.states,
            OrderedDict()
        )

    def test_duplicates(self):
        def add_dup():
            File.managed('dup', name='/dup')

        add_dup()
        self.assertRaises(DuplicateState, add_dup)

        Service.running('dup', name='dup-service')

        self.assertEqual(
            Registry.states,
            OrderedDict([
                ('dup',
                 OrderedDict([
                     ('file.managed', [
                         {'name': '/dup'}
                     ]),
                     ('service.running', [
                         {'name': 'dup-service'}
                     ])
                 ]))
            ])
        )


class RendererMixin(object):
    '''
    This is a mixin that adds a ``.render()`` method to render a template

    It must come BEFORE ``TestCase`` in the declaration of your test case
    class so that our setUp & tearDown get invoked first, and super can
    trigger the methods in the ``TestCase`` class.
    '''
    def setUp(self, *args, **kwargs):
        super(RendererMixin, self).setUp(*args, **kwargs)

        self.root_dir = tempfile.mkdtemp('pyobjects_test_root')

        self.config = minion_config(None)
        self.config.update({
            'file_client': 'local',
            'file_roots': {
                'base': [self.root_dir]
            }
        })

    def tearDown(self, *args, **kwargs):
        shutil.rmtree(self.root_dir)

        super(RendererMixin, self).tearDown(*args, **kwargs)

    def write_template_file(self, filename, content):
        full_path = os.path.join(self.root_dir, filename)
        with open(full_path, 'w') as f:
            f.write(content)
        return full_path

    def render(self, template, opts=None, filename=None):
        if opts:
            self.config.update(opts)

        if not filename:
            filename = ".".join([
                str(uuid.uuid4()),
                "sls"
            ])
        full_path = self.write_template_file(filename, template)

        state = salt.state.State(self.config)
        return compile_template(full_path,
                                state.rend,
                                state.opts['renderer'])


class RendererTests(RendererMixin, TestCase):
    def test_basic(self):
        ret = self.render(basic_template)
        self.assertEqual(ret, OrderedDict([
            ('/tmp', {
                'file.directory': [
                    {'group': 'root'},
                    {'mode': '1777'},
                    {'owner': 'root'}
                ]
            }),
        ]))

        self.assertEqual(Registry.states, OrderedDict())

    def test_invalid_function(self):
        def _test():
            self.render(invalid_template)
        self.assertRaises(InvalidFunction, _test)

    def test_include(self):
        ret = self.render(include_template)
        self.assertEqual(ret, OrderedDict([
            ('include', ['http']),
        ]))

    def test_extend(self):
        ret = self.render(extend_template)
        self.assertEqual(ret, OrderedDict([
            ('include', ['http']),
            ('extend', OrderedDict([
                ('apache', {
                    'service.running': [
                        {'watch': [{'file': '/etc/file'}]}
                    ]
                }),
            ])),
        ]))

    def test_sls_imports(self):
        def render_and_assert(template):
            ret = self.render(template,
                              {'grains': {
                                  'os_family': 'Debian',
                                  'os': 'Debian'
                              }})

            self.assertEqual(ret, OrderedDict([
                ('samba-imported', {
                    'pkg.removed': [
                        {'names': ['samba', 'samba-client']},
                    ]
                })
            ]))

        self.write_template_file("map.sls", map_template)
        render_and_assert(import_template)
        render_and_assert(from_import_template)


class MapTests(RendererMixin, TestCase):
    def test_map(self):
        def samba_with_grains(grains):
            return self.render(map_template, {'grains': grains})

        def assert_ret(ret, server, client, service):
            self.assertEqual(ret, OrderedDict([
                ('samba', {
                    'pkg.installed': [
                        {'names': [server, client]}
                    ],
                    'service.running': [
                        {'name': service},
                        {'require': [{'pkg': 'samba'}]}
                    ]
                })
            ]))

        ret = samba_with_grains({'os_family': 'Debian', 'os': 'Debian'})
        assert_ret(ret, 'samba', 'samba-client', 'samba')

        ret = samba_with_grains({'os_family': 'Debian', 'os': 'Ubuntu'})
        assert_ret(ret, 'samba', 'samba-client', 'smbd')

        ret = samba_with_grains({'os_family': 'RedHat', 'os': 'CentOS'})
        assert_ret(ret, 'samba', 'samba', 'smb')


class SaltObjectTests(TestCase):
    def test_salt_object(self):
        def attr_fail():
            Salt.fail.blah()

        def times2(x):
            return x*2

        __salt__ = {
            'math.times2': times2
        }

        Salt = SaltObject(__salt__)

        self.assertRaises(AttributeError, attr_fail)
        self.assertEqual(Salt.math.times2, times2)
        self.assertEqual(Salt.math.times2(2), 4)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StateTests, RendererTests, MapTests, SaltObjectTests, needs_daemon=False)
