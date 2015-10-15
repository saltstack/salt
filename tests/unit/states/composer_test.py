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
    patch)

from salttesting.helpers import ensure_in_syspath
from salt.exceptions import SaltException

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import composer

composer.__salt__ = {}
composer.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ComposerTestCase(TestCase):
    '''
    Test cases for salt.states.composer
    '''
    # 'installed' function tests: 1

    def test_installed(self):
        '''
        Test to verify that the correct versions of composer
        dependencies are present.
        '''
        name = 'CURL'

        ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

        mock = MagicMock(return_value=True)
        with patch.dict(composer.__salt__,
                        {'composer.did_composer_install': mock}):
            comt = ('Composer already installed this directory')
            ret.update({'comment': comt})
            self.assertDictEqual(composer.installed(name, always_check=False),
                                 ret)

            with patch.dict(composer.__opts__, {'test': True}):
                comt = ('The state of "CURL" will be changed.')
                changes = {'new': 'composer install will be run in CURL',
                           'old': 'composer install has been run in CURL'}
                ret.update({'comment': comt, 'result': None,
                            'changes': changes})
                self.assertDictEqual(composer.installed(name), ret)

            with patch.dict(composer.__opts__, {'test': False}):
                mock = MagicMock(side_effect=[SaltException, {}])
                with patch.dict(composer.__salt__, {'composer.install': mock}):
                    comt = ("Error executing composer in "
                            "''CURL'': SaltException('',)")
                    ret.update({'comment': comt, 'result': False,
                                'changes': {}})
                    self.assertDictEqual(composer.installed(name), ret)

                    comt = ('Composer install completed successfully,'
                            ' output silenced by quiet flag')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(composer.installed(name, quiet=True),
                                         ret)

    # 'update' function tests: 1

    def test_update(self):
        '''
        Test to composer update the directory to ensure we have
        the latest versions of all project dependencies.
        '''
        name = 'CURL'

        ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

        changes = {'new': 'composer install/update will be run in CURL',
                   'old': 'composer install has not yet been run in CURL'}

        mock = MagicMock(return_value=True)
        with patch.dict(composer.__salt__,
                        {'composer.did_composer_install': mock}):
            with patch.dict(composer.__opts__, {'test': True}):
                comt = ('The state of "CURL" will be changed.')
                ret.update({'comment': comt, 'result': None,
                            'changes': changes})
                self.assertDictEqual(composer.update(name), ret)

            with patch.dict(composer.__opts__, {'test': False}):
                mock = MagicMock(side_effect=[SaltException, {}])
                with patch.dict(composer.__salt__, {'composer.update': mock}):
                    comt = ("Error executing composer in "
                            "''CURL'': SaltException('',)")
                    ret.update({'comment': comt, 'result': False,
                                'changes': {}})
                    self.assertDictEqual(composer.update(name), ret)

                    comt = ('Composer update completed successfully,'
                            ' output silenced by quiet flag')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(composer.update(name, quiet=True),
                                         ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ComposerTestCase, needs_daemon=False)
