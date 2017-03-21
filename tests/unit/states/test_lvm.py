# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.lvm as lvm

lvm.__opts__ = {}
lvm.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LvmTestCase(TestCase):
    '''
    Test cases for salt.states.lvm
    '''
    # 'pv_present' function tests: 1

    def test_pv_present(self):
        '''
        Test to set a physical device to be used as an LVM physical volume
        '''
        name = '/dev/sda5'

        comt = ('Physical Volume {0} already present'.format(name))

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': comt}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(lvm.__salt__, {'lvm.pvdisplay': mock}):
            self.assertDictEqual(lvm.pv_present(name), ret)

            comt = ('Physical Volume {0} is set to be created'.format(name))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(lvm.__opts__, {'test': True}):
                self.assertDictEqual(lvm.pv_present(name), ret)

    # 'pv_absent' function tests: 1

    def test_pv_absent(self):
        '''
        Test to ensure that a Physical Device is not being used by lvm
        '''
        name = '/dev/sda5'

        comt = ('Physical Volume {0} does not exist'.format(name))

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': comt}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(lvm.__salt__, {'lvm.pvdisplay': mock}):
            self.assertDictEqual(lvm.pv_absent(name), ret)

            comt = ('Physical Volume {0} is set to be removed'.format(name))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(lvm.__opts__, {'test': True}):
                self.assertDictEqual(lvm.pv_absent(name), ret)

    # 'vg_present' function tests: 1

    def test_vg_present(self):
        '''
        Test to create an LVM volume group
        '''
        name = '/dev/sda5'

        comt = ('Failed to create Volume Group {0}'.format(name))

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': comt}

        mock = MagicMock(return_value=False)
        with patch.dict(lvm.__salt__, {'lvm.vgdisplay': mock,
                                       'lvm.vgcreate': mock}):
            with patch.dict(lvm.__opts__, {'test': False}):
                self.assertDictEqual(lvm.vg_present(name), ret)

            comt = ('Volume Group {0} is set to be created'.format(name))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(lvm.__opts__, {'test': True}):
                self.assertDictEqual(lvm.vg_present(name), ret)

    # 'vg_absent' function tests: 1

    def test_vg_absent(self):
        '''
        Test to remove an LVM volume group
        '''
        name = '/dev/sda5'

        comt = ('Volume Group {0} already absent'.format(name))

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': comt}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(lvm.__salt__, {'lvm.vgdisplay': mock}):
            self.assertDictEqual(lvm.vg_absent(name), ret)

            comt = ('Volume Group {0} is set to be removed'.format(name))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(lvm.__opts__, {'test': True}):
                self.assertDictEqual(lvm.vg_absent(name), ret)

    # 'lv_present' function tests: 1

    def test_lv_present(self):
        '''
        Test to create a new logical volume
        '''
        name = '/dev/sda5'

        comt = ('Logical Volume {0} already present'.format(name))

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': comt}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(lvm.__salt__, {'lvm.lvdisplay': mock}):
            self.assertDictEqual(lvm.lv_present(name), ret)

            comt = ('Logical Volume {0} is set to be created'.format(name))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(lvm.__opts__, {'test': True}):
                self.assertDictEqual(lvm.lv_present(name), ret)

    # 'lv_absent' function tests: 1

    def test_lv_absent(self):
        '''
        Test to remove a given existing logical volume
        from a named existing volume group
        '''
        name = '/dev/sda5'

        comt = ('Logical Volume {0} already absent'.format(name))

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': comt}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(lvm.__salt__, {'lvm.lvdisplay': mock}):
            self.assertDictEqual(lvm.lv_absent(name), ret)

            comt = ('Logical Volume {0} is set to be removed'.format(name))
            ret.update({'comment': comt, 'result': None})
            with patch.dict(lvm.__opts__, {'test': True}):
                self.assertDictEqual(lvm.lv_absent(name), ret)
