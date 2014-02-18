# -*- coding: utf-8 -*-

import os
from cStringIO import StringIO

from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

from salt.renderers.pyobjects import render as pyobjects_render
from salt.utils.odict import OrderedDict
from salt.utils.pyobjects import StateFactory, State, StateRegistry

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


def tmpl(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", name)


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
    def test_basic(self):
        ret = pyobjects_render(StringIO(basic_template))
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
            pyobjects_render(StringIO(invalid_template))
        self.assertRaises(Exception, _test)
