# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import textwrap

# Import Salt Libs
from salt.modules import parallels
from salt.exceptions import SaltInvocationError

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

# Import third party libs
import salt.ext.six as six

ensure_in_syspath('../../')
parallels.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ParallelsTestCase(TestCase):
    '''
    Test parallels desktop execution module functions
    '''
    def test___virtual__(self):
        '''
        Test parallels.__virtual__
        '''
        mock_true = MagicMock(return_value=True)
        mock_false = MagicMock(return_value=False)

        # Validate false return
        with patch('salt.utils.which', mock_false):
            ret = parallels.__virtual__()
            self.assertTrue(isinstance(ret, tuple))
            self.assertEqual(len(ret), 2)
            self.assertFalse(ret[0])
            self.assertTrue(isinstance(ret[1], six.string_types))

        # Validate true return
        with patch('salt.utils.which', mock_true):
            ret = parallels.__virtual__()
            self.assertTrue(ret)
            self.assertEqual(ret, 'parallels')

    def test__normalize_args(self):
        '''
        Test parallels._normalize_args
        '''
        def _validate_ret(ret):
            '''
            Assert that the returned data is a list of strings
            '''
            self.assertTrue(isinstance(ret, list))
            for arg in ret:
                self.assertTrue(isinstance(arg, six.string_types))

        # Validate string arguments
        str_args = 'electrolytes --aqueous --anion hydroxide --cation=ammonium free radicals -- hydrogen'
        _validate_ret(parallels._normalize_args(str_args))

        # Validate list arguments
        list_args = ' '.join(str_args)
        _validate_ret(parallels._normalize_args(list_args))

        # Validate tuple arguments
        tuple_args = tuple(list_args)
        _validate_ret(parallels._normalize_args(tuple_args))

        # Validate dictionary arguments
        other_args = {'anion': 'hydroxide', 'cation': 'ammonium'}
        _validate_ret(parallels._normalize_args(other_args))

    def test__find_guids(self):
        '''
        Test parallels._find_guids
        '''
        guid_str = textwrap.dedent('''
            PARENT_SNAPSHOT_ID                      SNAPSHOT_ID
                                                    {a5b8999f-5d95-4aff-82de-e515b0101b66}
            {a5b8999f-5d95-4aff-82de-e515b0101b66} *{a7345be5-ab66-478c-946e-a6c2caf14909}
        ''')
        guids = set(['a5b8999f-5d95-4aff-82de-e515b0101b66',
                     'a7345be5-ab66-478c-946e-a6c2caf14909'])

        self.assertEqual(parallels._find_guids(guid_str), guids)

    def test_prlctl(self):
        '''
        Test parallels.prlctl
        '''
        runas = 'macdev'

        # Validate 'prlctl user list'
        user_cmd = ['prlctl', 'user', 'list']
        user_fcn = MagicMock()
        with patch.dict(parallels.__salt__, {'cmd.run': user_fcn}):
            parallels.prlctl('user', 'list', runas=runas)
            user_fcn.assert_called_once_with(user_cmd, runas=runas)

        # Validate 'prlctl exec macvm uname'
        exec_cmd = ['prlctl', 'exec', 'macvm', 'uname']
        exec_fcn = MagicMock()
        with patch.dict(parallels.__salt__, {'cmd.run': exec_fcn}):
            parallels.prlctl('exec', 'macvm uname', runas=runas)
            exec_fcn.assert_called_once_with(exec_cmd, runas=runas)

    def test_list_vms(self):
        '''
        Test parallels.list_vms
        '''
        runas = 'macdev'

        # Validate a simple list
        mock_plain = MagicMock()
        with patch.object(parallels, 'prlctl', mock_plain):
            parallels.list_vms(runas=runas)
            mock_plain.assert_called_once_with('list', [], runas=runas)

        # Validate listing a single VM
        mock_name = MagicMock()
        with patch.object(parallels, 'prlctl', mock_name):
            parallels.list_vms(name='macvm', runas=runas)
            mock_name.assert_called_once_with('list',
                                              ['--info', 'macvm'],
                                              runas=runas)

        # Validate listing extra info
        mock_info = MagicMock()
        with patch.object(parallels, 'prlctl', mock_info):
            parallels.list_vms(info=True, runas=runas)
            mock_info.assert_called_once_with('list',
                                              ['--info'],
                                              runas=runas)

        # Validate listing with extra options
        mock_complex = MagicMock()
        with patch.object(parallels, 'prlctl', mock_complex):
            parallels.list_vms(args=' -o uuid,status', all=True, runas=runas)
            mock_complex.assert_called_once_with('list',
                                                 ['-o', 'uuid,status', '--all'],
                                                 runas=runas)

    def test_start(self):
        '''
        Test parallels.start
        '''
        name = 'macvm'
        runas = 'macdev'

        mock_start = MagicMock()
        with patch.object(parallels, 'prlctl', mock_start):
            parallels.start(name, runas=runas)
            mock_start.assert_called_once_with('start', name, runas=runas)

    def test_stop(self):
        '''
        Test parallels.stop
        '''
        name = 'macvm'
        runas = 'macdev'

        # Validate stop
        mock_stop = MagicMock()
        with patch.object(parallels, 'prlctl', mock_stop):
            parallels.stop(name, runas=runas)
            mock_stop.assert_called_once_with('stop', [name], runas=runas)

        # Validate immediate stop
        mock_kill = MagicMock()
        with patch.object(parallels, 'prlctl', mock_kill):
            parallels.stop(name, kill=True, runas=runas)
            mock_kill.assert_called_once_with('stop', [name, '--kill'], runas=runas)

    def test_restart(self):
        '''
        Test parallels.restart
        '''
        name = 'macvm'
        runas = 'macdev'

        mock_start = MagicMock()
        with patch.object(parallels, 'prlctl', mock_start):
            parallels.restart(name, runas=runas)
            mock_start.assert_called_once_with('restart', name, runas=runas)

    def test_reset(self):
        '''
        Test parallels.reset
        '''
        name = 'macvm'
        runas = 'macdev'

        mock_start = MagicMock()
        with patch.object(parallels, 'prlctl', mock_start):
            parallels.reset(name, runas=runas)
            mock_start.assert_called_once_with('reset', name, runas=runas)

    def test_status(self):
        '''
        Test parallels.status
        '''
        name = 'macvm'
        runas = 'macdev'

        mock_start = MagicMock()
        with patch.object(parallels, 'prlctl', mock_start):
            parallels.status(name, runas=runas)
            mock_start.assert_called_once_with('status', name, runas=runas)

    def test_exec_(self):
        '''
        Test parallels.exec_
        '''
        name = 'macvm'
        runas = 'macdev'

        mock_start = MagicMock()
        with patch.object(parallels, 'prlctl', mock_start):
            parallels.exec_(name, 'find /etc/paths.d', runas=runas)
            mock_start.assert_called_once_with('exec',
                                               [name, 'find', '/etc/paths.d'],
                                               runas=runas)

    def test_snapshot_id_to_name(self):
        '''
        Test parallels.snapshot_id_to_name
        '''
        name = 'macvm'
        snap_id = 'a5b8999f-5d95-4aff-82de-e515b0101b66'

        # Invalid GUID raises error
        self.assertRaises(SaltInvocationError,
                          parallels.snapshot_id_to_name,
                          name,
                          '{8-4-4-4-12}')

        # Empty return from prlctl raises error (name/snap_id mismatch?)
        mock_no_data = MagicMock(return_value='')
        with patch.object(parallels, 'prlctl', mock_no_data):
            self.assertRaises(SaltInvocationError,
                              parallels.snapshot_id_to_name,
                              name,
                              snap_id)

        # Data returned from prlctl is invalid YAML
        mock_invalid_data = MagicMock(return_value='[string theory is falsifiable}')
        with patch.object(parallels, 'prlctl', mock_invalid_data):
            snap_name = parallels.snapshot_id_to_name(name, snap_id)
            self.assertEqual(snap_name, '')

        # Data returned from prlctl does not render as a dictionary
        mock_unknown_data = MagicMock(return_value="['sfermions', 'bosinos']")
        with patch.object(parallels, 'prlctl', mock_unknown_data):
            snap_name = parallels.snapshot_id_to_name(name, snap_id)
            self.assertEqual(snap_name, '')

        # Snapshot is unnamed
        mock_no_name = MagicMock(return_value='Name:')
        with patch.object(parallels, 'prlctl', mock_no_name):
            snap_name = parallels.snapshot_id_to_name(name, snap_id)
            self.assertEqual(snap_name, '')

        # If strict, then raise an error when name is not found
        mock_no_name = MagicMock(return_value='Name:')
        with patch.object(parallels, 'prlctl', mock_no_name):
            self.assertRaises(SaltInvocationError,
                              parallels.snapshot_id_to_name,
                              name,
                              snap_id,
                              strict=True)

        # Return name when found
        mock_yes_name = MagicMock(return_value='Name: top')
        with patch.object(parallels, 'prlctl', mock_yes_name):
            snap_name = parallels.snapshot_id_to_name(name, snap_id)
            self.assertEqual(snap_name, 'top')

    def test_snapshot_name_to_id(self):
        '''
        Test parallels.snapshot_name_to_id
        '''
        name = 'macvm'
        snap_ids = ['a5b8999f-5d95-4aff-82de-e515b0101b66',
                    'a7345be5-ab66-478c-946e-a6c2caf14909']
        snap_id = snap_ids[0]
        guid_str = textwrap.dedent('''
            PARENT_SNAPSHOT_ID                      SNAPSHOT_ID
                                                    {a5b8999f-5d95-4aff-82de-e515b0101b66}
            {a5b8999f-5d95-4aff-82de-e515b0101b66} *{a7345be5-ab66-478c-946e-a6c2caf14909}
        ''')
        mock_guids = MagicMock(return_value=guid_str)

        # Raise error when no IDs found for snapshot name
        with patch.object(parallels, 'prlctl', mock_guids):
            mock_no_names = MagicMock(return_value=[])
            with patch.object(parallels, 'snapshot_id_to_name', mock_no_names):
                self.assertRaises(SaltInvocationError,
                                  parallels.snapshot_name_to_id,
                                  name,
                                  'graviton')

        # Validate singly-valued name
        with patch.object(parallels, 'prlctl', mock_guids):
            mock_one_name = MagicMock(side_effect=[u'', u'ν_e'])
            with patch.object(parallels, 'snapshot_id_to_name', mock_one_name):
                self.assertEqual(parallels.snapshot_name_to_id(name, u'ν_e'), snap_id)

        # Validate multiply-valued name
        with patch.object(parallels, 'prlctl', mock_guids):
            mock_many_names = MagicMock(side_effect=[u'J/Ψ', u'J/Ψ'])
            with patch.object(parallels, 'snapshot_id_to_name', mock_many_names):
                self.assertEqual(sorted(parallels.snapshot_name_to_id(name, u'J/Ψ')),
                                 sorted(snap_ids))

        # Raise error for multiply-valued name
        with patch.object(parallels, 'prlctl', mock_guids):
            mock_many_names = MagicMock(side_effect=[u'J/Ψ', u'J/Ψ'])
            with patch.object(parallels, 'snapshot_id_to_name', mock_many_names):
                self.assertRaises(SaltInvocationError,
                                  parallels.snapshot_name_to_id,
                                  name,
                                  u'J/Ψ',
                                  strict=True)

    def test__validate_snap_name(self):
        '''
        Test parallels._validate_snap_name
        '''
        name = 'macvm'
        snap_id = 'a5b8999f-5d95-4aff-82de-e515b0101b66'

        # Validate a GUID passthrough
        self.assertEqual(parallels._validate_snap_name(name, snap_id), snap_id)

        # Validate an unicode name
        mock_snap_symb = MagicMock(return_value=snap_id)
        with patch.object(parallels, 'snapshot_name_to_id', mock_snap_symb):
            self.assertEqual(parallels._validate_snap_name(name, u'π'), snap_id)
            mock_snap_symb.assert_called_once_with(name, u'π', strict=True, runas=None)

        # Validate an ascii name
        mock_snap_name = MagicMock(return_value=snap_id)
        with patch.object(parallels, 'snapshot_name_to_id', mock_snap_name):
            self.assertEqual(parallels._validate_snap_name(name, 'pion'), snap_id)
            mock_snap_name.assert_called_once_with(name, 'pion', strict=True, runas=None)

        # Validate a numerical name
        mock_snap_numb = MagicMock(return_value=snap_id)
        with patch.object(parallels, 'snapshot_name_to_id', mock_snap_numb):
            self.assertEqual(parallels._validate_snap_name(name, 3.14159), snap_id)
            mock_snap_numb.assert_called_once_with(name, u'3.14159', strict=True, runas=None)

    def test_list_snapshots(self):
        '''
        Test parallels.list_snapshots
        '''
        name = 'macvm'
        guid_str = textwrap.dedent('''
            PARENT_SNAPSHOT_ID                      SNAPSHOT_ID
                                                    {a5b8999f-5d95-4aff-82de-e515b0101b66}
            {a5b8999f-5d95-4aff-82de-e515b0101b66} *{a7345be5-ab66-478c-946e-a6c2caf14909}
            {a5b8999f-5d95-4aff-82de-e515b0101b66}  {5da9faef-cb0e-466d-9b41-e5571b62ac2a}
        ''')

        # Validate listing all snapshots for the VM
        mock_prlctl = MagicMock(return_value=guid_str)
        with patch.object(parallels, 'prlctl', mock_prlctl):
            parallels.list_snapshots(name)
            mock_prlctl.assert_called_once_with('snapshot-list', [name], runas=None)

        # Validate listing all snapshots in tree mode
        mock_prlctl = MagicMock(return_value=guid_str)
        with patch.object(parallels, 'prlctl', mock_prlctl):
            parallels.list_snapshots(name, tree=True)
            mock_prlctl.assert_called_once_with('snapshot-list', [name, '--tree'], runas=None)

        # Validate listing a single snapshot
        snap_name = 'muon'
        mock_snap_name = MagicMock(return_value=snap_name)
        with patch.object(parallels, '_validate_snap_name', mock_snap_name):
            mock_prlctl = MagicMock(return_value=guid_str)
            with patch.object(parallels, 'prlctl', mock_prlctl):
                parallels.list_snapshots(name, snap_name)
                mock_prlctl.assert_called_once_with('snapshot-list',
                                                    [name, '--id', snap_name],
                                                    runas=None)

        # Validate listing snapshot ID and name pairs
        snap_names = ['electron', 'muon', 'tauon']
        mock_snap_name = MagicMock(side_effect=snap_names)
        with patch.object(parallels, 'snapshot_id_to_name', mock_snap_name):
            mock_prlctl = MagicMock(return_value=guid_str)
            with patch.object(parallels, 'prlctl', mock_prlctl):
                ret = parallels.list_snapshots(name, names=True)
                for snap_name in snap_names:
                    self.assertIn(snap_name, ret)
                mock_prlctl.assert_called_once_with('snapshot-list', [name], runas=None)

    def test_snapshot(self):
        '''
        Test parallels.snapshot
        '''
        name = 'macvm'

        # Validate creating a snapshot
        mock_snap = MagicMock(return_value='')
        with patch.object(parallels, 'prlctl', mock_snap):
            parallels.snapshot(name)
            mock_snap.assert_called_once_with('snapshot', [name], runas=None)

        # Validate creating a snapshot with a name
        snap_name = 'h_0'
        mock_snap_name = MagicMock(return_value='')
        with patch.object(parallels, 'prlctl', mock_snap_name):
            parallels.snapshot(name, snap_name)
            mock_snap_name.assert_called_once_with('snapshot',
                                                   [name, '--name', snap_name],
                                                   runas=None)

        # Validate creating a snapshot with a name and a description
        snap_name = 'h_0'
        snap_desc = textwrap.dedent('The ground state particle of the higgs '
            'multiplet family of bosons')
        mock_snap_name = MagicMock(return_value='')
        with patch.object(parallels, 'prlctl', mock_snap_name):
            parallels.snapshot(name, snap_name, snap_desc)
            mock_snap_name.assert_called_once_with('snapshot',
                                                   [name,
                                                    '--name', snap_name,
                                                    '--description', snap_desc],
                                                   runas=None)

    def test_delete_snapshot(self):
        '''
        Test parallels.delete_snapshot
        '''
        name = 'macvm'
        snap_name = 'kaon'
        snap_id = 'c2eab062-a635-4ccd-b9ae-998370f898b5'

        mock_snap_name = MagicMock(return_value=snap_id)
        with patch.object(parallels, '_validate_snap_name', mock_snap_name):
            mock_delete = MagicMock(return_value='')
            with patch.object(parallels, 'prlctl', mock_delete):
                parallels.delete_snapshot(name, snap_name)
                mock_delete.assert_called_once_with('snapshot-delete',
                                                    [name, '--id', snap_id],
                                                    runas=None)

    def test_revert_snapshot(self):
        '''
        Test parallels.revert_snapshot
        '''
        name = 'macvm'
        snap_name = 'k-bar'
        snap_id = 'c2eab062-a635-4ccd-b9ae-998370f898b5'

        mock_snap_name = MagicMock(return_value=snap_id)
        with patch.object(parallels, '_validate_snap_name', mock_snap_name):
            mock_delete = MagicMock(return_value='')
            with patch.object(parallels, 'prlctl', mock_delete):
                parallels.revert_snapshot(name, snap_name)
                mock_delete.assert_called_once_with('snapshot-switch',
                                                    [name, '--id', snap_id],
                                                    runas=None)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ParallelsTestCase, needs_daemon=False)
