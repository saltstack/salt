# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import data

# Globals
data.__grains__ = {}
data.__salt__ = {}
data.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DataTestCase(TestCase):
    '''
    Test cases for salt.modules.data
    '''
    # 'clear' function tests: 1

    @patch('os.remove', MagicMock(return_value=''))
    def test_clear(self):
        '''
        Test if it clear out all of the data in the minion datastore
        '''
        mock = MagicMock(return_value='')
        with patch.dict(data.__opts__, {'cachedir': mock}):
            self.assertTrue(data.clear())

    # 'load' function tests: 1

    @patch('salt.utils.fopen', MagicMock(return_value=True))
    @patch('salt.payload.Serial.load', MagicMock(return_value=True))
    def test_load(self):
        '''
        Test if it return all of the data in the minion datastore
        '''
        mock = MagicMock(return_value='/')
        with patch.dict(data.__opts__, {'cachedir': mock}):
            self.assertTrue(data.load())

    # 'dump' function tests: 3

    def test_dump(self):
        '''
        Test if it replace the entire datastore with a passed data structure
        '''
        mock = MagicMock(return_value='/')
        with patch.dict(data.__opts__, {'cachedir': mock}):
            with patch('salt.utils.fopen', mock_open()):
                self.assertTrue(data.dump('{"eggs": "spam"}'))

    @patch('ast.literal_eval', MagicMock(return_value=''))
    def test_dump_isinstance(self):
        '''
        Test if it replace the entire datastore with a passed data structure
        '''
        self.assertFalse(data.dump('salt'))

    def test_dump_ioerror(self):
        '''
        Test if it replace the entire datastore with a passed data structure
        '''
        mock = MagicMock(return_value='/')
        with patch.dict(data.__opts__, {'cachedir': mock}):
            mock = MagicMock(side_effect=IOError(''))
            with patch('salt.utils.fopen', mock):
                self.assertFalse(data.dump('{"eggs": "spam"}'))

    # 'update' function tests: 1

    @patch('salt.modules.data.load', MagicMock(return_value={}))
    @patch('salt.modules.data.dump', MagicMock(return_value=True))
    def test_update(self):
        '''
        Test if it update a key with a value in the minion datastore
        '''
        self.assertTrue(data.update('foo', 'salt'))

    # 'get' function tests: 2

    @patch('salt.modules.data.load', MagicMock(return_value={'salt': 'SALT'}))
    def test_get(self):
        '''
        Test if it gets a value from the minion datastore
        '''
        self.assertEqual(data.get('salt'), 'SALT')

    @patch('salt.modules.data.load',
           MagicMock(return_value={'salt': 'SALT', 'salt1': 'SALT1'}))
    def test_get_vals(self):
        '''
        Test if it gets values from the minion datastore
        '''
        self.assertEqual(data.get(['salt', 'salt1']), ['SALT', 'SALT1'])

    # 'cas' function tests: 1

    @patch('salt.modules.data.load',
           MagicMock(return_value={'salt': 'SALT', 'salt1': 'SALT1'}))
    def test_cas_not_load(self):
        '''
        Test if it check and set a value in the minion datastore
        '''
        self.assertFalse(data.cas('salt3', 'SALT', 'SALTSTACK'))

    @patch('salt.modules.data.load',
           MagicMock(return_value={'salt': 'SALT', 'salt1': 'SALT1'}))
    def test_cas_not_equal(self):
        '''
        Test if it check and set a value in the minion datastore
        '''
        self.assertFalse(data.cas('salt', 'SALT', 'SALTSTACK'))

    @patch('salt.modules.data.load',
           MagicMock(return_value={'salt': 'SALT', 'salt1': 'SALT1'}))
    @patch('salt.modules.data.dump',
           MagicMock(return_value=True))
    def test_cas(self):
        '''
        Test if it check and set a value in the minion datastore
        '''
        self.assertTrue(data.cas('salt', 'SALTSTACK', 'SALT'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DataTestCase, needs_daemon=False)
