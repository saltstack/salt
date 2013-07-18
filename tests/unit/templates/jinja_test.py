# -*- coding: utf-8 -*-

# Import python libs
import os
import tempfile
import json
import datetime

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import salt.utils
from salt.utils.jinja import SaltCacheLoader, SerializerExtension
from salt.utils.templates import render_jinja_tmpl

# Import 3rd party libs
import yaml
from jinja2 import Environment
try:
    import timelib
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

    def get_file(self, template, dest='', makedirs=False, env='base'):
        self.requests.append({
            'path': template,
            'dest': dest,
            'makedirs': makedirs,
            'env': env
        })


class TestSaltCacheLoader(TestCase):
    def test_searchpath(self):
        '''
        The searchpath is based on the cachedir option and the env parameter
        '''
        tmp = tempfile.gettempdir()
        loader = SaltCacheLoader({'cachedir': tmp}, env='test')
        assert loader.searchpath == [os.path.join(tmp, 'files', 'test')]

    def test_mockclient(self):
        '''
        A MockFileClient is used that records all file requests normally sent
        to the master.
        '''
        loader = SaltCacheLoader({'cachedir': TEMPLATES_DIR}, 'test')
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

    def get_test_env(self):
        '''
        Setup a simple jinja test environment
        '''
        loader = SaltCacheLoader({'cachedir': TEMPLATES_DIR}, 'test')
        fc = MockFileClient(loader)
        jinja = Environment(loader=loader)
        return fc, jinja

    def test_import(self):
        '''
        You can import and use macros from other files
        '''
        fc, jinja = self.get_test_env()
        result = jinja.get_template('hello_import').render()
        self.assertEqual(result, 'Hey world !a b !')
        assert len(fc.requests) == 2
        self.assertEqual(fc.requests[0]['path'], 'salt://hello_import')
        self.assertEqual(fc.requests[1]['path'], 'salt://macro')

    def test_include(self):
        '''
        You can also include a template that imports and uses macros
        '''
        fc, jinja = self.get_test_env()
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
        _, jinja = self.get_test_env()
        result = jinja.get_template('hello_include').render(a='Hi', b='Salt')
        self.assertEqual(result, 'Hey world !Hi Salt !')


class TestGetTemplate(TestCase):
    def __init__(self, *args, **kws):
        TestCase.__init__(self, *args, **kws)
        self.local_opts = {
            'cachedir': TEMPLATES_DIR,
            'file_client': 'local',
            'file_roots': {
                'other': [os.path.join(TEMPLATES_DIR, 'files', 'test')]
            }
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
                    dict(opts=self.local_opts, env='other'))
        self.assertEqual(out, 'world\n')

    def test_fallback_noloader(self):
        '''
        A Template with a filesystem loader is returned as fallback
        if the file is not contained in the searchpath
        '''
        filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_import')
        out = render_jinja_tmpl(
                salt.utils.fopen(filename).read(),
                dict(opts=self.local_opts, env='other'))
        self.assertEqual(out, 'Hey world !a b !\n')

    def test_env(self):
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
        out = render_jinja_tmpl(
                salt.utils.fopen(filename).read(),
                dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote'},
                     a='Hi', b='Salt', env='test'))
        self.assertEqual(out, 'Hey world !Hi Salt !\n')
        self.assertEqual(fc.requests[0]['path'], 'salt://macro')
        SaltCacheLoader.file_client = _fc

    def test_non_ascii_encoding(self):
        fc = MockFileClient()
        # monkey patch file client
        _fc = SaltCacheLoader.file_client
        SaltCacheLoader.file_client = lambda loader: fc
        filename = os.path.join(TEMPLATES_DIR, 'files', 'test', 'hello_import')
        out = render_jinja_tmpl(
                salt.utils.fopen(filename).read(),
                dict(opts={'cachedir': TEMPLATES_DIR, 'file_client': 'remote'},
                     a='Hi', b='Sàlt', env='test'))
        self.assertEqual(out, 'Hey world !Hi Sàlt !\n')
        self.assertEqual(fc.requests[0]['path'], 'salt://macro')
        SaltCacheLoader.file_client = _fc

    @skipIf(HAS_TIMELIB is False, 'The `timelib` library is not installed.')
    def test_strftime(self):
        response = render_jinja_tmpl('{{ "2002/12/25"|strftime }}',
                dict(opts=self.local_opts, env='other'))
        self.assertEqual(response, '2002-12-25')

        objects = (
            datetime.datetime(2002, 12, 25, 12, 00, 00, 00),
            '2002/12/25',
            1040814000,
            '1040814000'
        )

        for object in objects:
            response = render_jinja_tmpl('{{ object|strftime }}',
                    dict(object=object, opts=self.local_opts, env='other'))
            self.assertEqual(response, '2002-12-25')

            response = render_jinja_tmpl('{{ object|strftime("%b %d, %Y") }}',
                    dict(object=object, opts=self.local_opts, env='other'))
            self.assertEqual(response, 'Dec 25, 2002')

            response = render_jinja_tmpl('{{ object|strftime("%y") }}',
                    dict(object=object, opts=self.local_opts, env='other'))
            self.assertEqual(response, '02')


class TestCustomExtensions(TestCase):
    def test_serialize(self):
        dataset = {
            "foo": True,
            "bar": 42,
            "baz": [1, 2, 3],
            "qux": 2.0
        }
        env = Environment(extensions=[SerializerExtension])
        rendered = env.from_string('{{ dataset|yaml }}').render(dataset=dataset)
        self.assertEquals(dataset, yaml.load(rendered))

        rendered = env.from_string('{{ dataset|json }}').render(dataset=dataset)
        self.assertEquals(dataset, json.loads(rendered))


if __name__ == '__main__':
    from integration import run_tests
    run_tests([TestSaltCacheLoader, TestGetTemplate, TestCustomExtensions], needs_daemon=False)
