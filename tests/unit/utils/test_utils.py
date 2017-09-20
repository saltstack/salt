# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.utils
import salt.utils.jid
import salt.utils.yamlencoding
import salt.utils.zeromq
from salt.exceptions import SaltSystemExit, CommandNotFoundError

# Import Python libraries
import datetime
import os
import yaml
import zmq

# Import 3rd-party libs
try:
    import timelib  # pylint: disable=import-error,unused-import
    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

LOREM_IPSUM = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis. \n' \
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
        ret = salt.utils.get_context(LOREM_IPSUM, 1, num_lines=1)
        self.assertEqual(ret, expected_context)

    def test_jid_to_time(self):
        test_jid = 20131219110700123489
        expected_jid = '2013, Dec 19 11:07:00.123489'
        self.assertEqual(salt.utils.jid.jid_to_time(test_jid), expected_jid)

        # Test incorrect lengths
        incorrect_jid_length = 2012
        self.assertEqual(salt.utils.jid.jid_to_time(incorrect_jid_length), '')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_gen_mac(self):
        with patch('random.randint', return_value=1) as random_mock:
            self.assertEqual(random_mock.return_value, 1)
            ret = salt.utils.gen_mac('00:16:3E')
            expected_mac = '00:16:3E:01:01:01'
            self.assertEqual(ret, expected_mac)

    def test_mac_str_to_bytes(self):
        self.assertRaises(ValueError, salt.utils.mac_str_to_bytes, '31337')
        self.assertRaises(ValueError, salt.utils.mac_str_to_bytes, '0001020304056')
        self.assertRaises(ValueError, salt.utils.mac_str_to_bytes, '00:01:02:03:04:056')
        self.assertRaises(ValueError, salt.utils.mac_str_to_bytes, 'a0:b0:c0:d0:e0:fg')
        self.assertEqual(b'\x10\x08\x06\x04\x02\x00', salt.utils.mac_str_to_bytes('100806040200'))
        self.assertEqual(b'\xf8\xe7\xd6\xc5\xb4\xa3', salt.utils.mac_str_to_bytes('f8e7d6c5b4a3'))

    def test_ip_bracket(self):
        test_ipv4 = '127.0.0.1'
        test_ipv6 = '::1'
        self.assertEqual(test_ipv4, salt.utils.ip_bracket(test_ipv4))
        self.assertEqual('[{0}]'.format(test_ipv6), salt.utils.ip_bracket(test_ipv6))

    def test_is_jid(self):
        self.assertTrue(salt.utils.jid.is_jid('20131219110700123489'))  # Valid JID
        self.assertFalse(salt.utils.jid.is_jid(20131219110700123489))  # int
        self.assertFalse(salt.utils.jid.is_jid('2013121911070012348911111'))  # Wrong length

    def test_build_whitespace_split_regex(self):
        expected_regex = '(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet\\,' \
                         '(?:[\\s]+)?$'
        ret = salt.utils.build_whitespace_split_regex(' '.join(LOREM_IPSUM.split()[:5]))
        self.assertEqual(ret, expected_regex)

    def test_isorted(self):
        test_list = ['foo', 'Foo', 'bar', 'Bar']
        expected_list = ['bar', 'Bar', 'foo', 'Foo']
        self.assertEqual(salt.utils.isorted(test_list), expected_list)

    def test_mysql_to_dict(self):
        test_mysql_output = ['+----+------+-----------+------+---------+------+-------+------------------+',
                             '| Id | User | Host      | db   | Command | Time | State | Info             |',
                             '+----+------+-----------+------+---------+------+-------+------------------+',
                             '|  7 | root | localhost | NULL | Query   |    0 | init  | show processlist |',
                             '+----+------+-----------+------+---------+------+-------+------------------+']

        ret = salt.utils.mysql_to_dict(test_mysql_output, 'Info')
        expected_dict = {
            'show processlist': {'Info': 'show processlist', 'db': 'NULL', 'State': 'init', 'Host': 'localhost',
                                 'Command': 'Query', 'User': 'root', 'Time': 0, 'Id': 7}}

        self.assertDictEqual(ret, expected_dict)

    def test_subdict_match(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}
        test_two_level_comb_dict = {'foo': {'bar': 'baz:woz'}}
        test_two_level_dict_and_list = {
            'abc': ['def', 'ghi', {'lorem': {'ipsum': [{'dolor': 'sit'}]}}],
        }
        test_three_level_dict = {'a': {'b': {'c': 'v'}}}

        self.assertTrue(
            salt.utils.subdict_match(
                test_two_level_dict, 'foo:bar:baz'
            )
        )
        # In test_two_level_comb_dict, 'foo:bar' corresponds to 'baz:woz', not
        # 'baz'. This match should return False.
        self.assertFalse(
            salt.utils.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz'
            )
        )
        # This tests matching with the delimiter in the value part (in other
        # words, that the path 'foo:bar' corresponds to the string 'baz:woz').
        self.assertTrue(
            salt.utils.subdict_match(
                test_two_level_comb_dict, 'foo:bar:baz:woz'
            )
        )
        # This would match if test_two_level_comb_dict['foo']['bar'] was equal
        # to 'baz:woz:wiz', or if there was more deep nesting. But it does not,
        # so this should return False.
        self.assertFalse(
            salt.utils.subdict_match(
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
            salt.utils.subdict_match(
                test_two_level_dict_and_list, 'abc:ghi'
            )
        )
        # This tests the use case of a dict embedded in a list, embedded in a
        # list, embedded in a dict. This is a rather absurd case, but it
        # confirms that match recursion works properly.
        self.assertTrue(
            salt.utils.subdict_match(
                test_two_level_dict_and_list, 'abc:lorem:ipsum:dolor:sit'
            )
        )
        # Test four level dict match for reference
        self.assertTrue(
            salt.utils.subdict_match(
                test_three_level_dict, 'a:b:c:v'
            )
        )
        self.assertFalse(
        # Test regression in 2015.8 where 'a:c:v' would match 'a:b:c:v'
            salt.utils.subdict_match(
                test_three_level_dict, 'a:c:v'
            )
        )
        # Test wildcard match
        self.assertTrue(
            salt.utils.subdict_match(
                test_three_level_dict, 'a:*:c:v'
            )
        )

    def test_traverse_dict(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}

        self.assertDictEqual(
            {'not_found': 'nope'},
            salt.utils.traverse_dict(
                test_two_level_dict, 'foo:bar:baz', {'not_found': 'nope'}
            )
        )
        self.assertEqual(
            'baz',
            salt.utils.traverse_dict(
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
            salt.utils.traverse_dict_and_list(
                test_two_level_dict, 'foo:bar:baz', {'not_found': 'nope'}
            )
        )
        # Now check to ensure that foo:bar corresponds to baz
        self.assertEqual(
            'baz',
            salt.utils.traverse_dict_and_list(
                test_two_level_dict, 'foo:bar', {'not_found': 'not_found'}
            )
        )
        # Check traversing too far
        self.assertDictEqual(
            {'not_found': 'nope'},
            salt.utils.traverse_dict_and_list(
                test_two_level_dict_and_list, 'foo:bar', {'not_found': 'nope'}
            )
        )
        # Check index 1 (2nd element) of list corresponding to path 'foo'
        self.assertEqual(
            'baz',
            salt.utils.traverse_dict_and_list(
                test_two_level_dict_and_list, 'foo:1', {'not_found': 'not_found'}
            )
        )
        # Traverse a couple times into dicts embedded in lists
        self.assertEqual(
            'sit',
            salt.utils.traverse_dict_and_list(
                test_two_level_dict_and_list,
                'foo:lorem:ipsum:dolor',
                {'not_found': 'not_found'}
            )
        )

    def test_sanitize_win_path_string(self):
        p = '\\windows\\system'
        self.assertEqual(salt.utils.sanitize_win_path_string('\\windows\\system'), '\\windows\\system')
        self.assertEqual(salt.utils.sanitize_win_path_string('\\bo:g|us\\p?at*h>'), '\\bo_g_us\\p_at_h_')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    @skipIf(not hasattr(zmq, 'IPC_PATH_MAX_LEN'), "ZMQ does not have max length support.")
    def test_check_ipc_length(self):
        '''
        Ensure we throw an exception if we have a too-long IPC URI
        '''
        with patch('zmq.IPC_PATH_MAX_LEN', 1):
            self.assertRaises(SaltSystemExit, salt.utils.zeromq.check_ipc_path_max_len, '1' * 1024)

    def test_test_mode(self):
        self.assertTrue(salt.utils.test_mode(test=True))
        self.assertTrue(salt.utils.test_mode(Test=True))
        self.assertTrue(salt.utils.test_mode(tEsT=True))

    def test_option(self):
        test_two_level_dict = {'foo': {'bar': 'baz'}}

        self.assertDictEqual({'not_found': 'nope'}, salt.utils.option('foo:bar', {'not_found': 'nope'}))
        self.assertEqual('baz', salt.utils.option('foo:bar', {'not_found': 'nope'}, opts=test_two_level_dict))
        self.assertEqual('baz', salt.utils.option('foo:bar', {'not_found': 'nope'}, pillar={'master': test_two_level_dict}))
        self.assertEqual('baz', salt.utils.option('foo:bar', {'not_found': 'nope'}, pillar=test_two_level_dict))

    def test_get_hash_exception(self):
        self.assertRaises(ValueError, salt.utils.get_hash, '/tmp/foo/', form='INVALID')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_date_cast(self):
        now = datetime.datetime.now()
        with patch('datetime.datetime'):
            datetime.datetime.now.return_value = now
            self.assertEqual(now, salt.utils.date_cast(None))
        self.assertEqual(now, salt.utils.date_cast(now))
        try:
            ret = salt.utils.date_cast('Mon Dec 23 10:19:15 MST 2013')
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
        ret = salt.utils.date_format(src)
        self.assertEqual(ret, expected_ret)

        src = '2002/12/25'
        ret = salt.utils.date_format(src)
        self.assertEqual(ret, expected_ret)

        src = 1040814000
        ret = salt.utils.date_format(src)
        self.assertEqual(ret, expected_ret)

        src = '1040814000'
        ret = salt.utils.date_format(src)
        self.assertEqual(ret, expected_ret)

    def test_yaml_dquote(self):
        for teststr in (r'"\ []{}"',):
            self.assertEqual(teststr, yaml.safe_load(salt.utils.yamlencoding.yaml_dquote(teststr)))

    def test_yaml_dquote_doesNotAddNewLines(self):
        teststr = '"' * 100
        self.assertNotIn('\n', salt.utils.yamlencoding.yaml_dquote(teststr))

    def test_yaml_squote(self):
        ret = salt.utils.yamlencoding.yaml_squote(r'"')
        self.assertEqual(ret, r"""'"'""")

    def test_yaml_squote_doesNotAddNewLines(self):
        teststr = "'" * 100
        self.assertNotIn('\n', salt.utils.yamlencoding.yaml_squote(teststr))

    def test_yaml_encode(self):
        for testobj in (None, True, False, '[7, 5]', '"monkey"', 5, 7.5, "2014-06-02 15:30:29.7"):
            self.assertEqual(testobj, yaml.safe_load(salt.utils.yamlencoding.yaml_encode(testobj)))

        for testobj in ({}, [], set()):
            self.assertRaises(TypeError, salt.utils.yamlencoding.yaml_encode, testobj)

    def test_compare_dicts(self):
        ret = salt.utils.compare_dicts(old={'foo': 'bar'}, new={'foo': 'bar'})
        self.assertEqual(ret, {})

        ret = salt.utils.compare_dicts(old={'foo': 'bar'}, new={'foo': 'woz'})
        expected_ret = {'foo': {'new': 'woz', 'old': 'bar'}}
        self.assertDictEqual(ret, expected_ret)

    def test_decode_list(self):
        test_data = [u'unicode_str', [u'unicode_item_in_list', 'second_item_in_list'], {'dict_key': u'dict_val'}]
        expected_ret = ['unicode_str', ['unicode_item_in_list', 'second_item_in_list'], {'dict_key': 'dict_val'}]
        ret = salt.utils.decode_list(test_data)
        self.assertEqual(ret, expected_ret)

    def test_decode_dict(self):
        test_data = {u'test_unicode_key': u'test_unicode_val',
                     'test_list_key': ['list_1', u'unicode_list_two'],
                     u'test_dict_key': {'test_sub_dict_key': 'test_sub_dict_val'}}
        expected_ret = {'test_unicode_key': 'test_unicode_val',
                        'test_list_key': ['list_1', 'unicode_list_two'],
                        'test_dict_key': {'test_sub_dict_key': 'test_sub_dict_val'}}
        ret = salt.utils.decode_dict(test_data)
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
        ret = salt.utils.find_json(test_sample_json)
        self.assertDictEqual(ret, expected_ret)

        # Now pre-pend some garbage and re-test
        garbage_prepend_json = '{0}{1}'.format(LOREM_IPSUM, test_sample_json)
        ret = salt.utils.find_json(garbage_prepend_json)
        self.assertDictEqual(ret, expected_ret)

        # Test to see if a ValueError is raised if no JSON is passed in
        self.assertRaises(ValueError, salt.utils.find_json, LOREM_IPSUM)

    def test_repack_dict(self):
        list_of_one_element_dicts = [{'dict_key_1': 'dict_val_1'},
                                     {'dict_key_2': 'dict_val_2'},
                                     {'dict_key_3': 'dict_val_3'}]
        expected_ret = {'dict_key_1': 'dict_val_1',
                        'dict_key_2': 'dict_val_2',
                        'dict_key_3': 'dict_val_3'}
        ret = salt.utils.repack_dictlist(list_of_one_element_dicts)
        self.assertDictEqual(ret, expected_ret)

        # Try with yaml
        yaml_key_val_pair = '- key1: val1'
        ret = salt.utils.repack_dictlist(yaml_key_val_pair)
        self.assertDictEqual(ret, {'key1': 'val1'})

        # Make sure we handle non-yaml junk data
        ret = salt.utils.repack_dictlist(LOREM_IPSUM)
        self.assertDictEqual(ret, {})

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_daemonize_if(self):
        # pylint: disable=assignment-from-none
        with patch('sys.argv', ['salt-call']):
            ret = salt.utils.daemonize_if({})
            self.assertEqual(None, ret)

        ret = salt.utils.daemonize_if({'multiprocessing': False})
        self.assertEqual(None, ret)

        with patch('sys.platform', 'win'):
            ret = salt.utils.daemonize_if({})
            self.assertEqual(None, ret)

        with patch('salt.utils.daemonize'):
            salt.utils.daemonize_if({})
            self.assertTrue(salt.utils.daemonize.called)
        # pylint: enable=assignment-from-none

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_gen_jid(self):
        now = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
        with patch('datetime.datetime'):
            datetime.datetime.now.return_value = now
            ret = salt.utils.jid.gen_jid({})
            self.assertEqual(ret, '20021225120000000000')
            salt.utils.jid.LAST_JID_DATETIME = None
            ret = salt.utils.jid.gen_jid({'unique_jid': True})
            self.assertEqual(ret, '20021225120000000000_{0}'.format(os.getpid()))
            ret = salt.utils.jid.gen_jid({'unique_jid': True})
            self.assertEqual(ret, '20021225120000000001_{0}'.format(os.getpid()))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_check_or_die(self):
        self.assertRaises(CommandNotFoundError, salt.utils.check_or_die, None)

        with patch('salt.utils.path.which', return_value=False):
            self.assertRaises(CommandNotFoundError, salt.utils.check_or_die, 'FAKE COMMAND')
