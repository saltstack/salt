import salt.modules.mac_user as user
from tests.support.unit import TestCase


class MacUserTestCase(TestCase):
    def test_kcpass(self):
        hashes = {
            # Actual hashes from macOS, since reference implementation didn't account for trailing null
            "0": "4d 89 f9 91 1f 7a 46 5e f7 a8 11 ff",
            "password": "0d e8 21 50 a5 d3 af 8e a3 de d9 14",
            "shorterpwd": "0e e1 3d 51 a6 d9 af 9a d4 dd 1f 27",
            "Squarepants": "2e f8 27 42 a0 d9 ad 8b cd cd 6c 7d",
            "longerpasswd": "11 e6 3c 44 b7 ce ad 8b d0 ca 68 19 89 b1 65 ae 7e 89 12 b8 51 f8 f0 ff",
            "ridiculouslyextendedpass": "0f e0 36 4a b1 c9 b1 85 d6 ca 73 04 ec 2a 57 b7 d2 b9 8f c7 c9 7e 0e fa 52 7b 71 e6 f8 b7 a6 ae 47 94 d7 86",
        }
        for password, hash in hashes.items():
            kcpass = user._kcpassword(password)
            hash = bytes.fromhex(hash)

            # macOS adds a trailing null and pads the rest with random data
            length = len(password) + 1

            self.assertEqual(kcpass[:length], hash[:length])
            self.assertEqual(len(kcpass), len(hash))
