# -*- coding: utf-8 -*-

from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

import salt.state
from salt.config import minion_config
from salt.template import compile_template_str
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
pydmesg_salt_expected = OrderedDict([('/usr/local/bin/pydmesg', pydmesg_expected)])
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
                ('dup', OrderedDict([
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
    def render(self, template, opts=None):
        _config = minion_config(None)
        _config['file_client'] = 'local'
        if opts:
            _config.update(opts)
        _state = salt.state.State(_config)
        return compile_template_str(template,
                                    _state.rend,
                                    _state.opts['renderer'])


class RendererTests(TestCase, RendererMixin):
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


class MapTests(TestCase, RendererMixin):
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
