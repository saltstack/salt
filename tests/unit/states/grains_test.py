# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import grains

grains.__opts__ = {}
grains.__salt__ = {}
grains.__grains__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrainsTestCase(TestCase):
    '''
    Test cases for salt.states.grains
    '''
    name = 'cheese'
    value = 'edam'

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that a grain is set
        '''
        ret = {'comment': 'Grain value cannot be dict',
               'changes': {}, 'name': self.name, 'result': False}

        ret1 = {'changes': {}, 'name': self.name, 'result': True,
                'comment': 'Grain is already set'}

        ret2 = {'changes': {'new': self.name}, 'name': self.name,
                'result': None, 'comment': 'Grain cheese is set to be added'}

        ret3 = {'changes': {}, 'name': self.name, 'result': False,
                'comment': 'Failed to set grain cheese'}

        ret4 = {'changes': {self.name: self.value}, 'name': self.name,
                'result': True, 'comment': 'Set grain cheese to edam'}

        self.assertDictEqual(grains.present(self.name, {}), ret)

        with patch.dict(grains.__grains__, {self.name: self.value}):
            self.assertDictEqual(grains.present(self.name, self.value), ret1)

        with patch.dict(grains.__opts__, {'test': True}):
            self.assertDictEqual(grains.present(self.name, self.value), ret2)

        with patch.dict(grains.__opts__, {'test': False}):
            mock = MagicMock(side_effect=[{self.name: 'eves'},
                                          {self.name: self.value}])
            with patch.dict(grains.__salt__, {'grains.setval': mock}):
                self.assertDictEqual(grains.present(self.name, self.value),
                                     ret3)

                self.assertDictEqual(grains.present(self.name, self.value),
                                     ret4)

    # 'list_present' function tests: 1

    def test_list_present(self):
        '''
        Test to ensure the value is present in the list type grain
        '''
        ret = {'changes': {}, 'name': self.name, 'result': False,
               'comment': 'Grain cheese is not a valid list'}

        with patch.dict(grains.__grains__, {self.name: self.value}):
            self.assertDictEqual(grains.list_present(self.name, self.value),
                                 ret)

        ret = {'changes': {}, 'name': self.name, 'result': True,
               'comment': 'Value edam is already in grain cheese'}

        with patch.dict(grains.__grains__, {self.name: [self.value]}):
            self.assertDictEqual(grains.list_present(self.name, self.value),
                                 ret)

        ret = {'changes': {'new': None}, 'name': self.name, 'result': None,
               'comment': 'Grain cheese is set to be added'}

        ret1 = {'changes': {'new': ['eves']}, 'name': self.name, 'result': None,
                'comment': 'Value edam is set to be appended to grain cheese'}

        ret2 = {'changes': {}, 'name': self.name, 'result': False,
                'comment': 'Failed append value edam to grain cheese'}

        with patch.dict(grains.__opts__, {'test': True}):
            self.assertDictEqual(grains.list_present(self.name, self.value),
                                 ret)

            with patch.dict(grains.__grains__, {self.name: ['eves']}):
                self.assertDictEqual(grains.list_present(self.name, self.value),
                                     ret1)

                with patch.dict(grains.__opts__, {'test': False}):
                    mock = MagicMock(return_value={self.name: 'eves'})
                    with patch.dict(grains.__salt__, {'grains.append': mock}):
                        self.assertDictEqual(grains.list_present(self.name,
                                                                 self.value),
                                             ret2)

        ret = {'changes': {'new': self.value}, 'name': self.name,
               'result': True, 'comment': 'Append value edam to grain cheese'}

        def add_grain(name, value):
            '''
            Add key: value to __grains__ dict.
            '''
            grains.__grains__[name].append(value)
            return value

        with patch.dict(grains.__opts__, {'test': False}):
            with patch.dict(grains.__grains__, {self.name: []}):
                with patch.dict(grains.__salt__, {'grains.append': add_grain}):
                    self.assertDictEqual(grains.list_present(self.name,
                                                             self.value), ret)

    # 'list_absent' function tests: 1

    def test_list_absent(self):
        '''
        Test to delete a value from a grain formed as a list
        '''
        ret = {'changes': {}, 'name': self.name, 'result': True,
               'comment': 'Value edam is absent from grain cheese'}

        ret1 = {'changes': {'deleted': self.value}, 'name': self.name,
                'result': None,
                'comment': 'Value edam in grain cheese is set to be deleted'}

        ret2 = {'changes': {}, 'name': self.name, 'result': True,
                'comment': 'Grain cheese does not exist'}

        ret3 = {'changes': {}, 'name': self.name, 'result': False,
                'comment': 'Grain cheese is not a valid list'}

        with patch.dict(grains.__grains__, {self.name: ['eves']}):
            self.assertDictEqual(grains.list_absent(self.name, self.value), ret)

        with patch.dict(grains.__opts__, {'test': True}):
            with patch.dict(grains.__grains__, {self.name: [self.value]}):
                self.assertDictEqual(grains.list_absent(self.name, self.value),
                                     ret1)

        self.assertDictEqual(grains.list_absent(self.name, self.value), ret2)

        with patch.dict(grains.__grains__, {self.name: 'eves'}):
            self.assertDictEqual(grains.list_absent(self.name, self.value), ret3)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to delete a grain from the grains config file
        '''
        ret = {'changes': {'grain': self.name, 'value': None},
               'name': self.name, 'result': None,
               'comment': 'Value for grain cheese is set to be deleted (None)'}

        ret1 = {'changes': {}, 'name': self.name, 'result': True,
                'comment': 'Grain cheese does not exist'}

        with patch.dict(grains.__opts__, {'test': True}):
            with patch.dict(grains.__grains__, {self.name: ['edam']}):
                self.assertDictEqual(grains.absent(self.name), ret)

        self.assertDictEqual(grains.absent(self.name), ret1)

    # 'append' function tests: 1

    def test_append(self):
        '''
        Test to append a value to a list in the grains config file
        '''
        ret = {'changes': {}, 'name': self.name, 'result': True,
               'comment': 'Value edam is already in the list for grain cheese'}

        ret1 = {'changes': {'added': self.value}, 'name': self.name,
                'result': None,
                'comment': 'Value edam in grain cheese is set to be added'}

        comment = ('Grain cheese is set to be converted to list'
                   ' and value edam will be added')
        ret2 = {'changes': {'added': self.value}, 'name': self.name,
                'result': None,
                'comment': comment}

        ret3 = {'changes': {}, 'name': self.name, 'result': False,
                'comment': 'Grain cheese does not exist'}

        ret4 = {'changes': {}, 'name': self.name, 'result': False,
                'comment': 'Grain cheese is not a valid list'}

        with patch.dict(grains.__grains__, {self.name: ['edam']}):
            self.assertDictEqual(grains.append(self.name, self.value), ret)

        with patch.dict(grains.__grains__, {self.name: ['eves']}):
            with patch.dict(grains.__opts__, {'test': True}):
                self.assertDictEqual(grains.append(self.name, self.value), ret1)

        with patch.dict(grains.__grains__, {self.name: 'edam'}):
            with patch.dict(grains.__opts__, {'test': True}):
                self.assertDictEqual(grains.append(self.name, self.value,
                                                   convert=True), ret2)

        self.assertDictEqual(grains.append(self.name, self.value), ret3)

        with patch.dict(grains.__grains__, {self.name: 'eves'}):
            self.assertDictEqual(grains.append(self.name, self.value), ret4)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GrainsTestCase, needs_daemon=False)
