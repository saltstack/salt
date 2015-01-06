# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`jmoney <justin@saltstack.com>`
'''

# Import Salt Libs
from salt.modules import cp
from salt.utils import templates
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    mock_open,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Globals
cp.__salt__ = {}
cp.__opts__ = {}
cp.__pillar__ = {}
cp.__grains__ = {}
cp.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CpTestCase(TestCase):
    '''
    TestCase for salt.modules.cp module
    '''

    @patch('os.path.isdir', MagicMock(return_value=False))
    def test_recv_return_unavailable(self):
        '''
        Test if recv returns unavailable.
        '''
        files = {'saltines': '/srv/salt/saltines',
                 'biscuits': '/srv/salt/biscuits'}
        dest = '/srv/salt/cheese'
        self.assertEqual(cp.recv(files, dest), 'Destination unavailable')

    @patch('os.path.isdir', MagicMock(return_value=True))
    def test_recv_return_success(self):
        '''
        Test if recv returns success.
        '''
        files = {'saltines': 'salt://saltines',
                 'biscuits': 'salt://biscuits'}
        ret = {'/srv/salt/cheese/saltines': True,
               '/srv/salt/cheese/biscuits': True}
        dest = '/srv/salt/cheese'
        file_data = 'Remember to keep your files well salted.'
        with patch('salt.utils.fopen', mock_open(read_data=file_data)):
            self.assertEqual(cp.recv(files, dest), ret)

    def test__render_filenames_undefined_template(self):
        '''
        Test if _render_filenames fails upon getting a template not in
        TEMPLATE_REGISTRY.
        '''
        path = '/srv/salt/saltines'
        dest = '/srv/salt/cheese'
        saltenv = 'base'
        template = 'biscuits'
        ret = (path, dest)
        self.assertRaises(CommandExecutionError,
                          cp._render_filenames,
                          path, dest, saltenv, template)

    def test__render_filenames_render_failed(self):
        '''
        Test if _render_filenames fails when template rendering fails.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        saltenv = 'base'
        template = 'jinja'
        file_data = 'Remember to keep your files well salted.'
        mock_jinja = lambda *args, **kwargs: {'result': False,
                                              'data': file_data}
        with patch.dict(templates.TEMPLATE_REGISTRY,
                        {'jinja': mock_jinja}):
            with patch('salt.utils.fopen', mock_open(read_data=file_data)):
                self.assertRaises(CommandExecutionError,
                                  cp._render_filenames,
                                  path, dest, saltenv, template)

    def test__render_filenames_success(self):
        '''
        Test if _render_filenames succeeds.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        saltenv = 'base'
        template = 'jinja'
        file_data = '/srv/salt/biscuits'
        mock_jinja = lambda *args, **kwargs: {'result': True,
                                              'data': file_data}
        ret = (file_data, file_data)  # salt.utils.fopen can only be mocked once
        with patch.dict(templates.TEMPLATE_REGISTRY,
                        {'jinja': mock_jinja}):
            with patch('salt.utils.fopen', mock_open(read_data=file_data)):
                self.assertEqual(cp._render_filenames(
                                 path, dest, saltenv, template), ret)

    @patch('salt.modules.cp.hash_file', MagicMock(return_value=False))
    def test_get_file_not_found(self):
        '''
        Test if get_file can't find the file.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        ret = ''
        self.assertEqual(cp.get_file(path, dest), ret)

    @patch('salt.modules.cp.hash_file', MagicMock(return_value=True))
    def test_get_file_success(self):
        '''
        Test if get_file succeeds.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        saltenv = 'base'
        ret = (path, dest, False, saltenv, None)

        class MockFileClient(object):
            def get_file(self, *args):
                return args

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.get_file(path, dest), ret)

    def test_get_template_success(self):
        '''
        Test if get_template succeeds.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        template = 'jinja'
        saltenv = 'base'
        ret = ((path, dest, template, False, saltenv),
               {'grains': {}, 'opts': {}, 'pillar': {}, 'salt': {}})

        class MockFileClient(object):
            def get_template(self, *args, **kwargs):
                return args, kwargs

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.get_template(path, dest), ret)

    def test_get_dir_success(self):
        '''
        Test if get_template succeeds.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        saltenv = 'base'
        ret = (path, dest, saltenv, None)

        class MockFileClient(object):
            def get_dir(self, *args):
                return args

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            with patch('salt.modules.cp._render_filenames',
                       MagicMock(return_value=(path, dest))):
                self.assertEqual(cp.get_dir(path, dest), ret)

    def test_get_url_success(self):
        '''
        Test if get_url succeeds.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese'
        saltenv = 'base'
        ret = (path, dest, False, saltenv)

        class MockFileClient(object):
            def get_url(self, *args):
                return args

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.get_url(path, dest), ret)

    def test_get_file_str_success(self):
        '''
        Test if get_file_str succeeds.
        '''
        path = 'salt://saltines'
        dest = '/srv/salt/cheese/saltines'
        file_data = 'Remember to keep your files well salted.'
        saltenv = 'base'
        ret = file_data
        with patch('salt.utils.fopen', mock_open(read_data=file_data)):
            with patch('salt.modules.cp.cache_file',
                       MagicMock(return_value=dest)):
                self.assertEqual(cp.get_file_str(path, dest), ret)

    def test_cache_file_success(self):
        '''
        Test if cache_file succeeds.
        '''
        path = 'salt://saltines'
        saltenv = 'base'
        ret = path

        class MockFileClient(object):
            def cache_file(self, path, saltenv):
                return path

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.cache_file(path), ret)

    def test_cache_files_success(self):
        '''
        Test if cache_files succeeds.
        '''
        paths = ['salt://saltines', 'salt://biscuits']
        saltenv = 'base'
        ret = paths

        class MockFileClient(object):
            def cache_files(self, paths, saltenv):
                return paths

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.cache_files(paths), ret)

    def test_cache_dir_success(self):
        '''
        Test if cache_dir succeeds.
        '''
        path = 'saltk//cheese'
        files = ['/srv/salt/cheese/saltines', '/srv/salt/cheese/biscuits']
        saltenv = 'base'
        ret = files

        class MockFileClient(object):
            def cache_dir(self, *args):
                return files

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.cache_dir(files), ret)

    def test_cache_master_success(self):
        '''
        Test if cache_master succeeds.
        '''
        path = 'saltk//cheese'
        files = ['/srv/salt/cheese/saltines', '/srv/salt/cheese/biscuits']
        saltenv = 'base'
        ret = files

        class MockFileClient(object):
            def cache_master(self, saltenv):
                return files

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.cache_master(), ret)

    @patch('os.path.exists', MagicMock(return_value=False))
    def test_cache_local_file_not_exists(self):
        '''
        Test if cache_local_file handles a nonexistent file.
        '''
        path = 'saltk//saltines'
        ret = ''

        self.assertEqual(cp.cache_local_file(path), ret)

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_cache_local_file_already_cached(self):
        '''
        Test if cache_local_file handles an already cached file.
        '''
        path = 'saltk//saltines'
        dest_file = '/srv/salt/cheese/saltines'
        mock_hash = {'hsum': 'deadbeef'}
        ret = dest_file

        with patch('salt.modules.cp.hash_file',
                   MagicMock(return_value=mock_hash)):
            with patch('salt.modules.cp.is_cached',
                       MagicMock(return_value=dest_file)):
                self.assertEqual(cp.cache_local_file(path), ret)

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_cache_local_file_success(self):
        '''
        Test if cache_local_file succeeds.
        '''
        path = 'saltk//saltines'
        dest_file = '/srv/salt/cheese/saltines'
        ret = dest_file

        class MockFileClient(object):
            def cache_local_file(self, path):
                return dest_file

        mock_file_client = MockFileClient()
        with patch('salt.modules.cp.is_cached',
                   MagicMock(return_value=False)):
            with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
                self.assertEqual(cp.cache_local_file(path), ret)

    def test_list_states_success(self):
        '''
        Test if list_states succeeds.
        '''
        states = ['cheesse.saltines', 'cheese.biscuits']
        ret = states

        class MockFileClient(object):
            def list_states(self, saltenv):
                return states

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.list_states(), ret)

    def test_list_master_success(self):
        '''
        Test if list_master succeeds.
        '''
        files = ['cheesse/saltines.sls', 'cheese/biscuits.sls']
        ret = files

        class MockFileClient(object):
            def file_list(self, saltenv, prefix):
                return files

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.list_master(), ret)

    def test_list_master_dirs_success(self):
        '''
        Test if list_master_dirs succeeds.
        '''
        dirs = ['cheesse', 'gravy']
        ret = dirs

        class MockFileClient(object):
            def dir_list(self, saltenv, prefix):
                return dirs

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.list_master_dirs(), ret)

    def test_list_master_symlinks_success(self):
        '''
        Test if list_master_symlinks succeeds.
        '''
        symlinks = ['american_cheesse', 'vegan_gravy']
        ret = symlinks

        class MockFileClient(object):
            def symlink_list(self, saltenv, prefix):
                return symlinks

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.list_master_symlinks(), ret)

    def test_is_cached_success(self):
        '''
        Test if is_cached succeeds.
        '''
        path = 'salt://saltines'
        ret = path

        class MockFileClient(object):
            def is_cached(self, path, saltenv):
                return path

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            self.assertEqual(cp.is_cached(path), ret)

    def test_hash_file_success(self):
        '''
        Test if hash_file succeeds.
        '''
        path = 'salt://saltines'
        mock_hash = {'hsum': 'deadbeef', 'htype': 'sha65536'}
        ret = mock_hash

        class MockFileClient(object):
            def hash_file(self, path, saltenv):
                return mock_hash

        mock_file_client = MockFileClient()
        with patch.dict(cp.__context__, {'cp.fileclient': mock_file_client}):
            with patch('salt.modules.cp.hash_file',
                       MagicMock(return_value=mock_hash)):
                self.assertEqual(cp.hash_file(path), ret)

    def test_push_non_absolute_path(self):
        '''
        Test if push fails on a non absolute path.
        '''
        path = '../saltines'
        ret = False

        self.assertEqual(cp.push(path), ret)

    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_push_non_file(self):
        '''
        Test if push fails on a non file.
        '''
        path = '/srv/salt/saltines'
        ret = False

        self.assertEqual(cp.push(path), ret)

    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_push_failed(self):
        '''
        Test if push fails.
        '''
        path = '/srv/salt/saltines'
        file_data = 'Remember to keep your files well salted.'
        mock_buf_size = len(file_data)
        mock_id = 'You don\'t need to see his identification.'
        ret = None

        class MockChannel(object):
            @staticmethod
            def factory(__opts__):
                return MockChannel()

            def send(self, load):
                return None

        class MockAuth(object):
            def gen_token(self, salt):
                return 'token info'

        def mock_auth_factory():
            return MockAuth()

        with patch('salt.transport.Channel', MockChannel):
            with patch('salt.modules.cp._auth', mock_auth_factory):
                with patch('salt.utils.fopen', mock_open(read_data=file_data)):
                    with patch.dict(cp.__opts__,
                                    {'file_buffer_size': mock_buf_size,
                                     'id': mock_id}):
                        self.assertEqual(cp.push(path), ret)

    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_push_success(self):
        '''
        Test if push succeeds.
        '''
        path = '/srv/salt/saltines'
        file_data = ''
        mock_buf_size = len(file_data)
        mock_id = 'You don\'t need to see his identification.'
        ret = True

        class MockChannel(object):
            @staticmethod
            def factory(__opts__):
                return MockChannel()

            def send(self, load):
                return 'channel info'

        class MockAuth(object):
            def gen_token(self, salt):
                return 'token info'

        def mock_auth_factory():
            return MockAuth()

        with patch('salt.transport.Channel', MockChannel):
            with patch('salt.modules.cp._auth', mock_auth_factory):
                with patch('salt.utils.fopen', mock_open(read_data=file_data)):
                    with patch.dict(cp.__opts__,
                                    {'file_buffer_size': mock_buf_size,
                                     'id': mock_id}):
                        self.assertEqual(cp.push(path), ret)

    def test_push_dir_non_absolute_path(self):
        '''
        Test if push_dir fails on a non absolute path.
        '''
        path = '../saltines'
        ret = False

        self.assertEqual(cp.push_dir(path), ret)

    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_push_dir_file_success(self):
        '''
        Test if push_dir succeeds on a file.
        '''
        path = '/srv/salt/saltines'
        ret = True

        with patch('salt.modules.cp.push', MagicMock(return_value=True)):
            self.assertEqual(cp.push_dir(path), ret)

    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_push_dir_success(self):
        '''
        Test if push_dir succeeds on a file.
        '''
        path = '/srv/salt/cheese'
        # The tuple must be enclosed within another tuple since Mock/MagicMock
        # will unpack its return_value if return_value is set to an iterable.
        # This at least happens when Mock is mocking a function that is being
        # returned into a generator context.
        mock_walk_ret = (('/srv/salt/cheese',
                         [],
                         ['saltines.sls', 'biscuits.sls']),)
        ret = True

        with patch('salt.modules.cp.push', MagicMock(return_value=True)):
            with patch('os.walk', MagicMock(return_value=mock_walk_ret)):
                self.assertEqual(cp.push_dir(path), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CpTestCase, needs_daemon=False)
