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
from salt.states import augeas

augeas.__opts__ = {}
augeas.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AugeasTestCase(TestCase):
    '''
    Test cases for salt.states.augeas
    '''
    # 'change' function tests: 1

    def test_change(self):
        '''
        Test to issue changes to Augeas, optionally for a specific context,
        with a specific lens.
        '''
        name = 'zabbix'
        context = '/files/etc/services'
        changes = ['ins service-name after service-name[last()]',
                   'set service-name[last()] zabbix-agent']
        changes_ret = {'updates': changes}

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        comt = ('\'changes\' must be specified as a list')
        ret.update({'comment': comt})
        self.assertDictEqual(augeas.change(name), ret)

        comt = ('Executing commands in file "/files/etc/services":\n'
                'ins service-name after service-name[last()]'
                '\nset service-name[last()] zabbix-agent')
        ret.update({'comment': comt, 'result': None})
        with patch.dict(augeas.__opts__, {'test': True}):
            self.assertDictEqual(augeas.change(name, context, changes), ret)

        with patch.dict(augeas.__opts__, {'test': False}):
            mock = MagicMock(return_value={'retval': False, 'error': 'error'})
            with patch.dict(augeas.__salt__, {'augeas.execute': mock}):
                ret.update({'comment': 'Error: error', 'result': False})
                self.assertDictEqual(augeas.change(name, changes=changes), ret)

            mock = MagicMock(return_value={'retval': True})
            with patch.dict(augeas.__salt__, {'augeas.execute': mock}):
                ret.update({'comment': 'Changes have been saved',
                            'result': True, 'changes': changes_ret})
                self.assertDictEqual(augeas.change(name, changes=changes), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AugeasTestCase, needs_daemon=False)
