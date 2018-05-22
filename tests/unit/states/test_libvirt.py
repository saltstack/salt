# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import tempfile
import shutil

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    mock_open,
    patch)

# Import Salt Libs
import salt.states.virt as virt
import salt.utils.files


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LibvirtTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.libvirt
    '''
    def setup_loader_modules(self):
        return {virt: {}}

    @classmethod
    def setUpClass(cls):
        cls.pki_dir = tempfile.mkdtemp(dir=TMP)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.pki_dir)
        del cls.pki_dir

    # 'keys' function tests: 1

    def test_keys(self):
        '''
        Test to manage libvirt keys.
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)):
            name = 'sunrise'

            ret = {'name': name,
                   'result': True,
                   'comment': '',
                   'changes': {}}

            mock = MagicMock(side_effect=[[], ['libvirt.servercert.pem'],
                                          {'libvirt.servercert.pem': 'A'}])
            with patch.dict(virt.__salt__, {'pillar.ext': mock}):
                comt = ('All keys are correct')
                ret.update({'comment': comt})
                self.assertDictEqual(virt.keys(name, basepath=self.pki_dir), ret)

                with patch.dict(virt.__opts__, {'test': True}):
                    comt = ('Libvirt keys are set to be updated')
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(virt.keys(name, basepath=self.pki_dir), ret)

                with patch.dict(virt.__opts__, {'test': False}):
                    with patch.object(salt.utils.files, 'fopen', MagicMock(mock_open())):
                        comt = ('Updated libvirt certs and keys')
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'servercert': 'new'}})
                        self.assertDictEqual(virt.keys(name, basepath=self.pki_dir), ret)

    def test_keys_with_expiration_days(self):
        '''
        Test to manage libvirt keys.
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)):
            name = 'sunrise'

            ret = {'name': name,
                   'result': True,
                   'comment': '',
                   'changes': {}}

            mock = MagicMock(side_effect=[[], ['libvirt.servercert.pem'],
                                          {'libvirt.servercert.pem': 'A'}])
            with patch.dict(virt.__salt__, {'pillar.ext': mock}):
                comt = ('All keys are correct')
                ret.update({'comment': comt})
                self.assertDictEqual(virt.keys(name,
                                               basepath=self.pki_dir,
                                               expiration_days=700), ret)

                with patch.dict(virt.__opts__, {'test': True}):
                    comt = ('Libvirt keys are set to be updated')
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(virt.keys(name,
                                                   basepath=self.pki_dir,
                                                   expiration_days=700), ret)

                with patch.dict(virt.__opts__, {'test': False}):
                    with patch.object(salt.utils.files, 'fopen', MagicMock(mock_open())):
                        comt = ('Updated libvirt certs and keys')
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'servercert': 'new'}})
                        self.assertDictEqual(virt.keys(name,
                                                       basepath=self.pki_dir,
                                                       expiration_days=700), ret)

    def test_keys_with_state(self):
        '''
        Test to manage libvirt keys.
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)):
            name = 'sunrise'

            ret = {'name': name,
                   'result': True,
                   'comment': '',
                   'changes': {}}

            mock = MagicMock(side_effect=[[], ['libvirt.servercert.pem'],
                                          {'libvirt.servercert.pem': 'A'}])
            with patch.dict(virt.__salt__, {'pillar.ext': mock}):
                comt = ('All keys are correct')
                ret.update({'comment': comt})
                self.assertDictEqual(virt.keys(name,
                                               basepath=self.pki_dir,
                                               st='California'), ret)

                with patch.dict(virt.__opts__, {'test': True}):
                    comt = ('Libvirt keys are set to be updated')
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(virt.keys(name,
                                                   basepath=self.pki_dir,
                                                   st='California'), ret)

                with patch.dict(virt.__opts__, {'test': False}):
                    with patch.object(salt.utils.files, 'fopen', MagicMock(mock_open())):
                        comt = ('Updated libvirt certs and keys')
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'servercert': 'new'}})
                        self.assertDictEqual(virt.keys(name,
                                                       basepath=self.pki_dir,
                                                       st='California'), ret)

    def test_keys_with_all_options(self):
        '''
        Test to manage libvirt keys.
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)):
            name = 'sunrise'

            ret = {'name': name,
                   'result': True,
                   'comment': '',
                   'changes': {}}

            mock = MagicMock(side_effect=[[], ['libvirt.servercert.pem'],
                                          {'libvirt.servercert.pem': 'A'}])
            with patch.dict(virt.__salt__, {'pillar.ext': mock}):
                comt = ('All keys are correct')
                ret.update({'comment': comt})
                self.assertDictEqual(virt.keys(name,
                                               basepath=self.pki_dir,
                                               country='USA',
                                               st='California',
                                               locality='Los_Angeles',
                                               organization='SaltStack',
                                               expiration_days=700), ret)

                with patch.dict(virt.__opts__, {'test': True}):
                    comt = ('Libvirt keys are set to be updated')
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(virt.keys(name,
                                                   basepath=self.pki_dir,
                                                   country='USA',
                                                   st='California',
                                                   locality='Los_Angeles',
                                                   organization='SaltStack',
                                                   expiration_days=700), ret)

                with patch.dict(virt.__opts__, {'test': False}):
                    with patch.object(salt.utils.files, 'fopen', MagicMock(mock_open())):
                        comt = ('Updated libvirt certs and keys')
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'servercert': 'new'}})
                        self.assertDictEqual(virt.keys(name,
                                                       basepath=self.pki_dir,
                                                       country='USA',
                                                       st='California',
                                                       locality='Los_Angeles',
                                                       organization='SaltStack',
                                                       expiration_days=700), ret)
