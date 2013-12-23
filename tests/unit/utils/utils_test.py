# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, call, DEFAULT

from salt import utils
from salt.exceptions import (SaltInvocationError, SaltSystemExit)

import os
from collections import namedtuple

ensure_in_syspath('../../')

LORUM_IPSUM = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis. \n' \
              'Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor \n' \
              'nibh eu urna. Aliquam iaculis massa risus, sed elementum risus accumsan id. Suspendisse mattis, \n' \
              'metus sed lacinia dictum, leo orci dapibus sapien, at porttitor sapien nulla ac velit. \n' \
              'Duis ac cursus leo, non varius metus. Sed laoreet felis magna, vel tempor diam malesuada nec. \n' \
              'Quisque cursus odio tortor. In consequat augue nisl, eget lacinia odio vestibulum eget. \n' \
              'Donec venenatis elementum arcu at rhoncus. Nunc pharetra erat in lacinia convallis. Ut condimentum \n' \
              'eu mauris sit amet convallis. Morbi vulputate vel odio non laoreet. Nullam in suscipit tellus. \n' \
              'Sed quis posuere urna.'


class UtilsTestCase(TestCase):
    def test_get_context(self):
        expected_context = '---\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis. \n' \
                           'Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor \n' \
                           '[...]\n' \
                           '---'
        ret = utils.get_context(LORUM_IPSUM, 1, num_lines=1)
        self.assertEqual(ret, expected_context)

    def test_jid_to_time(self):
        test_jid = 20131219110700123489
        expected_jid = '2013, Dec 19 11:07:00.123489'
        self.assertEqual(utils.jid_to_time(test_jid), expected_jid)

        # Test incorrect lengths
        incorrect_jid_lenth = 2012
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
        self.assertTrue(utils.is_jid('20131219110700123489'))  # Valid JID
        self.assertFalse(utils.is_jid(20131219110700123489))  # int
        self.assertFalse(utils.is_jid('2013121911070012348911111'))  # Wrong length

    @patch('salt.utils.is_windows', return_value=False)
    def test_path_join(self, is_windows_mock):
        expected_path = '/a/b/c/d'
        ret = utils.path_join('/a/b/c', 'd')
        self.assertEqual(ret, expected_path)

    def test_build_whitespace_split_regex(self):
        expected_regex = '(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet\\,(?:[\\s]+)?$'
        ret = utils.build_whitespace_split_regex(' '.join(LORUM_IPSUM.split()[:5]))
        self.assertEqual(ret, expected_regex)

    @patch('warnings.warn')
    def test_build_whitepace_splited_regex(self, warnings_mock):
        utils.build_whitepace_splited_regex('foo')
        self.assertTrue(warnings_mock.called)

    def test_get_function_argspec(self):
        def dummy_func(first, second, third, fourth='fifth'):
            pass

        expected_argspec = namedtuple('ArgSpec', 'args varargs keywords defaults')(
            args=['first', 'second', 'third', 'fourth'], varargs=None, keywords=None, defaults=('fifth',))
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
    # def test_format_call(self):
        def dummy_func(first=None, second=None, third=None):
            pass

        arg_lookup.return_value = {'args': ['first', 'second', 'third'], 'kwargs': {}}
        get_function_argspec.return_value = namedtuple('ArgSpec', 'args varargs keywords defaults')(
            args=['first', 'second', 'third', 'fourth'], varargs=None, keywords=None, defaults=('fifth',))

        # Make sure we raise an error if we don't pass in the requisite number of arguments
        self.assertRaises(SaltInvocationError, utils.format_call, dummy_func, {'1': 2})

        # Make sure we warn on invalid kwargs
        ret = utils.format_call(dummy_func, {'first': 2, 'second': 2, 'third': 3})
        self.assertGreaterEqual(len(ret['warnings']), 1)

        ret = utils.format_call(dummy_func, {'first': 2, 'second': 2, 'third': 3},
                                expected_extra_kws=('first', 'second', 'third'))
        self.assertDictEqual(ret, {'args': [], 'kwargs': {}})

    def test_isorted(self):
        test_list = ['foo', 'Foo', 'bar', 'Bar']
        expected_list = ['bar', 'Bar', 'foo', 'Foo']
        self.assertEqual(utils.isorted(test_list), expected_list)

    def test_mysql_to_dict(self):
        test_mysql_output = ['+----+------+-----------+------+---------+------+-------+------------------+',
                             '| Id | User | Host      | db   | Command | Time | State | Info             |',
                             '+----+------+-----------+------+---------+------+-------+------------------+',
                             '|  7 | root | localhost | NULL | Query   |    0 | init  | show processlist |',
                             '+----+------+-----------+------+---------+------+-------+------------------+']

        ret = utils.mysql_to_dict(test_mysql_output, 'Info')
        expected_dict = {
        'show processlist': {'Info': 'show processlist', 'db': 'NULL', 'State': 'init', 'Host': 'localhost',
                             'Command': 'Query', 'User': 'root', 'Time': 0, 'Id': 7}}

        self.assertDictEqual(ret, expected_dict)

    def test_contains_whitespace(self):
        does_contain_whitespace = 'A brown fox jumped over the red hen.'
        does_not_contain_whitespace = 'Abrownfoxjumpedovertheredhen.'

        self.assertTrue(utils.contains_whitespace(does_contain_whitespace))
        self.assertFalse(utils.contains_whitespace(does_not_contain_whitespace))

    def test_str_to_num(self):
        self.assertEqual(7, utils.str_to_num('7'))
        self.assertIsInstance(utils.str_to_num('7'), int)
        self.assertEqual(7, utils.str_to_num('7.0'))
        self.assertIsInstance(utils.str_to_num('7.0'), float)
        self.assertEqual(utils.str_to_num('Seven'), 'Seven')
        self.assertIsInstance(utils.str_to_num('Seven'), str)

    def test_subdict_match(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}
        test_two_level_comb_dict = {'foo': {'bar': 'baz:woz'}}

        self.assertTrue(utils.subdict_match(test_two_level_dict, 'foo:bar:baz'))
        self.assertFalse(utils.subdict_match(test_two_level_comb_dict, 'foo:bar:baz'))

        self.assertTrue(utils.subdict_match(test_two_level_comb_dict, 'foo:bar:baz:woz'))
        self.assertFalse(utils.subdict_match(test_two_level_comb_dict, 'foo:bar:baz:woz:wiz'))

    def test_traverse_dict(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}

        self.assertDictEqual({'not_found': 'nope'},
                             utils.traverse_dict(test_two_level_dict, 'foo:bar:baz', {'not_found': 'nope'}))
        self.assertEqual('baz', utils.traverse_dict(test_two_level_dict, 'foo:bar', {'not_found': 'not_found'}))

    def test_clean_kwargs(self):
        self.assertDictEqual(utils.clean_kwargs(foo='bar'), {'foo': 'bar'})
        self.assertDictEqual(utils.clean_kwargs(__pub_foo='bar'), {})
        self.assertDictEqual(utils.clean_kwargs(__foo_bar='gwar'), {'__foo_bar': 'gwar'})

    def test_check_state_result(self):
        self.assertFalse(utils.check_state_result([]), "Failed to handle an invalid data type.")
        self.assertFalse(utils.check_state_result(None), "Failed to handle None as an invalid data type.")
        self.assertFalse(utils.check_state_result({'host1': []}), "Failed to handle an invalid data structure for a host")
        self.assertFalse(utils.check_state_result({}), "Failed to handle an empty dictionary.")
        self.assertFalse(utils.check_state_result({'host1': []}), "Failed to handle an invalid host data structure.")

        self.assertTrue(utils.check_state_result({'    _|-': {}}))

        test_valid_state = {'host1': {'test_state': {'result': 'We have liftoff!'}}}
        self.assertTrue(utils.check_state_result(test_valid_state))

        test_valid_false_state = {'host1': {'test_state': {'result': False}}}
        self.assertFalse(utils.check_state_result(test_valid_false_state))

    def test_check_ipc_length(self):
        '''
        Ensure we throw an exception if we have a too-long IPC URI
        '''
        self.assertRaises(SaltSystemExit, utils.check_ipc_path_max_len, '111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111')

