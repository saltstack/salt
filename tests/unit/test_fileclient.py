# -*- coding: utf-8 -*-
'''
Tests for the salt fileclient
'''

# Import Python libs
from __future__ import absolute_import
import errno
import logging
import os
import shutil

# Import Salt Testing libs
from tests.support.mixins import AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin
from tests.support.mock import patch, Mock, MagicMock, NO_MOCK, NO_MOCK_REASON
from tests.support.unit import TestCase, skipIf
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.files
from salt.ext.six.moves import range
from salt import fileclient
from salt.ext import six

log = logging.getLogger(__name__)


class FileclientTestCase(TestCase):
    '''
    Fileclient test
    '''
    opts = {
        'extension_modules': '',
        'cachedir': '/__test__',
    }

    def _fake_makedir(self, num=errno.EEXIST):
        def _side_effect(*args, **kwargs):
            raise OSError(num, 'Errno {0}'.format(num))
        return Mock(side_effect=_side_effect)

    def test_cache_skips_makedirs_on_race_condition(self):
        '''
        If cache contains already a directory, do not raise an exception.
        '''
        with patch('os.path.isfile', lambda prm: False):
            for exists in range(2):
                with patch('os.makedirs', self._fake_makedir()):
                    with fileclient.Client(self.opts)._cache_loc('testfile') as c_ref_itr:
                        assert c_ref_itr == os.sep + os.sep.join(['__test__', 'files', 'base', 'testfile'])

    def test_cache_raises_exception_on_non_eexist_ioerror(self):
        '''
        If makedirs raises other than EEXIST errno, an exception should be raised.
        '''
        with patch('os.path.isfile', lambda prm: False):
            with patch('os.makedirs', self._fake_makedir(num=errno.EROFS)):
                with self.assertRaises(OSError):
                    with fileclient.Client(self.opts)._cache_loc('testfile') as c_ref_itr:
                        assert c_ref_itr == '/__test__/files/base/testfile'

    def test_extrn_path_with_long_filename(self):
        safe_file_name = os.path.split(fileclient.Client(self.opts)._extrn_path('https://test.com/' + ('A' * 254), 'base'))[-1]
        assert safe_file_name == 'A' * 254

        oversized_file_name = os.path.split(fileclient.Client(self.opts)._extrn_path('https://test.com/' + ('A' * 255), 'base'))[-1]
        assert len(oversized_file_name) < 256
        assert oversized_file_name != 'A' * 255

        oversized_file_with_query_params = os.path.split(fileclient.Client(self.opts)._extrn_path('https://test.com/file?' + ('A' * 255), 'base'))[-1]
        assert len(oversized_file_with_query_params) < 256


SALTENVS = ('base', 'dev')
SUBDIR = 'subdir'
SUBDIR_FILES = ('foo.txt', 'bar.txt', 'baz.txt')


def _get_file_roots(fs_root):
    return dict(
        [(x, [os.path.join(fs_root, x)]) for x in SALTENVS]
    )


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FileClientTest(TestCase, AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        FS_ROOT = os.path.join(RUNTIME_VARS.TMP, 'fileclient_fs_root')
        CACHE_ROOT = os.path.join(RUNTIME_VARS.TMP, 'fileclient_cache_root')
        MOCKED_OPTS = {
            'file_roots': _get_file_roots(FS_ROOT),
            'fileserver_backend': ['roots'],
            'cachedir': CACHE_ROOT,
            'file_client': 'local',
        }
        self.addCleanup(shutil.rmtree, FS_ROOT, ignore_errors=True)
        self.addCleanup(shutil.rmtree, CACHE_ROOT, ignore_errors=True)
        return {fileclient: {'__opts__': MOCKED_OPTS}}

    def setUp(self):
        self.file_client = fileclient.Client(self.master_opts)

    def tearDown(self):
        del self.file_client

    def test_file_list_emptydirs(self):
        '''
        Ensure that the fileclient class won't allow a direct call to file_list_emptydirs()
        '''
        with self.assertRaises(NotImplementedError):
            self.file_client.file_list_emptydirs()

    def test_get_file(self):
        '''
        Ensure that the fileclient class won't allow a direct call to get_file()
        '''
        with self.assertRaises(NotImplementedError):
            self.file_client.get_file(None)

    def test_get_file_client(self):
        minion_opts = self.get_temp_config('minion')
        minion_opts['file_client'] = 'remote'
        with patch('salt.fileclient.RemoteClient', MagicMock(return_value='remote_client')):
            ret = fileclient.get_file_client(minion_opts)
            self.assertEqual('remote_client', ret)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FileclientCacheTest(TestCase, AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin):
    '''
    Tests for the fileclient caching. The LocalClient is the only thing we can
    test as it is the only way we can mock the fileclient (the tests run from
    the minion process, so the master cannot be mocked from test code).
    '''

    def setup_loader_modules(self):
        self.FS_ROOT = os.path.join(RUNTIME_VARS.TMP, 'fileclient_fs_root')
        self.CACHE_ROOT = os.path.join(RUNTIME_VARS.TMP, 'fileclient_cache_root')
        self.MOCKED_OPTS = {
            'file_roots': _get_file_roots(self.FS_ROOT),
            'fileserver_backend': ['roots'],
            'cachedir': self.CACHE_ROOT,
            'file_client': 'local',
        }
        self.addCleanup(shutil.rmtree, self.FS_ROOT, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.CACHE_ROOT, ignore_errors=True)
        return {fileclient: {'__opts__': self.MOCKED_OPTS}}

    def setUp(self):
        '''
        No need to add a dummy foo.txt to muddy up the github repo, just make
        our own fileserver root on-the-fly.
        '''
        def _new_dir(path):
            '''
            Add a new dir at ``path`` using os.makedirs. If the directory
            already exists, remove it recursively and then try to create it
            again.
            '''
            try:
                os.makedirs(path)
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    # Just in case a previous test was interrupted, remove the
                    # directory and try adding it again.
                    shutil.rmtree(path)
                    os.makedirs(path)
                else:
                    raise

        # Crete the FS_ROOT
        for saltenv in SALTENVS:
            saltenv_root = os.path.join(self.FS_ROOT, saltenv)
            # Make sure we have a fresh root dir for this saltenv
            _new_dir(saltenv_root)

            path = os.path.join(saltenv_root, 'foo.txt')
            with salt.utils.files.fopen(path, 'w') as fp_:
                fp_.write(
                    'This is a test file in the \'{0}\' saltenv.\n'
                    .format(saltenv)
                )

            subdir_abspath = os.path.join(saltenv_root, SUBDIR)
            os.makedirs(subdir_abspath)
            for subdir_file in SUBDIR_FILES:
                path = os.path.join(subdir_abspath, subdir_file)
                with salt.utils.files.fopen(path, 'w') as fp_:
                    fp_.write(
                        'This is file \'{0}\' in subdir \'{1} from saltenv '
                        '\'{2}\''.format(subdir_file, SUBDIR, saltenv)
                    )

        # Create the CACHE_ROOT
        _new_dir(self.CACHE_ROOT)

    def test_cache_dir(self):
        '''
        Ensure entire directory is cached to correct location
        '''
        patched_opts = dict((x, y) for x, y in six.iteritems(self.minion_opts))
        patched_opts.update(self.MOCKED_OPTS)

        with patch.dict(fileclient.__opts__, patched_opts):
            client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
            for saltenv in SALTENVS:
                self.assertTrue(
                    client.cache_dir(
                        'salt://{0}'.format(SUBDIR),
                        saltenv,
                        cachedir=None
                    )
                )
                for subdir_file in SUBDIR_FILES:
                    cache_loc = os.path.join(fileclient.__opts__['cachedir'],
                                             'files',
                                             saltenv,
                                             SUBDIR,
                                             subdir_file)
                    # Double check that the content of the cached file
                    # identifies it as being from the correct saltenv. The
                    # setUp function creates the file with the name of the
                    # saltenv mentioned in the file, so a simple 'in' check is
                    # sufficient here. If opening the file raises an exception,
                    # this is a problem, so we are not catching the exception
                    # and letting it be raised so that the test fails.
                    with salt.utils.files.fopen(cache_loc) as fp_:
                        content = fp_.read()
                    log.debug('cache_loc = %s', cache_loc)
                    log.debug('content = %s', content)
                    self.assertTrue(subdir_file in content)
                    self.assertTrue(SUBDIR in content)
                    self.assertTrue(saltenv in content)

    def test_cache_dir_with_alternate_cachedir_and_absolute_path(self):
        '''
        Ensure entire directory is cached to correct location when an alternate
        cachedir is specified and that cachedir is an absolute path
        '''
        patched_opts = dict((x, y) for x, y in six.iteritems(self.minion_opts))
        patched_opts.update(self.MOCKED_OPTS)
        alt_cachedir = os.path.join(RUNTIME_VARS.TMP, 'abs_cachedir')

        with patch.dict(fileclient.__opts__, patched_opts):
            client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
            for saltenv in SALTENVS:
                self.assertTrue(
                    client.cache_dir(
                        'salt://{0}'.format(SUBDIR),
                        saltenv,
                        cachedir=alt_cachedir
                    )
                )
                for subdir_file in SUBDIR_FILES:
                    cache_loc = os.path.join(alt_cachedir,
                                             'files',
                                             saltenv,
                                             SUBDIR,
                                             subdir_file)
                    # Double check that the content of the cached file
                    # identifies it as being from the correct saltenv. The
                    # setUp function creates the file with the name of the
                    # saltenv mentioned in the file, so a simple 'in' check is
                    # sufficient here. If opening the file raises an exception,
                    # this is a problem, so we are not catching the exception
                    # and letting it be raised so that the test fails.
                    with salt.utils.files.fopen(cache_loc) as fp_:
                        content = fp_.read()
                    log.debug('cache_loc = %s', cache_loc)
                    log.debug('content = %s', content)
                    self.assertTrue(subdir_file in content)
                    self.assertTrue(SUBDIR in content)
                    self.assertTrue(saltenv in content)

    def test_cache_dir_with_alternate_cachedir_and_relative_path(self):
        '''
        Ensure entire directory is cached to correct location when an alternate
        cachedir is specified and that cachedir is a relative path
        '''
        patched_opts = dict((x, y) for x, y in six.iteritems(self.minion_opts))
        patched_opts.update(self.MOCKED_OPTS)
        alt_cachedir = 'foo'

        with patch.dict(fileclient.__opts__, patched_opts):
            client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
            for saltenv in SALTENVS:
                self.assertTrue(
                    client.cache_dir(
                        'salt://{0}'.format(SUBDIR),
                        saltenv,
                        cachedir=alt_cachedir
                    )
                )
                for subdir_file in SUBDIR_FILES:
                    cache_loc = os.path.join(fileclient.__opts__['cachedir'],
                                             alt_cachedir,
                                             'files',
                                             saltenv,
                                             SUBDIR,
                                             subdir_file)
                    # Double check that the content of the cached file
                    # identifies it as being from the correct saltenv. The
                    # setUp function creates the file with the name of the
                    # saltenv mentioned in the file, so a simple 'in' check is
                    # sufficient here. If opening the file raises an exception,
                    # this is a problem, so we are not catching the exception
                    # and letting it be raised so that the test fails.
                    with salt.utils.files.fopen(cache_loc) as fp_:
                        content = fp_.read()
                    log.debug('cache_loc = %s', cache_loc)
                    log.debug('content = %s', content)
                    self.assertTrue(subdir_file in content)
                    self.assertTrue(SUBDIR in content)
                    self.assertTrue(saltenv in content)

    def test_cache_file(self):
        '''
        Ensure file is cached to correct location
        '''
        patched_opts = dict((x, y) for x, y in six.iteritems(self.minion_opts))
        patched_opts.update(self.MOCKED_OPTS)

        with patch.dict(fileclient.__opts__, patched_opts):
            client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
            for saltenv in SALTENVS:
                self.assertTrue(
                    client.cache_file('salt://foo.txt', saltenv, cachedir=None)
                )
                cache_loc = os.path.join(
                    fileclient.__opts__['cachedir'], 'files', saltenv, 'foo.txt')
                # Double check that the content of the cached file identifies
                # it as being from the correct saltenv. The setUp function
                # creates the file with the name of the saltenv mentioned in
                # the file, so a simple 'in' check is sufficient here. If
                # opening the file raises an exception, this is a problem, so
                # we are not catching the exception and letting it be raised so
                # that the test fails.
                with salt.utils.files.fopen(cache_loc) as fp_:
                    content = fp_.read()
                log.debug('cache_loc = %s', cache_loc)
                log.debug('content = %s', content)
                self.assertTrue(saltenv in content)

    def test_cache_file_with_alternate_cachedir_and_absolute_path(self):
        '''
        Ensure file is cached to correct location when an alternate cachedir is
        specified and that cachedir is an absolute path
        '''
        patched_opts = dict((x, y) for x, y in six.iteritems(self.minion_opts))
        patched_opts.update(self.MOCKED_OPTS)
        alt_cachedir = os.path.join(RUNTIME_VARS.TMP, 'abs_cachedir')

        with patch.dict(fileclient.__opts__, patched_opts):
            client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
            for saltenv in SALTENVS:
                self.assertTrue(
                    client.cache_file('salt://foo.txt',
                                      saltenv,
                                      cachedir=alt_cachedir)
                )
                cache_loc = os.path.join(alt_cachedir,
                                         'files',
                                         saltenv,
                                         'foo.txt')
                # Double check that the content of the cached file identifies
                # it as being from the correct saltenv. The setUp function
                # creates the file with the name of the saltenv mentioned in
                # the file, so a simple 'in' check is sufficient here. If
                # opening the file raises an exception, this is a problem, so
                # we are not catching the exception and letting it be raised so
                # that the test fails.
                with salt.utils.files.fopen(cache_loc) as fp_:
                    content = fp_.read()
                log.debug('cache_loc = %s', cache_loc)
                log.debug('content = %s', content)
                self.assertTrue(saltenv in content)

    def test_cache_file_with_alternate_cachedir_and_relative_path(self):
        '''
        Ensure file is cached to correct location when an alternate cachedir is
        specified and that cachedir is a relative path
        '''
        patched_opts = dict((x, y) for x, y in six.iteritems(self.minion_opts))
        patched_opts.update(self.MOCKED_OPTS)
        alt_cachedir = 'foo'

        with patch.dict(fileclient.__opts__, patched_opts):
            client = fileclient.get_file_client(fileclient.__opts__, pillar=False)
            for saltenv in SALTENVS:
                self.assertTrue(
                    client.cache_file('salt://foo.txt',
                                      saltenv,
                                      cachedir=alt_cachedir)
                )
                cache_loc = os.path.join(fileclient.__opts__['cachedir'],
                                         alt_cachedir,
                                         'files',
                                         saltenv,
                                         'foo.txt')
                # Double check that the content of the cached file identifies
                # it as being from the correct saltenv. The setUp function
                # creates the file with the name of the saltenv mentioned in
                # the file, so a simple 'in' check is sufficient here. If
                # opening the file raises an exception, this is a problem, so
                # we are not catching the exception and letting it be raised so
                # that the test fails.
                with salt.utils.files.fopen(cache_loc) as fp_:
                    content = fp_.read()
                log.debug('cache_loc = %s', cache_loc)
                log.debug('content = %s', content)
                self.assertTrue(saltenv in content)
