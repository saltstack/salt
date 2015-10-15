# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import mdadm

# Globals
mdadm.__salt__ = {}
mdadm.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MdadmTestCase(TestCase):
    '''
        Validate the mdadm state
    '''
    def test_present(self):
        '''
            Test to verify that the raid is present
        '''
        ret = [{'changes': {}, 'comment': 'Raid salt already present',
                'name': 'salt', 'result': True},
               {'changes': {},
                'comment': "Devices are a mix of RAID constituents"
                " (['dev0']) and non-RAID-constituents(['dev1']).",
                'name': 'salt', 'result': False},
               {'changes': {},
                'comment': 'Raid will be created with: True', 'name': 'salt',
                'result': None},
               {'changes': {}, 'comment': 'Raid salt failed to be created.',
                'name': 'salt', 'result': False}]

        mock = MagicMock(side_effect=[{'salt': True}, {'salt': False},
                                      {'salt': False}, {'salt': False},
                                      {'salt': False}])
        with patch.dict(mdadm.__salt__, {'raid.list': mock}):
            self.assertEqual(mdadm.present("salt", 5, "dev0"), ret[0])

            mock = MagicMock(side_effect=[0, 1])
            with patch.dict(mdadm.__salt__, {'cmd.retcode': mock}):
                self.assertDictEqual(mdadm.present("salt", 5,
                                                   ["dev0", "dev1"]),
                                     ret[1])

            mock = MagicMock(return_value=True)
            with patch.dict(mdadm.__salt__, {'cmd.retcode': mock}):
                with patch.dict(mdadm.__opts__, {'test': True}):
                    with patch.dict(mdadm.__salt__, {'raid.create': mock}):
                        self.assertDictEqual(mdadm.present("salt", 5, "dev0"),
                                             ret[2])

                with patch.dict(mdadm.__opts__, {'test': False}):
                    with patch.dict(mdadm.__salt__, {'raid.create': mock}):
                        self.assertDictEqual(mdadm.present("salt", 5, "dev0"),
                                             ret[3])

    def test_absent(self):
        '''
            Test to verify that the raid is absent
        '''
        ret = [{'changes': {}, 'comment': 'Raid salt already absent',
                'name': 'salt', 'result': True},
               {'changes': {},
                'comment': 'Raid saltstack is set to be destroyed',
                'name': 'saltstack', 'result': None},
               {'changes': {}, 'comment': 'Raid saltstack has been destroyed',
                'name': 'saltstack', 'result': True}]

        mock = MagicMock(return_value=["saltstack"])
        with patch.dict(mdadm.__salt__, {'raid.list': mock}):
            self.assertDictEqual(mdadm.absent("salt"), ret[0])

            with patch.dict(mdadm.__opts__, {'test': True}):
                self.assertDictEqual(mdadm.absent("saltstack"), ret[1])

            with patch.dict(mdadm.__opts__, {'test': False}):
                mock = MagicMock(return_value=True)
                with patch.dict(mdadm.__salt__, {'raid.destroy': mock}):
                    self.assertDictEqual(mdadm.absent("saltstack"), ret[2])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MdadmTestCase, needs_daemon=False)
