# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.ext.six as six
from salt.utils.odict import OrderedDict
import salt.modules.nacl as nacl
import salt.modules.test as test
import salt.config


sk='SVWut5SqNpuPeNzb1b9y6b2eXg2PLIog43GBzp48Sow='
pk = '/kfGX7PbWeu099702PBbKWLpG/9p06IQRswkdWHCDk0=',
_config = salt.config.minion_config(None)
_config['nacl.config'] = {
    'sk': sk,
    'pk': pk
}

clrtext='blabol'
pillar_value_dec = dict(a=None, b='very unencrypted', c=clrtext)

class NaclModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        optd = salt.config.DEFAULT_MASTER_OPTS
        opts = optd.copy()
        opts.update(_config)
        utils = salt.loader.utils(opts, whitelist=['nacl'])
        funcs = salt.loader.minion_mods(opts, utils=utils)
        return {nacl: {
                '__opts__': opts,
                '__utils__': utils,
                '__salt__': funcs
        }}

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_nacl(self):
      """Test NACL encryption and decription
      - encryption key passed as attribute
      - decryption key is read from configuration"""
      with patch.dict(nacl.__salt__, {'nacl.dec': MagicMock(return_value=clrtext)}):
        self.assertEqual(nacl.dec(nacl.enc(clrtext, sk=sk)), 'blabol')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_nacl_dec_none(self):
      "Test NACL decryption with None on input"
      with patch.dict(nacl.__salt__, {'nacl.dec': MagicMock(return_value=clrtext)}):
        self.assertEqual(nacl.dec(None, sk=sk), None)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_nacl_dec_clrtext(self):
      "Test NACL decryption"
      with patch.dict(nacl.__salt__, {'nacl.dec': MagicMock(return_value=clrtext)}):
        self.assertEqual(test.try_(module='nacl.dec', data=clrtext), None)

