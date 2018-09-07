# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
import logging
from tests.support.paths import BASE_FILES
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.mixins import SaltReturnAssertsMixin

import salt.utils.files

try:
    from M2Crypto.RSA import RSAError
    HAS_M2CRYPTO = True
except ImportError:
    HAS_M2CRYPTO = False


log = logging.getLogger(__name__)


class x509Test(ModuleCase, SaltReturnAssertsMixin):

    def tearDown(self):
        paths = [
            '/test-49027.crt',
            '/test-ca-49008.key',
            '/test-ca-49008.crt',
        ]
        for path in paths:
            try:
                os.remove(path)
            except:
                pass

    @staticmethod
    def get_cert_lines(path):
        lines = []
        started = False
        with salt.utils.files.fopen(path, 'rb') as fp:
            for line in fp:
                if line.find(b'-----BEGIN CERTIFICATE-----') != -1:
                    started = True
                    continue
                if line.find(b'-----END CERTIFICATE-----') != -1:
                    break
                if started:
                    lines.append(line.strip())
        return lines


    @skipIf(not HAS_M2CRYPTO, 'Skip when no M2Crypto found')
    def test_issue_49027(self):
        expected = self.get_cert_lines(os.path.join(BASE_FILES, 'issue-49027.sls'))
        started = False
        ret = self.run_function('state.sls', ['issue-49027'])
        log.warn("ret = %s", repr(ret))
        self.assertSaltTrueReturn(ret)
        self.assertEqual(expected, self.get_cert_lines('/test-49027.crt'))
