# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, call, DEFAULT

from salt import utils
from salt.exceptions import SaltInvocationError

import os
from collections import namedtuple

ensure_in_syspath('../../')

LORUM_IPSUM = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis. \n' \
              'Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor \n' \
              'nibh eu urna. Aliquam iaculis massa risus, sed elementum risus accumsan id. Suspendisse mattis, \n'\
              'metus sed lacinia dictum, leo orci dapibus sapien, at porttitor sapien nulla ac velit. \n'\
              'Duis ac cursus leo, non varius metus. Sed laoreet felis magna, vel tempor diam malesuada nec. \n'\
              'Quisque cursus odio tortor. In consequat augue nisl, eget lacinia odio vestibulum eget. \n'\
              'Donec venenatis elementum arcu at rhoncus. Nunc pharetra erat in lacinia convallis. Ut condimentum \n'\
              'eu mauris sit amet convallis. Morbi vulputate vel odio non laoreet. Nullam in suscipit tellus. \n'\
              'Sed quis posuere urna.'




class UtilsTestCase(TestCase):
    def test_get_context(self):
        expected_context = '---\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis. \n'\
'Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor \n'\
'[...]\n'\
'---'
        ret = utils.get_context(LORUM_IPSUM, 1, num_lines=1)
        self.assertEqual(ret, expected_context)

    def test_jid_to_time(self):
        test_jid = 20131219110700123489
        expected_jid = '2013, Dec 19 11:07:00.123489'
        self.assertEqual(utils.jid_to_time(test_jid), expected_jid)

        # Test incorrect lengths
        incorrect_jid_lenth=2012
        self.assertEqual(utils.jid_to_time(incorrect_jid_lenth), '')

    @patch('random.randint', return_value=1)
    def test_gen_mac(self, random_mock):
        ret = utils.gen_mac('00:16:3E')
        expected_mac = '00:16:3E:01:01:01'
        self.assertEqual(ret, expected_mac)

    def test_ip_bracket(self):
        test_ipv4 = '127.0.0.1'
        test_ipv6 = '::1'
        self.assertEqual(test_ipv4, utils.ip_bracket(test_ipv4))
        self.assertEqual('[{0}]'.format(test_ipv6), utils.ip_bracket(test_ipv6))

    def test_jid_dir(self):
        test_jid = 20131219110700123489
        test_cache_dir = '/tmp/cachdir'
        test_hash_type = 'md5'

        expected_jid_dir = '/tmp/cachdir/jobs/69/fda308ccfa70d8296345e6509de136'

        ret = utils.jid_dir(test_jid, test_cache_dir, test_hash_type)

        self.assertEqual(ret, expected_jid_dir)

    def test_is_jid(self):
        self.assertTrue(utils.is_jid('20131219110700123489')) # Valid JID
        self.assertFalse(utils.is_jid(20131219110700123489)) # int
        self.assertFalse(utils.is_jid('2013121911070012348911111')) # Wrong length

    @patch('salt.utils.is_windows', return_value=False)
    def test_path_join(self, is_windows_mock):
        expected_path = '/a/b/c/d'
        ret = utils.path_join('/a/b/c', 'd')
        self.assertEqual(ret, expected_path)

    def test_build_whitespace_split_regex(self):
        expected_regex = '(?m)^(?:[\s]+)?Lorem(?:[\s]+)?ipsum(?:[\s]+)?dolor(?:[\s]+)?sit(?:[\s]+)?amet\,(?:[\s]+)?$'
        ret =  utils.build_whitespace_split_regex(' '.join(LORUM_IPSUM.split()[:5]))
        self.assertEqual(ret, expected_regex)

    @patch('warnings.warn')
    def test_build_whitepace_splited_regex(self, warnings_mock):
        utils.build_whitepace_splited_regex('foo')
        self.assertTrue(warnings_mock.called)

    def test_get_function_argspec(self):
        def dummy_func(first, second, third, fourth='fifth'):
            pass
        expected_argspec = namedtuple('ArgSpec', 'args varargs keywords defaults')(args=['first', 'second', 'third', 'fourth'], varargs=None, keywords=None, defaults=('fifth',))
        ret = utils.get_function_argspec(dummy_func)

        self.assertEqual(ret, expected_argspec)

    def test_arg_lookup(self):
        def dummy_func(first, second, third, fourth='fifth'):
            pass
        expected_dict = {'args': ['first', 'second', 'third'], 'kwargs': {'fourth': 'fifth'}}
        ret = utils.arg_lookup(dummy_func)
        self.assertEqual(expected_dict, ret)

    @patch('os.remove')
    def test_safe_rm(self, os_remove_mock):
        utils.safe_rm('dummy_tgt')
        self.assertTrue(os_remove_mock.called)

    @skipIf(os.path.exists('/tmp/no_way_this_is_a_file_nope.sh'), 'Test file exists! Skipping safe_rm_exceptions test!')
    def test_safe_rm_exceptions(self):
        try:
            utils.safe_rm('/tmp/no_way_this_is_a_file_nope.sh')
        except (IOError, OSError):
            self.assertTrue(False, "utils.safe_rm raised exception when it should not have")

    @patch.multiple('salt.utils', get_function_argspec=DEFAULT, arg_lookup=DEFAULT)
    def test_format_call(self, arg_lookup, get_function_argspec):
        def dummy_func(first, second, third, fourth='fifth'):
            pass

        arg_lookup.return_value = {'args': ['first', 'second', 'third'], 'kwargs': {'fourth': 'fifth'}}
        get_function_argspec.return_value = namedtuple('ArgSpec', 'args varargs keywords defaults')(args=['first', 'second', 'third', 'fourth'], varargs=None, keywords=None, defaults=('fifth',))

        # Make sure we raise an error if we don't pass in the requisite number of arguments
        self.assertRaises(SaltInvocationError, utils.format_call, dummy_func, {'1': 2})
