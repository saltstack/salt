# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import ast
import copy
import tempfile
import json
import datetime
import pprint
import re

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.case import ModuleCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.paths import TMP_CONF_DIR

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
        self.local_salt = {
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
                dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
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
                dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(out, 'Hey world !a b !\n')

    def test_saltenv(self):
        '''
        If the template is within the searchpath it can
        import, include and extend other templates.
        The initial template is expected to be already cached
        get_template does not request it from the master again.
        '''
        fc = MockFileClient()
        with patch.object(SaltCacheLoader, 'file_client', MagicMock(return_value=fc)):
            filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_import')
            with salt.utils.fopen(filename) as fp_:
                out = render_jinja_tmpl(
                    fp_.read(),
                    dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote',
                               'file_roots': self.local_opts['file_roots'],
                               'pillar_roots': self.local_opts['pillar_roots']},
                         a='Hi', b='Salt', saltenv='test', salt=self.local_salt))
            self.assertEqual(out, 'Hey world !Hi Salt !\n')
            self.assertEqual(fc.requests[0]['path'], 'salt://macro')

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
        with patch.object(SaltCacheLoader, 'file_client', MagicMock(return_value=fc)):
            with salt.utils.fopen(filename) as fp_:
                self.assertRaisesRegex(
                    SaltRenderError,
                    expected,
                    render_jinja_tmpl,
                    fp_.read(),
                    dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))

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
        with patch.object(SaltCacheLoader, 'file_client', MagicMock(return_value=fc)):
            with salt.utils.fopen(filename) as fp_:
                self.assertRaisesRegex(
                    SaltRenderError,
                    expected,
                    render_jinja_tmpl,
                    fp_.read(),
                    dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))

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
        with patch.object(SaltCacheLoader, 'file_client', MagicMock(return_value=fc)):
            with salt.utils.fopen(filename) as fp_:
                self.assertRaisesRegex(
                    SaltRenderError,
                    expected,
                    render_jinja_tmpl,
                    fp_.read(),
                    dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))

    def test_non_ascii_encoding(self):
        fc = MockFileClient()
        with patch.object(SaltCacheLoader, 'file_client', MagicMock(return_value=fc)):
            filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_import')
            with salt.utils.fopen(filename) as fp_:
                out = render_jinja_tmpl(
                    fp_.read(),
                    dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote',
                               'file_roots': self.local_opts['file_roots'],
                               'pillar_roots': self.local_opts['pillar_roots']},
                         a='Hi', b='Sàlt', saltenv='test', salt=self.local_salt))
            self.assertEqual(out, u'Hey world !Hi Sàlt !\n')
            self.assertEqual(fc.requests[0]['path'], 'salt://macro')

            filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'non_ascii')
            with salt.utils.fopen(filename) as fp_:
                out = render_jinja_tmpl(
                    fp_.read(),
                    dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote',
                               'file_roots': self.local_opts['file_roots'],
                               'pillar_roots': self.local_opts['pillar_roots']},
                         a='Hi', b='Sàlt', saltenv='test', salt=self.local_salt))
            self.assertEqual(u'Assunção\n', out)
            self.assertEqual(fc.requests[0]['path'], 'salt://macro')

    @skipIf(HAS_TIMELIB is False, 'The `timelib` library is not installed.')
    def test_strftime(self):
        response = render_jinja_tmpl('{{ "2002/12/25"|strftime }}',
                dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(response, '2002-12-25')

        objects = (
            datetime.datetime(2002, 12, 25, 12, 00, 00, 00),
            '2002/12/25',
            1040814000,
            '1040814000'
        )

        for object in objects:
            response = render_jinja_tmpl('{{ object|strftime }}',
                    dict(object=object, opts=self.local_opts, saltenv='test', salt=self.local_salt))
            self.assertEqual(response, '2002-12-25')

            response = render_jinja_tmpl('{{ object|strftime("%b %d, %Y") }}',
                    dict(object=object, opts=self.local_opts, saltenv='test', salt=self.local_salt))
            self.assertEqual(response, 'Dec 25, 2002')

            response = render_jinja_tmpl('{{ object|strftime("%y") }}',
                    dict(object=object, opts=self.local_opts, saltenv='test', salt=self.local_salt))
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
        self.assertRaisesRegex(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test', salt=self.local_salt)
        )

    @skipIf(six.PY3, 'Not applicable to Python 3: skipping.')
    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_render_with_unicode_syntax_error(self):
        with patch.object(builtins, '__salt_system_encoding__', 'utf-8'):
            template = u'hello\n\n{{ bad\n\nfoo\ud55c'
            expected = r'.*---\nhello\n\n{{ bad\n\nfoo\xed\x95\x9c    <======================\n---'
            self.assertRaisesRegex(
                SaltRenderError,
                expected,
                render_jinja_tmpl,
                template,
                dict(opts=self.local_opts, saltenv='test', salt=self.local_salt)
            )

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_render_with_utf8_syntax_error(self):
        with patch.object(builtins, '__salt_system_encoding__', 'utf-8'):
            template = 'hello\n\n{{ bad\n\nfoo\xed\x95\x9c'
            expected = r'.*---\nhello\n\n{{ bad\n\nfoo\xed\x95\x9c    <======================\n---'
            self.assertRaisesRegex(
                SaltRenderError,
                expected,
                render_jinja_tmpl,
                template,
                dict(opts=self.local_opts, saltenv='test', salt=self.local_salt)
            )

    def test_render_with_undefined_variable(self):
        template = "hello\n\n{{ foo }}\n\nfoo"
        expected = r'Jinja variable \'foo\' is undefined'
        self.assertRaisesRegex(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test', salt=self.local_salt)
        )

    def test_render_with_undefined_variable_utf8(self):
        template = "hello\xed\x95\x9c\n\n{{ foo }}\n\nfoo"
        expected = r'Jinja variable \'foo\' is undefined'
        self.assertRaisesRegex(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test', salt=self.local_salt)
        )

    def test_render_with_undefined_variable_unicode(self):
        template = u"hello\ud55c\n\n{{ foo }}\n\nfoo"
        expected = r'Jinja variable \'foo\' is undefined'
        self.assertRaisesRegex(
            SaltRenderError,
            expected,
            render_jinja_tmpl,
            template,
            dict(opts=self.local_opts, saltenv='test', salt=self.local_salt)
        )


class TestCustomExtensions(TestCase):

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
        self.local_salt = {
            # 'dns.A': dnsutil.A,
            # 'dns.AAAA': dnsutil.AAAA,
            # 'file.exists': filemod.file_exists,
            # 'file.basename': filemod.basename,
            # 'file.dirname': filemod.dirname
        }

    def test_regex_escape(self):
        dataset = 'foo?:.*/\\bar'
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|regex_escape }}').render(dataset=dataset)
        self.assertEqual(rendered, re.escape(dataset))

    def test_unique_string(self):
        dataset = 'foo'
        unique = set(dataset)
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|unique }}').render(dataset=dataset)
        self.assertEqual(rendered, u"{0}".format(unique))

    def test_unique_tuple(self):
        dataset = ('foo', 'foo', 'bar')
        unique = set(dataset)
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|unique }}').render(dataset=dataset)
        self.assertEqual(rendered, u"{0}".format(unique))

    def test_unique_list(self):
        dataset = ['foo', 'foo', 'bar']
        unique = ['foo', 'bar']
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|unique }}').render(dataset=dataset)
        self.assertEqual(rendered, u"{0}".format(unique))

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
        if six.PY3:
            self.assertEqual("str value", rendered)
        else:
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

    def test_is_ip(self):
        '''Test the `is_ip` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1' | is_ip }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

        rendered = render_jinja_tmpl("{{ 'FE80::' | is_ip }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

        rendered = render_jinja_tmpl("{{ 'random' | is_ip }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'False')

    def test_is_ipv4(self):
        '''Test the `is_ipv4` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1' | is_ipv4 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

        rendered = render_jinja_tmpl("{{ 'FE80::' | is_ipv4 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'False')

        rendered = render_jinja_tmpl("{{ 'random' | is_ipv4 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'False')

    def test_is_ipv6(self):
        '''Test the `is_ipv6` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1' | is_ipv6 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'False')

        rendered = render_jinja_tmpl("{{ 'FE80::' | is_ipv6 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

        rendered = render_jinja_tmpl("{{ 'random' | is_ipv6 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'False')

    def test_ipaddr(self):
        '''Test the `ipaddr` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1' | ipaddr }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'192.168.0.1')

        # provides a list with valid IP addresses only
        rendered = render_jinja_tmpl("{{ ['192.168.0.1', '172.17.17.1', 'foo', 'bar', '::'] | ipaddr | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'192.168.0.1, 172.17.17.1, ::')

        # return only multicast addresses
        rendered = render_jinja_tmpl("{{ ['224.0.0.1', 'FF01::1', '::'] | ipaddr(options='multicast') | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'224.0.0.1, ff01::1')

    def test_ipv4(self):
        '''Test the `ipv4` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1' | ipv4 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'192.168.0.1')

        rendered = render_jinja_tmpl("{{ ['192.168.0.1', '172.17.17.1'] | ipv4 | join(', ')}}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'192.168.0.1, 172.17.17.1')

        rendered = render_jinja_tmpl("{{ 'fe80::' | ipv4 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'None')

        rendered = render_jinja_tmpl("{{ 'random' | ipv4 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'None')

        rendered = render_jinja_tmpl("{{ '192.168.0.1' | ipv4(options='lo') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'None')

        rendered = render_jinja_tmpl("{{ '127.0.0.1' | ipv4(options='lo') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'127.0.0.1')

    def test_ipv6(self):
        '''Test the `ipv6` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1' | ipv6 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'None')

        rendered = render_jinja_tmpl("{{ 'random' | ipv6 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'None')

        # returns the standard format value
        rendered = render_jinja_tmpl("{{ 'FE80:0:0::0' | ipv6 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'fe80::')

        # fe80:: is link local therefore will be returned
        rendered = render_jinja_tmpl("{{ 'fe80::' | ipv6(options='ll') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'fe80::')

        # fe80:: is not loopback
        rendered = render_jinja_tmpl("{{ 'fe80::' | ipv6(options='lo') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'None')

        # returns only IPv6 addresses in the list
        rendered = render_jinja_tmpl("{{ ['fe80::', '192.168.0.1'] | ipv6 | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'fe80::')

        rendered = render_jinja_tmpl("{{ ['fe80::', '::'] | ipv6 | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'fe80::, ::')

    def test_network_hosts(self):
        '''Test the `network_hosts` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1/30' | network_hosts | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'192.168.0.1, 192.168.0.2')

    def test_network_size(self):
        '''Test the `network_size` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ '192.168.0.1' | network_size }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'1')

        rendered = render_jinja_tmpl("{{ '192.168.0.1/8' | network_size }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'16777216')

    def test_http_query(self):
        '''Test the `http_query` Jinja filter.'''
        for backend in ('requests', 'tornado', 'urllib2'):
            rendered = render_jinja_tmpl("{{ 'http://www.google.com' | http_query(backend='" + backend + "') }}",
                                         dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
            self.assertIsInstance(rendered, six.text_type, 'Failed with backend: {}'.format(backend))
            dict_reply = ast.literal_eval(rendered)
            self.assertIsInstance(dict_reply, dict, 'Failed with backend: {}'.format(backend))
            self.assertIsInstance(dict_reply['body'], six.string_types, 'Failed with backend: {}'.format(backend))

    def test_to_bool(self):
        '''Test the `to_bool` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 1 | to_bool }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

        rendered = render_jinja_tmpl("{{ 'True' | to_bool }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

        rendered = render_jinja_tmpl("{{ 0 | to_bool }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'False')

        rendered = render_jinja_tmpl("{{ 'Yes' | to_bool }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

    def test_quote(self):
        '''Test the `quote` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'random' | quote }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'random')

    def test_regex_search(self):
        '''Test the `regex_search` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'abcdefabcdef' | regex_search('BC(.*)', ignorecase=True) }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u"('defabcdef',)")  # because search looks only at the beginning

    def test_regex_match(self):
        '''Test the `regex_match` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'abcdefabcdef' | regex_match('BC(.*)', ignorecase=True)}}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u"None")

    def test_regex_replace(self):
        '''Test the `regex_replace` Jinja filter.'''
        rendered = render_jinja_tmpl(r"{{ 'lets replace spaces' | regex_replace('\s+', '__') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'lets__replace__spaces')

    def test_uuid(self):
        '''Test the `uuid` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'random' | uuid }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'3652b285-26ad-588e-a5dc-c2ee65edc804')

    def test_min(self):
        '''Test the `min` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ [1, 2, 3] | min }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'1')

    def test_max(self):
        '''Test the `max` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ [1, 2, 3] | max }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'3')

    def test_avg(self):
        '''Test the `avg` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ [1, 2, 3] | avg }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'2.0')

    def test_union(self):
        '''Test the `union` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ [1, 2, 3] | union([2, 3, 4]) | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'1, 2, 3, 4')

    def test_intersect(self):
        '''Test the `intersect` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ [1, 2, 3] | intersect([2, 3, 4]) | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'2, 3')

    def test_difference(self):
        '''Test the `difference` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ [1, 2, 3] | difference([2, 3, 4]) | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'1')

    def test_symmetric_difference(self):
        '''Test the `symmetric_difference` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ [1, 2, 3] | symmetric_difference([2, 3, 4]) | join(', ') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'1, 4')

    def test_md5(self):
        '''Test the `md5` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'random' | md5 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'7ddf32e17a6ac5ce04a8ecbf782ca509')

    def test_sha256(self):
        '''Test the `sha256` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'random' | sha256 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'a441b15fe9a3cf56661190a0b93b9dec7d04127288cc87250967cf3b52894d11')

    def test_sha512(self):
        '''Test the `sha512` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'random' | sha512 }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, six.text_type(('811a90e1c8e86c7b4c0eef5b2c0bf0ec1b19c4b1b5a242e6455be93787cb473cb7bc'
                                                  '9b0fdeb960d00d5c6881c2094dd63c5c900ce9057255e2a4e271fc25fef1')))

    def test_hmac(self):
        '''Test the `hmac` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'random' | hmac('secret', 'blah') }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'False')

        rendered = render_jinja_tmpl(("{{ 'get salted' | "
                                      "hmac('shared secret', 'eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ=') }}"),
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'True')

    def test_base64_encode(self):
        '''Test the `base64_encode` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'random' | base64_encode }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'cmFuZG9t')

    def test_base64_decode(self):
        '''Test the `base64_decode` Jinja filter.'''
        rendered = render_jinja_tmpl("{{ 'cmFuZG9t' | base64_decode }}",
                                     dict(opts=self.local_opts, saltenv='test', salt=self.local_salt))
        self.assertEqual(rendered, u'random')

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

    def tearDown(self):
        del self.jinja

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
