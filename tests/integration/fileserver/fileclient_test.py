# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import errno
import logging
import os
import shutil

log = logging.getLogger(__name__)

# Import Salt Testing libs
from salttesting.unit import skipIf
from salttesting.helpers import ensure_in_syspath, destructiveTest
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
ensure_in_syspath('../..')

# Import salt libs
import integration
import salt.utils
from salt import fileclient
from salt.ext import six

SALTENVS = ('base', 'dev')
FS_ROOT = os.path.join(integration.TMP, 'fileclient_fs_root')
CACHE_ROOT = os.path.join(integration.TMP, 'fileclient_cache_root')
SUBDIR = 'subdir'
SUBDIR_FILES = ('foo.txt', 'bar.txt', 'baz.txt')


def _get_file_roots():
    return dict(
        [(x, [os.path.join(FS_ROOT, x)]) for x in SALTENVS]
    )


fileclient.__opts__ = {}
MOCKED_OPTS = {
    'file_roots': _get_file_roots(),
    'fileserver_backend': ['roots'],
    'cachedir': CACHE_ROOT,
    'file_client': 'local',
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FileClientTest(integration.ModuleCase):

    def setUp(self):
        self.file_client = fileclient.Client(self.master_opts)

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
        with patch.dict(self.get_config('minion', from_scratch=True), {'file_client': 'remote'}):
            with patch('salt.fileclient.RemoteClient', MagicMock(return_value='remote_client')):
                ret = fileclient.get_file_client(self.minion_opts)
                self.assertEqual('remote_client', ret)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@destructiveTest
class FileclientCacheTest(integration.ModuleCase):
    '''
    Tests for the fileclient caching. The LocalClient is the only thing we can
    test as it is the only way we can mock the fileclient (the tests run from
    the minion process, so the master cannot be mocked from test code).
    '''

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
            saltenv_root = os.path.join(FS_ROOT, saltenv)
            # Make sure we have a fresh root dir for this saltenv
            _new_dir(saltenv_root)

            path = os.path.join(saltenv_root, 'foo.txt')
            with salt.utils.fopen(path, 'w') as fp_:
                fp_.write(
                    'This is a test file in the \'{0}\' saltenv.\n'
                    .format(saltenv)
                )

            subdir_abspath = os.path.join(saltenv_root, SUBDIR)
            os.makedirs(subdir_abspath)
            for subdir_file in SUBDIR_FILES:
                path = os.path.join(subdir_abspath, subdir_file)
                with salt.utils.fopen(path, 'w') as fp_:
                    fp_.write(
                        'This is file \'{0}\' in subdir \'{1} from saltenv '
                        '\'{2}\''.format(subdir_file, SUBDIR, saltenv)
                    )

        # Create the CACHE_ROOT
        _new_dir(CACHE_ROOT)

    def tearDown(self):
        '''
        Remove the directories created for these tests
        '''
        shutil.rmtree(FS_ROOT)
        shutil.rmtree(CACHE_ROOT)

    def test_cache_dir(self):
        '''
        Ensure entire directory is cached to correct location
        '''
        patched_opts = dict((x, y) for x, y in six.iteritems(self.minion_opts))
        patched_opts.update(MOCKED_OPTS)

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
                    with salt.utils.fopen(cache_loc) as fp_:
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
        patched_opts.update(MOCKED_OPTS)
        alt_cachedir = os.path.join(integration.TMP, 'abs_cachedir')

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
                    with salt.utils.fopen(cache_loc) as fp_:
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
        patched_opts.update(MOCKED_OPTS)
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
                    with salt.utils.fopen(cache_loc) as fp_:
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
        patched_opts.update(MOCKED_OPTS)

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
                with salt.utils.fopen(cache_loc) as fp_:
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
        patched_opts.update(MOCKED_OPTS)
        alt_cachedir = os.path.join(integration.TMP, 'abs_cachedir')

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
                with salt.utils.fopen(cache_loc) as fp_:
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
        patched_opts.update(MOCKED_OPTS)
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
                with salt.utils.fopen(cache_loc) as fp_:
                    content = fp_.read()
                log.debug('cache_loc = %s', cache_loc)
                log.debug('content = %s', content)
                self.assertTrue(saltenv in content)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileClientTest)
