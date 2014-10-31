# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    patch, DEFAULT,
    create_autospec,
    NO_MOCK,
    NO_MOCK_REASON
)
ensure_in_syspath('../../')

# Import Salt libs
from salt.utils.odict import OrderedDict
from salt import utils
from salt.utils import args
from salt.exceptions import (SaltInvocationError, SaltSystemExit, CommandNotFoundError)

# Import Python libraries
import os
import datetime
import zmq
from collections import namedtuple

# Import 3rd-party libs
try:
    import timelib  # pylint: disable=W0611
    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

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
        expected_context = '---\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu ' \
                           'lacinia sagittis. \n' \
                           'Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales' \
                           ' dolor \n' \
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

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @patch('random.randint', return_value=1)
    def test_gen_mac(self, random_mock):
        self.assertEqual(random_mock.return_value, 1)
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

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @patch('salt.utils.is_windows', return_value=False)
    def test_path_join(self, is_windows_mock):
        self.assertFalse(is_windows_mock.return_value)
        expected_path = '/a/b/c/d'
        ret = utils.path_join('/a/b/c', 'd')
        self.assertEqual(ret, expected_path)

    def test_build_whitespace_split_regex(self):
        expected_regex = '(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet\\,' \
                         '(?:[\\s]+)?$'
        ret = utils.build_whitespace_split_regex(' '.join(LORUM_IPSUM.split()[:5]))
        self.assertEqual(ret, expected_regex)

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

    @skipIf(NO_MOCK, NO_MOCK_REASON)
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

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @patch.multiple('salt.utils', get_function_argspec=DEFAULT, arg_lookup=DEFAULT)
    def test_format_call(self, arg_lookup, get_function_argspec):
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
        test_two_level_dict_and_list = {
            'abc': ['def', 'ghi', {'lorem': {'ipsum': [{'dolor': 'sit'}]}}],
        }

        self.assertTrue(
            utils.subdict_match(
                test_two_level_dict, 'foo:bar:baz'
            )
        )
        # In test_two_level_comb_dict, 'foo:bar' corresponds to 'baz:woz', not
        # 'baz'. This match should return False.
        self.assertFalse(
            utils.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz'
            )
        )
        # This tests matching with the delimiter in the value part (in other
        # words, that the path 'foo:bar' corresponds to the string 'baz:woz').
        self.assertTrue(
            utils.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz:woz'
            )
        )
        # This would match if test_two_level_comb_dict['foo']['bar'] was equal
        # to 'baz:woz:wiz', or if there was more deep nesting. But it does not,
        # so this should return False.
        self.assertFalse(
            utils.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz:woz:wiz'
            )
        )
        # This tests for cases when a key path corresponds to a list. The
        # value part 'ghi' should be successfully matched as it is a member of
        # the list corresponding to key path 'abc'. It is somewhat a
        # duplication of a test within test_traverse_dict_and_list, but
        # salt.utils.subdict_match() does more than just invoke
        # salt.utils.traverse_list_and_dict() so this particular assertion is a
        # sanity check.
        self.assertTrue(
            utils.subdict_match(
                test_two_level_dict_and_list, 'abc:ghi'
            )
        )
        # This tests the use case of a dict embedded in a list, embedded in a
        # list, embedded in a dict. This is a rather absurd case, but it
        # confirms that match recursion works properly.
        self.assertTrue(
            utils.subdict_match(
                test_two_level_dict_and_list, 'abc:lorem:ipsum:dolor:sit'
            )
        )

    def test_traverse_dict(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}

        self.assertDictEqual(
            {'not_found': 'nope'},
            utils.traverse_dict(
                test_two_level_dict, 'foo:bar:baz', {'not_found': 'nope'}
            )
        )
        self.assertEqual(
            'baz',
            utils.traverse_dict(
                test_two_level_dict, 'foo:bar', {'not_found': 'not_found'}
            )
        )

    def test_traverse_dict_and_list(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}
        test_two_level_dict_and_list = {
            'foo': ['bar', 'baz', {'lorem': {'ipsum': [{'dolor': 'sit'}]}}]
        }

        # Check traversing too far: salt.utils.traverse_dict_and_list() returns
        # the value corresponding to a given key path, and baz is a value
        # corresponding to the key path foo:bar.
        self.assertDictEqual(
            {'not_found': 'nope'},
            utils.traverse_dict_and_list(
                test_two_level_dict, 'foo:bar:baz', {'not_found': 'nope'}
            )
        )
        # Now check to ensure that foo:bar corresponds to baz
        self.assertEqual(
            'baz',
            utils.traverse_dict_and_list(
                test_two_level_dict, 'foo:bar', {'not_found': 'not_found'}
            )
        )
        # Check traversing too far
        self.assertDictEqual(
            {'not_found': 'nope'},
            utils.traverse_dict_and_list(
                test_two_level_dict_and_list, 'foo:bar', {'not_found': 'nope'}
            )
        )
        # Check index 1 (2nd element) of list corresponding to path 'foo'
        self.assertEqual(
            'baz',
            utils.traverse_dict_and_list(
                test_two_level_dict_and_list, 'foo:1', {'not_found': 'not_found'}
            )
        )
        # Traverse a couple times into dicts embedded in lists
        self.assertEqual(
            'sit',
            utils.traverse_dict_and_list(
                test_two_level_dict_and_list,
                'foo:lorem:ipsum:dolor',
                {'not_found': 'not_found'}
            )
        )

    def test_clean_kwargs(self):
        self.assertDictEqual(utils.clean_kwargs(foo='bar'), {'foo': 'bar'})
        self.assertDictEqual(utils.clean_kwargs(__pub_foo='bar'), {})
        self.assertDictEqual(utils.clean_kwargs(__foo_bar='gwar'), {'__foo_bar': 'gwar'})

    def test_check_state_result(self):
        self.assertFalse(utils.check_state_result(None), "Failed to handle None as an invalid data type.")
        self.assertFalse(utils.check_state_result([]), "Failed to handle an invalid data type.")
        self.assertFalse(utils.check_state_result({}), "Failed to handle an empty dictionary.")
        self.assertFalse(utils.check_state_result({'host1': []}), "Failed to handle an invalid host data structure.")
        test_valid_state = {'host1': {'test_state': {'result': 'We have liftoff!'}}}
        self.assertTrue(utils.check_state_result(test_valid_state))
        test_valid_false_states = {
            'test1': OrderedDict([
                ('host1',
                 OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': False}),
                 ])),
            ]),
            'test2': OrderedDict([
                ('host1',
                 OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
                ('host2',
                 OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': False}),
                 ])),
            ]),
            'test3': ['a'],
            'test4': OrderedDict([
                ('asup', OrderedDict([
                    ('host1',
                     OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ])),
                    ('host2',
                     OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': False}),
                     ]))
                ]))
            ]),
            'test5': OrderedDict([
                ('asup', OrderedDict([
                    ('host1',
                     OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ])),
                    ('host2', [])
                ]))
            ])
        }
        for test, data in test_valid_false_states.items():
            self.assertFalse(
                utils.check_state_result(data),
                msg='{0} failed'.format(test))
        test_valid_true_states = {
            'test1': OrderedDict([
                ('host1',
                 OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
            ]),
            'test3': OrderedDict([
                ('host1',
                 OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
                ('host2',
                 OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': True}),
                 ])),
            ]),
            'test4': OrderedDict([
                ('asup', OrderedDict([
                    ('host1',
                     OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ])),
                    ('host2',
                     OrderedDict([
                         ('test_state0', {'result':  True}),
                         ('test_state', {'result': True}),
                     ]))
                ]))
            ]),
            'test2': OrderedDict([
                ('host1',
                 OrderedDict([
                     ('test_state0', {'result':  None}),
                     ('test_state', {'result': True}),
                 ])),
                ('host2',
                 OrderedDict([
                     ('test_state0', {'result':  True}),
                     ('test_state', {'result': 'abc'}),
                 ]))
            ])
        }
        for test, data in test_valid_true_states.items():
            self.assertTrue(
                utils.check_state_result(data),
                msg='{0} failed'.format(test))
        test_valid_false_state = {'host1': {'test_state': {'result': False}}}
        self.assertFalse(utils.check_state_result(test_valid_false_state))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @skipIf(not hasattr(zmq, 'IPC_PATH_MAX_LEN'), "ZMQ does not have max length support.")
    def test_check_ipc_length(self):
        '''
        Ensure we throw an exception if we have a too-long IPC URI
        '''
        with patch('zmq.IPC_PATH_MAX_LEN', 1):
            self.assertRaises(SaltSystemExit, utils.check_ipc_path_max_len, '1' * 1024)

    def test_test_mode(self):
        self.assertTrue(utils.test_mode(test=True))
        self.assertTrue(utils.test_mode(Test=True))
        self.assertTrue(utils.test_mode(tEsT=True))

    def test_option(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}

        self.assertDictEqual({'not_found': 'nope'}, utils.option('foo:bar', {'not_found': 'nope'}))
        self.assertEqual('baz', utils.option('foo:bar', {'not_found': 'nope'}, opts=test_two_level_dict))
        self.assertEqual('baz', utils.option('foo:bar', {'not_found': 'nope'}, pillar={'master': test_two_level_dict}))
        self.assertEqual('baz', utils.option('foo:bar', {'not_found': 'nope'}, pillar=test_two_level_dict))

    def test_parse_docstring(self):
        test_keystone_str = '''Management of Keystone users
                                ============================

                                :depends:   - keystoneclient Python module
                                :configuration: See :py:mod:`salt.modules.keystone` for setup instructions.
'''

        ret = utils.parse_docstring(test_keystone_str)
        expected_dict = {'deps': ['keystoneclient'],
                         'full': 'Management of Keystone users\n                                '
                                 '============================\n\n                                '
                                 ':depends:   - keystoneclient Python module\n                                '
                                 ':configuration: See :py:mod:`salt.modules.keystone` for setup instructions.\n'}
        self.assertDictEqual(ret, expected_dict)

    def test_get_hash_exception(self):
        self.assertRaises(ValueError, utils.get_hash, '/tmp/foo/', form='INVALID')

    def test_parse_kwarg(self):
        ret = args.parse_kwarg('foo=bar')
        self.assertEqual(ret, ('foo', 'bar'))

        ret = args.parse_kwarg('foobar')
        self.assertEqual(ret, (None, None))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_date_cast(self):
        now = datetime.datetime.now()
        with patch('datetime.datetime'):
            datetime.datetime.now.return_value = now
            self.assertEqual(now, utils.date_cast(None))
        self.assertEqual(now, utils.date_cast(now))
        try:
            import timelib

            ret = utils.date_cast('Mon Dec 23 10:19:15 MST 2013')
            expected_ret = datetime.datetime(2013, 12, 23, 10, 19, 15)
            self.assertEqual(ret, expected_ret)
        except ImportError:
            try:
                ret = utils.date_cast('Mon Dec 23 10:19:15 MST 2013')
                expected_ret = datetime.datetime(2013, 12, 23, 10, 19, 15)
                self.assertEqual(ret, expected_ret)
            except RuntimeError:
                # Unparseable without timelib installed
                self.skipTest('\'timelib\' is not installed')

    @skipIf(not HAS_TIMELIB, '\'timelib\' is not installed')
    def test_date_format(self):

        # Taken from doctests

        expected_ret = '2002-12-25'

        src = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
        ret = utils.date_format(src)
        self.assertEqual(ret, expected_ret)

        src = '2002/12/25'
        ret = utils.date_format(src)
        self.assertEqual(ret, expected_ret)

        src = 1040814000
        ret = utils.date_format(src)
        self.assertEqual(ret, expected_ret)

        src = '1040814000'
        ret = utils.date_format(src)
        self.assertEqual(ret, expected_ret)

    def test_compare_dicts(self):
        ret = utils.compare_dicts(old={'foo': 'bar'}, new={'foo': 'bar'})
        self.assertEqual(ret, {})

        ret = utils.compare_dicts(old={'foo': 'bar'}, new={'foo': 'woz'})
        expected_ret = {'foo': {'new': 'woz', 'old': 'bar'}}
        self.assertDictEqual(ret, expected_ret)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_argspec_report(self):
        def _test_spec(arg1, arg2, kwarg1=None):
            pass

        sys_mock = create_autospec(_test_spec)
        test_functions = {'test_module.test_spec': sys_mock}
        ret = utils.argspec_report(test_functions, 'test_module.test_spec')
        self.assertDictEqual(ret, {'test_module.test_spec':
                                       {'kwargs': True, 'args': None, 'defaults': None, 'varargs': True}})

    def test_decode_list(self):
        test_data = [u'unicode_str', [u'unicode_item_in_list', 'second_item_in_list'], {'dict_key': u'dict_val'}]
        expected_ret = ['unicode_str', ['unicode_item_in_list', 'second_item_in_list'], {'dict_key': 'dict_val'}]
        ret = utils.decode_list(test_data)
        self.assertEqual(ret, expected_ret)

    def test_decode_dict(self):
        test_data = {u'test_unicode_key': u'test_unicode_val',
                     'test_list_key': ['list_1', u'unicode_list_two'],
                     u'test_dict_key': {'test_sub_dict_key': 'test_sub_dict_val'}}
        expected_ret = {'test_unicode_key': 'test_unicode_val',
                        'test_list_key': ['list_1', 'unicode_list_two'],
                        'test_dict_key': {'test_sub_dict_key': 'test_sub_dict_val'}}
        ret = utils.decode_dict(test_data)
        self.assertDictEqual(ret, expected_ret)

    def test_find_json(self):
        test_sample_json = '''
                            {
                                "glossary": {
                                    "title": "example glossary",
                                    "GlossDiv": {
                                        "title": "S",
                                        "GlossList": {
                                            "GlossEntry": {
                                                "ID": "SGML",
                                                "SortAs": "SGML",
                                                "GlossTerm": "Standard Generalized Markup Language",
                                                "Acronym": "SGML",
                                                "Abbrev": "ISO 8879:1986",
                                                "GlossDef": {
                                                    "para": "A meta-markup language, used to create markup languages such as DocBook.",
                                                    "GlossSeeAlso": ["GML", "XML"]
                                                },
                                                "GlossSee": "markup"
                                            }
                                        }
                                    }
                                }
                            }
                            '''
        expected_ret = {'glossary': {'GlossDiv': {'GlossList': {'GlossEntry': {
            'GlossDef': {'GlossSeeAlso': ['GML', 'XML'],
                         'para': 'A meta-markup language, used to create markup languages such as DocBook.'},
            'GlossSee': 'markup', 'Acronym': 'SGML', 'GlossTerm': 'Standard Generalized Markup Language',
            'SortAs': 'SGML',
            'Abbrev': 'ISO 8879:1986', 'ID': 'SGML'}}, 'title': 'S'}, 'title': 'example glossary'}}

        # First test the valid JSON
        ret = utils.find_json(test_sample_json)
        self.assertDictEqual(ret, expected_ret)

        # Now pre-pend some garbage and re-test
        garbage_prepend_json = '{0}{1}'.format(LORUM_IPSUM, test_sample_json)
        ret = utils.find_json(garbage_prepend_json)
        self.assertDictEqual(ret, expected_ret)

        # Test to see if a ValueError is raised if no JSON is passed in
        self.assertRaises(ValueError, utils.find_json, LORUM_IPSUM)

    def test_is_bin_str(self):
        self.assertFalse(utils.is_bin_str(LORUM_IPSUM))

        zero_str = '{0}{1}'.format(LORUM_IPSUM, '\0')
        self.assertTrue(utils.is_bin_str(zero_str))

        # To to ensure safe exit if str passed doesn't evaluate to True
        self.assertFalse(utils.is_bin_str(''))

        # TODO: Test binary detection

    def test_repack_dict(self):
        list_of_one_element_dicts = [{'dict_key_1': 'dict_val_1'},
                                     {'dict_key_2': 'dict_val_2'},
                                     {'dict_key_3': 'dict_val_3'}]
        expected_ret = {'dict_key_1': 'dict_val_1',
                        'dict_key_2': 'dict_val_2',
                        'dict_key_3': 'dict_val_3'}
        ret = utils.repack_dictlist(list_of_one_element_dicts)
        self.assertDictEqual(ret, expected_ret)

        # Try with yaml
        yaml_key_val_pair = '- key1: val1'
        ret = utils.repack_dictlist(yaml_key_val_pair)
        self.assertDictEqual(ret, {'key1': 'val1'})

        # Make sure we handle non-yaml junk data
        ret = utils.repack_dictlist(LORUM_IPSUM)
        self.assertDictEqual(ret, {})

    def test_get_colors(self):
        ret = utils.get_colors()
        self.assertDictContainsSubset({'LIGHT_GRAY': '\x1b[0;37m'}, ret)

        ret = utils.get_colors(use=False)
        self.assertDictContainsSubset({'LIGHT_GRAY': ''}, ret)

        ret = utils.get_colors(use='LIGHT_GRAY')
        self.assertDictContainsSubset({'YELLOW': '\x1b[0;37m'}, ret)  # YELLOW now == LIGHT_GRAY

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_daemonize_if(self):
        # pylint: disable=assignment-from-none
        with patch('sys.argv', ['salt-call']):
            ret = utils.daemonize_if({})
            self.assertEqual(None, ret)

        ret = utils.daemonize_if({'multiprocessing': False})
        self.assertEqual(None, ret)

        with patch('sys.platform', 'win'):
            ret = utils.daemonize_if({})
            self.assertEqual(None, ret)

        with patch('salt.utils.daemonize'):
            utils.daemonize_if({})
            self.assertTrue(utils.daemonize.called)
        # pylint: enable=assignment-from-none

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_which_bin(self):
        ret = utils.which_bin('str')
        self.assertIs(None, ret)

        test_exes = ['ls', 'echo']
        with patch('salt.utils.which', return_value='/tmp/dummy_path'):
            ret = utils.which_bin(test_exes)
            self.assertEqual(ret, '/tmp/dummy_path')

            ret = utils.which_bin([])
            self.assertIs(None, ret)

        with patch('salt.utils.which', return_value=''):
            ret = utils.which_bin(test_exes)
            self.assertIs(None, ret)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_gen_jid(self):
        now = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
        with patch('datetime.datetime'):
            datetime.datetime.now.return_value = now
            ret = utils.gen_jid()
            self.assertEqual(ret, '20021225120000000000')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_check_or_die(self):
        self.assertRaises(CommandNotFoundError, utils.check_or_die, None)

        with patch('salt.utils.which', return_value=False):
            self.assertRaises(CommandNotFoundError, utils.check_or_die, 'FAKE COMMAND')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_compare_versions(self):
        ret = utils.compare_versions('1.0', '==', '1.0')
        self.assertTrue(ret)

        ret = utils.compare_versions('1.0', '!=', '1.0')
        self.assertFalse(ret)

        with patch('salt.utils.log') as log_mock:
            ret = utils.compare_versions('1.0', 'HAH I AM NOT A COMP OPERATOR! I AM YOUR FATHER!', '1.0')
            self.assertTrue(log_mock.error.called)

    def test_kwargs_warn_until(self):
        # Test invalid version arg
        self.assertRaises(RuntimeError, utils.kwargs_warn_until, {}, [])

if __name__ == '__main__':
    from integration import run_tests
    run_tests(UtilsTestCase, needs_daemon=False)
