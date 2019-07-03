# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
from tests.support.unit import TestCase, skipIf
from tests.support.helpers import TestsLoggingHandler
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

import salt.exceptions
from salt.utils import thin
from salt.utils import json
import salt.utils.stringutils
import salt.utils.platform
from salt.utils.stringutils import to_bytes as bts
from salt.ext.six.moves import range
import salt.ext.six

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class SSHThinTestCase(TestCase):
    '''
    TestCase for SaltSSH-related parts.
    '''
    def _popen(self, return_value=None, side_effect=None, returncode=0):
        '''
        Fake subprocess.Popen

        :return:
        '''

        proc = MagicMock()
        proc.communicate = MagicMock(return_value=return_value, side_effect=side_effect)
        proc.returncode = returncode
        popen = MagicMock(return_value=proc)

        return popen

    def _version_info(self, major=None, minor=None):
        '''
        Fake version info.

        :param major:
        :param minor:
        :return:
        '''
        class VersionInfo(tuple):
            pass

        vi = VersionInfo([major, minor])
        vi.major = major or sys.version_info.major
        vi.minor = minor or sys.version_info.minor

        return vi

    def _tarfile(self, getinfo=False):
        '''
        Fake tarfile handler.

        :return:
        '''
        spec = ['add', 'close']
        if getinfo:
            spec.append('getinfo')

        tf = MagicMock()
        tf.open = MagicMock(return_value=MagicMock(spec=spec))

        return tf

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_missing_dependencies(self):
        '''
        Test thin.get_ext_tops contains all required dependencies.

        :return:
        '''
        cfg = {'namespace': {'py-version': [0, 0], 'path': '/foo', 'dependencies': []}}

        with pytest.raises(Exception) as err:
            thin.get_ext_tops(cfg)
        self.assertIn('Missing dependencies', str(err.value))
        self.assertTrue(thin.log.error.called)
        self.assertIn('Missing dependencies', thin.log.error.call_args[0][0])
        self.assertIn('jinja2, yaml, tornado, msgpack',
                      thin.log.error.call_args[0][0])

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_missing_interpreter(self):
        '''
        Test thin.get_ext_tops contains interpreter configuration.

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'dependencies': []}}
        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        self.assertIn('missing specific locked Python version', str(err.value))

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_wrong_interpreter(self):
        '''
        Test thin.get_ext_tops contains correct interpreter configuration.

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': 2,
                             'dependencies': []}}

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        self.assertIn('specific locked Python version should be a list of '
                      'major/minor version', str(err.value))

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_cfg_interpreter(self):
        '''
        Test thin.get_ext_tops interpreter configuration.

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': [2, 6],
                             'dependencies': {'jinja2': '',
                                              'yaml': '',
                                              'tornado': '',
                                              'msgpack': ''}}}

        with pytest.raises(salt.exceptions.SaltSystemExit):
            thin.get_ext_tops(cfg)
        assert len(thin.log.warning.mock_calls) == 4
        assert sorted([x[1][1] for x in thin.log.warning.mock_calls]) == ['jinja2', 'msgpack', 'tornado', 'yaml']
        assert 'Module test has missing configuration' == thin.log.warning.mock_calls[0][1][0] % 'test'

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=False))
    def test_get_ext_tops_dependency_config_check(self):
        '''
        Test thin.get_ext_tops dependencies are importable

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': [2, 6],
                             'dependencies': {'jinja2': '/jinja/foo.py',
                                              'yaml': '/yaml/',
                                              'tornado': '/tornado/wrong.rb',
                                              'msgpack': 'msgpack.sh'}}}

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)

        self.assertIn('Missing dependencies for the alternative version in the '
                      'external configuration', str(err.value))

        messages = {}
        for cl in thin.log.warning.mock_calls:
            messages[cl[1][1]] = cl[1][0] % (cl[1][1], cl[1][2])
        for mod in ['tornado', 'yaml', 'msgpack']:
            self.assertIn('not a Python importable module', messages[mod])
        self.assertIn('configured with not a file or does not exist',
                      messages['jinja2'])

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.path.isfile', MagicMock(return_value=True))
    def test_get_ext_tops_config_pass(self):
        '''
        Test thin.get_ext_tops configuration

        :return:
        '''
        cfg = {'namespace': {'path': '/foo',
                             'py-version': [2, 6],
                             'dependencies': {'jinja2': '/jinja/foo.py',
                                              'yaml': '/yaml/',
                                              'tornado': '/tornado/tornado.py',
                                              'msgpack': 'msgpack.py'}}}
        out = thin.get_ext_tops(cfg)
        assert out['namespace']['py-version'] == cfg['namespace']['py-version']
        assert out['namespace']['path'] == cfg['namespace']['path']
        assert sorted(out['namespace']['dependencies']) == sorted(['/tornado/tornado.py',
                                                                   '/jinja/foo.py', '/yaml/', 'msgpack.py'])

    @patch('salt.utils.thin.sys.argv', [None, '{"foo": "bar"}'])
    @patch('salt.utils.thin.get_tops', lambda **kw: kw)
    def test_gte(self):
        '''
        Test thin.gte external call for processing the info about tops per interpreter.

        :return:
        '''
        assert json.loads(thin.gte()).get('foo') == 'bar'

    def test_add_dep_path(self):
        '''
        Test thin._add_dependency function to setup dependency paths
        :return:
        '''
        container = []
        for pth in ['/foo/bar.py', '/something/else/__init__.py']:
            thin._add_dependency(container, type(str('obj'), (), {'__file__': pth})())
        assert '__init__' not in container[1]
        assert container == ['/foo/bar.py', '/something/else']

    def test_thin_path(self):
        '''
        Test thin.thin_path returns the expected path.

        :return:
        '''
        path = os.sep + os.path.join('path', 'to')
        expected = os.path.join(path, 'thin', 'thin.tgz')
        self.assertEqual(thin.thin_path(path), expected)

    def test_get_salt_call_script(self):
        '''
        Test get salt-call script rendered.

        :return:
        '''
        out = thin._get_salt_call('foo', 'bar', py26=[2, 6], py27=[2, 7], py34=[3, 4])
        for line in salt.utils.stringutils.to_str(out).split(os.linesep):
            if line.startswith('namespaces = {'):
                data = json.loads(line.replace('namespaces = ', '').strip())
                assert data.get('py26') == [2, 6]
                assert data.get('py27') == [2, 7]
                assert data.get('py34') == [3, 4]
            if line.startswith('syspaths = '):
                data = json.loads(line.replace('syspaths = ', ''))
                assert data == ['foo', 'bar']

    def test_get_ext_namespaces_empty(self):
        '''
        Test thin._get_ext_namespaces function returns an empty dictionary on nothing
        :return:
        '''
        for obj in [None, {}, []]:
            assert thin._get_ext_namespaces(obj) == {}

    def test_get_ext_namespaces(self):
        '''
        Test thin._get_ext_namespaces function returns namespaces properly out of the config.
        :return:
        '''
        cfg = {'ns': {'py-version': [2, 7]}}
        assert thin._get_ext_namespaces(cfg).get('ns') == (2, 7,)
        assert isinstance(thin._get_ext_namespaces(cfg).get('ns'), tuple)

    def test_get_ext_namespaces_failure(self):
        '''
        Test thin._get_ext_namespaces function raises an exception
        if python major/minor version is not configured.
        :return:
        '''
        with pytest.raises(salt.exceptions.SaltSystemExit):
            thin._get_ext_namespaces({'ns': {}})

    @patch('salt.utils.thin.salt', type(str('salt'), (), {'__file__': '/site-packages/salt'}))
    @patch('salt.utils.thin.jinja2', type(str('jinja2'), (), {'__file__': '/site-packages/jinja2'}))
    @patch('salt.utils.thin.yaml', type(str('yaml'), (), {'__file__': '/site-packages/yaml'}))
    @patch('salt.utils.thin.tornado', type(str('tornado'), (), {'__file__': '/site-packages/tornado'}))
    @patch('salt.utils.thin.msgpack', type(str('msgpack'), (), {'__file__': '/site-packages/msgpack'}))
    @patch('salt.utils.thin.certifi', type(str('certifi'), (), {'__file__': '/site-packages/certifi'}))
    @patch('salt.utils.thin.singledispatch', type(str('singledispatch'), (), {'__file__': '/site-packages/sdp'}))
    @patch('salt.utils.thin.singledispatch_helpers', type(str('singledispatch_helpers'), (), {'__file__': '/site-packages/sdp_hlp'}))
    @patch('salt.utils.thin.ssl_match_hostname', type(str('ssl_match_hostname'), (), {'__file__': '/site-packages/ssl_mh'}))
    @patch('salt.utils.thin.markupsafe', type(str('markupsafe'), (), {'__file__': '/site-packages/markupsafe'}))
    @patch('salt.utils.thin.backports_abc', type(str('backports_abc'), (), {'__file__': '/site-packages/backports_abc'}))
    @patch('salt.utils.thin.concurrent', type(str('concurrent'), (), {'__file__': '/site-packages/concurrent'}))
    @patch('salt.utils.thin.log', MagicMock())
    def test_get_tops(self):
        '''
        Test thin.get_tops to get top directories, based on the interpreter.
        :return:
        '''
        base_tops = ['/site-packages/salt', '/site-packages/jinja2', '/site-packages/yaml',
                     '/site-packages/tornado', '/site-packages/msgpack', '/site-packages/certifi',
                     '/site-packages/sdp', '/site-packages/sdp_hlp', '/site-packages/ssl_mh',
                     '/site-packages/markupsafe', '/site-packages/backports_abc', '/site-packages/concurrent']

        tops = thin.get_tops()
        assert len(tops) == len(base_tops)
        assert sorted(tops) == sorted(base_tops)

    @patch('salt.utils.thin.salt', type(str('salt'), (), {'__file__': '/site-packages/salt'}))
    @patch('salt.utils.thin.jinja2', type(str('jinja2'), (), {'__file__': '/site-packages/jinja2'}))
    @patch('salt.utils.thin.yaml', type(str('yaml'), (), {'__file__': '/site-packages/yaml'}))
    @patch('salt.utils.thin.tornado', type(str('tornado'), (), {'__file__': '/site-packages/tornado'}))
    @patch('salt.utils.thin.msgpack', type(str('msgpack'), (), {'__file__': '/site-packages/msgpack'}))
    @patch('salt.utils.thin.certifi', type(str('certifi'), (), {'__file__': '/site-packages/certifi'}))
    @patch('salt.utils.thin.singledispatch', type(str('singledispatch'), (), {'__file__': '/site-packages/sdp'}))
    @patch('salt.utils.thin.singledispatch_helpers', type(str('singledispatch_helpers'), (), {'__file__': '/site-packages/sdp_hlp'}))
    @patch('salt.utils.thin.ssl_match_hostname', type(str('ssl_match_hostname'), (), {'__file__': '/site-packages/ssl_mh'}))
    @patch('salt.utils.thin.markupsafe', type(str('markupsafe'), (), {'__file__': '/site-packages/markupsafe'}))
    @patch('salt.utils.thin.backports_abc', type(str('backports_abc'), (), {'__file__': '/site-packages/backports_abc'}))
    @patch('salt.utils.thin.concurrent', type(str('concurrent'), (), {'__file__': '/site-packages/concurrent'}))
    @patch('salt.utils.thin.log', MagicMock())
    def test_get_tops_extra_mods(self):
        '''
        Test thin.get_tops to get extra-modules alongside the top directories, based on the interpreter.
        :return:
        '''
        base_tops = ['/site-packages/salt',
                     '/site-packages/jinja2',
                     '/site-packages/yaml',
                     '/site-packages/tornado',
                     '/site-packages/msgpack',
                     '/site-packages/certifi',
                     '/site-packages/sdp',
                     '/site-packages/sdp_hlp',
                     '/site-packages/ssl_mh',
                     '/site-packages/concurrent',
                     '/site-packages/markupsafe',
                     '/site-packages/backports_abc',
                     os.sep + os.path.join('custom', 'foo'),
                     os.sep + os.path.join('custom', 'bar.py')]
        builtins = sys.version_info.major == 3 and 'builtins' or '__builtin__'
        foo = {'__file__': os.sep + os.path.join('custom', 'foo', '__init__.py')}
        bar = {'__file__': os.sep + os.path.join('custom', 'bar')}
        with patch('{}.__import__'.format(builtins),
                   MagicMock(side_effect=[type(str('foo'), (), foo),
                                          type(str('bar'), (), bar)])):
            tops = thin.get_tops(extra_mods='foo,bar')
        self.assertEqual(len(tops), len(base_tops))
        self.assertListEqual(sorted(tops), sorted(base_tops))

    @patch('salt.utils.thin.salt', type(str('salt'), (), {'__file__': '/site-packages/salt'}))
    @patch('salt.utils.thin.jinja2', type(str('jinja2'), (), {'__file__': '/site-packages/jinja2'}))
    @patch('salt.utils.thin.yaml', type(str('yaml'), (), {'__file__': '/site-packages/yaml'}))
    @patch('salt.utils.thin.tornado', type(str('tornado'), (), {'__file__': '/site-packages/tornado'}))
    @patch('salt.utils.thin.msgpack', type(str('msgpack'), (), {'__file__': '/site-packages/msgpack'}))
    @patch('salt.utils.thin.certifi', type(str('certifi'), (), {'__file__': '/site-packages/certifi'}))
    @patch('salt.utils.thin.singledispatch', type(str('singledispatch'), (), {'__file__': '/site-packages/sdp'}))
    @patch('salt.utils.thin.singledispatch_helpers', type(str('singledispatch_helpers'), (), {'__file__': '/site-packages/sdp_hlp'}))
    @patch('salt.utils.thin.ssl_match_hostname', type(str('ssl_match_hostname'), (), {'__file__': '/site-packages/ssl_mh'}))
    @patch('salt.utils.thin.markupsafe', type(str('markupsafe'), (), {'__file__': '/site-packages/markupsafe'}))
    @patch('salt.utils.thin.backports_abc', type(str('backports_abc'), (), {'__file__': '/site-packages/backports_abc'}))
    @patch('salt.utils.thin.concurrent', type(str('concurrent'), (), {'__file__': '/site-packages/concurrent'}))
    @patch('salt.utils.thin.log', MagicMock())
    def test_get_tops_so_mods(self):
        '''
        Test thin.get_tops to get extra-modules alongside the top directories, based on the interpreter.
        :return:
        '''
        base_tops = ['/site-packages/salt', '/site-packages/jinja2', '/site-packages/yaml',
                     '/site-packages/tornado', '/site-packages/msgpack', '/site-packages/certifi',
                     '/site-packages/sdp', '/site-packages/sdp_hlp', '/site-packages/ssl_mh', '/site-packages/concurrent',
                     '/site-packages/markupsafe', '/site-packages/backports_abc', '/custom/foo.so', '/custom/bar.so']
        builtins = sys.version_info.major == 3 and 'builtins' or '__builtin__'
        with patch('{}.__import__'.format(builtins),
                   MagicMock(side_effect=[type(str('salt'), (), {'__file__': '/custom/foo.so'}),
                                          type(str('salt'), (), {'__file__': '/custom/bar.so'})])):
            tops = thin.get_tops(so_mods='foo,bar')
        assert len(tops) == len(base_tops)
        assert sorted(tops) == sorted(base_tops)

    @patch('salt.utils.thin.gen_thin', MagicMock(return_value='/path/to/thin/thin.tgz'))
    @patch('salt.utils.hashutils.get_hash', MagicMock(return_value=12345))
    def test_thin_sum(self):
        '''
        Test thin.thin_sum function.

        :return:
        '''
        assert thin.thin_sum('/cachedir', form='sha256')[1] == 12345
        thin.salt.utils.hashutils.get_hash.assert_called()
        assert thin.salt.utils.hashutils.get_hash.call_count == 1

        path, form = thin.salt.utils.hashutils.get_hash.call_args[0]
        assert path == '/path/to/thin/thin.tgz'
        assert form == 'sha256'

    @patch('salt.utils.thin.gen_min', MagicMock(return_value='/path/to/thin/min.tgz'))
    @patch('salt.utils.hashutils.get_hash', MagicMock(return_value=12345))
    def test_min_sum(self):
        '''
        Test thin.thin_sum function.

        :return:
        '''
        assert thin.min_sum('/cachedir', form='sha256') == 12345
        thin.salt.utils.hashutils.get_hash.assert_called()
        assert thin.salt.utils.hashutils.get_hash.call_count == 1

        path, form = thin.salt.utils.hashutils.get_hash.call_args[0]
        assert path == '/path/to/thin/min.tgz'
        assert form == 'sha256'

    @patch('salt.utils.thin.sys.version_info', (2, 5))
    @patch('salt.exceptions.SaltSystemExit', Exception)
    def test_gen_thin_fails_ancient_python_version(self):
        '''
        Test thin.gen_thin function raises an exception
        if Python major/minor version is lower than 2.6

        :return:
        '''
        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.sys.exc_clear = lambda: None
            thin.gen_thin('')
        self.assertIn('The minimum required python version to run salt-ssh is '
                      '"2.6"', str(err.value))

    @skipIf(salt.utils.platform.is_windows() and thin._six.PY2,
            'Dies on Python2 on Windows')
    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.os.makedirs', MagicMock())
    @patch('salt.utils.files.fopen', MagicMock())
    @patch('salt.utils.thin._get_salt_call', MagicMock())
    @patch('salt.utils.thin._get_ext_namespaces', MagicMock())
    @patch('salt.utils.thin.get_tops', MagicMock(return_value=['/foo3', '/bar3']))
    @patch('salt.utils.thin.get_ext_tops', MagicMock(return_value={}))
    @patch('salt.utils.thin.os.path.isfile', MagicMock())
    @patch('salt.utils.thin.os.path.isdir', MagicMock(return_value=True))
    @patch('salt.utils.thin.os.remove', MagicMock())
    @patch('salt.utils.thin.os.path.exists', MagicMock())
    @patch('salt.utils.path.os_walk', MagicMock(return_value=[]))
    @patch('salt.utils.thin.subprocess.Popen',
           _popen(None, side_effect=[(bts('2.7'), bts('')), (bts('["/foo27", "/bar27"]'), bts(''))]))
    @patch('salt.utils.thin.tarfile', MagicMock())
    @patch('salt.utils.thin.zipfile', MagicMock())
    @patch('salt.utils.thin.os.getcwd', MagicMock())
    @patch('salt.utils.thin.os.chdir', MagicMock())
    @patch('salt.utils.thin.tempfile.mkdtemp', MagicMock())
    @patch('salt.utils.thin.tempfile.mkstemp', MagicMock(return_value=(3, ".temporary")))
    @patch('salt.utils.thin.shutil', MagicMock())
    @patch('salt.utils.path.which', MagicMock(return_value=''))
    @patch('salt.utils.thin._get_thintar_prefix', MagicMock())
    def test_gen_thin_python_exist_or_not(self):
        '''
        Test thin.gen_thin function if the opposite python
        binary does not exist
        '''
        with TestsLoggingHandler() as handler:
            thin.gen_thin('')
            salt.utils.thin.subprocess.Popen.assert_not_called()

            if salt.ext.six.PY2:
                self.assertIn('DEBUG:python3 binary does not exist. Will not attempt to generate '
                              'tops for Python 3',
                              handler.messages)

            if salt.ext.six.PY3:
                self.assertIn('DEBUG:python2 binary does not exist. Will not '
                              'detect Python 2 version',
                              handler.messages)
                self.assertIn('DEBUG:python2 binary does not exist. Will not attempt to generate '
                              'tops for Python 2',
                              handler.messages)

    @skipIf(salt.utils.platform.is_windows() and thin._six.PY2,
            'Dies on Python2 on Windows')
    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.makedirs', MagicMock())
    @patch('salt.utils.files.fopen', MagicMock())
    @patch('salt.utils.thin._get_salt_call', MagicMock())
    @patch('salt.utils.thin._get_ext_namespaces', MagicMock())
    @patch('salt.utils.thin.get_tops', MagicMock(return_value=['/foo3', '/bar3']))
    @patch('salt.utils.thin.get_ext_tops', MagicMock(return_value={}))
    @patch('salt.utils.thin.os.path.isfile', MagicMock())
    @patch('salt.utils.thin.os.path.isdir', MagicMock(return_value=True))
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.remove', MagicMock())
    @patch('salt.utils.thin.os.path.exists', MagicMock())
    @patch('salt.utils.path.os_walk', MagicMock(return_value=[]))
    @patch('salt.utils.thin.subprocess.Popen',
           _popen(None, side_effect=[(bts('2.7'), bts('')), (bts('["/foo27", "/bar27"]'), bts(''))]))
    @patch('salt.utils.thin.tarfile', MagicMock())
    @patch('salt.utils.thin.zipfile', MagicMock())
    @patch('salt.utils.thin.os.getcwd', MagicMock())
    @patch('salt.utils.thin.os.chdir', MagicMock())
    @patch('salt.utils.thin.os.close', MagicMock())
    @patch('salt.utils.thin.tempfile.mkdtemp', MagicMock())
    @patch('salt.utils.thin.tempfile.mkstemp', MagicMock(return_value=(3, ".temporary")))
    @patch('salt.utils.thin.shutil', MagicMock())
    @patch('salt.utils.thin._six.PY3', True)
    @patch('salt.utils.thin._six.PY2', False)
    @patch('salt.utils.thin.sys.version_info', _version_info(None, 3, 6))
    @patch('salt.utils.path.which', MagicMock(return_value='/usr/bin/python'))
    def test_gen_thin_compression_fallback_py3(self):
        '''
        Test thin.gen_thin function if fallbacks to the gzip compression, once setup wrong.
        NOTE: Py2 version of this test is not required, as code shares the same spot across the versions.

        :return:
        '''
        thin.gen_thin('', compress='arj')
        thin.log.warning.assert_called()
        pt, msg = thin.log.warning.mock_calls[0][1]
        assert pt % msg == 'Unknown compression type: "arj". Falling back to "gzip" compression.'
        thin.zipfile.ZipFile.assert_not_called()
        thin.tarfile.open.assert_called()

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.makedirs', MagicMock())
    @patch('salt.utils.files.fopen', MagicMock())
    @patch('salt.utils.thin._get_salt_call', MagicMock())
    @patch('salt.utils.thin._get_ext_namespaces', MagicMock())
    @patch('salt.utils.thin.get_tops', MagicMock(return_value=['/foo3', '/bar3']))
    @patch('salt.utils.thin.get_ext_tops', MagicMock(return_value={}))
    @patch('salt.utils.thin.os.path.isfile', MagicMock())
    @patch('salt.utils.thin.os.path.isdir', MagicMock(return_value=False))
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.remove', MagicMock())
    @patch('salt.utils.thin.os.path.exists', MagicMock())
    @patch('salt.utils.path.os_walk', MagicMock(return_value=[]))
    @patch('salt.utils.thin.subprocess.Popen',
           _popen(None, side_effect=[(bts('2.7'), bts('')), (bts('["/foo27", "/bar27"]'), bts(''))]))
    @patch('salt.utils.thin.tarfile', MagicMock())
    @patch('salt.utils.thin.zipfile', MagicMock())
    @patch('salt.utils.thin.os.getcwd', MagicMock())
    @patch('salt.utils.thin.os.chdir', MagicMock())
    @patch('salt.utils.thin.os.close', MagicMock())
    @patch('salt.utils.thin.tempfile.mkdtemp', MagicMock(return_value=''))
    @patch('salt.utils.thin.tempfile.mkstemp', MagicMock(return_value=(3, ".temporary")))
    @patch('salt.utils.thin.shutil', MagicMock())
    @patch('salt.utils.thin._six.PY3', True)
    @patch('salt.utils.thin._six.PY2', False)
    @patch('salt.utils.thin.sys.version_info', _version_info(None, 3, 6))
    @patch('salt.utils.path.which', MagicMock(return_value='/usr/bin/python'))
    def test_gen_thin_control_files_written_py3(self):
        '''
        Test thin.gen_thin function if control files are written (version, salt-call etc).
        NOTE: Py2 version of this test is not required, as code shares the same spot across the versions.

        :return:
        '''
        thin.gen_thin('')
        arc_name, arc_mode = thin.tarfile.method_calls[0][1]
        self.assertEqual(arc_name, ".temporary")
        self.assertEqual(arc_mode, 'w:gz')
        for idx, fname in enumerate(['version', '.thin-gen-py-version', 'salt-call', 'supported-versions']):
            name = thin.tarfile.open().method_calls[idx + 4][1][0]
            self.assertEqual(name, fname)
        thin.tarfile.open().close.assert_called()

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.makedirs', MagicMock())
    @patch('salt.utils.files.fopen', MagicMock())
    @patch('salt.utils.thin._get_salt_call', MagicMock())
    @patch('salt.utils.thin._get_ext_namespaces', MagicMock())
    @patch('salt.utils.thin.get_tops', MagicMock(return_value=['/salt', '/bar3']))
    @patch('salt.utils.thin.get_ext_tops', MagicMock(return_value={}))
    @patch('salt.utils.thin.os.path.isfile', MagicMock())
    @patch('salt.utils.thin.os.path.isdir', MagicMock(return_value=True))
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.remove', MagicMock())
    @patch('salt.utils.thin.os.path.exists', MagicMock())
    @patch('salt.utils.path.os_walk',
           MagicMock(return_value=(('root', [], ['r1', 'r2', 'r3']), ('root2', [], ['r4', 'r5', 'r6']))))
    @patch('salt.utils.thin.subprocess.Popen',
           _popen(None, side_effect=[(bts('2.7'), bts('')), (bts('["/foo27", "/bar27"]'), bts(''))]))
    @patch('salt.utils.thin.tarfile', _tarfile(None))
    @patch('salt.utils.thin.zipfile', MagicMock())
    @patch('salt.utils.thin.os.getcwd', MagicMock())
    @patch('salt.utils.thin.os.chdir', MagicMock())
    @patch('salt.utils.thin.os.close', MagicMock())
    @patch('salt.utils.thin.tempfile.mkdtemp', MagicMock(return_value=''))
    @patch('salt.utils.thin.tempfile.mkstemp', MagicMock(return_value=(3, ".temporary")))
    @patch('salt.utils.thin.shutil', MagicMock())
    @patch('salt.utils.thin._six.PY3', True)
    @patch('salt.utils.thin._six.PY2', False)
    @patch('salt.utils.thin.sys.version_info', _version_info(None, 3, 6))
    @patch('salt.utils.hashutils.DigestCollector', MagicMock())
    @patch('salt.utils.path.which', MagicMock(return_value='/usr/bin/python'))
    def test_gen_thin_main_content_files_written_py3(self):
        '''
        Test thin.gen_thin function if main content files are written.
        NOTE: Py2 version of this test is not required, as code shares the same spot across the versions.

        :return:
        '''
        thin.gen_thin('')
        files = []
        for py in ('py2', 'py2', 'py3', 'pyall'):
            for i in range(1, 4):
                files.append(os.path.join(py, 'root', 'r{0}'.format(i)))
            for i in range(4, 7):
                files.append(os.path.join(py, 'root2', 'r{0}'.format(i)))
        for cl in thin.tarfile.open().method_calls[:-6]:
            arcname = cl[2].get('arcname')
            self.assertIn(arcname, files)
            files.pop(files.index(arcname))
        self.assertFalse(files)

    @patch('salt.exceptions.SaltSystemExit', Exception)
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.makedirs', MagicMock())
    @patch('salt.utils.files.fopen', MagicMock())
    @patch('salt.utils.thin._get_salt_call', MagicMock())
    @patch('salt.utils.thin._get_ext_namespaces', MagicMock())
    @patch('salt.utils.thin.get_tops', MagicMock(return_value=[]))
    @patch('salt.utils.thin.get_ext_tops',
           MagicMock(return_value={'namespace': {'py-version': [2, 7],
                                                 'path': '/opt/2015.8/salt',
                                                 'dependencies': ['/opt/certifi', '/opt/whatever']}}))
    @patch('salt.utils.thin.os.path.isfile', MagicMock())
    @patch('salt.utils.thin.os.path.isdir', MagicMock(return_value=True))
    @patch('salt.utils.thin.log', MagicMock())
    @patch('salt.utils.thin.os.remove', MagicMock())
    @patch('salt.utils.thin.os.path.exists', MagicMock())
    @patch('salt.utils.path.os_walk',
           MagicMock(return_value=(('root', [], ['r1', 'r2', 'r3']), ('root2', [], ['r4', 'r5', 'r6']))))
    @patch('salt.utils.thin.subprocess.Popen',
           _popen(None, side_effect=[(bts('2.7'), bts('')), (bts('["/foo27", "/bar27"]'), bts(''))]))
    @patch('salt.utils.thin.tarfile', _tarfile(None))
    @patch('salt.utils.thin.zipfile', MagicMock())
    @patch('salt.utils.thin.os.getcwd', MagicMock())
    @patch('salt.utils.thin.os.chdir', MagicMock())
    @patch('salt.utils.thin.os.close', MagicMock())
    @patch('salt.utils.thin.tempfile.mkdtemp', MagicMock(return_value=''))
    @patch('salt.utils.thin.tempfile.mkstemp', MagicMock(return_value=(3, ".temporary")))
    @patch('salt.utils.thin.shutil', MagicMock())
    @patch('salt.utils.thin._six.PY3', True)
    @patch('salt.utils.thin._six.PY2', False)
    @patch('salt.utils.thin.sys.version_info', _version_info(None, 3, 6))
    @patch('salt.utils.hashutils.DigestCollector', MagicMock())
    @patch('salt.utils.path.which', MagicMock(return_value='/usr/bin/python'))
    def test_gen_thin_ext_alternative_content_files_written_py3(self):
        '''
        Test thin.gen_thin function if external alternative content files are written.
        NOTE: Py2 version of this test is not required, as code shares the same spot across the versions.

        :return:
        '''
        thin.gen_thin('')
        files = []
        for py in ('pyall', 'pyall', 'py2'):
            for i in range(1, 4):
                files.append(
                    os.path.join('namespace', py, 'root', 'r{0}'.format(i)))
            for i in range(4, 7):
                files.append(
                    os.path.join('namespace', py, 'root2', 'r{0}'.format(i)))

        for idx, cl in enumerate(thin.tarfile.open().method_calls[12:-6]):
            arcname = cl[2].get('arcname')
            self.assertIn(arcname, files)
            files.pop(files.index(arcname))
        self.assertFalse(files)

    def test_get_supported_py_config_typecheck(self):
        '''
        Test collecting proper py-versions. Should return bytes type.
        :return:
        '''
        tops = {}
        ext_cfg = {}
        out = thin._get_supported_py_config(tops=tops, extended_cfg=ext_cfg)
        assert type(salt.utils.stringutils.to_bytes('')) == type(out)

    def test_get_supported_py_config_base_tops(self):
        '''
        Test collecting proper py-versions. Should return proper base tops.
        :return:
        '''
        tops = {'3': ['/groundkeepers', '/stole'], '2': ['/the-root', '/password']}
        ext_cfg = {}
        out = salt.utils.stringutils.to_str(thin._get_supported_py_config(
            tops=tops, extended_cfg=ext_cfg)).strip().split(os.linesep)
        self.assertEqual(len(out), 2)
        for t_line in ['py3:3:0', 'py2:2:7']:
            self.assertIn(t_line, out)

    def test_get_supported_py_config_ext_tops(self):
        '''
        Test collecting proper py-versions. Should return proper ext conf tops.
        :return:
        '''
        tops = {}
        ext_cfg = {
            'solar-interference': {
                'py-version': [2, 6]},
            'second-system-effect': {
                'py-version': [2, 7]}}
        out = salt.utils.stringutils.to_str(thin._get_supported_py_config(
            tops=tops, extended_cfg=ext_cfg)).strip().split(os.linesep)
        for t_line in ['second-system-effect:2:7', 'solar-interference:2:6']:
            self.assertIn(t_line, out)
