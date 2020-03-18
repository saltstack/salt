# -*- coding: utf-8 -*-
'''
Tests for salt.utils.json
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import textwrap

# Import Salt Testing libs
from tests.support.helpers import with_tempfile
from tests.support.mock import patch, MagicMock
from tests.support.unit import TestCase, LOREM_IPSUM, skipIf

# Import Salt libs
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.stringutils
from salt.ext import six


class JSONTestCase(TestCase):
    data = {
        'спам': 'яйца',
        'list': [1, 2, 'three'],
        'dict': {'subdict': {'спам': 'яйца'}},
        'True': False,
        'float': 1.5,
        'None': None,
    }

    serialized = salt.utils.stringutils.to_str(
        '{"None": null, "True": false, "dict": {"subdict": {"спам": "яйца"}}, "float": 1.5, "list": [1, 2, "three"], "спам": "яйца"}'
    )

    serialized_indent4 = salt.utils.stringutils.to_str(textwrap.dedent('''\
        {
            "None": null,
            "True": false,
            "dict": {
                "subdict": {
                    "спам": "яйца"
                }
            },
            "float": 1.5,
            "list": [
                1,
                2,
                "three"
            ],
            "спам": "яйца"
        }'''))

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
        ret = salt.utils.json.find_json(test_sample_json)
        self.assertDictEqual(ret, expected_ret)

        # Now pre-pend some garbage and re-test
        garbage_prepend_json = '{0}{1}'.format(LOREM_IPSUM, test_sample_json)
        ret = salt.utils.json.find_json(garbage_prepend_json)
        self.assertDictEqual(ret, expected_ret)

        # Test to see if a ValueError is raised if no JSON is passed in
        self.assertRaises(ValueError, salt.utils.json.find_json, LOREM_IPSUM)

    @skipIf(salt.utils.platform.is_windows(), 'skip until we figure out what to do about decoding unicode on windows')
    @skipIf(not six.PY2, 'Test only needed on Python 2')
    def test_find_json_unicode_splitlines(self):
        '''
        Tests a case in salt-ssh where a unicode string is split into a list of
        str types by .splitlines().
        '''
        raw = '{"foo": "öäü"}'
        mock_split = MagicMock(return_value=[raw.encode('utf8')])

        with patch.object(salt.utils.json, '__split', mock_split):
            ret = salt.utils.json.find_json(raw)
            self.assertEqual(ret, {'foo': 'öäü'})

    def test_dumps_loads(self):
        '''
        Test dumping to and loading from a string
        '''
        # Dump with no indentation
        ret = salt.utils.json.dumps(self.data, sort_keys=True)
        # Make sure the result is as expected
        self.assertEqual(ret, self.serialized)
        # Loading it should be equal to the original data
        self.assertEqual(salt.utils.json.loads(ret), self.data)

        # Dump with 4 spaces of indentation
        ret = salt.utils.json.dumps(self.data, sort_keys=True, indent=4)
        # Make sure the result is as expected. Note that in Python 2, dumping
        # results in trailing whitespace on lines ending in a comma. So, for a
        # proper comparison, we will have to run rstrip on each line of the
        # return and then stitch it back together.
        ret = str('\n').join([x.rstrip() for x in ret.splitlines()])  # future lint: disable=blacklisted-function
        self.assertEqual(ret, self.serialized_indent4)
        # Loading it should be equal to the original data
        self.assertEqual(salt.utils.json.loads(ret), self.data)

    @with_tempfile()
    def test_dump_load(self, json_out):
        '''
        Test dumping to and loading from a file handle
        '''
        with salt.utils.files.fopen(json_out, 'wb') as fp_:
            fp_.write(salt.utils.stringutils.to_bytes(salt.utils.json.dumps(self.data)))
        with salt.utils.files.fopen(json_out, 'rb') as fp_:
            ret = salt.utils.json.loads(salt.utils.stringutils.to_unicode(fp_.read()))
            # Loading should be equal to the original data
            self.assertEqual(ret, self.data)
