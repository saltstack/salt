from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase, skipIf

try:
    from salt.states import x509
except ImportError:
    x509 = None


@skipIf(x509 is None, "X509 cant be imported!")
class X509TestCase(TestCase):
    def test_deprecated_managed_private_key(self):
        """
        Test that deprecated message has been removed
        """
        dep_msg = call(
            "Aluminium",
            "Passing 'managed_private_key' to x509.certificate_managed has no effect and "
            "will be removed Salt Aluminium. Use a separate x509.private_key_managed call instead.",
        )

        with patch(
            "salt.utils.versions.warn_until", MagicMock(return_value=None)
        ) as warn:
            self.assertRaises(
                SaltInvocationError,
                x509.certificate_managed,
                name="c",
                managed_private_key="None",
            )
            self.assertNotIn(dep_msg, warn.call_args_list)
