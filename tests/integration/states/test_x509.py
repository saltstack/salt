# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
import logging

import salt.utils.files
from salt.ext import six
import textwrap

from tests.support.helpers import with_tempfile
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS

try:
    import M2Crypto  # pylint: disable=W0611
    HAS_M2CRYPTO = True
except ImportError:
    HAS_M2CRYPTO = False


log = logging.getLogger(__name__)


@skipIf(not HAS_M2CRYPTO, 'Skip when no M2Crypto found')
class x509Test(ModuleCase, SaltReturnAssertsMixin):

    @classmethod
    def setUpClass(cls):
        cert_path = os.path.join(RUNTIME_VARS.BASE_FILES, 'x509_test.crt')
        with salt.utils.files.fopen(cert_path) as fp:
            cls.x509_cert_text = fp.read()

    def setUp(self):
        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'signing_policies.sls'), 'w') as fp:
            fp.write(textwrap.dedent('''\
                x509_signing_policies:
                  ca_policy:
                    - minions: '*'
                    - signing_private_key: {0}/pki/ca.key
                    - signing_cert: {0}/pki/ca.crt
                    - O: Test Company
                    - basicConstraints: "CA:false"
                    - keyUsage: "critical digitalSignature, keyEncipherment"
                    - extendedKeyUsage: "critical serverAuth, clientAuth"
                    - subjectKeyIdentifier: hash
                    - authorityKeyIdentifier: keyid
                    - days_valid: 730
                    - copypath: {0}/pki
                     '''.format(RUNTIME_VARS.TMP)))
        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'top.sls'), 'w') as fp:
            fp.write(textwrap.dedent('''\
                     base:
                       '*':
                         - signing_policies
                     '''))
        self.run_function('saltutil.refresh_pillar')

    def tearDown(self):
        os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'signing_policies.sls'))
        os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'top.sls'))
        certs_path = os.path.join(RUNTIME_VARS.TMP, 'pki')
        if os.path.exists(certs_path):
            salt.utils.files.rm_rf(certs_path)
        self.run_function('saltutil.refresh_pillar')

    def run_function(self, *args, **kwargs):
        ret = super(x509Test, self).run_function(*args, **kwargs)
        log.debug('ret = %s', ret)
        return ret

    @with_tempfile(suffix='.pem', create=False)
    def test_issue_49027(self, pemfile):
        ret = self.run_state(
            'x509.pem_managed',
            name=pemfile,
            text=self.x509_cert_text)
        assert isinstance(ret, dict), ret
        ret = ret[next(iter(ret))]
        assert ret.get('result') is True, ret
        with salt.utils.files.fopen(pemfile) as fp:
            result = fp.readlines()
        self.assertEqual(self.x509_cert_text.splitlines(True), result)

    @with_tempfile(suffix='.crt', create=False)
    @with_tempfile(suffix='.key', create=False)
    def test_issue_49008(self, keyfile, crtfile):
        ret = self.run_function(
            'state.apply',
            ['issue-49008'],
            pillar={'keyfile': keyfile, 'crtfile': crtfile})
        assert isinstance(ret, dict), ret
        for state_result in six.itervalues(ret):
            assert state_result['result'] is True, state_result
        assert os.path.exists(keyfile)
        assert os.path.exists(crtfile)

    def test_cert_signing(self):
        ret = self.run_function('state.apply', ['test_cert'], pillar={'tmp_dir': RUNTIME_VARS.TMP})
        key = 'x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed'.format(RUNTIME_VARS.TMP)
        assert key in ret
        assert 'changes' in ret[key]
        assert 'Certificate' in ret[key]['changes']
        assert 'New' in ret[key]['changes']['Certificate']
