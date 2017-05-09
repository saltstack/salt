# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import copy
import tempfile
import json
import datetime
import pprint

# Import Salt Testing libs
from salttesting.unit import skipIf, TestCase
from salttesting.case import ModuleCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import salt.config
import salt.ext.six as six
import salt.loader
import salt.utils
from salt.exceptions import SaltRenderError
from salt.ext.six.moves import builtins
from salt.utils import get_context
from salt.utils.jinja import (
    SaltCacheLoader,
    SerializerExtension,
    ensure_sequence_filter
)
from salt.utils.templates import JINJA, render_jinja_tmpl
from salt.utils.odict import OrderedDict
from integration import TMP_CONF_DIR

# Import 3rd party libs
import yaml
from jinja2 import Environment, DictLoader, exceptions
try:
    import timelib  # pylint: disable=W0611
    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

TEMPLATES_DIR = os.path.dirname(os.path.abspath(__file__))


class MockFileClient(object):
    '''
    Does not download files but records any file request for testing
    '''
    def __init__(self, loader=None):
        if loader:
            loader._file_client = self
        self.requests = []

    def get_file(self, template, dest='', makedirs=False, saltenv='base'):
        self.requests.append({
            'path': template,
            'dest': dest,
            'makedirs': makedirs,
            'saltenv': saltenv
        })


class TestSaltCacheLoader(TestCase):
    def __init__(self, *args, **kws):
        TestCase.__init__(self, *args, **kws)
        self.opts = {
            'cachedir': TEMPLATES_DIR,
            'file_roots': {
                'test': [os.path.join(TEMPLATES_DIR, 'files', 'test')]
            },
            'pillar_roots': {
                'test': [os.path.join(TEMPLATES_DIR, 'files', 'test')]
            }
        }

    def test_searchpath(self):
        '''
        The searchpath is based on the cachedir option and the saltenv parameter
        '''
        tmp = tempfile.gettempdir()
        opts = copy.deepcopy(self.opts)
        opts.update({'cachedir': tmp})
        loader = SaltCacheLoader(opts, saltenv='test')
        assert loader.searchpath == [os.path.join(tmp, 'files', 'test')]

    def test_mockclient(self):
        '''
        A MockFileClient is used that records all file requests normally sent
        to the master.
        '''
        loader = SaltCacheLoader(self.opts, 'test')
        fc = MockFileClient(loader)
        res = loader.get_source(None, 'hello_simple')
        assert len(res) == 3
        # res[0] on Windows is unicode and use os.linesep so it works cross OS
        self.assertEqual(str(res[0]), 'world' + os.linesep)
        tmpl_dir = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_simple')
        self.assertEqual(res[1], tmpl_dir)
        assert res[2](), 'Template up to date?'
        assert len(fc.requests)
        self.assertEqual(fc.requests[0]['path'], 'salt://hello_simple')

    def get_test_saltenv(self):
        '''
        Setup a simple jinja test environment
        '''
        loader = SaltCacheLoader(self.opts, 'test')
        fc = MockFileClient(loader)
        jinja = Environment(loader=loader)
        return fc, jinja

    def test_import(self):
        '''
        You can import and use macros from other files
        '''
        fc, jinja = self.get_test_saltenv()
        result = jinja.get_template('hello_import').render()
        self.assertEqual(result, 'Hey world !a b !')
        assert len(fc.requests) == 2
        self.assertEqual(fc.requests[0]['path'], 'salt://hello_import')
        self.assertEqual(fc.requests[1]['path'], 'salt://macro')

    def test_include(self):
        '''
        You can also include a template that imports and uses macros
        '''
        fc, jinja = self.get_test_saltenv()
        result = jinja.get_template('hello_include').render()
        self.assertEqual(result, 'Hey world !a b !')
        assert len(fc.requests) == 3
        self.assertEqual(fc.requests[0]['path'], 'salt://hello_include')
        self.assertEqual(fc.requests[1]['path'], 'salt://hello_import')
        self.assertEqual(fc.requests[2]['path'], 'salt://macro')

    def test_include_context(self):
        '''
        Context variables are passes to the included template by default.
        '''
        _, jinja = self.get_test_saltenv()
        result = jinja.get_template('hello_include').render(a='Hi', b='Salt')
        self.assertEqual(result, 'Hey world !Hi Salt !')


class TestGetTemplate(TestCase):
    def __init__(self, *args, **kws):
        TestCase.__init__(self, *args, **kws)
        self.local_opts = {
            'cachedir': TEMPLATES_DIR,
            'file_client': 'local',
            'file_ignore_regex': None,
            'file_ignore_glob': None,
            'file_roots': {
                'test': [os.path.join(TEMPLATES_DIR, 'files', 'test')]
            },
            'pillar_roots': {
                'test': [os.path.join(TEMPLATES_DIR, 'files', 'test')]
            },
            'fileserver_backend': ['roots'],
            'hash_type': 'md5',
            'extension_modules': os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'extmods'),
        }

    def test_fallback(self):
        '''
        A Template with a filesystem loader is returned as fallback
        if the file is not contained in the searchpath
        '''
        fn_ = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_simple')
        with salt.utils.fopen(fn_) as fp_:
            out = render_jinja_tmpl(
                fp_.read(),
                dict(opts=self.local_opts, saltenv='test'))
        self.assertEqual(out, 'world\n')

    def test_fallback_noloader(self):
        '''
        A Template with a filesystem loader is returned as fallback
        if the file is not contained in the searchpath
        '''
        filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_import')
        with salt.utils.fopen(filename) as fp_:
            out = render_jinja_tmpl(
                fp_.read(),
                dict(opts=self.local_opts, saltenv='test'))
        self.assertEqual(out, 'Hey world !a b !\n')

    def test_saltenv(self):
        '''
        If the template is within the searchpath it can
        import, include and extend other templates.
        The initial template is expected to be already cached
        get_template does not request it from the master again.
        '''
        fc = MockFileClient()
        # monkey patch file client
        _fc = SaltCacheLoader.file_client
        SaltCacheLoader.file_client = lambda loader: fc
        filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_import')
        with salt.utils.fopen(filename) as fp_:
            out = render_jinja_tmpl(
                fp_.read(),
                dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote',
                           'file_roots': self.local_opts['file_roots'],
                           'pillar_roots': self.local_opts['pillar_roots']},
                     a='Hi', b='Salt', saltenv='test'))
        self.assertEqual(out, 'Hey world !Hi Salt !\n')
        self.assertEqual(fc.requests[0]['path'], 'salt://macro')
        SaltCacheLoader.file_client = _fc

    def test_macro_additional_log_for_generalexc(self):
        '''
        If we failed in a macro because of e.g. a TypeError, get
        more output from trace.
        '''
        expected = r'''Jinja error:.*division.*
.*/macrogeneral\(2\):
---
\{% macro mymacro\(\) -%\}
\{\{ 1/0 \}\}    <======================
\{%- endmacro %\}
---.*'''
        filename = os.path.join(TEMPLATES_DIR,
                                'files', 'test', 'hello_import_generalerror')
        fc = MockFileClient()
        _fc = SaltCacheLoader.file_client
        SaltCacheLoader.file_client = lambda loader: fc
        with salt.utils.fopen(filename) as fp_:
            self.assertRaisesRegexp(
                SaltRenderError,
                expected,
                render_jinja_tmpl,
                fp_.read(),
                dict(opts=self.local_opts, saltenv='test'))
        SaltCacheLoader.file_client = _fc

    def test_macro_additional_log_for_undefined(self):
        '''
        If we failed in a macro because of undefined variables, get
        more output from trace.
        '''
        expected = r'''Jinja variable 'b' is undefined
.*/macroundefined\(2\):
---
\{% macro mymacro\(\) -%\}
\{\{b.greetee\}\} <-- error is here    <======================
\{%- endmacro %\}
---'''
        filename = os.path.join(TEMPLATES_DIR,
                                'files', 'test', 'hello_import_undefined')
        fc = MockFileClient()
        _fc = SaltCacheLoader.file_client
        SaltCacheLoader.file_client = lambda loader: fc
        with salt.utils.fopen(filename) as fp_:
            self.assertRaisesRegexp(
                SaltRenderError,
                expected,
                render_jinja_tmpl,
                fp_.read(),
                dict(opts=self.local_opts, saltenv='test'))
        SaltCacheLoader.file_client = _fc

    def test_macro_additional_log_syntaxerror(self):
        '''
        If  we failed in a macro, get more output from trace.
        '''
        expected = r'''Jinja syntax error: expected token .*end.*got '-'.*
.*/macroerror\(2\):
---
# macro
\{% macro mymacro\(greeting, greetee='world'\) -\} <-- error is here    <======================
\{\{ greeting ~ ' ' ~ greetee \}\} !
\{%- endmacro %\}
---.*'''
        filename = os.path.join(TEMPLATES_DIR,
                                'files', 'test', 'hello_import_error')
        fc = MockFileClient()
        _fc = SaltCacheLoader.file_client
        SaltCacheLoader.file_client = lambda loader: fc
        with salt.utils.fopen(filename) as fp_:
            self.assertRaisesRegexp(
                SaltRenderError,
                expected,
                render_jinja_tmpl,
                fp_.read(),
                dict(opts=self.local_opts, saltenv='test'))
        SaltCacheLoader.file_client = _fc

    def test_non_ascii_encoding(self):
        fc = MockFileClient()
        # monkey patch file client
        _fc = SaltCacheLoader.file_client
        SaltCacheLoader.file_client = lambda loader: fc
        filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_import')
        with salt.utils.fopen(filename) as fp_:
            out = render_jinja_tmpl(
                fp_.read(),
                dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote',
                           'file_roots': self.local_opts['file_roots'],
                           'pillar_roots': self.local_opts['pillar_roots']},
                     a='Hi', b='Sàlt', saltenv='test'))
        self.assertEqual(out, u'Hey world !Hi Sàlt !\n')
        self.assertEqual(fc.requests[0]['path'], 'salt://macro')
        SaltCacheLoader.file_client = _fc

        _fc = SaltCacheLoader.file_client
        SaltCacheLoader.file_client = lambda loader: fc
        filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'non_ascii')
        with salt.utils.fopen(filename) as fp_:
            out = render_jinja_tmpl(
                fp_.read(),
                dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote',
                           'file_roots': self.local_opts['file_roots'],
                           'pillar_roots': self.local_opts['pillar_roots']},
                     a='Hi', b='Sàlt', saltenv='test'))
        self.assertEqual(u'Assunção\n', out)
        self.assertEqual(fc.requests[0]['path'], 'salt://macro')
        SaltCacheLoader.file_client = _fc

    @skipIf(HAS_TIMELIB is False, 'The `timelib` library is not installed.')
    def test_strftime(self):
        response = render_jinja_tmpl('{{ "2002/12/25"|strftime }}',
                dict(opts=self.local_opts, saltenv='test'))
        self.assertEqual(response, '2002-12-25')

        objects = (
            datetime.datetime(2002, 12, 25, 12, 00, 00, 00),
            '2002/12/25',
            1040814000,
            '1040814000'
        )

        for object in objects:
            response = render_jinja_tmpl('{{ object|strftime }}',
                    dict(object=object, opts=self.local_opts, saltenv='test'))
            self.assertEqual(response, '2002-12-25')

            response = render_jinja_tmpl('{{ object|strftime("%b %d, %Y") }}',
                    dict(object=object, opts=self.local_opts, saltenv='test'))
            self.assertEqual(response, 'Dec 25, 2002')

            response = render_jinja_tmpl('{{ object|strftime("%y") }}',
                    dict(object=object, opts=self.local_opts, saltenv='test'))
            self.assertEqual(response, '02')

    def test_non_ascii(self):
        fn = os.path.join(TEMPLATES_DIR, 'files', 'test', 'non_ascii')
        out = JINJA(fn, opts=self.local_opts, saltenv='test')
        with salt.utils.fopen(out['data']) as fp:
            result = fp.read()
            if six.PY2:
                result = result.decode('utf-8')
            self.assertEqual(u'Assunção\n', result)

    def test_get_context_has_enough_context(self):
        template = '1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf'
        context = get_context(template, 8)
        expected = '---\n[...]\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\n[...]\n---'
        self.assertEqual(expected, context)

    def test_get_context_at_top_of_file(self):
        template = '1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf'
        context = get_context(template, 1)
        expected = '---\n1\n2\n3\n4\n5\n6\n[...]\n---'
        self.assertEqual(expected, context)

    def test_get_context_at_bottom_of_file(self):
        template = '1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf'
        context = get_context(template, 15)
        expected = '---\n[...]\na\nb\nc\nd\ne\nf\n---'
        self.assertEqual(expected, context)

    def test_get_context_2_context_lines(self):
        template = '1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf'
        context = get_context(template, 8, num_lines=2)
        expected = '---\n[...]\n6\n7\n8\n9\na\n[...]\n---'
        self.assertEqual(expected, context)

    def test_get_context_with_marker(self):
        template = '1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf'
        context = get_context(template, 8, num_lines=2, marker=' <---')
        expected = '---\n[...]\n6\n7\n8 <---\n9\na\n[...]\n---'
        self.assertEqual(expected, context)

    def test_render_with_syntax_error(self):
        template = 'hello\n\n{{ bad\n\nfoo'
        expected = r'.*---\nhello\n\n{{ bad\n\nfoo    <======================\n---'
        self.assertRaisesRegexp(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test')
        )

    @skipIf(six.PY3, 'Not applicable to Python 3: skipping.')
    def test_render_with_unicode_syntax_error(self):
        encoding = builtins.__salt_system_encoding__
        builtins.__salt_system_encoding__ = 'utf-8'
        template = u'hello\n\n{{ bad\n\nfoo\ud55c'
        expected = r'.*---\nhello\n\n{{ bad\n\nfoo\xed\x95\x9c    <======================\n---'
        self.assertRaisesRegexp(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test')
        )
        builtins.__salt_system_encoding__ = encoding

    def test_render_with_utf8_syntax_error(self):
        encoding = builtins.__salt_system_encoding__
        builtins.__salt_system_encoding__ = 'utf-8'
        template = 'hello\n\n{{ bad\n\nfoo\xed\x95\x9c'
        expected = r'.*---\nhello\n\n{{ bad\n\nfoo\xed\x95\x9c    <======================\n---'
        self.assertRaisesRegexp(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test')
        )
        builtins.__salt_system_encoding__ = encoding

    def test_render_with_undefined_variable(self):
        template = "hello\n\n{{ foo }}\n\nfoo"
        expected = r'Jinja variable \'foo\' is undefined'
        self.assertRaisesRegexp(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test')
        )

    def test_render_with_undefined_variable_utf8(self):
        template = "hello\xed\x95\x9c\n\n{{ foo }}\n\nfoo"
        expected = r'Jinja variable \'foo\' is undefined'
        self.assertRaisesRegexp(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test')
        )

    def test_render_with_undefined_variable_unicode(self):
        template = u"hello\ud55c\n\n{{ foo }}\n\nfoo"
        expected = r'Jinja variable \'foo\' is undefined'
        self.assertRaisesRegexp(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test')
        )


class TestCustomExtensions(TestCase):
    def test_serialize_json(self):
        dataset = {
            "foo": True,
            "bar": 42,
            "baz": [1, 2, 3],
            "qux": 2.0
        }
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|json }}').render(dataset=dataset)
        self.assertEqual(dataset, json.loads(rendered))

    def test_serialize_yaml(self):
        dataset = {
            "foo": True,
            "bar": 42,
            "baz": [1, 2, 3],
            "qux": 2.0,
            "spam": OrderedDict([
                ('foo', OrderedDict([
                    ('bar', 'baz'),
                    ('qux', 42)
                ])
                )
            ])
        }
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|yaml }}').render(dataset=dataset)
        self.assertEqual(dataset, yaml.load(rendered))

    def test_serialize_yaml_str(self):
        dataset = "str value"
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|yaml }}').render(dataset=dataset)
        self.assertEqual(dataset, rendered)

    def test_serialize_yaml_unicode(self):
        dataset = u"str value"
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|yaml }}').render(dataset=dataset)
        self.assertEqual("!!python/unicode str value", rendered)

    def test_serialize_python(self):
        dataset = {
            "foo": True,
            "bar": 42,
            "baz": [1, 2, 3],
            "qux": 2.0
        }
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|python }}').render(dataset=dataset)
        self.assertEqual(rendered, pprint.pformat(dataset))

    def test_load_yaml(self):
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{% set document = "{foo: it works}"|load_yaml %}{{ document.foo }}').render()
        self.assertEqual(rendered, u"it works")

        rendered = env.from_string('{% set document = document|load_yaml %}'
                                   '{{ document.foo }}').render(document="{foo: it works}")
        self.assertEqual(rendered, u"it works")

        with self.assertRaises(exceptions.TemplateRuntimeError):
            env.from_string('{% set document = document|load_yaml %}'
                                       '{{ document.foo }}').render(document={"foo": "it works"})

    def test_load_tag(self):
        env = Environment(extensions=[SerializerExtension])

        source = '{{ bar }}, ' + \
                 '{% load_yaml as docu %}{foo: it works, {{ bar }}: baz}{% endload %}' + \
                                        '{{ docu.foo }}'

        rendered = env.from_string(source).render(bar="barred")
        self.assertEqual(rendered, u"barred, it works")

        source = '{{ bar }}, {% load_json as docu %}{"foo": "it works", "{{ bar }}": "baz"}{% endload %}' + \
                                        '{{ docu.foo }}'

        rendered = env.from_string(source).render(bar="barred")
        self.assertEqual(rendered, u"barred, it works")

        with self.assertRaises(exceptions.TemplateSyntaxError):
            env.from_string('{% load_yamle as document %}{foo, bar: it works}{% endload %}').render()

        with self.assertRaises(exceptions.TemplateRuntimeError):
            env.from_string('{% load_json as document %}{foo, bar: it works}{% endload %}').render()

    def test_load_json(self):
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{% set document = \'{"foo": "it works"}\'|load_json %}'
                                   '{{ document.foo }}').render()
        self.assertEqual(rendered, u"it works")

        rendered = env.from_string('{% set document = document|load_json %}'
                                   '{{ document.foo }}').render(document='{"foo": "it works"}')
        self.assertEqual(rendered, u"it works")

        # bad quotes
        with self.assertRaises(exceptions.TemplateRuntimeError):
            env.from_string("{{ document|load_json }}").render(document="{'foo': 'it works'}")

        # not a string
        with self.assertRaises(exceptions.TemplateRuntimeError):
            env.from_string('{{ document|load_json }}').render(document={"foo": "it works"})

    def test_load_yaml_template(self):
        loader = DictLoader({'foo': '{bar: "my god is blue", foo: [1, 2, 3]}'})
        env = Environment(extensions=[SerializerExtension], loader=loader)
        rendered = env.from_string('{% import_yaml "foo" as doc %}{{ doc.bar }}').render()
        self.assertEqual(rendered, u"my god is blue")

        with self.assertRaises(exceptions.TemplateNotFound):
            env.from_string('{% import_yaml "does not exists" as doc %}').render()

    def test_load_json_template(self):
        loader = DictLoader({'foo': '{"bar": "my god is blue", "foo": [1, 2, 3]}'})
        env = Environment(extensions=[SerializerExtension], loader=loader)
        rendered = env.from_string('{% import_json "foo" as doc %}{{ doc.bar }}').render()
        self.assertEqual(rendered, u"my god is blue")

        with self.assertRaises(exceptions.TemplateNotFound):
            env.from_string('{% import_json "does not exists" as doc %}').render()

    def test_load_text_template(self):
        loader = DictLoader({'foo': 'Foo!'})
        env = Environment(extensions=[SerializerExtension], loader=loader)

        rendered = env.from_string('{% import_text "foo" as doc %}{{ doc }}').render()
        self.assertEqual(rendered, u"Foo!")

        with self.assertRaises(exceptions.TemplateNotFound):
            env.from_string('{% import_text "does not exists" as doc %}').render()

    def test_catalog(self):
        loader = DictLoader({
            'doc1': '{bar: "my god is blue"}',
            'doc2': '{% import_yaml "doc1" as local2 %} never exported',
            'doc3': '{% load_yaml as local3 %}{"foo": "it works"}{% endload %} me neither',
            'main1': '{% from "doc2" import local2 %}{{ local2.bar }}',
            'main2': '{% from "doc3" import local3 %}{{ local3.foo }}',
            'main3': '''
                {% import "doc2" as imported2 %}
                {% import "doc3" as imported3 %}
                {{ imported2.local2.bar }}
            ''',
            'main4': '''
                {% import "doc2" as imported2 %}
                {% import "doc3" as imported3 %}
                {{ imported3.local3.foo }}
            ''',
            'main5': '''
                {% from "doc2" import local2 as imported2 %}
                {% from "doc3" import local3 as imported3 %}
                {{ imported2.bar }}
            ''',
            'main6': '''
                {% from "doc2" import local2 as imported2 %}
                {% from "doc3" import local3 as imported3 %}
                {{ imported3.foo }}
            '''

        })

        env = Environment(extensions=[SerializerExtension], loader=loader)
        rendered = env.get_template('main1').render()
        self.assertEqual(rendered, u"my god is blue")

        rendered = env.get_template('main2').render()
        self.assertEqual(rendered, u"it works")

        rendered = env.get_template('main3').render().strip()
        self.assertEqual(rendered, u"my god is blue")

        rendered = env.get_template('main4').render().strip()
        self.assertEqual(rendered, u"it works")

        rendered = env.get_template('main5').render().strip()
        self.assertEqual(rendered, u"my god is blue")

        rendered = env.get_template('main6').render().strip()
        self.assertEqual(rendered, u"it works")

    def test_nested_structures(self):
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ data }}').render(data="foo")
        self.assertEqual(rendered, u"foo")

        data = OrderedDict([
            ('foo', OrderedDict([
                        ('bar', 'baz'),
                        ('qux', 42)
                    ])
            )
        ])

        rendered = env.from_string('{{ data }}').render(data=data)
        self.assertEqual(rendered, u"{'foo': {'bar': 'baz', 'qux': 42}}")

        rendered = env.from_string('{{ data }}').render(data=[
                                                            OrderedDict(
                                                                foo='bar',
                                                            ),
                                                            OrderedDict(
                                                                baz=42,
                                                            )
                                                        ])
        self.assertEqual(rendered, u"[{'foo': 'bar'}, {'baz': 42}]")

    def test_sequence(self):
        env = Environment()
        env.filters['sequence'] = ensure_sequence_filter

        rendered = env.from_string('{{ data | sequence | length }}') \
                      .render(data='foo')
        self.assertEqual(rendered, '1')

        rendered = env.from_string('{{ data | sequence | length }}') \
                      .render(data=['foo', 'bar'])
        self.assertEqual(rendered, '2')

        rendered = env.from_string('{{ data | sequence | length }}') \
                      .render(data=('foo', 'bar'))
        self.assertEqual(rendered, '2')

        rendered = env.from_string('{{ data | sequence | length }}') \
                      .render(data=set(['foo', 'bar']))
        self.assertEqual(rendered, '2')

        rendered = env.from_string('{{ data | sequence | length }}') \
                      .render(data={'foo': 'bar'})
        self.assertEqual(rendered, '1')

    # def test_print(self):
    #     env = Environment(extensions=[SerializerExtension])
    #     source = '{% import_yaml "toto.foo" as docu %}'
    #     name, filename = None, '<filename>'
    #     parsed = env._parse(source, name, filename)
    #     print parsed
    #     print
    #     compiled = env._generate(parsed, name, filename)
    #     print compiled
    #     return


class TestDotNotationLookup(ModuleCase):
    '''
    Tests to call Salt functions via Jinja with various lookup syntaxes
    '''
    def setUp(self, *args, **kwargs):
        functions = {
            'mocktest.ping': lambda: True,
            'mockgrains.get': lambda x: 'jerry',
        }
        minion_opts = salt.config.minion_config(os.path.join(TMP_CONF_DIR, 'minion'))
        render = salt.loader.render(minion_opts, functions)
        self.jinja = render.get('jinja')

    def render(self, tmpl_str, context=None):
        return self.jinja(tmpl_str, context=context or {}, from_str=True).read()

    def test_normlookup(self):
        '''
        Sanity-check the normal dictionary-lookup syntax for our stub function
        '''
        tmpl_str = '''Hello, {{ salt['mocktest.ping']() }}.'''

        ret = self.render(tmpl_str)
        self.assertEqual(ret, 'Hello, True.')

    def test_dotlookup(self):
        '''
        Check calling a stub function using awesome dot-notation
        '''
        tmpl_str = '''Hello, {{ salt.mocktest.ping() }}.'''

        ret = self.render(tmpl_str)
        self.assertEqual(ret, 'Hello, True.')

    def test_shadowed_dict_method(self):
        '''
        Check calling a stub function with a name that shadows a ``dict``
        method name
        '''
        tmpl_str = '''Hello, {{ salt.mockgrains.get('id') }}.'''

        ret = self.render(tmpl_str)
        self.assertEqual(ret, 'Hello, jerry.')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestSaltCacheLoader, TestGetTemplate, TestCustomExtensions,
            TestDotNotationLookup,
              needs_daemon=False)
