# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.helpers import destructiveTest
from tests.support.runtests import RUNTIME_VARS
from tests.support.mock import patch

# Import Salt Libs
import salt.states.reg as reg
import salt.utils.platform
import salt.utils.win_reg
import salt.config
import salt.loader


@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class RegTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.reg
    '''
    hive = 'HKEY_CURRENT_USER'
    key = 'SOFTWARE\\Salt-Testing'
    name = hive + '\\' + key
    vname = 'version'
    vdata = '0.15.3'

    def setup_loader_modules(self):
        opts = salt.config.minion_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'minion'))
        utils = salt.loader.utils(opts, whitelist=['dacl', 'reg'])
        return {
            reg: {
                '__opts__': {'test': False},
                '__utils__': utils}}

    def tearDown(self):
        salt.utils.win_reg.delete_key_recursive(hive=self.hive, key=self.key)

    @destructiveTest
    def test_present(self):
        '''
        Test to set a registry entry.
        '''
        expected = {
            'comment': 'Added {0} to {0}'.format(self.name),
            'changes': {
                'reg': {
                    'Added': {
                        'Inheritance': True,
                        'Perms': {
                            'Deny': None,
                            'Grant': None},
                        'Value': '0.15.3',
                        'Key': self.name,
                        'Owner': None,
                        'Entry': 'version'}}},
            'name': self.name,
            'result': True}
        ret = reg.present(self.name, vname=self.vname, vdata=self.vdata)
        self.assertDictEqual(ret, expected)

    def test_present_test_true(self):
        expected = {
            'comment': '',
            'changes': {
                'reg': {
                    'Will add': {
                        'Inheritance': True,
                        'Perms': {
                            'Deny': None,
                            'Grant': None},
                        'Value': self.vdata,
                        'Key': self.name,
                        'Owner': None,
                        'Entry': 'version'}}},
            'name': self.name,
            'result': None}
        with patch.dict(reg.__opts__, {'test': True}):
            ret = reg.present(self.name, vname=self.vname, vdata=self.vdata)
        self.assertDictEqual(ret, expected)

    def test_present_existing(self):
        # Create the reg key for testing
        salt.utils.win_reg.set_value(hive=self.hive,
                                     key=self.key,
                                     vname=self.vname,
                                     vdata=self.vdata)

        expected = {
            'comment': '{0} in {1} is already present'.format(self.vname, self.name),
            'changes': {},
            'name': self.name,
            'result': True}
        ret = reg.present(self.name, vname=self.vname, vdata=self.vdata)
        self.assertDictEqual(ret, expected)

    def test_present_existing_test_true(self):
        # Create the reg key for testing
        salt.utils.win_reg.set_value(hive=self.hive,
                                     key=self.key,
                                     vname=self.vname,
                                     vdata=self.vdata)

        expected = {
            'comment': '{0} in {1} is already present'.format(self.vname, self.name),
            'changes': {},
            'name': self.name,
            'result': True}
        with patch.dict(reg.__opts__, {'test': True}):
            ret = reg.present(self.name, vname=self.vname, vdata=self.vdata)
        self.assertDictEqual(ret, expected)

    @destructiveTest
    def test_absent(self):
        '''
        Test to remove a registry entry.
        '''
        # Create the reg key for testing
        salt.utils.win_reg.set_value(hive=self.hive,
                                     key=self.key,
                                     vname=self.vname,
                                     vdata=self.vdata)
        expected = {
            'comment': 'Removed {0} from {1}'.format(self.key, self.hive),
            'changes': {
                'reg': {
                    'Removed': {
                        'Entry':
                            self.vname,
                        'Key': self.name}}},
            'name': self.name,
            'result': True}
        ret = reg.absent(self.name, self.vname)
        self.assertDictEqual(ret, expected)

    @destructiveTest
    def test_absent_test_true(self):
        # Create the reg key for testing
        salt.utils.win_reg.set_value(hive=self.hive,
                                     key=self.key,
                                     vname=self.vname,
                                     vdata=self.vdata)
        expected = {
            'comment': '',
            'changes': {
                'reg': {
                    'Will remove': {
                        'Entry': self.vname,
                        'Key': self.name}}},
            'name': self.name,
            'result': None}
        with patch.dict(reg.__opts__, {'test': True}):
            ret = reg.absent(self.name, self.vname)
        self.assertDictEqual(ret, expected)

    def test_absent_already_absent(self):
        '''
        Test to remove a registry entry.
        '''
        expected = {
            'comment': '{0} is already absent'.format(self.name),
            'changes': {},
            'name': self.name,
            'result': True}
        ret = reg.absent(self.name, self.vname)
        self.assertDictEqual(ret, expected)

    def test_absent_already_absent_test_true(self):
        '''
        Test to remove a registry entry.
        '''
        expected = {
            'comment': '{0} is already absent'.format(self.name),
            'changes': {},
            'name': self.name,
            'result': True}
        with patch.dict(reg.__opts__, {'test': True}):
            ret = reg.absent(self.name, self.vname)
        self.assertDictEqual(ret, expected)
