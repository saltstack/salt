# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    mock_open,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.nftables as nftables
import salt.utils
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NftablesTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.nftables
    '''
    def setup_loader_modules(self):
        return {nftables: {}}

    # 'version' function tests: 1

    def test_version(self):
        '''
        Test if it return version from nftables --version
        '''
        mock = MagicMock(return_value='nf_tables 0.3-1')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.version(), '0.3-1')

    # 'build_rule' function tests: 1

    def test_build_rule(self):
        '''
        Test if it build a well-formatted nftables rule based on kwargs.
        '''
        self.assertEqual(nftables.build_rule(full='True'),
                         'Error: Table needs to be specified')

        self.assertEqual(nftables.build_rule(table='filter', full='True'),
                         'Error: Chain needs to be specified')

        self.assertEqual(nftables.build_rule(table='filter', chain='input',
                                             full='True'),
                         'Error: Command needs to be specified')

        self.assertEqual(nftables.build_rule(table='filter', chain='input',
                                             command='insert', position='3',
                                             full='True'),
                         'nft insert rule ip filter input position 3 ')

        self.assertEqual(nftables.build_rule(table='filter', chain='input',
                                             command='insert', full='True'),
                         'nft insert rule ip filter input ')

        self.assertEqual(nftables.build_rule(table='filter', chain='input',
                                             command='halt', full='True'),
                         'nft halt rule ip filter input ')

        self.assertEqual(nftables.build_rule(), '')

    # 'get_saved_rules' function tests: 1

    def test_get_saved_rules(self):
        '''
        Test if it return a data structure of the rules in the conf file
        '''
        with patch.dict(nftables.__grains__, {'os_family': 'Debian'}):
            with patch.object(salt.utils, 'fopen', MagicMock(mock_open())):
                self.assertListEqual(nftables.get_saved_rules(), [])

    # 'get_rules' function tests: 1

    def test_get_rules(self):
        '''
        Test if it return a data structure of the current, in-memory rules
        '''
        mock = MagicMock(return_value='SALT STACK')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertListEqual(nftables.get_rules(), ['SALT STACK'])

        mock = MagicMock(return_value=False)
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertListEqual(nftables.get_rules(), [])

    # 'save' function tests: 1

    def test_save(self):
        '''
        Test if it save the current in-memory rules to disk
        '''
        with patch.dict(nftables.__grains__, {'os_family': 'Debian'}):
            mock = MagicMock(return_value=False)
            with patch.dict(nftables.__salt__, {'cmd.run': mock}):
                with patch.object(salt.utils, 'fopen', MagicMock(mock_open())):
                    self.assertEqual(nftables.save(), '#! nft -f\n\n')

                with patch.object(salt.utils, 'fopen',
                                  MagicMock(side_effect=IOError)):
                    self.assertRaises(CommandExecutionError, nftables.save)

    # 'get_rule_handle' function tests: 1

    def test_get_rule_handle(self):
        '''
        Test if it get the handle for a particular rule
        '''
        self.assertEqual(nftables.get_rule_handle(),
                         'Error: Chain needs to be specified')

        self.assertEqual(nftables.get_rule_handle(chain='input'),
                         'Error: Rule needs to be specified')

        _ru = 'input tcp dport 22 log accept'
        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.get_rule_handle(chain='input', rule=_ru),
                             ret)

        ret = 'Error: chain input in table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='table ip filter')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.get_rule_handle(chain='input', rule=_ru),
                             ret)

        ret = ('Error: rule input tcp dport 22 log accept chain input'
               ' in table filter in family ipv4 does not exist')
        ret1 = 'Error: could not find rule input tcp dport 22 log accept'
        with patch.object(nftables, 'check_table',
                          MagicMock(return_value=True)):
            with patch.object(nftables, 'check_chain',
                              MagicMock(return_value=True)):
                with patch.object(nftables, 'check',
                                  MagicMock(side_effect=[False, True])):
                    self.assertEqual(nftables.get_rule_handle(chain='input',
                                                              rule=_ru), ret)

                    _ru = 'input tcp dport 22 log accept'
                    mock = MagicMock(return_value='')
                    with patch.dict(nftables.__salt__, {'cmd.run': mock}):
                        self.assertEqual(nftables.get_rule_handle(chain='input',
                                                                  rule=_ru),
                                         ret1)

    # 'check' function tests: 1

    def test_check(self):
        '''
        Test if it check for the existence of a rule in the table and chain
        '''
        self.assertEqual(nftables.check(),
                         'Error: Chain needs to be specified')

        self.assertEqual(nftables.check(chain='input'),
                         'Error: Rule needs to be specified')

        _ru = 'input tcp dport 22 log accept'
        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.check(chain='input', rule=_ru), ret)

        mock = MagicMock(return_value='table ip filter')
        ret = 'Error: chain input in table filter in family ipv4 does not exist'
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.check(chain='input', rule=_ru), ret)

        mock = MagicMock(return_value='table ip filter chain input {{')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertFalse(nftables.check(chain='input', rule=_ru))

        r_val = 'table ip filter chain input {{ input tcp dport 22 log accept #'
        mock = MagicMock(return_value=r_val)
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertTrue(nftables.check(chain='input', rule=_ru))

    # 'check_chain' function tests: 1

    def test_check_chain(self):
        '''
        Test if it check for the existence of a chain in the table
        '''
        self.assertEqual(nftables.check_chain(),
                         'Error: Chain needs to be specified')

        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertFalse(nftables.check_chain(chain='input'))

        mock = MagicMock(return_value='chain input {{')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertTrue(nftables.check_chain(chain='input'))

    # 'check_table' function tests: 1

    def test_check_table(self):
        '''
        Test if it check for the existence of a table
        '''
        self.assertEqual(nftables.check_table(),
                         'Error: table needs to be specified')

        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertFalse(nftables.check_table(table='nat'))

        mock = MagicMock(return_value='table ip nat')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertTrue(nftables.check_table(table='nat'))

    # 'new_table' function tests: 1

    def test_new_table(self):
        '''
        Test if it create new custom table.
        '''
        self.assertEqual(nftables.new_table(table=None),
                         'Error: table needs to be specified')

        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.new_table(table='nat'), True)

        mock = MagicMock(return_value='table ip nat')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.new_table(table='nat'),
                             'Error: table nat in family ipv4 already exists')

    # 'delete_table' function tests: 1

    def test_delete_table(self):
        '''
        Test if it delete custom table.
        '''
        self.assertEqual(nftables.delete_table(table=None),
                         'Error: table needs to be specified')

        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.delete_table(table='nat'),
                             'Error: table nat in family ipv4 does not exist')

        mock = MagicMock(return_value='table ip nat')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.delete_table(table='nat'), 'table ip nat')

    # 'new_chain' function tests: 2

    def test_new_chain(self):
        '''
        Test if it create new chain to the specified table.
        '''
        self.assertEqual(nftables.new_chain(),
                         'Error: Chain needs to be specified')

        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.new_chain(chain='input'), ret)

        ret = 'Error: chain input in table filter in family ipv4 already exists'
        mock = MagicMock(return_value='table ip filter chain input {{')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.new_chain(chain='input'), ret)

    @patch('salt.modules.nftables.check_chain', MagicMock(return_value=False))
    @patch('salt.modules.nftables.check_table', MagicMock(return_value=True))
    def test_new_chain_variable(self):
        '''
        Test if it create new chain to the specified table.
        '''
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.new_chain(chain='input',
                                                table_type='filter'),
                             'Error: table_type hook and priority required')

            self.assertTrue(nftables.new_chain(chain='input',
                                               table_type='filter',
                                               hook='input', priority=0))

    # 'delete_chain' function tests: 1

    def test_delete_chain(self):
        '''
        Test if it delete the chain from the specified table.
        '''
        self.assertEqual(nftables.delete_chain(),
                         'Error: Chain needs to be specified')

        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.delete_chain(chain='input'), ret)

        ret = 'Error: chain input in table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='table ip filter')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.delete_chain(chain='input'), ret)

    @patch('salt.modules.nftables.check_chain', MagicMock(return_value=True))
    @patch('salt.modules.nftables.check_table', MagicMock(return_value=True))
    def test_delete_chain_variables(self):
        '''
        Test if it delete the chain from the specified table.
        '''
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertTrue(nftables.delete_chain(chain='input'))

    # 'append' function tests: 2

    def test_append(self):
        '''
        Test if it append a rule to the specified table & chain.
        '''
        self.assertEqual(nftables.append(),
                         'Error: Chain needs to be specified')

        self.assertEqual(nftables.append(chain='input'),
                         'Error: Rule needs to be specified')

        _ru = 'input tcp dport 22 log accept'
        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.append(chain='input', rule=_ru), ret)

        ret = 'Error: chain input in table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='table ip filter')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.append(chain='input', rule=_ru), ret)

        r_val = 'table ip filter chain input {{ input tcp dport 22 log accept #'
        mock = MagicMock(return_value=r_val)
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertTrue(nftables.append(chain='input', rule=_ru))

    @patch('salt.modules.nftables.check', MagicMock(return_value=False))
    @patch('salt.modules.nftables.check_chain', MagicMock(return_value=True))
    @patch('salt.modules.nftables.check_table', MagicMock(return_value=True))
    def test_append_rule(self):
        '''
        Test if it append a rule to the specified table & chain.
        '''
        _ru = 'input tcp dport 22 log accept'
        mock = MagicMock(side_effect=['1', ''])
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertFalse(nftables.append(chain='input', rule=_ru))
            self.assertTrue(nftables.append(chain='input', rule=_ru))

    # 'insert' function tests: 2

    def test_insert(self):
        '''
        Test if it insert a rule into the specified table & chain,
        at the specified position.
        '''
        self.assertEqual(nftables.insert(),
                         'Error: Chain needs to be specified')

        self.assertEqual(nftables.insert(chain='input'),
                         'Error: Rule needs to be specified')

        _ru = 'input tcp dport 22 log accept'
        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.insert(chain='input', rule=_ru), ret)

        ret = 'Error: chain input in table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='table ip filter')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.insert(chain='input', rule=_ru), ret)

        r_val = 'table ip filter chain input {{ input tcp dport 22 log accept #'
        mock = MagicMock(return_value=r_val)
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertTrue(nftables.insert(chain='input', rule=_ru))

    @patch('salt.modules.nftables.check', MagicMock(return_value=False))
    @patch('salt.modules.nftables.check_chain', MagicMock(return_value=True))
    @patch('salt.modules.nftables.check_table', MagicMock(return_value=True))
    def test_insert_rule(self):
        '''
        Test if it insert a rule into the specified table & chain,
        at the specified position.
        '''
        _ru = 'input tcp dport 22 log accept'
        mock = MagicMock(side_effect=['1', ''])
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertFalse(nftables.insert(chain='input', rule=_ru))
            self.assertTrue(nftables.insert(chain='input', rule=_ru))

    # 'delete' function tests: 2

    def test_delete(self):
        '''
        Test if it delete a rule from the specified table & chain,
        specifying either the rule in its entirety, or
        the rule's position in the chain.
        '''
        _ru = 'input tcp dport 22 log accept'
        self.assertEqual(nftables.delete(table='filter', chain='input',
                                         position='3', rule=_ru),
                         'Error: Only specify a position or a rule, not both')

        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.delete(table='filter', chain='input',
                                             rule=_ru), ret)

        ret = 'Error: chain input in table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='table ip filter')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.delete(table='filter', chain='input',
                                             rule=_ru), ret)

        mock = MagicMock(return_value='table ip filter chain input {{')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertTrue(nftables.delete(table='filter', chain='input',
                                            rule=_ru))

    @patch('salt.modules.nftables.check', MagicMock(return_value=True))
    @patch('salt.modules.nftables.check_chain', MagicMock(return_value=True))
    @patch('salt.modules.nftables.check_table', MagicMock(return_value=True))
    def test_delete_rule(self):
        '''
        Test if it delete a rule from the specified table & chain,
        specifying either the rule in its entirety, or
        the rule's position in the chain.
        '''
        mock = MagicMock(side_effect=['1', ''])
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertFalse(nftables.delete(table='filter', chain='input',
                                             position='3'))
            self.assertTrue(nftables.delete(table='filter', chain='input',
                                            position='3'))

    # 'flush' function tests: 2

    def test_flush(self):
        '''
        Test if it flush the chain in the specified table, flush all chains
        in the specified table if chain is not specified.
        '''
        ret = 'Error: table filter in family ipv4 does not exist'
        mock = MagicMock(return_value='')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.flush(table='filter', chain='input'), ret)

        ret = 'Error: chain input in table filter in family ip does not exist'
        mock = MagicMock(return_value='table ip filter')
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertEqual(nftables.flush(table='filter', chain='input'), ret)

    @patch('salt.modules.nftables.check_chain', MagicMock(return_value=True))
    @patch('salt.modules.nftables.check_table', MagicMock(return_value=True))
    def test_flush_chain(self):
        '''
        Test if it flush the chain in the specified table, flush all chains
        in the specified table if chain is not specified.
        '''
        mock = MagicMock(side_effect=['1', ''])
        with patch.dict(nftables.__salt__, {'cmd.run': mock}):
            self.assertFalse(nftables.flush(table='filter', chain='input'))
            self.assertTrue(nftables.flush(table='filter', chain='input'))
