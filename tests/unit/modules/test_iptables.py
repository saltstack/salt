# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import uuid

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.iptables as iptables


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IptablesTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.iptables
    '''
    def setup_loader_modules(self):
        return {iptables: {}}

    # 'version' function tests: 1

    def test_version(self):
        '''
        Test if it return version from iptables --version
        '''
        mock = MagicMock(return_value='iptables v1.4.21')
        with patch.dict(iptables.__salt__, {'cmd.run': mock}):
            self.assertEqual(iptables.version(), 'v1.4.21')

    # 'build_rule' function tests: 1

    def test_build_rule(self):
        '''
        Test if it build a well-formatted iptables rule based on kwargs.
        '''
        with patch.object(iptables, '_has_option', MagicMock(return_value=True)):
            self.assertEqual(iptables.build_rule(), '')

            self.assertEqual(iptables.build_rule(name='ignored', state='ignored'),
                             '',
                             'build_rule should ignore name and state')

            # Should properly negate bang-prefixed values
            self.assertEqual(iptables.build_rule(**{'if': '!eth0'}),
                             '! -i eth0')

            # Should properly negate "not"-prefixed values
            self.assertEqual(iptables.build_rule(**{'if': 'not eth0'}),
                             '! -i eth0')

            self.assertEqual(iptables.build_rule(dports=[80, 443], proto='tcp'),
                             '-p tcp -m multiport --dports 80,443')

            self.assertEqual(iptables.build_rule(dports='80,443', proto='tcp'),
                             '-p tcp -m multiport --dports 80,443')

            # Should it really behave this way?
            self.assertEqual(iptables.build_rule(dports=['!80', 443],
                                                 proto='tcp'),
                             '-p tcp -m multiport ! --dports 80,443')

            self.assertEqual(iptables.build_rule(dports='!80,443', proto='tcp'),
                             '-p tcp -m multiport ! --dports 80,443')

            self.assertEqual(iptables.build_rule(sports=[80, 443], proto='tcp'),
                             '-p tcp -m multiport --sports 80,443')

            self.assertEqual(iptables.build_rule(sports='80,443', proto='tcp'),
                             '-p tcp -m multiport --sports 80,443')

            self.assertEqual(iptables.build_rule('filter', 'INPUT', command='I',
                                                 position='3', full=True,
                                                 dports='proto', jump='ACCEPT'),
                             'Error: proto must be specified')

            self.assertEqual(iptables.build_rule('filter', 'INPUT', command='I',
                                                 position='3', full=True,
                                                 sports='proto', jump='ACCEPT'),
                             'Error: proto must be specified')

            self.assertEqual(iptables.build_rule('', 'INPUT', command='I',
                                                 position='3', full='True',
                                                 match='state', jump='ACCEPT'),
                             'Error: Table needs to be specified')

            self.assertEqual(iptables.build_rule('filter', '', command='I',
                                                 position='3', full='True',
                                                 match='state', jump='ACCEPT'),
                             'Error: Chain needs to be specified')

            self.assertEqual(iptables.build_rule('filter', 'INPUT', command='',
                                                 position='3', full='True',
                                                 match='state', jump='ACCEPT'),
                             'Error: Command needs to be specified')

            # Test arguments that should appear after the --jump
            self.assertEqual(iptables.build_rule(jump='REDIRECT',
                                                 **{'to-port': 8080}),
                             '--jump REDIRECT --to-port 8080')

            # Should quote arguments with spaces, like log-prefix often has
            self.assertEqual(iptables.build_rule(jump='LOG',
                                                 **{'log-prefix': 'long prefix'}),
                             '--jump LOG --log-prefix "long prefix"')

            # Should quote arguments with leading or trailing spaces
            self.assertEqual(iptables.build_rule(jump='LOG',
                                                 **{'log-prefix': 'spam: '}),
                             '--jump LOG --log-prefix "spam: "')

            # Should allow no-arg jump options
            self.assertEqual(iptables.build_rule(jump='CLUSTERIP',
                                                 **{'new': ''}),
                             '--jump CLUSTERIP --new')

            # Should allow no-arg jump options as None
            self.assertEqual(iptables.build_rule(jump='CT',
                                                 **{'notrack': None}),
                             '--jump CT --notrack')

            # should build match-sets with single string
            self.assertEqual(iptables.build_rule(**{'match-set': 'src flag1,flag2'}),
                             '-m set --match-set src flag1,flag2')

            # should build match-sets as list
            match_sets = ['src1 flag1',
                          'src2 flag2,flag3',
                         ]
            self.assertEqual(iptables.build_rule(**{'match-set': match_sets}),
                             '-m set --match-set src1 flag1 -m set --match-set src2 flag2,flag3')

            # should handle negations for string match-sets
            self.assertEqual(iptables.build_rule(**{'match-set': '!src flag'}),
                             '-m set ! --match-set src flag')

            # should handle negations for list match-sets
            match_sets = ['src1 flag',
                          'not src2 flag2']
            self.assertEqual(iptables.build_rule(**{'match-set': match_sets}),
                             '-m set --match-set src1 flag -m set ! --match-set src2 flag2')

            # should allow escaped name
            self.assertEqual(iptables.build_rule(**{'match': 'recent', 'name_': 'SSH'}),
                             '-m recent --name SSH')

            # should allow empty arguments
            self.assertEqual(iptables.build_rule(**{'match': 'recent', 'update': None}),
                             '-m recent --update')

            # Should allow the --save jump option to CONNSECMARK
            #self.assertEqual(iptables.build_rule(jump='CONNSECMARK',
            #                                     **{'save': ''}),
            #                 '--jump CONNSECMARK --save ')

            ret = '/sbin/iptables --wait -t salt -I INPUT 3 -m state --jump ACCEPT'
            with patch.object(iptables, '_iptables_cmd',
                              MagicMock(return_value='/sbin/iptables')):
                self.assertEqual(iptables.build_rule('salt', 'INPUT', command='I',
                                                     position='3', full='True',
                                                     match='state', jump='ACCEPT'),
                                 ret)

    # 'get_saved_rules' function tests: 1

    def test_get_saved_rules(self):
        '''
        Test if it return a data structure of the rules in the conf file
        '''
        mock = MagicMock(return_value=False)
        with patch.object(iptables, '_parse_conf', mock):
            self.assertFalse(iptables.get_saved_rules())
            mock.assert_called_with(conf_file=None, family='ipv4')

    # 'get_rules' function tests: 1

    def test_get_rules(self):
        '''
        Test if it return a data structure of the current, in-memory rules
        '''
        mock = MagicMock(return_value=False)
        with patch.object(iptables, '_parse_conf', mock):
            self.assertFalse(iptables.get_rules())
            mock.assert_called_with(in_mem=True, family='ipv4')

    # 'get_saved_policy' function tests: 1

    def test_get_saved_policy(self):
        '''
        Test if it return the current policy for the specified table/chain
        '''
        self.assertEqual(iptables.get_saved_policy(table='filter', chain=None,
                                                   conf_file=None,
                                                   family='ipv4'),
                         'Error: Chain needs to be specified')

        with patch.object(iptables, '_parse_conf',
                          MagicMock(return_value={'filter':
                                                  {'INPUT':
                                                   {'policy': True}}})):
            self.assertTrue(iptables.get_saved_policy(table='filter',
                                                       chain='INPUT',
                                                       conf_file=None,
                                                       family='ipv4'))

        with patch.object(iptables, '_parse_conf',
                          MagicMock(return_value={'filter':
                                                  {'INPUT':
                                                   {'policy1': True}}})):
            self.assertIsNone(iptables.get_saved_policy(table='filter',
                                                       chain='INPUT',
                                                       conf_file=None,
                                                       family='ipv4'))

    # 'get_policy' function tests: 1

    def test_get_policy(self):
        '''
        Test if it return the current policy for the specified table/chain
        '''
        self.assertEqual(iptables.get_policy(table='filter', chain=None,
                                                   family='ipv4'),
                         'Error: Chain needs to be specified')

        with patch.object(iptables, '_parse_conf',
                          MagicMock(return_value={'filter':
                                                  {'INPUT':
                                                   {'policy': True}}})):
            self.assertTrue(iptables.get_policy(table='filter',
                                                       chain='INPUT',
                                                       family='ipv4'))

        with patch.object(iptables, '_parse_conf',
                          MagicMock(return_value={'filter':
                                                  {'INPUT':
                                                   {'policy1': True}}})):
            self.assertIsNone(iptables.get_policy(table='filter',
                                                       chain='INPUT',
                                                       family='ipv4'))

    # 'set_policy' function tests: 1

    def test_set_policy(self):
        '''
        Test if it set the current policy for the specified table/chain
        '''
        with patch.object(iptables, '_has_option', MagicMock(return_value=True)):
            self.assertEqual(iptables.set_policy(table='filter', chain=None,
                                                       policy=None,
                                                       family='ipv4'),
                             'Error: Chain needs to be specified')

            self.assertEqual(iptables.set_policy(table='filter', chain='INPUT',
                                                       policy=None,
                                                       family='ipv4'),
                             'Error: Policy needs to be specified')

            mock = MagicMock(return_value=True)
            with patch.dict(iptables.__salt__, {'cmd.run': mock}):
                self.assertTrue(iptables.set_policy(table='filter',
                                                           chain='INPUT',
                                                           policy='ACCEPT',
                                                           family='ipv4'))

    # 'save' function tests: 1

    def test_save(self):
        '''
        Test if it save the current in-memory rules to disk
        '''
        with patch('salt.modules.iptables._conf', MagicMock(return_value=False)), \
                patch('os.path.isdir', MagicMock(return_value=True)):
            mock = MagicMock(return_value=True)
            with patch.dict(iptables.__salt__, {'cmd.run': mock,
                                                'file.write': mock,
                                                'config.option': MagicMock(return_value=[])}):
                self.assertTrue(iptables.save(filename='/xyz', family='ipv4'))

    # 'check' function tests: 1

    def test_check(self):
        '''
        Test if it check for the existence of a rule in the table and chain
        '''
        self.assertEqual(iptables.check(table='filter', chain=None,
                                                   rule=None,
                                                   family='ipv4'),
                         'Error: Chain needs to be specified')

        self.assertEqual(iptables.check(table='filter', chain='INPUT',
                                                   rule=None,
                                                   family='ipv4'),
                         'Error: Rule needs to be specified')

        mock_rule = 'm state --state RELATED,ESTABLISHED -j ACCEPT'
        mock_chain = 'INPUT'
        mock_uuid = 31337
        mock_cmd = MagicMock(return_value='-A {0}\n-A {1}'.format(mock_chain,
                                                                 hex(mock_uuid)))
        mock_has = MagicMock(return_value=True)
        mock_not = MagicMock(return_value=False)

        with patch.object(iptables, '_has_option', mock_not):
            with patch.object(uuid, 'getnode', MagicMock(return_value=mock_uuid)):
                with patch.dict(iptables.__salt__, {'cmd.run': mock_cmd}):
                    self.assertTrue(iptables.check(table='filter', chain=mock_chain,
                                                   rule=mock_rule, family='ipv4'))

        mock_cmd = MagicMock(return_value='')

        with patch.object(iptables, '_has_option', mock_not):
            with patch.object(uuid, 'getnode', MagicMock(return_value=mock_uuid)):
                with patch.dict(iptables.__salt__, {'cmd.run': MagicMock(return_value='')}):
                    self.assertFalse(iptables.check(table='filter', chain=mock_chain,
                                                    rule=mock_rule, family='ipv4'))

        with patch.object(iptables, '_has_option', mock_has):
            with patch.dict(iptables.__salt__, {'cmd.run': mock_cmd}):
                self.assertTrue(iptables.check(table='filter', chain='INPUT',
                                               rule=mock_rule, family='ipv4'))

        mock_cmd = MagicMock(return_value='-A 0x4d2')
        mock_uuid = MagicMock(return_value=1234)

        with patch.object(iptables, '_has_option', mock_has):
            with patch.object(uuid, 'getnode', mock_uuid):
                with patch.dict(iptables.__salt__, {'cmd.run': mock_cmd}):
                    self.assertTrue(iptables.check(table='filter',
                                                   chain='0x4d2',
                                                   rule=mock_rule, family='ipv4'))

    # 'check_chain' function tests: 1

    def test_check_chain(self):
        '''
        Test if it check for the existence of a chain in the table
        '''
        self.assertEqual(iptables.check_chain(table='filter', chain=None,
                                                   family='ipv4'),
                         'Error: Chain needs to be specified')

        mock_cmd = MagicMock(return_value='')
        with patch.dict(iptables.__salt__, {'cmd.run': mock_cmd}):
            self.assertFalse(iptables.check_chain(table='filter',
                                                       chain='INPUT',
                                                       family='ipv4'))

    # 'new_chain' function tests: 1

    def test_new_chain(self):
        '''
        Test if it create new custom chain to the specified table.
        '''
        self.assertEqual(iptables.new_chain(table='filter', chain=None,
                                                   family='ipv4'),
                         'Error: Chain needs to be specified')

        mock_cmd = MagicMock(return_value='')
        with patch.dict(iptables.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(iptables.new_chain(table='filter',
                                                       chain='INPUT',
                                                       family='ipv4'))

    # 'delete_chain' function tests: 1

    def test_delete_chain(self):
        '''
        Test if it delete custom chain to the specified table.
        '''
        self.assertEqual(iptables.delete_chain(table='filter', chain=None,
                                                   family='ipv4'),
                         'Error: Chain needs to be specified')

        mock_cmd = MagicMock(return_value='')
        with patch.dict(iptables.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(iptables.delete_chain(table='filter',
                                                       chain='INPUT',
                                                       family='ipv4'))

    # 'append' function tests: 1

    def test_append(self):
        '''
        Test if it append a rule to the specified table/chain.
        '''
        with patch.object(iptables, '_has_option', MagicMock(return_value=True)), \
                patch.object(iptables, 'check', MagicMock(return_value=False)):
            self.assertEqual(iptables.append(table='filter', chain=None,
                                                       rule=None,
                                                       family='ipv4'),
                             'Error: Chain needs to be specified')

            self.assertEqual(iptables.append(table='filter', chain='INPUT',
                                                       rule=None,
                                                       family='ipv4'),
                             'Error: Rule needs to be specified')

            _rule = 'm state --state RELATED,ESTABLISHED -j ACCEPT'
            mock = MagicMock(side_effect=['', 'SALT'])
            with patch.dict(iptables.__salt__, {'cmd.run': mock}):
                self.assertTrue(iptables.append(table='filter', chain='INPUT',
                                                rule=_rule, family='ipv4'))

                self.assertFalse(iptables.append(table='filter', chain='INPUT',
                                                rule=_rule, family='ipv4'))

    # 'insert' function tests: 1

    def test_insert(self):
        '''
        Test if it insert a rule into the specified table/chain,
        at the specified position.
        '''
        with patch.object(iptables, '_has_option', MagicMock(return_value=True)), \
                patch.object(iptables, 'check', MagicMock(return_value=False)):
            self.assertEqual(iptables.insert(table='filter', chain=None,
                                             position=None, rule=None,
                                                       family='ipv4'),
                             'Error: Chain needs to be specified')

            pos_err = 'Error: Position needs to be specified or use append (-A)'
            self.assertEqual(iptables.insert(table='filter', chain='INPUT',
                                             position=None, rule=None,
                                                       family='ipv4'), pos_err)

            self.assertEqual(iptables.insert(table='filter', chain='INPUT',
                                             position=3, rule=None,
                                                       family='ipv4'),
                             'Error: Rule needs to be specified')

            _rule = 'm state --state RELATED,ESTABLISHED -j ACCEPT'
            mock = MagicMock(return_value=True)
            with patch.dict(iptables.__salt__, {'cmd.run': mock}):
                self.assertTrue(iptables.insert(table='filter', chain='INPUT',
                                                position=3, rule=_rule,
                                                family='ipv4'))

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test if it delete a rule from the specified table/chain
        '''
        with patch.object(iptables, '_has_option', MagicMock(return_value=True)):
            _rule = 'm state --state RELATED,ESTABLISHED -j ACCEPT'
            self.assertEqual(iptables.delete(table='filter', chain=None,
                                             position=3, rule=_rule,
                                                       family='ipv4'),
                             'Error: Only specify a position or a rule, not both')

            mock = MagicMock(return_value=True)
            with patch.dict(iptables.__salt__, {'cmd.run': mock}):
                self.assertTrue(iptables.delete(table='filter', chain='INPUT',
                                                position=3, rule='',
                                                family='ipv4'))

    # 'flush' function tests: 1

    def test_flush(self):
        '''
        Test if it flush the chain in the specified table,
        flush all chains in the specified table if not specified chain.
        '''
        with patch.object(iptables, '_has_option', MagicMock(return_value=True)):
            mock_cmd = MagicMock(return_value=True)
            with patch.dict(iptables.__salt__, {'cmd.run': mock_cmd}):
                self.assertTrue(iptables.flush(table='filter',
                                                           chain='INPUT',
                                                           family='ipv4'))
