# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Salt Testing libs
from salt.utils import is_linux
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath

# Import salt libs
try:
    import salt.modules.shadow as shadow
    HAS_SHADOW = True
except ImportError:
    HAS_SHADOW = False

ensure_in_syspath('../../')

_PASSWORD = 'lamepassword'

# Not testing blowfish as it is not available on most Linux distros
_HASHES = dict(
    md5=dict(
        pw_salt='TgIp9OTu',
        pw_hash='$1$TgIp9OTu$.d0FFP6jVi5ANoQmk6GpM1'
    ),
    sha256=dict(
        pw_salt='3vINbSrC',
        pw_hash='$5$3vINbSrC$hH8A04jAY3bG123yU4FQ0wvP678QDTvWBhHHFbz6j0D'
    ),
    sha512=dict(
        pw_salt='PiGA3V2o',
        pw_hash='$6$PiGA3V2o$/PrntRYufz49bRV/V5Eb1V6DdHaS65LB0fu73Tp/xxmDFr6HWJKptY2TvHRDViXZugWpnAcOnrbORpOgZUGTn.'
    ),
)


@skipIf(not is_linux(), 'minion is not Linux')
class LinuxShadowTest(TestCase):

    def test_gen_password(self):
        '''
        Test shadow.gen_password
        '''
        self.assertTrue(HAS_SHADOW)
        for algorithm, hash_info in _HASHES.iteritems():
            self.assertEqual(
                shadow.gen_password(
                    _PASSWORD,
                    crypt_salt=hash_info['pw_salt'],
                    algorithm=algorithm
                ),
                hash_info['pw_hash']
            )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(LinuxShadowTest, needs_daemon=False)
