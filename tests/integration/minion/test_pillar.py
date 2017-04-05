# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import copy
import errno
import logging
import os
import shutil
import textwrap
import subprocess

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.paths import TMP, TMP_CONF_DIR
from tests.support.unit import skipIf
from tests.support.helpers import requires_system_grains

# Import 3rd-party libs
import yaml
import salt.ext.six as six

# Import salt libs
import salt.utils
import salt.pillar as pillar

log = logging.getLogger(__name__)


GPG_HOMEDIR = os.path.join(TMP_CONF_DIR, 'gpgkeys')
PILLAR_BASE = os.path.join(TMP, 'test-decrypt-pillar', 'pillar')
TOP_SLS = os.path.join(PILLAR_BASE, 'top.sls')
GPG_SLS = os.path.join(PILLAR_BASE, 'gpg.sls')
DEFAULT_OPTS = {
    'cachedir': os.path.join(TMP, 'rootdir', 'cache'),
    'config_dir': TMP_CONF_DIR,
    'extension_modules': os.path.join(TMP,
                                      'test-decrypt-pillar',
                                      'extmods'),
    'pillar_roots': {'base': [PILLAR_BASE]},
    'ext_pillar_first': False,
    'ext_pillar': [],
    'decrypt_pillar_default': 'gpg',
    'decrypt_pillar_delimiter': ':',
    'decrypt_pillar_renderers': ['gpg'],
}
ADDITIONAL_OPTS = (
    'file_roots',
    'state_top',
    'renderer',
    'renderer_whitelist',
    'renderer_blacklist',
)

TEST_KEY = '''\
-----BEGIN PGP PRIVATE KEY BLOCK-----

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
=06Tz
-----END PGP PRIVATE KEY BLOCK-----
'''

GPG_PILLAR_YAML = '''\
secrets:
  vault:
    foo: |
      -----BEGIN PGP MESSAGE-----

      hQEMAw2B674HRhwSAQgAhTrN8NizwUv/VunVrqa4/X8t6EUulrnhKcSeb8sZS4th
      W1Qz3K2NjL4lkUHCQHKZVx/VoZY7zsddBIFvvoGGfj8+2wjkEDwFmFjGE4DEsS74
      ZLRFIFJC1iB/O0AiQ+oU745skQkU6OEKxqavmKMrKo3rvJ8ZCXDC470+i2/Hqrp7
      +KWGmaDOO422JaSKRm5D9bQZr9oX7KqnrPG9I1+UbJyQSJdsdtquPWmeIpamEVHb
      VMDNQRjSezZ1yKC4kCWm3YQbBF76qTHzG1VlLF5qOzuGI9VkyvlMaLfMibriqY73
      zBbPzf6Bkp2+Y9qyzuveYMmwS4sEOuZL/PetqisWe9JGAWD/O+slQ2KRu9hNww06
      KMDPJRdyj5bRuBVE4hHkkP23KrYr7SuhW2vpe7O/MvWEJ9uDNegpMLhTWruGngJh
      iFndxegN9w==
      =bAuo
      -----END PGP MESSAGE-----
    bar: this was unencrypted already
    baz: |
      -----BEGIN PGP MESSAGE-----

      hQEMAw2B674HRhwSAQf+Ne+IfsP2IcPDrUWct8sTJrga47jQvlPCmO+7zJjOVcqz
      gLjUKvMajrbI/jorBWxyAbF+5E7WdG9WHHVnuoywsyTB9rbmzuPqYCJCe+ZVyqWf
      9qgJ+oUjcvYIFmH3h7H68ldqbxaAUkAOQbTRHdr253wwaTIC91ZeX0SCj64HfTg7
      Izwk383CRWonEktXJpientApQFSUWNeLUWagEr/YPNFA3vzpPF5/Ia9X8/z/6oO2
      q+D5W5mVsns3i2HHbg2A8Y+pm4TWnH6mTSh/gdxPqssi9qIrzGQ6H1tEoFFOEq1V
      kJBe0izlfudqMq62XswzuRB4CYT5Iqw1c97T+1RqENJCASG0Wz8AGhinTdlU5iQl
      JkLKqBxcBz4L70LYWyHhYwYROJWjHgKAywX5T67ftq0wi8APuZl9olnOkwSK+wrY
      1OZi
      =7epf
      -----END PGP MESSAGE-----
    qux:
      - foo
      - bar
      - |
        -----BEGIN PGP MESSAGE-----

        hQEMAw2B674HRhwSAQgAg1YCmokrweoOI1c9HO0BLamWBaFPTMblOaTo0WJLZoTS
        ksbQ3OJAMkrkn3BnnM/djJc5C7vNs86ZfSJ+pvE8Sp1Rhtuxh25EKMqGOn/SBedI
        gR6N5vGUNiIpG5Tf3DuYAMNFDUqw8uY0MyDJI+ZW3o3xrMUABzTH0ew+Piz85FDA
        YrVgwZfqyL+9OQuu6T66jOIdwQNRX2NPFZqvon8liZUPus5VzD8E5cAL9OPxQ3sF
        f7/zE91YIXUTimrv3L7eCgU1dSxKhhfvA2bEUi+AskMWFXFuETYVrIhFJAKnkFmE
        uZx+O9R9hADW3hM5hWHKH9/CRtb0/cC84I9oCWIQPdI+AaPtICxtsD2N8Q98hhhd
        4M7I0sLZhV+4ZJqzpUsOnSpaGyfh1Zy/1d3ijJi99/l+uVHuvmMllsNmgR+ZTj0=
        =LrCQ
        -----END PGP MESSAGE-----
'''

GPG_PILLAR_ENCRYPTED = {
    'secrets': {
        'vault': {
            'foo': '-----BEGIN PGP MESSAGE-----\n\nhQEMAw2B674HRhwSAQgAhTrN8NizwUv/VunVrqa4/X8t6EUulrnhKcSeb8sZS4th\nW1Qz3K2NjL4lkUHCQHKZVx/VoZY7zsddBIFvvoGGfj8+2wjkEDwFmFjGE4DEsS74\nZLRFIFJC1iB/O0AiQ+oU745skQkU6OEKxqavmKMrKo3rvJ8ZCXDC470+i2/Hqrp7\n+KWGmaDOO422JaSKRm5D9bQZr9oX7KqnrPG9I1+UbJyQSJdsdtquPWmeIpamEVHb\nVMDNQRjSezZ1yKC4kCWm3YQbBF76qTHzG1VlLF5qOzuGI9VkyvlMaLfMibriqY73\nzBbPzf6Bkp2+Y9qyzuveYMmwS4sEOuZL/PetqisWe9JGAWD/O+slQ2KRu9hNww06\nKMDPJRdyj5bRuBVE4hHkkP23KrYr7SuhW2vpe7O/MvWEJ9uDNegpMLhTWruGngJh\niFndxegN9w==\n=bAuo\n-----END PGP MESSAGE-----\n',
            'bar': 'this was unencrypted already',
            'baz': '-----BEGIN PGP MESSAGE-----\n\nhQEMAw2B674HRhwSAQf+Ne+IfsP2IcPDrUWct8sTJrga47jQvlPCmO+7zJjOVcqz\ngLjUKvMajrbI/jorBWxyAbF+5E7WdG9WHHVnuoywsyTB9rbmzuPqYCJCe+ZVyqWf\n9qgJ+oUjcvYIFmH3h7H68ldqbxaAUkAOQbTRHdr253wwaTIC91ZeX0SCj64HfTg7\nIzwk383CRWonEktXJpientApQFSUWNeLUWagEr/YPNFA3vzpPF5/Ia9X8/z/6oO2\nq+D5W5mVsns3i2HHbg2A8Y+pm4TWnH6mTSh/gdxPqssi9qIrzGQ6H1tEoFFOEq1V\nkJBe0izlfudqMq62XswzuRB4CYT5Iqw1c97T+1RqENJCASG0Wz8AGhinTdlU5iQl\nJkLKqBxcBz4L70LYWyHhYwYROJWjHgKAywX5T67ftq0wi8APuZl9olnOkwSK+wrY\n1OZi\n=7epf\n-----END PGP MESSAGE-----\n',
            'qux': [
                'foo',
                'bar',
                '-----BEGIN PGP MESSAGE-----\n\nhQEMAw2B674HRhwSAQgAg1YCmokrweoOI1c9HO0BLamWBaFPTMblOaTo0WJLZoTS\nksbQ3OJAMkrkn3BnnM/djJc5C7vNs86ZfSJ+pvE8Sp1Rhtuxh25EKMqGOn/SBedI\ngR6N5vGUNiIpG5Tf3DuYAMNFDUqw8uY0MyDJI+ZW3o3xrMUABzTH0ew+Piz85FDA\nYrVgwZfqyL+9OQuu6T66jOIdwQNRX2NPFZqvon8liZUPus5VzD8E5cAL9OPxQ3sF\nf7/zE91YIXUTimrv3L7eCgU1dSxKhhfvA2bEUi+AskMWFXFuETYVrIhFJAKnkFmE\nuZx+O9R9hADW3hM5hWHKH9/CRtb0/cC84I9oCWIQPdI+AaPtICxtsD2N8Q98hhhd\n4M7I0sLZhV+4ZJqzpUsOnSpaGyfh1Zy/1d3ijJi99/l+uVHuvmMllsNmgR+ZTj0=\n=LrCQ\n-----END PGP MESSAGE-----\n'
            ],
        },
    },
}

GPG_PILLAR_DECRYPTED = {
    'secrets': {
        'vault': {
            'foo': 'supersecret',
            'bar': 'this was unencrypted already',
            'baz': 'rosebud',
            'qux': ['foo', 'bar', 'baz'],
        },
    },
}


@skipIf(not salt.utils.which('gpg'), 'GPG is not installed')
class DecryptGPGPillarTest(ModuleCase):
    '''
    Tests for pillar decryption
    '''
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        try:
            os.makedirs(GPG_HOMEDIR, mode=0o700)
        except Exception:
            cls.created_gpg_homedir = False
            raise
        else:
            cls.created_gpg_homedir = True
            cmd_prefix = ['gpg', '--homedir', GPG_HOMEDIR]

            cmd = cmd_prefix + ['--list-keys']
            log.debug('Instantiating gpg keyring using: %s', cmd)
            output = subprocess.Popen(cmd,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      shell=False).communicate()[0]
            log.debug('Result:\n%s', output)

            cmd = cmd_prefix + ['--import', '--allow-secret-key-import']
            log.debug('Importing keypair using: %s', cmd)
            output = subprocess.Popen(cmd,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      shell=False).communicate(input=six.b(TEST_KEY))[0]
            log.debug('Result:\n%s', output)

            os.makedirs(PILLAR_BASE)
            with salt.utils.fopen(TOP_SLS, 'w') as fp_:
                fp_.write(textwrap.dedent('''\
                base:
                  '*':
                    - gpg
                '''))
            with salt.utils.fopen(GPG_SLS, 'w') as fp_:
                fp_.write(GPG_PILLAR_YAML)

    @classmethod
    def tearDownClass(cls):
        if cls.created_gpg_homedir:
            try:
                shutil.rmtree(GPG_HOMEDIR)
            except OSError as exc:
                # GPG socket can disappear before rmtree gets to this point
                if exc.errno != errno.ENOENT:
                    raise
        shutil.rmtree(PILLAR_BASE)

    def _build_opts(self, opts):
        ret = copy.deepcopy(DEFAULT_OPTS)
        for item in ADDITIONAL_OPTS:
            ret[item] = self.master_opts[item]
        ret.update(opts)
        return ret

    @requires_system_grains
    def test_decrypt_pillar_default_renderer(self, grains=None):
        '''
        Test recursive decryption of secrets:vault as well as the fallback to
        default decryption renderer.
        '''
        decrypt_pillar_opts = yaml.safe_load(textwrap.dedent('''\
            decrypt_pillar:
              - 'secrets:vault'
            '''))
        opts = self._build_opts(decrypt_pillar_opts)
        pillar_obj = pillar.Pillar(opts, grains, 'test', 'base')
        ret = pillar_obj.compile_pillar()
        self.assertEqual(ret, GPG_PILLAR_DECRYPTED)

    @requires_system_grains
    def test_decrypt_pillar_alternate_delimiter(self, grains=None):
        '''
        Test recursive decryption of secrets:vault using a pipe instead of a
        colon as the nesting delimiter.
        '''
        decrypt_pillar_opts = yaml.safe_load(textwrap.dedent('''\
            decrypt_pillar_delimiter: '|'
            decrypt_pillar:
              - 'secrets|vault'
            '''))
        opts = self._build_opts(decrypt_pillar_opts)
        pillar_obj = pillar.Pillar(opts, grains, 'test', 'base')
        ret = pillar_obj.compile_pillar()
        self.assertEqual(ret, GPG_PILLAR_DECRYPTED)

    @requires_system_grains
    def test_decrypt_pillar_deeper_nesting(self, grains=None):
        '''
        Test recursive decryption, only with a more deeply-nested target. This
        should leave the other keys in secrets:vault encrypted.
        '''
        decrypt_pillar_opts = yaml.safe_load(textwrap.dedent('''\
            decrypt_pillar:
              - 'secrets:vault:qux'
            '''))
        opts = self._build_opts(decrypt_pillar_opts)
        pillar_obj = pillar.Pillar(opts, grains, 'test', 'base')
        ret = pillar_obj.compile_pillar()
        expected = copy.deepcopy(GPG_PILLAR_ENCRYPTED)
        expected['secrets']['vault']['qux'][-1] = \
            GPG_PILLAR_DECRYPTED['secrets']['vault']['qux'][-1]
        self.assertEqual(ret, expected)

    @requires_system_grains
    def test_decrypt_pillar_explicit_renderer(self, grains=None):
        '''
        Test recursive decryption of secrets:vault, with the renderer
        explicitly defined, overriding the default. Setting the default to a
        nonexistant renderer so we can be sure that the override happened.
        '''
        decrypt_pillar_opts = yaml.safe_load(textwrap.dedent('''\
            decrypt_pillar_default: asdf
            decrypt_pillar_renderers:
              - asdf
              - gpg
            decrypt_pillar:
              - 'secrets:vault': gpg
            '''))
        opts = self._build_opts(decrypt_pillar_opts)
        pillar_obj = pillar.Pillar(opts, grains, 'test', 'base')
        ret = pillar_obj.compile_pillar()
        self.assertEqual(ret, GPG_PILLAR_DECRYPTED)

    @requires_system_grains
    def test_decrypt_pillar_missing_renderer(self, grains=None):
        '''
        Test decryption using a missing renderer. It should fail, leaving the
        encrypted keys intact, and add an error to the pillar dictionary.
        '''
        decrypt_pillar_opts = yaml.safe_load(textwrap.dedent('''\
            decrypt_pillar_default: asdf
            decrypt_pillar_renderers:
              - asdf
            decrypt_pillar:
              - 'secrets:vault'
            '''))
        opts = self._build_opts(decrypt_pillar_opts)
        pillar_obj = pillar.Pillar(opts, grains, 'test', 'base')
        ret = pillar_obj.compile_pillar()
        expected = copy.deepcopy(GPG_PILLAR_ENCRYPTED)
        expected['_errors'] = [
            'Failed to decrypt pillar key \'secrets:vault\': Decryption '
            'renderer \'asdf\' is not available'
        ]
        self.assertEqual(ret, expected)

    @requires_system_grains
    def test_decrypt_pillar_invalid_renderer(self, grains=None):
        '''
        Test decryption using a renderer which is not permitted. It should
        fail, leaving the encrypted keys intact, and add an error to the pillar
        dictionary.
        '''
        decrypt_pillar_opts = yaml.safe_load(textwrap.dedent('''\
            decrypt_pillar_default: foo
            decrypt_pillar_renderers:
              - foo
              - bar
            decrypt_pillar:
              - 'secrets:vault': gpg
            '''))
        opts = self._build_opts(decrypt_pillar_opts)
        pillar_obj = pillar.Pillar(opts, grains, 'test', 'base')
        ret = pillar_obj.compile_pillar()
        expected = copy.deepcopy(GPG_PILLAR_ENCRYPTED)
        expected['_errors'] = [
            'Failed to decrypt pillar key \'secrets:vault\': \'gpg\' is '
            'not a valid decryption renderer. Valid choices are: foo, bar'
        ]
        self.assertEqual(ret, expected)
