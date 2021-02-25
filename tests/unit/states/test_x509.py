from tests.support.unit import TestCase, skipIf

try:
    from salt.states import x509
except ImportError:
    x509 = None


@skipIf(x509 is None, "X509 cant be imported!")
class X509TestCase(TestCase):
    def test_deprecated_managed_private_key(self):
        self.assertRaises(
            ValueError, x509.certificate_managed, name=".c", managed_private_key=None
        )
