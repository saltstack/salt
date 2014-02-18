# -*- coding: utf-8 -*-

from cStringIO import StringIO

from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

from salt.config import minion_config
from salt.loader import states
from salt.minion import SMinion
from salt.renderers.pyobjects import render as pyobjects_render
from salt.utils.odict import OrderedDict
from salt.utils.pyobjects import (StateFactory, State, StateRegistry,
                                  InvalidFunction)

test_registry = StateRegistry()
File = StateFactory('file', registry=test_registry)

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

basic_template = """#!pyobjects
File.directory('/tmp', mode='1777', owner='root', group='root')
"""

invalid_template = """#!pyobjects
File.fail('/tmp')
"""

include_template = """#!pyobjects
Include('http')
"""

extend_template = """#!pyobjects
Include('http')
Service.running(Extend('apache'), watch=[{'file': '/etc/file'}])
"""


class StateTests(TestCase):
    def setUp(self):
        test_registry.empty()

    def test_serialization(self):
        f = State('/usr/local/bin/pydmesg', 'file', 'managed',
                  require=File('/usr/local/bin'),
                  registry=test_registry,
                  **pydmesg_kwargs)

        self.assertEqual(f(), pydmesg_expected)

    def test_factory_serialization(self):
        File.managed('/usr/local/bin/pydmesg',
                     require=File('/usr/local/bin'),
                     **pydmesg_kwargs)

        self.assertEqual(
            test_registry.states['/usr/local/bin/pydmesg'](),
            pydmesg_expected
        )

    def test_context_manager(self):
        with File('/usr/local/bin'):
            pydmesg = File.managed('/usr/local/bin/pydmesg', **pydmesg_kwargs)

            self.assertEqual(
                test_registry.states['/usr/local/bin/pydmesg'](),
                pydmesg_expected
            )

            with pydmesg:
                File.managed('/tmp/something', owner='root')

                self.assertEqual(
                    test_registry.states['/tmp/something'](),
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
            test_registry.states['/usr/local/bin/pydmesg'](),
            pydmesg_expected
        )

        self.assertEqual(
            test_registry.salt_data(),
            pydmesg_salt_expected
        )

        self.assertEqual(
            test_registry.states,
            OrderedDict()
        )


class RendererTests(TestCase):
    def render(self, template):
        _config = minion_config(None)
        _config['file_client'] = 'local'
        _minion = SMinion(_config)
        _states = states(_config, _minion.functions)

        return pyobjects_render(StringIO(template), _states=_states)

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

        self.assertEqual(test_registry.states, OrderedDict())

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
