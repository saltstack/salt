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
#import salt.modules.pillar as pillarmod
import salt.modules.nacl as nacl
import salt.modules.test as test
import salt.config




key='cKEzd4kXsbeCE7/nLTIqXwnUiD1ulg4NoeeYcCFpd9k='
_config = salt.config.minion_config(None)
_config['nacl.config'] = {'key': key}

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
      with patch.dict(nacl.__salt__, {'nacl.dec': MagicMock(return_value=clrtext)}):
        self.assertEqual(nacl.dec(nacl.enc(clrtext, key=key)), 'blabol')
        #self.assertEqual(test.try_(module='nacl.enc', data=clrtext, key=key), 'blabol')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_nacl_dec(self):
      with patch.dict(nacl.__salt__, {'nacl.dec': MagicMock(return_value=clrtext)}):
        self.assertEqual(test.try_(module='nacl.dec', data=None), None)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_nacl_get_safe(self):
      with patch.dict(nacl.__salt__, {'nacl.dec': MagicMock(return_value=clrtext)}):
        self.assertEqual(test.try_(module='nacl.dec', data=clrtext), None)

    # TODO: test {{ salt.nacl.dec(xyz) | default }} in states


