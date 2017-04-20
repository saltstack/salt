# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`jmoney <justin@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import cp
from salt.utils import templates
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    Mock,
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

    def test_push_non_absolute_path(self):
        '''
        Test if push fails on a non absolute path.
        '''
        path = '../saltines'
        ret = False

        self.assertEqual(cp.push(path), ret)

    def test_push_dir_non_absolute_path(self):
        '''
        Test if push_dir fails on a non absolute path.
        '''
        path = '../saltines'
        ret = False

        self.assertEqual(cp.push_dir(path), ret)

    @patch(
        'salt.modules.cp.os.path',
        MagicMock(isfile=Mock(return_value=True), wraps=cp.os.path))
    @patch.multiple(
        'salt.modules.cp',
        _auth=MagicMock(**{'return_value.gen_token.return_value': 'token'}),
        __opts__={'id': 'abc', 'file_buffer_size': 10})
    @patch('salt.utils.fopen', mock_open(read_data='content'))
    @patch('salt.transport.Channel.factory', MagicMock())
    def test_push(self):
        '''
        Test if push works with good posix path.
        '''
        import salt
        response = cp.push('/saltines/test.file')
        self.assertEqual(response, True)
        self.assertEqual(salt.utils.fopen().read.call_count, 2)
        salt.transport.Channel.factory({}).send.assert_called_once_with(
            dict(
                loc=salt.utils.fopen().tell(),
                cmd='_file_recv',
                tok='token',
                path=('saltines', 'test.file'),
                data='',  # data is empty here because load['data'] is overwritten
                id='abc'
            )
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CpTestCase, needs_daemon=False)
