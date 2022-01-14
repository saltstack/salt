from salt.runners import manage
from tests.support.unit import TestCase


class ManageTest(TestCase):
    def test_deprecation_58638(self):
        # check that type error will be raised
        self.assertRaises(TypeError, manage.list_state, show_ipv4="data")

        # check that show_ipv4 will raise an error
        try:
            manage.list_state(  # pylint: disable=unexpected-keyword-arg
                show_ipv4="data"
            )
        except TypeError as no_show_ipv4:
            self.assertEqual(
                str(no_show_ipv4),
                "list_state() got an unexpected keyword argument 'show_ipv4'",
            )
